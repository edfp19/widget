from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services import CacheService, ClickHouseHttpClient
from worker.events import load_demo_events


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _document_row(document_key: str, payload: Any) -> dict[str, Any]:
    return {
        "document_key": document_key,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "updated_at": utc_now_iso(),
    }


class ReplayService:
    DEFAULT_BATCH_SIZE = 2
    DEFAULT_BATCH_WINDOW_SECONDS = 0.25
    LIVE_SERVING_TABLES = (
        "widget.match_state_latest",
        "widget.match_xg_events",
        "widget.match_facts",
    )

    def __init__(self, client: ClickHouseHttpClient, cache: CacheService, project_root: Path) -> None:
        self.client = client
        self.cache = cache
        self.project_root = project_root
        self._events = load_demo_events()
        self._index = 0
        self._pending_events: list[dict[str, Any]] = []
        self._last_flush_monotonic = 0.0
        self.batch_size = self.DEFAULT_BATCH_SIZE
        self.batch_window_seconds = self.DEFAULT_BATCH_WINDOW_SECONDS

    async def reset(self) -> None:
        from worker.seed import seed_clickhouse_from_mock_data

        await seed_clickhouse_from_mock_data(self.client, self.project_root / "backend" / "mock_data")
        await self.cache.delete_pattern("widget:v1:*")
        self._index = 0
        self._pending_events = []
        self._last_flush_monotonic = 0.0

    async def reset_with_retry(self, *, attempts: int = 20, delay_seconds: float = 1.0) -> None:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                await self.reset()
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(delay_seconds)
        if last_error is not None:
            raise last_error

    async def rebuild_from_raw(self) -> dict[str, int]:
        for table in self.LIVE_SERVING_TABLES:
            await self.client.command(f"TRUNCATE TABLE IF EXISTS {table} SYNC")

        raw_rows = await self.client.query_json_rows(
            "SELECT payload_json, event_ts FROM widget.raw_match_events "
            "ORDER BY match_id ASC, event_ts ASC, event_id ASC"
        )
        await self.cache.delete_pattern("widget:v1:*")

        rebuilt_matches: set[str] = set()
        for row in raw_rows:
            event = json.loads(row["payload_json"])
            rebuilt_matches.add(event["state"]["match_id"])
            await self._apply_serving_updates(
                event,
                event_ts=str(row["event_ts"]),
                invalidate_cache=False,
            )

        await self.cache.delete_pattern("widget:v1:*")
        return {
            "events_replayed": len(raw_rows),
            "matches_rebuilt": len(rebuilt_matches),
        }

    async def rebuild_from_raw_with_retry(
        self,
        *,
        attempts: int = 20,
        delay_seconds: float = 1.0,
    ) -> dict[str, int]:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                return await self.rebuild_from_raw()
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Rebuild failed without raising a concrete exception")

    async def step(self) -> dict[str, Any]:
        if self._index >= len(self._events):
            self._index = 0

        event = self._events[self._index]
        await self.enqueue_event(event, force_flush=True)
        self._index += 1
        return event

    async def run_forever(self, *, autorun: bool, idle_sleep_seconds: float = 1.0) -> None:
        if not autorun:
            while True:
                await asyncio.sleep(idle_sleep_seconds)

        while True:
            if self._index >= len(self._events):
                await self.reset()

            event = self._events[self._index]
            await self.enqueue_event(event)
            self._index += 1
            event = self._events[(self._index - 1) % len(self._events)]
            await asyncio.sleep(float(event.get("delay_seconds", 0.5)))
            await self.flush_pending_events_if_due(force=False)

    async def enqueue_event(self, event: dict[str, Any], *, force_flush: bool = False) -> None:
        self._pending_events.append(event)
        await self.flush_pending_events_if_due(force=force_flush)

    async def flush_pending_events_if_due(self, *, force: bool) -> None:
        if not self._pending_events:
            return
        now = asyncio.get_running_loop().time()
        if self._last_flush_monotonic == 0.0:
            self._last_flush_monotonic = now

        age = now - self._last_flush_monotonic
        if force or len(self._pending_events) >= self.batch_size or age >= self.batch_window_seconds:
            batch = list(self._pending_events)
            self._pending_events.clear()
            await self.apply_event_batch(batch)
            self._last_flush_monotonic = asyncio.get_running_loop().time()

    async def apply_event_batch(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            await self.apply_event(event)

    async def apply_event(self, event: dict[str, Any], *, event_ts: str | None = None) -> None:
        state = event.get("state")
        event_id = event["event_id"]
        event_ts = event_ts or utc_now_iso()

        status = await self._get_event_status(event_id)
        if status == "applied":
            return

        raw_exists = await self._raw_event_exists(event_id)
        if not raw_exists:
            await self.client.insert_json_rows(
                "widget.raw_match_events",
                [
                    {
                        "match_id": state["match_id"],
                        "event_id": event_id,
                        "event_ts": event_ts,
                        "event_type": "resource_update",
                        "payload_json": json.dumps(event, ensure_ascii=False),
                    }
                ],
            )

        await self._mark_event_status(
            event_id=event_id,
            match_id=state["match_id"],
            status="pending",
            last_error="",
        )

        try:
            await self._apply_serving_updates(event, event_ts=event_ts, invalidate_cache=True)
            await self._mark_event_status(
                event_id=event_id,
                match_id=state["match_id"],
                status="applied",
                last_error="",
            )
        except Exception as exc:
            await self._mark_event_status(
                event_id=event_id,
                match_id=state["match_id"],
                status="pending",
                last_error=str(exc),
            )
            raise

    async def _apply_serving_updates(
        self,
        event: dict[str, Any],
        *,
        event_ts: str,
        invalidate_cache: bool,
    ) -> None:
        state = event.get("state")
        xg_point = event.get("xg_point")
        fact = event.get("fact")
        live_team_stats = event.get("live_team_stats")
        event_id = event["event_id"]

        await self.client.insert_json_rows(
            "widget.match_state_latest",
            [
                {
                    "match_id": state["match_id"],
                    "version_ts": event_ts,
                    "competition_id": state["competition_id"],
                    "phase": state["phase"],
                    "clock": state["clock"],
                    "home_score": state["home_score"],
                    "away_score": state["away_score"],
                    "home_team": state["home_team"],
                    "away_team": state["away_team"],
                    "lineups_confirmed": int(bool(state["lineups_confirmed"])),
                    "kickoff_utc": state["kickoff_utc"],
                }
            ],
        )

        if xg_point is not None and not await self._serving_event_exists("widget.match_xg_events", event_id):
            await self.client.insert_json_rows(
                "widget.match_xg_events",
                [
                    {
                        "match_id": state["match_id"],
                        "source_event_id": event_id,
                        "event_ts": event_ts,
                        "minute": xg_point["minute"],
                        "home_team": xg_point["home_team"],
                        "away_team": xg_point["away_team"],
                        "home_xg_cumulative": xg_point["home_xg_cumulative"],
                        "away_xg_cumulative": xg_point["away_xg_cumulative"],
                    }
                ],
            )

        if fact is not None and not await self._serving_event_exists("widget.match_facts", event_id):
            existing_rows = await self.client.query_json_rows(
                "SELECT max(sort_index) AS max_sort_index FROM widget.match_facts "
                f"WHERE match_id = '{state['match_id']}'"
            )
            next_sort_index = int(existing_rows[0]["max_sort_index"] or 0) + 1
            await self.client.insert_json_rows(
                "widget.match_facts",
                [
                    {
                        "match_id": state["match_id"],
                        "source_event_id": event_id,
                        "fact_id": fact["fact_id"],
                        "sort_index": next_sort_index,
                        "fact_ts": event_ts,
                        "minute": fact["minute"] if fact["minute"] is not None else 0,
                        "category": fact["category"],
                        "text": fact["text"],
                        "event_type": fact["event_type"] or "",
                    }
                ],
            )

        if live_team_stats is not None:
            current_payload = await self._load_document(
                f"match_team_stats:{state['match_id']}",
                default={
                    "season": {},
                    "last_5": {},
                    "last_10": {},
                    "home": {},
                    "away": {},
                    "live": {},
                },
            )
            current_payload["live"] = live_team_stats
            await self.client.insert_json_rows(
                "widget.widget_documents",
                [_document_row(f"match_team_stats:{state['match_id']}", current_payload)],
            )

        if invalidate_cache:
            await self.cache.invalidate_match_live_keys(state["match_id"])

    async def _load_document(self, document_key: str, *, default: Any | None = None) -> Any:
        rows = await self.client.query_json_rows(
            "SELECT payload_json FROM widget.widget_documents FINAL "
            f"WHERE document_key = '{document_key}' "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        if not rows:
            if default is not None:
                return default
            raise KeyError(f"Document '{document_key}' not found")
        return json.loads(rows[0]["payload_json"])

    async def _get_event_status(self, event_id: str) -> str | None:
        rows = await self.client.query_json_rows(
            "SELECT status FROM widget.ingest_event_ledger FINAL "
            f"WHERE event_id = '{event_id}' "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        if not rows:
            return None
        return rows[0]["status"]

    async def _raw_event_exists(self, event_id: str) -> bool:
        rows = await self.client.query_json_rows(
            "SELECT count() AS count FROM widget.raw_match_events "
            f"WHERE event_id = '{event_id}'"
        )
        return int(rows[0]["count"]) > 0

    async def _serving_event_exists(self, table: str, event_id: str) -> bool:
        rows = await self.client.query_json_rows(
            f"SELECT count() AS count FROM {table} "
            f"WHERE source_event_id = '{event_id}'"
        )
        return int(rows[0]["count"]) > 0

    async def _mark_event_status(
        self,
        *,
        event_id: str,
        match_id: str,
        status: str,
        last_error: str,
    ) -> None:
        await self.client.insert_json_rows(
            "widget.ingest_event_ledger",
            [
                {
                    "event_id": event_id,
                    "match_id": match_id,
                    "status": status,
                    "updated_at": utc_now_iso(),
                    "last_error": last_error,
                }
            ],
        )
