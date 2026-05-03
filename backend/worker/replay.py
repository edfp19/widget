from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from providers.registry import build_provider
from services import CacheService, ClickHouseHttpClient
from services.replay_service import ReplayService


async def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    os.environ.setdefault("WIDGET_PROVIDER", "clickhouse")
    provider = build_provider(project_root)
    if provider.__class__.__name__ == "MockDataProvider":
        raise RuntimeError("Replay worker requires WIDGET_PROVIDER=clickhouse.")

    client = ClickHouseHttpClient.from_env(
        hosts=os.environ.get("CLICKHOUSE_HOSTS"),
        primary_host=os.environ.get("CLICKHOUSE_HOST", "127.0.0.1"),
        port=os.environ.get("CLICKHOUSE_PORT", "8123"),
    )
    cache = CacheService.from_env(os.environ.get("REDIS_URL"))
    service = ReplayService(client, cache, project_root)
    if os.environ.get("REPLAY_RESET_ON_START", "true").lower() == "true":
        await service.reset_with_retry()

    autorun = os.environ.get("REPLAY_AUTORUN", "false").lower() == "true"
    await service.run_forever(autorun=autorun)


if __name__ == "__main__":
    asyncio.run(main())
