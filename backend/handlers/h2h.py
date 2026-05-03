import json

from providers.base import DataSourceDecodeError, DataSourceNotFoundError

from .base import BaseHandler


class H2HBaseHandler(BaseHandler):
    CACHE_TTL = 300

    async def load_h2h_payload(self, loader, match_id: str):
        try:
            payload = await loader()
        except DataSourceNotFoundError:
            self.write_error_envelope(
                status_code=404,
                code="h2h_not_found",
                message=f"No mock head-to-head data found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return None
        except (DataSourceDecodeError, json.JSONDecodeError):
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"H2H data for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return None

        return payload


class MatchH2HHandler(H2HBaseHandler):
    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        limit = self.get_query_argument("limit", default="5")
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

        payload = await self.load_h2h_payload(
            lambda: self.provider.get_match_h2h(match_id, limit=limit_value),
            match_id,
        )
        if payload is None:
            return

        if not isinstance(payload, list):
            self.write_error_envelope(
                status_code=500,
                code="invalid_h2h_payload",
                message="H2H payload must be a JSON array of match rows.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)


class MatchH2HPlayersHandler(H2HBaseHandler):
    async def get(self, match_id: str) -> None:
        self.apply_cache_headers(self.CACHE_TTL)

        home_player_id = self.get_query_argument("home_player_id", default=None)
        away_player_id = self.get_query_argument("away_player_id", default=None)

        if (home_player_id and not away_player_id) or (away_player_id and not home_player_id):
            self.write_error_envelope(
                status_code=400,
                code="invalid_player_selection",
                message="Both 'home_player_id' and 'away_player_id' must be provided together.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        try:
            payload = await self.provider.get_match_h2h_players(
                match_id,
                home_player_id=home_player_id,
                away_player_id=away_player_id,
            )
        except DataSourceNotFoundError as exc:
            if str(exc) == "player_not_found":
                self.write_error_envelope(
                    status_code=404,
                    code="player_not_found",
                    message="One or both selected players were not found in the H2H dataset.",
                    cache_ttl=self.CACHE_TTL,
                )
                return
            self.write_error_envelope(
                status_code=404,
                code="h2h_not_found",
                message=f"No mock head-to-head data found for match_id '{match_id}'.",
                cache_ttl=self.CACHE_TTL,
            )
            return
        except (DataSourceDecodeError, json.JSONDecodeError):
            self.write_error_envelope(
                status_code=500,
                code="invalid_mock_data",
                message=f"H2H data for match_id '{match_id}' is not valid JSON.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if not isinstance(payload, dict):
            self.write_error_envelope(
                status_code=500,
                code="invalid_h2h_payload",
                message="H2H player payload must be a JSON object.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        if home_player_id and away_player_id and (
            "home_player" not in payload or "away_player" not in payload
        ):
            self.write_error_envelope(
                status_code=404,
                code="player_not_found",
                message="One or both selected players were not found in the H2H dataset.",
                cache_ttl=self.CACHE_TTL,
            )
            return

        self.write_envelope(data=payload, error=None, cache_ttl=self.CACHE_TTL)
