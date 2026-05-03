import json
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.cache import CacheKeys, CacheService, InMemoryCacheBackend  # noqa: E402
from services.replay_service import ReplayService  # noqa: E402
from worker.seed import build_seed_replay_events  # noqa: E402


class FakeReplayClient:
    def __init__(self) -> None:
        self.inserts = []
        self.commands = []
        self.documents = {
            "match_team_stats:12345": {
                "season": {},
                "last_5": {},
                "last_10": {},
                "home": {},
                "away": {},
                "live": {
                    "home": {"team_name": "Arsenal", "shots": 1},
                    "away": {"team_name": "Chelsea", "shots": 1},
                },
            }
        }
        self.raw_event_ids = set()
        self.ledger = {}
        self.xg_event_ids = set()
        self.fact_event_ids = set()
        self.max_sort_index = 10
        self.fail_once_on_state = False
        self.raw_events = []

    async def insert_json_rows(self, table: str, rows: list[dict]) -> None:
        self.inserts.append((table, rows))
        if table == "widget.raw_match_events":
            for row in rows:
                self.raw_event_ids.add(row["event_id"])
                self.raw_events.append(
                    {
                        "event_id": row["event_id"],
                        "event_ts": row["event_ts"],
                        "payload_json": row["payload_json"],
                    }
                )
        elif table == "widget.ingest_event_ledger":
            for row in rows:
                self.ledger[row["event_id"]] = row["status"]
        elif table == "widget.match_xg_events":
            for row in rows:
                self.xg_event_ids.add(row["source_event_id"])
        elif table == "widget.match_facts":
            for row in rows:
                self.fact_event_ids.add(row["source_event_id"])
                self.max_sort_index = max(self.max_sort_index, row["sort_index"])
        elif table == "widget.widget_documents":
            for row in rows:
                self.documents[row["document_key"]] = json.loads(row["payload_json"])
        elif table == "widget.match_state_latest" and self.fail_once_on_state:
            self.fail_once_on_state = False
            raise RuntimeError("simulated_state_failure")

    async def query_json_rows(self, query: str):
        if "SELECT payload_json, event_ts FROM widget.raw_match_events" in query:
            return list(self.raw_events)
        if "FROM widget.ingest_event_ledger FINAL" in query:
            event_id = query.split("WHERE event_id = '", 1)[1].split("'", 1)[0]
            if event_id not in self.ledger:
                return []
            return [{"status": self.ledger[event_id]}]
        if "FROM widget.raw_match_events" in query:
            event_id = query.split("WHERE event_id = '", 1)[1].split("'", 1)[0]
            return [{"count": 1 if event_id in self.raw_event_ids else 0}]
        if "FROM widget.match_xg_events" in query and "count() AS count" in query:
            event_id = query.split("WHERE source_event_id = '", 1)[1].split("'", 1)[0]
            return [{"count": 1 if event_id in self.xg_event_ids else 0}]
        if "FROM widget.match_facts" in query and "count() AS count" in query:
            event_id = query.split("WHERE source_event_id = '", 1)[1].split("'", 1)[0]
            return [{"count": 1 if event_id in self.fact_event_ids else 0}]
        if "max(sort_index)" in query:
            return [{"max_sort_index": self.max_sort_index}]
        if "FROM widget.widget_documents FINAL" in query:
            document_key = query.split("WHERE document_key = '", 1)[1].split("'", 1)[0]
            if document_key not in self.documents:
                return []
            return [{"payload_json": json.dumps(self.documents[document_key])}]
        raise AssertionError(f"Unexpected query: {query}")

    async def command_all_hosts(self, query: str) -> None:
        self.commands.append(query)
        if "TRUNCATE TABLE IF EXISTS widget.match_xg_events" in query:
            self.xg_event_ids.clear()
        elif "TRUNCATE TABLE IF EXISTS widget.match_facts" in query:
            self.fact_event_ids.clear()
            self.max_sort_index = 0
        elif "TRUNCATE TABLE IF EXISTS widget.match_state_latest" in query:
            pass

    async def command(self, query: str, *, apply_write_settings: bool = False) -> None:
        await self.command_all_hosts(query)


class ReplayServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = FakeReplayClient()
        self.cache = CacheService(InMemoryCacheBackend())
        self.service = ReplayService(self.client, self.cache, PROJECT_ROOT)

    async def test_step_updates_storage_and_invalidates_match_cache(self) -> None:
        await self.cache.set_json(CacheKeys.match_state("12345"), {"phase": "PRE_MATCH"}, ttl_seconds=5)
        await self.cache.set_json(CacheKeys.match_xg_race("12345"), {"timeline_minute": [5]}, ttl_seconds=10)
        await self.cache.set_json(
            CacheKeys.match_team_stats("12345", "live"),
            {"home": {"shots": 1}},
            ttl_seconds=120,
        )

        self.service._index = 2
        event = await self.service.step()

        self.assertEqual(event["event_id"], "evt_goal_saka_34")
        inserted_tables = [table for table, _rows in self.client.inserts]
        self.assertIn("widget.raw_match_events", inserted_tables)
        self.assertIn("widget.match_state_latest", inserted_tables)
        self.assertIn("widget.match_xg_events", inserted_tables)
        self.assertIn("widget.match_facts", inserted_tables)
        self.assertIn("widget.widget_documents", inserted_tables)
        self.assertIsNone(await self.cache.get_json(CacheKeys.match_state("12345")))
        self.assertEqual(self.client.documents["match_team_stats:12345"]["live"]["home"]["shots"], 6)
        self.assertEqual(self.client.ledger["evt_goal_saka_34"], "applied")

    async def test_duplicate_event_does_not_double_apply(self) -> None:
        event = self.service._events[2]

        await self.service.apply_event(event)
        insert_count_after_first = len(self.client.inserts)
        await self.service.apply_event(event)

        self.assertEqual(len(self.client.raw_event_ids), 1)
        self.assertEqual(len(self.client.xg_event_ids), 1)
        self.assertEqual(len(self.client.fact_event_ids), 1)
        self.assertEqual(len(self.client.inserts), insert_count_after_first)

    async def test_batch_flush_waits_for_threshold(self) -> None:
        self.service.batch_size = 2
        self.service.batch_window_seconds = 999

        await self.service.enqueue_event(self.service._events[0], force_flush=False)
        self.assertEqual(len(self.client.inserts), 0)

        await self.service.enqueue_event(self.service._events[1], force_flush=False)
        self.assertGreater(len(self.client.inserts), 0)

    async def test_recovery_after_raw_insert_failure_reuses_existing_raw_event(self) -> None:
        self.client.fail_once_on_state = True
        event = self.service._events[2]

        with self.assertRaises(RuntimeError):
            await self.service.apply_event(event)

        self.assertIn("evt_goal_saka_34", self.client.raw_event_ids)
        self.assertEqual(self.client.ledger["evt_goal_saka_34"], "pending")
        raw_insert_count = sum(1 for table, _rows in self.client.inserts if table == "widget.raw_match_events")

        await self.service.apply_event(event)

        self.assertEqual(self.client.ledger["evt_goal_saka_34"], "applied")
        self.assertEqual(
            sum(1 for table, _rows in self.client.inserts if table == "widget.raw_match_events"),
            raw_insert_count,
        )

    async def test_rebuild_from_raw_reapplies_live_serving_state(self) -> None:
        await self.service.apply_event(self.service._events[1])
        await self.service.apply_event(self.service._events[2])
        self.client.inserts.clear()
        self.client.xg_event_ids.clear()
        self.client.fact_event_ids.clear()
        self.client.documents["match_team_stats:12345"]["live"]["home"]["shots"] = 1
        await self.cache.set_json(CacheKeys.match_state("12345"), {"phase": "LIVE"}, ttl_seconds=5)

        summary = await self.service.rebuild_from_raw()

        inserted_tables = [table for table, _rows in self.client.inserts]
        self.assertEqual(summary, {"events_replayed": 2, "matches_rebuilt": 1})
        self.assertIn("widget.match_state_latest", inserted_tables)
        self.assertIn("widget.match_xg_events", inserted_tables)
        self.assertIn("widget.match_facts", inserted_tables)
        self.assertEqual(self.client.documents["match_team_stats:12345"]["live"]["home"]["shots"], 6)
        self.assertIsNone(await self.cache.get_json(CacheKeys.match_state("12345")))

    async def test_rebuild_from_raw_can_restore_seed_baseline_events(self) -> None:
        mock_dir = PROJECT_ROOT / "backend" / "mock_data"
        state = json.loads((mock_dir / "match_12345_state.json").read_text(encoding="utf-8"))
        xg_race = json.loads((mock_dir / "match_12345_xg_race.json").read_text(encoding="utf-8"))
        facts = json.loads((mock_dir / "match_12345_facts.json").read_text(encoding="utf-8"))
        team_stats = json.loads((mock_dir / "match_12345_team_stats.json").read_text(encoding="utf-8"))

        for event in build_seed_replay_events(state, xg_race, facts, team_stats):
            await self.service.apply_event(event)

        self.client.inserts.clear()
        self.client.xg_event_ids.clear()
        self.client.fact_event_ids.clear()
        self.client.documents["match_team_stats:12345"]["live"]["home"]["shots"] = 0

        summary = await self.service.rebuild_from_raw()

        self.assertEqual(summary["events_replayed"], 1 + len(xg_race["timeline_minute"]) + len(facts) + 1)
        self.assertEqual(summary["matches_rebuilt"], 1)
        self.assertEqual(len(self.client.xg_event_ids), len(xg_race["timeline_minute"]))
        self.assertEqual(len(self.client.fact_event_ids), len(facts))
        self.assertEqual(self.client.documents["match_team_stats:12345"]["live"]["home"]["shots"], 11)
