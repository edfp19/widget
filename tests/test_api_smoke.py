import json
import sys
from pathlib import Path
import unittest

import tornado.testing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402


class ApiSmokeTest(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def fetch_json(self, path: str):
        response = self.fetch(path)
        self.assertEqual(response.code, 200, response.body.decode("utf-8"))
        return json.loads(response.body)

    def test_health_endpoint(self):
        response = self.fetch("/api/health")
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {"status": "ok"})

    def test_state_endpoint(self):
        payload = self.fetch_json("/api/v1/match/12345/state")
        self.assertEqual(payload["meta"]["cache_ttl"], 5)
        self.assertEqual(payload["data"]["phase"], "PRE_MATCH")
        self.assertEqual(payload["data"]["home_team"], "Arsenal")

    def test_table_endpoint(self):
        payload = self.fetch_json("/api/v1/competition/39/table")
        self.assertEqual(payload["meta"]["cache_ttl"], 300)
        self.assertEqual(payload["data"][0]["team_name"], "Liverpool")

    def test_filtered_fixtures_endpoint(self):
        payload = self.fetch_json("/api/v1/competition/39/fixtures?status=played&limit=2")
        self.assertEqual(len(payload["data"]), 2)
        self.assertTrue(all(item["status"] == "played" for item in payload["data"]))

    def test_h2h_selector_endpoint(self):
        payload = self.fetch_json("/api/v1/match/12345/h2h/players")
        self.assertIn("home_players", payload["data"])
        self.assertIn("away_players", payload["data"])

    def test_facts_endpoint(self):
        payload = self.fetch_json("/api/v1/match/12345/facts?category=live&limit=2")
        self.assertEqual(len(payload["data"]), 2)
        self.assertTrue(all(item["category"] == "live" for item in payload["data"]))


if __name__ == "__main__":
    unittest.main()
