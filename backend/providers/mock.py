from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .base import DataSourceDecodeError, DataSourceNotFoundError, WidgetDataProvider


class MockDataProvider(WidgetDataProvider):
    IO_DELAY_SECONDS = 0.05

    def __init__(self, mock_data_dir: Path) -> None:
        self.mock_data_dir = mock_data_dir

    @staticmethod
    def _read_json_file(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    async def _load_json(self, filename: str) -> Any:
        await asyncio.sleep(self.IO_DELAY_SECONDS)
        path = self.mock_data_dir / filename

        try:
            return await asyncio.to_thread(self._read_json_file, path)
        except FileNotFoundError as exc:
            raise DataSourceNotFoundError(str(path)) from exc
        except json.JSONDecodeError as exc:
            raise DataSourceDecodeError(str(path)) from exc

    async def get_match_state(self, match_id: str) -> dict[str, Any]:
        return await self._load_json(f"match_{match_id}_state.json")

    async def get_competition_table(self, competition_id: str) -> list[dict[str, Any]]:
        return await self._load_json(f"competition_{competition_id}_table.json")

    async def get_competition_fixtures(
        self, competition_id: str, *, status: str | None, limit: int
    ) -> list[dict[str, Any]]:
        payload = await self._load_json(f"competition_{competition_id}_fixtures.json")
        if status is not None:
            payload = [row for row in payload if row.get("status") == status]
        return payload[:limit]

    async def get_match_xg_race(self, match_id: str) -> dict[str, Any]:
        return await self._load_json(f"match_{match_id}_xg_race.json")

    async def get_match_squads(self, match_id: str) -> dict[str, Any]:
        return await self._load_json(f"match_{match_id}_squads.json")

    async def get_match_team_stats(self, match_id: str, *, split: str) -> dict[str, Any]:
        payload = await self._load_json(f"match_{match_id}_team_stats.json")
        return payload[split]

    async def get_team_stats(self, team_id: str, *, split: str) -> dict[str, Any]:
        payload = await self._load_json(f"team_{team_id}_stats.json")
        return payload[split]

    async def get_match_h2h(self, match_id: str, *, limit: int) -> list[dict[str, Any]]:
        payload = await self._load_json(f"match_{match_id}_h2h.json")
        return payload["results"][:limit]

    async def get_match_h2h_players(
        self,
        match_id: str,
        *,
        home_player_id: str | None,
        away_player_id: str | None,
    ) -> dict[str, Any]:
        payload = await self._load_json(f"match_{match_id}_h2h.json")
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
        payload = await self._load_json(f"match_{match_id}_facts.json")
        if category is not None:
            payload = [row for row in payload if row.get("category") == category]
        return payload[:limit]
