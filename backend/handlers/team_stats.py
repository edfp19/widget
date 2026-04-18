import json

from .base import BaseHandler


class TeamStatsBaseHandler(BaseHandler):
    CACHE_TTL = 120
    VALID_SPLITS = {"season", "last_5", "last_10", "home", "away", "live"}

    def validate_split(self, split: str) -> bool:
        if split not in self.VALID_SPLITS:
            self.write_error_envelope(
                status_code=400,
                code="invalid_split",
                message="Query parameter 'split' must be one of: season, last_5, last_10, home, away, live.",
                cache_ttl=self.CACHE_TTL,
            )
            return False

        return True

    async def load_stats_payload(self, filename: str, error_code: str, missing_message: str):
        try:
            return await self.load_mock_json(filename)
        except FileNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code=error_code,
                message=missing_message,
                cache_ttl=self.CACHE_TTL,
            )
            return None
        except json.JSONDecodeError:
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Mock team stats file '{filename}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return None

    def write_split_payload(self, payload, split: str) -> None:
        if not isinstance(payload, dict) or split not in payload:
            self.write_error_envelope(
                status_code=500,
                code="invalid_team_stats_payload",
                message=f"Team stats payload must include the requested split '{split}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload[split], error=None, cache_ttl=self.CACHE_TTL)


class TeamStatsHandler(TeamStatsBaseHandler):
    async def get(self, team_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        split = self.get_query_argument("split", default="season")
        if not self.validate_split(split):
            return

        payload = await self.load_stats_payload(
            f"team_{team_id}_stats.json",
            "team_stats_not_found",
            f"No mock team stats found for team_id '{team_id}'.",
        )
        if payload is None:
            return

        self.write_split_payload(payload, split)


class MatchTeamStatsHandler(TeamStatsBaseHandler):
    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        split = self.get_query_argument("split", default="season")
        if not self.validate_split(split):
            return

        payload = await self.load_stats_payload(
            f"match_{match_id}_team_stats.json",
            "match_team_stats_not_found",
            f"No mock team stats found for match_id '{match_id}'.",
        )
        if payload is None:
            return

        self.write_split_payload(payload, split)
