from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.clickhouse_http import ClickHouseHttpClient  # noqa: E402
from worker.seed import ensure_schema  # noqa: E402


TABLES = [
    "widget.raw_match_events",
    "widget.ingest_event_ledger",
    "widget.match_state_latest",
    "widget.match_xg_events",
    "widget.match_facts",
    "widget.competition_table_rows",
    "widget.competition_fixture_rows",
    "widget.widget_documents",
]


async def restore_tables(client: ClickHouseHttpClient, backup_dir: Path) -> None:
    await ensure_schema(client)
    for table in TABLES:
        await client.command_all_hosts(f"TRUNCATE TABLE IF EXISTS {table} SYNC")

    for table in TABLES:
        filename = backup_dir / (table.replace(".", "__") + ".json")
        rows = json.loads(filename.read_text(encoding="utf-8"))
        if rows:
            await client.insert_json_rows(table, rows)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup_dir")
    args = parser.parse_args()

    client = ClickHouseHttpClient.from_env()
    await restore_tables(client, Path(args.backup_dir))
    print(f"Restore complete from {args.backup_dir}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
