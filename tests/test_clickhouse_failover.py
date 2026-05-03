import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.clickhouse_http import ClickHouseHttpClient  # noqa: E402


class _ClickHouseJsonHandler(BaseHTTPRequestHandler):
    def _write_response(self) -> None:
        body = json.dumps({"data": [{"value": 1}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._write_response()

    def do_POST(self):  # noqa: N802
        self._write_response()

    def log_message(self, format, *args):  # noqa: A003
        return


class ClickHouseFailoverTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _ClickHouseJsonHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    async def asyncTearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    async def test_client_falls_back_to_next_host(self) -> None:
        unreachable = "http://127.0.0.1:9"
        healthy = f"http://127.0.0.1:{self.port}"
        client = ClickHouseHttpClient([unreachable, healthy])

        rows = await client.query_json_rows("SELECT 1")

        self.assertEqual(rows, [{"value": 1}])
