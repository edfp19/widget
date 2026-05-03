import json
from datetime import datetime, timezone

import tornado.web

from providers.base import WidgetDataProvider


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def options(self, *args, **kwargs) -> None:
        self.set_status(204)
        self.finish()

    def apply_cache_headers(self, ttl: int) -> None:
        self.set_header("Cache-Control", f"public, max-age={ttl}")

    @property
    def provider(self) -> WidgetDataProvider:
        return self.settings["provider"]

    @property
    def replay_service(self):
        return self.settings.get("replay_service")

    def write_json(self, payload: dict, status_code: int = 200) -> None:
        self.set_status(status_code)
        self.finish(json.dumps(payload, ensure_ascii=False))

    def write_envelope(
        self,
        *,
        data,
        error=None,
        status_code: int = 200,
        cache_ttl: int = 0,
    ) -> None:
        payload = {
            "meta": {
                "endpoint": self.request.path,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "cache_ttl": cache_ttl,
                "version": "1.0",
            },
            "data": data,
            "error": error,
        }
        self.write_json(payload, status_code=status_code)

    def write_error_envelope(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        cache_ttl: int = 0,
    ) -> None:
        self.write_envelope(
            data={},
            error={
                "code": code,
                "message": message,
            },
            status_code=status_code,
            cache_ttl=cache_ttl,
        )
