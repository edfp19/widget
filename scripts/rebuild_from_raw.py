from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services import CacheService, ClickHouseHttpClient  # noqa: E402
from services.replay_service import ReplayService  # noqa: E402


async def main() -> None:
    client = ClickHouseHttpClient.from_env()
    cache = CacheService.from_env(os.environ.get("REDIS_URL"))
    service = ReplayService(client, cache, PROJECT_ROOT)
    summary = await service.rebuild_from_raw_with_retry()
    print(
        "Rebuild complete from raw events: "
        f"{summary['events_replayed']} events across {summary['matches_rebuilt']} matches"
    )


if __name__ == "__main__":
    asyncio.run(main())
