import json

from .base import BaseHandler


class MatchSquadsHandler(BaseHandler):
    CACHE_TTL = 60
    REQUIRED_TOP_LEVEL_FIELDS = {"home", "away"}

    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        try:
            payload = await self.load_mock_json(f"match_{match_id}_squads.json")
        except FileNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="squads_not_found",
                message=f"No mock squads data found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except json.JSONDecodeError:
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Mock squads file for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, dict):
            self.write_error_envelope(
                status_code=500,
                code="invalid_squads_payload",
                message="Squads payload must be a JSON object.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        missing_fields = sorted(self.REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
        if missing_fields:
            self.write_error_envelope(
                status_code=500,
                code="invalid_squads_payload",
                message=f"Squads payload is missing required fields: {', '.join(missing_fields)}.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
