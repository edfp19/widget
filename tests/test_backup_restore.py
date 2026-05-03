import json
import shutil
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backup_clickhouse import backup_tables  # noqa: E402
from scripts.restore_clickhouse import restore_tables  # noqa: E402


class FakeBackupClient:
    def __init__(self) -> None:
        self.table_data = {
            "widget.raw_match_events": [{"event_id": "evt_1"}],
            "widget.ingest_event_ledger": [{"event_id": "evt_1", "status": "applied"}],
            "widget.match_state_latest": [{"match_id": "12345"}],
            "widget.match_xg_events": [{"minute": 5}],
            "widget.match_facts": [{"fact_id": "f_1"}],
            "widget.competition_table_rows": [{"competition_id": "39", "position": 1}],
            "widget.competition_fixture_rows": [{"competition_id": "39", "match_id": "m_001"}],
            "widget.widget_documents": [{"document_key": "match_team_stats:12345"}],
        }
        self.commands = []
        self.inserted = []

    async def query_json_rows(self, query: str):
        table = query.split("FROM ", 1)[1]
        return self.table_data[table]

    async def command(self, query: str) -> None:
        self.commands.append(query)

    async def command_all_hosts(self, query: str) -> None:
        self.commands.append(query)

    async def insert_json_rows(self, table: str, rows: list[dict]) -> None:
        self.inserted.append((table, rows))


class FailingBackupClient(FakeBackupClient):
    async def query_json_rows(self, query: str):
        raise RuntimeError("simulated_backup_failure")


class BackupRestoreTest(unittest.IsolatedAsyncioTestCase):
    async def test_backup_and_restore_round_trip(self) -> None:
        client = FakeBackupClient()
        tmpdir = PROJECT_ROOT / ".tmp-test-backup"
        if tmpdir.exists():
            shutil.rmtree(tmpdir)
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            backup_dir = await backup_tables(client, tmpdir)
            manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["tables"]), 8)

            await restore_tables(client, backup_dir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertTrue(any("TRUNCATE TABLE IF EXISTS widget.match_state_latest" in cmd for cmd in client.commands))
        restored_tables = [table for table, _rows in client.inserted]
        self.assertIn("widget.widget_documents", restored_tables)

    async def test_backup_writes_health_marker_and_prunes_old_backups(self) -> None:
        client = FakeBackupClient()
        tmpdir = PROJECT_ROOT / ".tmp-test-backup-retention"
        if tmpdir.exists():
            shutil.rmtree(tmpdir)
        tmpdir.mkdir(parents=True, exist_ok=True)
        (tmpdir / "widget-backup-20240101T000000000000Z").mkdir()
        (tmpdir / "widget-backup-20240102T000000000000Z").mkdir()
        try:
            backup_dir = await backup_tables(client, tmpdir, retention_limit=2)
            marker = json.loads((tmpdir / "latest.json").read_text(encoding="utf-8"))
            backup_dirs = sorted(path.name for path in tmpdir.iterdir() if path.is_dir())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(marker["status"], "success")
        self.assertEqual(marker["backup_dir"], backup_dir.name)
        self.assertEqual(marker["table_count"], 8)
        self.assertIn(backup_dir.name, backup_dirs)
        self.assertEqual(len(backup_dirs), 2)
        self.assertNotIn("widget-backup-20240101T000000000000Z", backup_dirs)

    async def test_backup_failure_writes_failed_marker(self) -> None:
        client = FailingBackupClient()
        tmpdir = PROJECT_ROOT / ".tmp-test-backup-failure"
        if tmpdir.exists():
            shutil.rmtree(tmpdir)
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            with self.assertRaises(RuntimeError):
                await backup_tables(client, tmpdir)
            marker = json.loads((tmpdir / "latest.json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(marker["status"], "failed")
        self.assertIn("simulated_backup_failure", marker["error"])
