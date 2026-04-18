import json

from .base import BaseHandler


class TeamStatsHandler(BaseHandler):
    CACHE_TTL = 120
    VALID_SPLITS = {"season", "last_5", "last_10", "home", "away"}

    async def get(self, team_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        split = self.get_query_argument("split", default="season")
        if split not in self.VALID_SPLITS:
            self.write_error_envelope(
                status_code=400,
                code="invalid_split",
                message="Query parameter 'split' must be one of: season, last_5, last_10, home, away.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        try:
            payload = await self.load_mock_json(f"team_{team_id}_stats.json")
        except FileNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="team_stats_not_found",
                message=f"No mock team stats found for team_id '{team_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except json.JSONDecodeError:
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Mock team stats file for team_id '{team_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, dict) or split not in payload:
            self.write_error_envelope(
                status_code=500,
                code="invalid_team_stats_payload",
                message=f"Team stats payload must include the requested split '{split}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload[split], error=None, cache_ttl=self.CACHE_TTL)
