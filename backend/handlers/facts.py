import json

from providers.base import DataSourceDecodeError, DataSourceNotFoundError

from .base import BaseHandler


class MatchFactsHandler(BaseHandler):
    CACHE_TTL = 15
    VALID_CATEGORIES = {"team", "player", "match", "live"}

    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        category = self.get_query_argument("category", default=None)
        limit = self.get_query_argument("limit", default="10")

        if category is not None and category not in self.VALID_CATEGORIES:
            self.write_error_envelope(
                status_code=400,
                code="invalid_category",
                message="Query parameter 'category' must be one of: team, player, match, live.",
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
            payload = await self.provider.get_match_facts(
                match_id,
                category=category,
                limit=limit_value,
            )
        except DataSourceNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="facts_not_found",
                message=f"No mock facts data found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except (DataSourceDecodeError, json.JSONDecodeError):
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"Facts data for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, list):
            self.write_error_envelope(
                status_code=500,
                code="invalid_facts_payload",
                message="Facts payload must be a JSON array.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
