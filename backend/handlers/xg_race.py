import json

from .base import BaseHandler


class MatchXgRaceHandler(BaseHandler):
    CACHE_TTL = 10
    REQUIRED_FIELDS = {
        "home_team",
        "away_team",
        "timeline_minute",
        "home_xg_cumulative",
        "away_xg_cumulative",
    }

    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        try:
            payload = await self.load_mock_json(f"match_{match_id}_xg_race.json")
        except FileNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="xg_race_not_found",
                message=f"No mock xG race data found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except json.JSONDecodeError:
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Mock xG race file for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, dict):
            self.write_error_envelope(
                status_code=500,
                code="invalid_xg_race_payload",
                message="xG race payload must be a JSON object.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        missing_fields = sorted(self.REQUIRED_FIELDS - payload.keys())
        if missing_fields:
            self.write_error_envelope(
                status_code=500,
                code="invalid_xg_race_payload",
                message=f"xG race payload is missing required fields: {', '.join(missing_fields)}.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
