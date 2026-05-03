from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.clickhouse_http import ClickHouseHttpClient  # noqa: E402


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


def _backup_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _write_latest_marker(output_dir: Path, payload: dict) -> None:
    (output_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _prune_backups(output_dir: Path, retention_limit: int) -> None:
    backup_dirs = sorted(
        [
            path
            for path in output_dir.iterdir()
            if path.is_dir() and path.name.startswith("widget-backup-")
        ],
        key=lambda path: path.name,
        reverse=True,
    )
    for stale_dir in backup_dirs[retention_limit:]:
        shutil.rmtree(stale_dir, ignore_errors=True)


async def backup_tables(client: ClickHouseHttpClient, output_dir: Path, *, retention_limit: int = 5) -> Path:
    timestamp = _backup_timestamp()
    backup_dir = output_dir / f"widget-backup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"tables": []}
    total_rows = 0
    try:
        for table in TABLES:
            rows = await client.query_json_rows(f"SELECT * FROM {table}")
            filename = table.replace(".", "__") + ".json"
            (backup_dir / filename).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            row_count = len(rows)
            total_rows += row_count
            manifest["tables"].append({"table": table, "file": filename, "rows": row_count})
    except Exception as exc:
        shutil.rmtree(backup_dir, ignore_errors=True)
        _write_latest_marker(
            output_dir,
            {
                "status": "failed",
                "timestamp": timestamp,
                "error": str(exc),
            },
        )
        raise

    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_latest_marker(
        output_dir,
        {
            "status": "success",
            "timestamp": timestamp,
            "backup_dir": backup_dir.name,
            "table_count": len(TABLES),
            "total_rows": total_rows,
        },
    )
    _prune_backups(output_dir, max(1, retention_limit))
    return backup_dir


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "backups"))
    parser.add_argument("--retention-limit", type=int, default=int(os.environ.get("BACKUP_RETENTION_COUNT", "5")))
    args = parser.parse_args()

    client = ClickHouseHttpClient.from_env()
    output_dir = Path(args.output_dir)
    backup_dir = await backup_tables(client, output_dir, retention_limit=args.retention_limit)
    print(f"Backup written to {backup_dir}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
