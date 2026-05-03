from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse


class InMemoryCacheBackend:
    def __init__(self) -> None:
        self._values: dict[str, tuple[float | None, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at is not None and expires_at <= time.time():
                self._values.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        async with self._lock:
            expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
            self._values[key] = (expires_at, value)

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            removed = 0
            for key in keys:
                if key in self._values:
                    removed += 1
                    self._values.pop(key, None)
            return removed

    async def keys(self, pattern: str) -> list[str]:
        async with self._lock:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [key for key in self._values if key.startswith(prefix)]
            return [pattern] if pattern in self._values else []

    async def ping(self) -> bool:
        return True


class RedisProtocolBackend:
    def __init__(self, host: str, port: int, db: int = 0) -> None:
        self.host = host
        self.port = port
        self.db = db

    @classmethod
    def from_url(cls, url: str) -> "RedisProtocolBackend":
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        db = int((parsed.path or "/0").lstrip("/") or "0")
        return cls(host=host, port=port, db=db)

    @staticmethod
    def _encode(parts: list[str | bytes]) -> bytes:
        encoded = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            raw = part if isinstance(part, bytes) else part.encode("utf-8")
            encoded.append(f"${len(raw)}\r\n".encode("utf-8"))
            encoded.append(raw + b"\r\n")
        return b"".join(encoded)

    async def _read_exactly(self, reader: asyncio.StreamReader, length: int) -> bytes:
        return await reader.readexactly(length)

    async def _read_response(self, reader: asyncio.StreamReader) -> Any:
        prefix = await self._read_exactly(reader, 1)
        if prefix == b"+":
            return (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
        if prefix == b"-":
            message = (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
            raise RuntimeError(message)
        if prefix == b":":
            return int((await reader.readline()).rstrip(b"\r\n"))
        if prefix == b"$":
            length = int((await reader.readline()).rstrip(b"\r\n"))
            if length == -1:
                return None
            payload = await self._read_exactly(reader, length)
            await self._read_exactly(reader, 2)
            return payload.decode("utf-8")
        if prefix == b"*":
            length = int((await reader.readline()).rstrip(b"\r\n"))
            if length == -1:
                return None
            return [await self._read_response(reader) for _ in range(length)]
        raise RuntimeError(f"Unsupported RESP prefix: {prefix!r}")

    async def _command(self, *parts: str | bytes) -> Any:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            if self.db:
                writer.write(self._encode(["SELECT", str(self.db)]))
                await writer.drain()
                await self._read_response(reader)

            writer.write(self._encode(list(parts)))
            await writer.drain()
            return await self._read_response(reader)
        finally:
            writer.close()
            await writer.wait_closed()

    async def get(self, key: str) -> str | None:
        return await self._command("GET", key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._command("SET", key, value, "EX", str(ttl_seconds))

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return int(await self._command("DEL", *keys))

    async def keys(self, pattern: str) -> list[str]:
        result = await self._command("KEYS", pattern)
        return result or []

    async def ping(self) -> bool:
        return (await self._command("PING")) == "PONG"


class CacheKeys:
    VERSION = "widget:v1"

    @classmethod
    def match_state(cls, match_id: str) -> str:
        return f"{cls.VERSION}:match:{match_id}:state"

    @classmethod
    def match_xg_race(cls, match_id: str) -> str:
        return f"{cls.VERSION}:match:{match_id}:xg-race"

    @classmethod
    def match_facts(cls, match_id: str, category: str | None, limit: int) -> str:
        category_part = category or "all"
        return f"{cls.VERSION}:match:{match_id}:facts:{category_part}:{limit}"

    @classmethod
    def match_team_stats(cls, match_id: str, split: str) -> str:
        return f"{cls.VERSION}:match:{match_id}:team-stats:{split}"

    @classmethod
    def team_stats(cls, team_id: str, split: str) -> str:
        return f"{cls.VERSION}:team:{team_id}:stats:{split}"

    @classmethod
    def competition_fixtures(cls, competition_id: str, status: str | None, limit: int) -> str:
        status_part = status or "all"
        return f"{cls.VERSION}:competition:{competition_id}:fixtures:{status_part}:{limit}"

    @classmethod
    def competition_table(cls, competition_id: str) -> str:
        return f"{cls.VERSION}:competition:{competition_id}:table"

    @classmethod
    def match_h2h(cls, match_id: str, limit: int) -> str:
        return f"{cls.VERSION}:match:{match_id}:h2h:{limit}"

    @classmethod
    def match_h2h_players(
        cls, match_id: str, home_player_id: str | None, away_player_id: str | None
    ) -> str:
        home_part = home_player_id or "selector"
        away_part = away_player_id or "selector"
        return f"{cls.VERSION}:match:{match_id}:h2h:players:{home_part}:{away_part}"

    @classmethod
    def match_squads(cls, match_id: str) -> str:
        return f"{cls.VERSION}:match:{match_id}:squads"

    @classmethod
    def match_prefix(cls, match_id: str) -> str:
        return f"{cls.VERSION}:match:{match_id}:"


class CacheService:
    def __init__(self, backend: InMemoryCacheBackend | RedisProtocolBackend) -> None:
        self.backend = backend

    @classmethod
    def from_env(cls, redis_url: str | None) -> "CacheService":
        if redis_url:
            return cls(RedisProtocolBackend.from_url(redis_url))
        return cls(InMemoryCacheBackend())

    async def ping(self) -> bool:
        return await self.backend.ping()

    async def get_json(self, key: str) -> Any | None:
        payload = await self.backend.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self.backend.set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)

    async def get_or_set(
        self,
        *,
        key: str,
        ttl_seconds: int,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        cached = await self.get_json(key)
        if cached is not None:
            return cached
        value = await loader()
        await self.set_json(key, value, ttl_seconds)
        return value

    async def delete(self, *keys: str) -> int:
        return await self.backend.delete(*keys)

    async def delete_pattern(self, pattern: str) -> int:
        keys = await self.backend.keys(pattern)
        if not keys:
            return 0
        return await self.backend.delete(*keys)

    async def invalidate_match_live_keys(self, match_id: str) -> int:
        return await self.delete_pattern(CacheKeys.match_prefix(match_id) + "*")
