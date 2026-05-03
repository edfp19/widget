import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from providers.clickhouse import ClickHouseDataProvider  # noqa: E402
from services.cache import CacheService, InMemoryCacheBackend  # noqa: E402


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.queries = []

    async def query_json_rows(self, query: str):
        self.queries.append(query)
        if "FROM widget.match_state_latest" in query:
            return [
                {
                    "match_id": "12345",
                    "competition_id": "39",
                    "phase": "PRE_MATCH",
                    "clock": 0,
                    "home_score": 0,
                    "away_score": 0,
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "lineups_confirmed": 0,
                    "kickoff_utc": "2026-04-19T15:00:00Z",
                }
            ]
        if "FROM widget.competition_table_rows" in query:
            return [
                {
                    "snapshot_ts": "2026-05-02 00:00:00.000",
                    "position": 1,
                    "previous_position": 1,
                    "team_name": "Liverpool",
                    "played": 32,
                    "won": 24,
                    "drawn": 5,
                    "lost": 3,
                    "gf": 75,
                    "ga": 28,
                    "gd": 47,
                    "points": 77,
                    "form_json": '["W","W","D","W","W"]',
                    "home_json": '{"played":16,"won":13,"drawn":2,"lost":1,"gf":41,"ga":12,"gd":29,"points":41}',
                    "away_json": '{"played":16,"won":11,"drawn":3,"lost":2,"gf":34,"ga":16,"gd":18,"points":36}',
                }
            ]
        if "FROM widget.competition_fixture_rows" in query:
            return [
                {
                    "snapshot_ts": "2026-05-02 00:00:00.000",
                    "match_id": "m_004",
                    "fixture_date": "2026-04-12T15:30:00Z",
                    "home_team": "Chelsea",
                    "away_team": "Newcastle United",
                    "home_score": 2,
                    "away_score": 1,
                    "status": "played",
                }
            ]
        raise AssertionError(f"Unexpected query: {query}")


class ClickHouseProviderStateTest(unittest.IsolatedAsyncioTestCase):
    async def test_state_is_cached_after_first_read(self) -> None:
        client = FakeClickHouseClient()
        cache = CacheService(InMemoryCacheBackend())
        provider = ClickHouseDataProvider(client, cache)

        first = await provider.get_match_state("12345")
        second = await provider.get_match_state("12345")

        self.assertEqual(first["home_team"], "Arsenal")
        self.assertEqual(second["away_team"], "Chelsea")
        self.assertEqual(len(client.queries), 1)

    async def test_competition_table_reads_normalized_rows(self) -> None:
        client = FakeClickHouseClient()
        cache = CacheService(InMemoryCacheBackend())
        provider = ClickHouseDataProvider(client, cache)

        rows = await provider.get_competition_table("39")

        self.assertEqual(rows[0]["team_name"], "Liverpool")
        self.assertEqual(rows[0]["form"][0], "W")
        self.assertEqual(rows[0]["home"]["points"], 41)

    async def test_competition_fixtures_reads_normalized_rows(self) -> None:
        client = FakeClickHouseClient()
        cache = CacheService(InMemoryCacheBackend())
        provider = ClickHouseDataProvider(client, cache)

        rows = await provider.get_competition_fixtures("39", status="played", limit=2)

        self.assertEqual(rows[0]["match_id"], "m_004")
        self.assertEqual(rows[0]["status"], "played")
        self.assertEqual(rows[0]["home_score"], 2)
