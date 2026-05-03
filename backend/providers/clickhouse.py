from __future__ import annotations

import json
from typing import Any

from services import CacheKeys, CacheService, ClickHouseHttpClient

from .base import DataSourceDecodeError, DataSourceNotFoundError, WidgetDataProvider


class ClickHouseDataProvider(WidgetDataProvider):
    def __init__(self, client: ClickHouseHttpClient, cache: CacheService) -> None:
        self.client = client
        self.cache = cache

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    async def _fetch_document(self, document_key: str) -> Any:
        rows = await self.client.query_json_rows(
            "SELECT payload_json "
            "FROM widget.widget_documents FINAL "
            f"WHERE document_key = {self._quote(document_key)} "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        if not rows:
            raise DataSourceNotFoundError(document_key)

        try:
            return json.loads(rows[0]["payload_json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise DataSourceDecodeError(document_key) from exc

    async def get_match_state(self, match_id: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_state(match_id),
            ttl_seconds=5,
            loader=lambda: self._load_match_state(match_id),
        )

    async def _load_match_state(self, match_id: str) -> dict[str, Any]:
        rows = await self.client.query_json_rows(
            "SELECT match_id, competition_id, phase, clock, home_score, away_score, "
            "home_team, away_team, lineups_confirmed, kickoff_utc "
            "FROM widget.match_state_latest FINAL "
            f"WHERE match_id = {self._quote(match_id)} "
            "ORDER BY version_ts DESC LIMIT 1"
        )
        if not rows:
            raise DataSourceNotFoundError(match_id)

        row = rows[0]
        return {
            "match_id": row["match_id"],
            "competition_id": row["competition_id"],
            "phase": row["phase"],
            "clock": row["clock"],
            "home_score": row["home_score"],
            "away_score": row["away_score"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "lineups_confirmed": bool(row["lineups_confirmed"]),
            "kickoff_utc": row["kickoff_utc"],
        }

    async def get_competition_table(self, competition_id: str) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            key=CacheKeys.competition_table(competition_id),
            ttl_seconds=300,
            loader=lambda: self._load_competition_table(competition_id),
        )

    async def _load_competition_table(self, competition_id: str) -> list[dict[str, Any]]:
        rows = await self.client.query_json_rows(
            "SELECT snapshot_ts, position, previous_position, team_name, played, won, drawn, lost, "
            "gf, ga, gd, points, form_json, home_json, away_json "
            "FROM widget.competition_table_rows "
            f"WHERE competition_id = {self._quote(competition_id)} "
            "ORDER BY snapshot_ts DESC, position ASC"
        )
        if not rows:
            raise DataSourceNotFoundError(competition_id)

        latest_snapshot = rows[0].get("snapshot_ts")
        filtered = [row for row in rows if row.get("snapshot_ts") == latest_snapshot] if latest_snapshot else rows
        return [
            {
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
                "form": json.loads(row["form_json"]),
                "home": json.loads(row["home_json"]),
                "away": json.loads(row["away_json"]),
            }
            for row in filtered
        ]

    async def get_competition_fixtures(
        self, competition_id: str, *, status: str | None, limit: int
    ) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            key=CacheKeys.competition_fixtures(competition_id, status, limit),
            ttl_seconds=60,
            loader=lambda: self._load_competition_fixtures(competition_id, status=status, limit=limit),
        )

    async def _load_competition_fixtures(
        self, competition_id: str, *, status: str | None, limit: int
    ) -> list[dict[str, Any]]:
        where = f"competition_id = {self._quote(competition_id)}"
        if status is not None:
            where += f" AND status = {self._quote(status)}"

        rows = await self.client.query_json_rows(
            "SELECT match_id, fixture_date, home_team, away_team, home_score, away_score, status, snapshot_ts "
            "FROM widget.competition_fixture_rows "
            f"WHERE {where} "
            "ORDER BY snapshot_ts DESC, fixture_date DESC, match_id ASC"
        )
        if not rows:
            raise DataSourceNotFoundError(competition_id)

        latest_snapshot = rows[0].get("snapshot_ts")
        filtered = [row for row in rows if row.get("snapshot_ts") == latest_snapshot] if latest_snapshot else rows
        return [
            {
                "match_id": row["match_id"],
                "date": row["fixture_date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "status": row["status"],
            }
            for row in filtered[:limit]
        ]

    async def get_match_xg_race(self, match_id: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_xg_race(match_id),
            ttl_seconds=10,
            loader=lambda: self._load_match_xg_race(match_id),
        )

    async def _load_match_xg_race(self, match_id: str) -> dict[str, Any]:
        rows = await self.client.query_json_rows(
            "SELECT home_team, away_team, minute, home_xg_cumulative, away_xg_cumulative "
            "FROM widget.match_xg_events "
            f"WHERE match_id = {self._quote(match_id)} "
            "ORDER BY minute ASC, event_ts ASC"
        )
        if not rows:
            raise DataSourceNotFoundError(match_id)

        return {
            "home_team": rows[0]["home_team"],
            "away_team": rows[0]["away_team"],
            "timeline_minute": [row["minute"] for row in rows],
            "home_xg_cumulative": [row["home_xg_cumulative"] for row in rows],
            "away_xg_cumulative": [row["away_xg_cumulative"] for row in rows],
        }

    async def get_match_squads(self, match_id: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_squads(match_id),
            ttl_seconds=60,
            loader=lambda: self._fetch_document(f"match_squads:{match_id}"),
        )

    async def get_match_team_stats(self, match_id: str, *, split: str) -> dict[str, Any]:
        ttl = 120
        key = CacheKeys.match_team_stats(match_id, split)
        if split == "live":
            return await self.cache.get_or_set(
                key=key,
                ttl_seconds=ttl,
                loader=lambda: self._load_match_team_stats(match_id, split=split),
            )
        return await self._load_match_team_stats(match_id, split=split)

    async def _load_match_team_stats(self, match_id: str, *, split: str) -> dict[str, Any]:
        payload = await self._fetch_document(f"match_team_stats:{match_id}")
        return payload[split]

    async def get_team_stats(self, team_id: str, *, split: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            key=CacheKeys.team_stats(team_id, split),
            ttl_seconds=120,
            loader=lambda: self._load_team_stats(team_id, split=split),
        )

    async def _load_team_stats(self, team_id: str, *, split: str) -> dict[str, Any]:
        payload = await self._fetch_document(f"team_stats:{team_id}")
        return payload[split]

    async def get_match_h2h(self, match_id: str, *, limit: int) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_h2h(match_id, limit),
            ttl_seconds=300,
            loader=lambda: self._load_match_h2h(match_id, limit=limit),
        )

    async def _load_match_h2h(self, match_id: str, *, limit: int) -> list[dict[str, Any]]:
        payload = await self._fetch_document(f"match_h2h:{match_id}")
        return payload["results"][:limit]

    async def get_match_h2h_players(
        self,
        match_id: str,
        *,
        home_player_id: str | None,
        away_player_id: str | None,
    ) -> dict[str, Any]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_h2h_players(match_id, home_player_id, away_player_id),
            ttl_seconds=300,
            loader=lambda: self._load_match_h2h_players(
                match_id,
                home_player_id=home_player_id,
                away_player_id=away_player_id,
            ),
        )

    async def _load_match_h2h_players(
        self,
        match_id: str,
        *,
        home_player_id: str | None,
        away_player_id: str | None,
    ) -> dict[str, Any]:
        payload = await self._fetch_document(f"match_h2h:{match_id}")
        players = payload["players"]
        home_players = players["home"]
        away_players = players["away"]
        if not home_player_id and not away_player_id:
            return {
                "home_players": [
                    {"player_id": player["player_id"], "name": player["name"]}
                    for player in home_players
                ],
                "away_players": [
                    {"player_id": player["player_id"], "name": player["name"]}
                    for player in away_players
                ],
            }

        home_player = next(
            (player for player in home_players if player.get("player_id") == home_player_id),
            None,
        )
        away_player = next(
            (player for player in away_players if player.get("player_id") == away_player_id),
            None,
        )
        if home_player is None or away_player is None:
            raise DataSourceNotFoundError("player_not_found")
        return {
            "home_player": home_player,
            "away_player": away_player,
        }

    async def get_match_facts(
        self, match_id: str, *, category: str | None, limit: int
    ) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            key=CacheKeys.match_facts(match_id, category, limit),
            ttl_seconds=15,
            loader=lambda: self._load_match_facts(match_id, category=category, limit=limit),
        )

    async def _load_match_facts(
        self, match_id: str, *, category: str | None, limit: int
    ) -> list[dict[str, Any]]:
        where = f"match_id = {self._quote(match_id)}"
        if category is not None:
            where += f" AND category = {self._quote(category)}"

        rows = await self.client.query_json_rows(
            "SELECT fact_id, category, text, minute, event_type "
            "FROM widget.match_facts "
            f"WHERE {where} "
            "ORDER BY sort_index ASC "
            f"LIMIT {limit}"
        )
        if not rows:
            payload = await self._fetch_document(f"match_facts:{match_id}")
            if category is not None:
                payload = [row for row in payload if row.get("category") == category]
            return payload[:limit]
        return rows
