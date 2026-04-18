import json

from .base import BaseHandler


class MatchStateHandler(BaseHandler):
    CACHE_TTL = 5
    REQUIRED_FIELDS = {
        "phase",
        "clock",
        "home_score",
        "away_score",
        "home_team",
        "away_team",
    }

    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        try:
            payload = await self.load_mock_json(f"match_{match_id}_state.json")
        except FileNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="state_not_found",
                message=f"No mock match state found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except json.JSONDecodeError:
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Mock state file for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        missing_fields = sorted(self.REQUIRED_FIELDS - payload.keys())
        if missing_fields:
            self.write_error_envelope(
                status_code=500,
                code="invalid_state_payload",
                message=f"Mock state payload is missing required fields: {', '.join(missing_fields)}.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
