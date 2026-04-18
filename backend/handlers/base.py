import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tornado.web


class BaseHandler(tornado.web.RequestHandler):
    MOCK_IO_DELAY_SECONDS = 0.05

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
    def mock_data_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "mock_data"

    @staticmethod
    def _read_json_file(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    async def load_mock_json(self, filename: str) -> Any:
        await asyncio.sleep(self.MOCK_IO_DELAY_SECONDS)
        return await asyncio.to_thread(self._read_json_file, self.mock_data_dir / filename)

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
