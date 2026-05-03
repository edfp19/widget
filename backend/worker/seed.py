from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from services import CacheService, ClickHouseHttpClient, InMemoryCacheBackend
from services.replay_service import ReplayService


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _document_row(document_key: str, payload: Any) -> dict[str, Any]:
    return {
        "document_key": document_key,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "updated_at": utc_now_iso(),
    }


def _parse_utc_iso(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)


def _format_datetime64(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def build_seed_replay_events(
    state: dict[str, Any],
    xg_race: dict[str, Any],
    facts: list[dict[str, Any]],
    team_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    base_state = {
        "match_id": state["match_id"],
        "competition_id": state["competition_id"],
        "phase": state["phase"],
        "clock": state["clock"],
        "home_score": state["home_score"],
        "away_score": state["away_score"],
        "home_team": state["home_team"],
        "away_team": state["away_team"],
        "lineups_confirmed": state["lineups_confirmed"],
        "kickoff_utc": state["kickoff_utc"],
    }

    events: list[dict[str, Any]] = [
        {
            "event_id": "seed_state_initial",
            "state": dict(base_state),
        }
    ]

    for index, minute in enumerate(xg_race["timeline_minute"]):
        events.append(
            {
                "event_id": f"seed_xg_{index:03d}",
                "state": dict(base_state),
                "xg_point": {
                    "minute": minute,
                    "home_team": xg_race["home_team"],
                    "away_team": xg_race["away_team"],
                    "home_xg_cumulative": xg_race["home_xg_cumulative"][index],
                    "away_xg_cumulative": xg_race["away_xg_cumulative"][index],
                },
            }
        )

    for row in facts:
        events.append(
            {
                "event_id": f"seed_fact_{row['fact_id']}",
                "state": dict(base_state),
                "fact": {
                    "fact_id": row["fact_id"],
                    "category": row["category"],
                    "text": row["text"],
                    "minute": row["minute"],
                    "event_type": row["event_type"],
                },
            }
        )

    events.append(
        {
            "event_id": "seed_live_team_stats",
            "state": dict(base_state),
            "live_team_stats": team_stats["live"],
        }
    )
    return events


async def ensure_schema(client: ClickHouseHttpClient) -> None:
    sql_dir = Path(__file__).resolve().parents[2] / "sql"
    for name in ("001_init.sql", "002_views.sql"):
        path = sql_dir / name
        if path.exists():
            sql_text = path.read_text(encoding="utf-8")
            statements = [segment.strip() for segment in sql_text.split(";") if segment.strip()]
            for statement in statements:
                await client.command_all_hosts(statement)


async def seed_clickhouse_from_mock_data(client: ClickHouseHttpClient, mock_data_dir: Path) -> None:
    await ensure_schema(client)

    state = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_state.json")
    xg_race = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_xg_race.json")
    facts = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_facts.json")
    squads = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_squads.json")
    team_stats = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_team_stats.json")
    team_one_stats = await asyncio.to_thread(_read_json, mock_data_dir / "team_1_stats.json")
    table = await asyncio.to_thread(_read_json, mock_data_dir / "competition_39_table.json")
    fixtures = await asyncio.to_thread(_read_json, mock_data_dir / "competition_39_fixtures.json")
    h2h = await asyncio.to_thread(_read_json, mock_data_dir / "match_12345_h2h.json")

    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.raw_match_events SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.ingest_event_ledger SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.match_state_latest SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.match_xg_events SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.match_facts SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.competition_table_rows SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.competition_fixture_rows SYNC")
    await client.command_all_hosts("TRUNCATE TABLE IF EXISTS widget.widget_documents SYNC")

    snapshot_ts = utc_now_iso()
    await client.insert_json_rows(
        "widget.competition_table_rows",
        [
            {
                "competition_id": "39",
                "snapshot_ts": snapshot_ts,
                "position": row["position"],
                "previous_position": row["previous_position"],
                "team_name": row["team_name"],
                "played": row["played"],
                "won": row["won"],
                "drawn": row["drawn"],
                "lost": row["lost"],
                "gf": row["gf"],
                "ga": row["ga"],
                "gd": row["gd"],
                "points": row["points"],
                "form_json": json.dumps(row["form"], ensure_ascii=False),
                "home_json": json.dumps(row["home"], ensure_ascii=False),
                "away_json": json.dumps(row["away"], ensure_ascii=False),
            }
            for row in table
        ],
    )

    await client.insert_json_rows(
        "widget.competition_fixture_rows",
        [
            {
                "competition_id": "39",
                "snapshot_ts": snapshot_ts,
                "match_id": row["match_id"],
                "fixture_date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "status": row["status"],
            }
            for row in fixtures
        ],
    )

    await client.insert_json_rows(
        "widget.widget_documents",
        [
            _document_row("match_squads:12345", squads),
            _document_row("match_team_stats:12345", team_stats),
            _document_row("team_stats:1", team_one_stats),
            _document_row("match_h2h:12345", h2h),
            _document_row("match_facts:12345", facts),
        ],
    )

    replay_service = ReplayService(
        client,
        CacheService(InMemoryCacheBackend()),
        Path(__file__).resolve().parents[2],
    )
    seed_events = build_seed_replay_events(state, xg_race, facts, team_stats)
    kickoff = _parse_utc_iso(state["kickoff_utc"])
    for index, event in enumerate(seed_events):
        event_ts = _format_datetime64(kickoff + timedelta(milliseconds=index))
        await replay_service.apply_event(event, event_ts=event_ts)


async def main() -> None:
    client = ClickHouseHttpClient.from_env()
    mock_data_dir = Path(__file__).resolve().parents[1] / "mock_data"
    await seed_clickhouse_from_mock_data(client, mock_data_dir)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
