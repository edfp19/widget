import json

from providers.base import DataSourceDecodeError, DataSourceNotFoundError

from .base import BaseHandler


class CompetitionFixturesHandler(BaseHandler):
    CACHE_TTL = 60
    VALID_STATUSES = {"scheduled", "played"}

    async def get(self, competition_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        status = self.get_query_argument("status", default=None)
        limit = self.get_query_argument("limit", default="5")

        if status is not None and status not in self.VALID_STATUSES:
            self.write_error_envelope(
                status_code=400,
                code="invalid_status",
                message="Query parameter 'status' must be one of: scheduled, played.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        try:
            limit_value = int(limit)
        except ValueError:
            self.write_error_envelope(
                status_code=400,
                code="invalid_limit",
                message="Query parameter 'limit' must be an integer.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if limit_value < 1:
            self.write_error_envelope(
                status_code=400,
                code="invalid_limit",
                message="Query parameter 'limit' must be greater than 0.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        try:
            payload = await self.provider.get_competition_fixtures(
                competition_id,
                status=status,
                limit=limit_value,
            )
        except DataSourceNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="fixtures_not_found",
                message=f"No mock fixtures found for competition_id '{competition_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except (DataSourceDecodeError, json.JSONDecodeError):
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Fixtures data for competition_id '{competition_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, list):
            self.write_error_envelope(
                status_code=500,
                code="invalid_fixtures_payload",
                message="Fixtures payload must be a JSON array of rows.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
