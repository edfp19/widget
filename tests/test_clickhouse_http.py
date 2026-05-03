import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.clickhouse_http import ClickHouseHttpClient  # noqa: E402


class _CaptureHandler(BaseHTTPRequestHandler):
    last_method = None
    last_query = None

    def _capture(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        self.__class__.last_method = self.command
        self.__class__.last_query = unquote(params["query"][0])

    def _write_response(self) -> None:
        body = json.dumps({"data": [{"value": 1}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._capture()
        self._write_response()

    def do_POST(self):  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length:
            self.rfile.read(content_length)
        self._capture()
        self._write_response()

    def log_message(self, format, *args):  # noqa: A003
        return


class ClickHouseHttpClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _CaptureHandler.last_method = None
        _CaptureHandler.last_query = None
        self.server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    async def asyncTearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    async def test_insert_json_rows_applies_insert_quorum(self) -> None:
        client = ClickHouseHttpClient([self.host], insert_quorum=2)

        await client.insert_json_rows("widget.match_state_latest", [{"match_id": "12345"}])

        self.assertEqual(_CaptureHandler.last_method, "POST")
        self.assertIn("INSERT INTO widget.match_state_latest SETTINGS insert_quorum = 2 FORMAT JSONEachRow", _CaptureHandler.last_query)

    async def test_command_only_applies_insert_quorum_when_requested(self) -> None:
        client = ClickHouseHttpClient([self.host], insert_quorum=3)

        await client.command("INSERT INTO widget.ingest_event_ledger VALUES", apply_write_settings=True)

        self.assertEqual(_CaptureHandler.last_method, "POST")
        self.assertEqual(
            _CaptureHandler.last_query,
            "INSERT INTO widget.ingest_event_ledger VALUES SETTINGS insert_quorum = 3",
        )

    async def test_command_without_write_settings_uses_post(self) -> None:
        client = ClickHouseHttpClient([self.host], insert_quorum=3)

        await client.command("TRUNCATE TABLE IF EXISTS widget.match_state_latest SYNC")

        self.assertEqual(_CaptureHandler.last_method, "POST")
        self.assertEqual(_CaptureHandler.last_query, "TRUNCATE TABLE IF EXISTS widget.match_state_latest SYNC")

    async def test_query_json_rows_remains_read_only(self) -> None:
        client = ClickHouseHttpClient([self.host], insert_quorum=4)

        rows = await client.query_json_rows("SELECT 1 AS value")

        self.assertEqual(rows, [{"value": 1}])
        self.assertEqual(_CaptureHandler.last_method, "GET")
        self.assertEqual(_CaptureHandler.last_query, "SELECT 1 AS value FORMAT JSON")

    async def test_from_env_prefers_clickhouse_hosts_variable(self) -> None:
        previous_hosts = os.environ.get("CLICKHOUSE_HOSTS")
        previous_host = os.environ.get("CLICKHOUSE_HOST")
        previous_port = os.environ.get("CLICKHOUSE_PORT")
        os.environ["CLICKHOUSE_HOSTS"] = f"{self.host},http://secondary:8123"
        os.environ["CLICKHOUSE_HOST"] = "ignored-primary"
        os.environ["CLICKHOUSE_PORT"] = "9999"
        try:
            client = ClickHouseHttpClient.from_env()
        finally:
            if previous_hosts is None:
                os.environ.pop("CLICKHOUSE_HOSTS", None)
            else:
                os.environ["CLICKHOUSE_HOSTS"] = previous_hosts
            if previous_host is None:
                os.environ.pop("CLICKHOUSE_HOST", None)
            else:
                os.environ["CLICKHOUSE_HOST"] = previous_host
            if previous_port is None:
                os.environ.pop("CLICKHOUSE_PORT", None)
            else:
                os.environ["CLICKHOUSE_PORT"] = previous_port

        self.assertEqual(client.hosts, [self.host, "http://secondary:8123"])
