import json
import sys
from datetime import datetime
from pathlib import Path
import unittest

import tornado.testing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402


class ApiContractTest(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def fetch_json(self, path: str, expected_code: int = 200):
        response = self.fetch(path)
        self.assertEqual(response.code, expected_code, response.body.decode("utf-8"))
        return response, json.loads(response.body)

    def assert_timestamp(self, timestamp: str) -> None:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        self.assertIsNotNone(parsed)

    def assert_success_envelope(self, payload: dict, endpoint: str, ttl: int) -> None:
        self.assertEqual(payload["meta"]["endpoint"], endpoint)
        self.assertEqual(payload["meta"]["cache_ttl"], ttl)
        self.assertEqual(payload["meta"]["version"], "1.0")
        self.assertIsNone(payload["error"])
        self.assert_timestamp(payload["meta"]["timestamp"])

    def assert_error_envelope(
        self,
        payload: dict,
        endpoint: str,
        ttl: int,
        code: str,
        message_fragment: str | None = None,
    ) -> None:
        self.assertEqual(payload["meta"]["endpoint"], endpoint)
        self.assertEqual(payload["meta"]["cache_ttl"], ttl)
        self.assertEqual(payload["meta"]["version"], "1.0")
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["error"]["code"], code)
        if message_fragment:
            self.assertIn(message_fragment, payload["error"]["message"])
        self.assert_timestamp(payload["meta"]["timestamp"])

    def test_health_endpoint(self):
        response = self.fetch("/api/health")
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {"status": "ok"})

    def test_positive_endpoint_contracts(self):
        cases = [
            (
                "/api/v1/match/12345/state",
                5,
                lambda data: (
                    self.assertEqual(data["phase"], "PRE_MATCH"),
                    self.assertEqual(data["home_team"], "Arsenal"),
                ),
            ),
            (
                "/api/v1/competition/39/table",
                300,
                lambda data: (
                    self.assertGreater(len(data), 0),
                    self.assertEqual(data[0]["team_name"], "Liverpool"),
                ),
            ),
            (
                "/api/v1/competition/39/fixtures?status=played&limit=2",
                60,
                lambda data: (
                    self.assertEqual(len(data), 2),
                    self.assertTrue(all(item["status"] == "played" for item in data)),
                ),
            ),
            (
                "/api/v1/match/12345/xg-race",
                10,
                lambda data: (
                    self.assertEqual(data["home_team"], "Arsenal"),
                    self.assertEqual(len(data["timeline_minute"]), 7),
                ),
            ),
            (
                "/api/v1/match/12345/squads",
                60,
                lambda data: (
                    self.assertEqual(data["home"]["team_name"], "Arsenal"),
                    self.assertEqual(len(data["home"]["starting_xi"]), 11),
                ),
            ),
            (
                "/api/v1/match/12345/team-stats?split=last_5",
                120,
                lambda data: (
                    self.assertEqual(data["home"]["team_name"], "Arsenal"),
                    self.assertIn("shots_per_game", data["home"]),
                ),
            ),
            (
                "/api/v1/team/1/stats?split=season",
                120,
                lambda data: (
                    self.assertEqual(data["home"]["team_name"], "Arsenal"),
                    self.assertIn("xg_for_avg", data["home"]),
                ),
            ),
            (
                "/api/v1/match/12345/h2h?limit=3",
                300,
                lambda data: (
                    self.assertEqual(len(data), 3),
                    self.assertEqual(data[0]["match_id"], "h_001"),
                ),
            ),
            (
                "/api/v1/match/12345/h2h/players",
                300,
                lambda data: (
                    self.assertEqual(len(data["home_players"]), 3),
                    self.assertEqual(len(data["away_players"]), 3),
                ),
            ),
            (
                "/api/v1/match/12345/h2h/players?home_player_id=p_09&away_player_id=p_28",
                300,
                lambda data: (
                    self.assertEqual(data["home_player"]["name"], "Bukayo Saka"),
                    self.assertEqual(data["away_player"]["name"], "Cole Palmer"),
                ),
            ),
            (
                "/api/v1/match/12345/facts?category=live&limit=2",
                15,
                lambda data: (
                    self.assertEqual(len(data), 2),
                    self.assertTrue(all(item["category"] == "live" for item in data)),
                ),
            ),
        ]

        for path, ttl, assertions in cases:
            with self.subTest(path=path):
                response, payload = self.fetch_json(path)
                self.assertEqual(response.headers["Cache-Control"], f"public, max-age={ttl}")
                self.assert_success_envelope(payload, path.split("?")[0], ttl)
                assertions(payload["data"])

    def test_fixtures_validation_errors(self):
        cases = [
            (
                "/api/v1/competition/39/fixtures?status=live",
                "invalid_status",
                "must be one of",
            ),
            (
                "/api/v1/competition/39/fixtures?limit=abc",
                "invalid_limit",
                "must be an integer",
            ),
            (
                "/api/v1/competition/39/fixtures?limit=0",
                "invalid_limit",
                "greater than 0",
            ),
        ]

        for path, code, fragment in cases:
            with self.subTest(path=path):
                response, payload = self.fetch_json(path, expected_code=400)
                self.assertEqual(response.headers["Cache-Control"], "public, max-age=60")
                self.assert_error_envelope(payload, "/api/v1/competition/39/fixtures", 60, code, fragment)

    def test_team_stats_validation_errors(self):
        cases = [
            "/api/v1/match/12345/team-stats?split=recent",
            "/api/v1/team/1/stats?split=recent",
        ]

        for path in cases:
            with self.subTest(path=path):
                response, payload = self.fetch_json(path, expected_code=400)
                self.assertEqual(response.headers["Cache-Control"], "public, max-age=120")
                self.assert_error_envelope(
                    payload,
                    path.split("?")[0],
                    120,
                    "invalid_split",
                    "must be one of",
                )

    def test_h2h_player_validation_errors(self):
        response, payload = self.fetch_json(
            "/api/v1/match/12345/h2h/players?home_player_id=p_09",
            expected_code=400,
        )
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=300")
        self.assert_error_envelope(
            payload,
            "/api/v1/match/12345/h2h/players",
            300,
            "invalid_player_selection",
            "must be provided together",
        )

        response, payload = self.fetch_json(
            "/api/v1/match/12345/h2h/players?home_player_id=unknown&away_player_id=p_28",
            expected_code=404,
        )
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=300")
        self.assert_error_envelope(
            payload,
            "/api/v1/match/12345/h2h/players",
            300,
            "player_not_found",
            "not found",
        )

    def test_facts_validation_errors(self):
        cases = [
            (
                "/api/v1/match/12345/facts?category=preview",
                "invalid_category",
                "must be one of",
            ),
            (
                "/api/v1/match/12345/facts?limit=abc",
                "invalid_limit",
                "must be an integer",
            ),
            (
                "/api/v1/match/12345/facts?limit=0",
                "invalid_limit",
                "greater than 0",
            ),
        ]

        for path, code, fragment in cases:
            with self.subTest(path=path):
                response, payload = self.fetch_json(path, expected_code=400)
                self.assertEqual(response.headers["Cache-Control"], "public, max-age=15")
                self.assert_error_envelope(
                    payload,
                    "/api/v1/match/12345/facts",
                    15,
                    code,
                    fragment,
                )

    def test_missing_resource_endpoints(self):
        missing_cases = [
            ("/api/v1/match/99999/state", 5, "state_not_found"),
            ("/api/v1/competition/99999/table", 300, "table_not_found"),
            ("/api/v1/competition/99999/fixtures", 60, "fixtures_not_found"),
            ("/api/v1/match/99999/xg-race", 10, "xg_race_not_found"),
            ("/api/v1/match/99999/squads", 60, "squads_not_found"),
            ("/api/v1/match/99999/team-stats", 120, "match_team_stats_not_found"),
            ("/api/v1/team/99999/stats", 120, "team_stats_not_found"),
            ("/api/v1/match/99999/h2h", 300, "h2h_not_found"),
            ("/api/v1/match/99999/h2h/players", 300, "h2h_not_found"),
            ("/api/v1/match/99999/facts", 15, "facts_not_found"),
        ]

        for path, ttl, code in missing_cases:
            with self.subTest(path=path):
                response, payload = self.fetch_json(path, expected_code=404)
                self.assertEqual(response.headers["Cache-Control"], f"public, max-age={ttl}")
                self.assert_error_envelope(payload, path, ttl, code, "No mock")


if __name__ == "__main__":
    unittest.main()
