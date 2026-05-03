import json

from providers.base import DataSourceDecodeError, DataSourceNotFoundError

from .base import BaseHandler


class CompetitionTableHandler(BaseHandler):
    CACHE_TTL = 300

    async def get(self, competition_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        try:
            payload = await self.provider.get_competition_table(competition_id)
        except DataSourceNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="table_not_found",
                message=f"No mock league table found for competition_id '{competition_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except (DataSourceDecodeError, json.JSONDecodeError):
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Table data for competition_id '{competition_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, list):
            self.write_error_envelope(
                status_code=500,
                code="invalid_table_payload",
                message="League table payload must be a JSON array of rows.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
