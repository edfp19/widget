import asyncio
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.cache import CacheKeys, CacheService, InMemoryCacheBackend  # noqa: E402


class CacheServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.cache = CacheService(InMemoryCacheBackend())

    async def test_get_or_set_miss_then_hit(self) -> None:
        calls = {"count": 0}

        async def loader():
            calls["count"] += 1
            return {"value": 42}

        key = CacheKeys.match_state("12345")
        first = await self.cache.get_or_set(key=key, ttl_seconds=5, loader=loader)
        second = await self.cache.get_or_set(key=key, ttl_seconds=5, loader=loader)

        self.assertEqual(first, {"value": 42})
        self.assertEqual(second, {"value": 42})
        self.assertEqual(calls["count"], 1)

    async def test_keys_include_query_dimensions(self) -> None:
        one = CacheKeys.match_facts("12345", "live", 2)
        two = CacheKeys.match_facts("12345", "match", 2)
        three = CacheKeys.match_facts("12345", "live", 5)
        self.assertNotEqual(one, two)
        self.assertNotEqual(one, three)

    async def test_invalidate_match_live_keys(self) -> None:
        await self.cache.set_json(CacheKeys.match_state("12345"), {"state": 1}, ttl_seconds=5)
        await self.cache.set_json(CacheKeys.match_xg_race("12345"), {"xg": 1}, ttl_seconds=10)
        await self.cache.set_json(CacheKeys.match_state("99999"), {"state": 2}, ttl_seconds=5)

        removed = await self.cache.invalidate_match_live_keys("12345")

        self.assertEqual(removed, 2)
        self.assertIsNone(await self.cache.get_json(CacheKeys.match_state("12345")))
        self.assertIsNotNone(await self.cache.get_json(CacheKeys.match_state("99999")))
