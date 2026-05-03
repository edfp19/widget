from __future__ import annotations

import asyncio
import json
from urllib import error, parse, request


class ClickHouseUnavailableError(RuntimeError):
    """Raised when every configured ClickHouse host fails."""


class ClickHouseHttpClient:
    def __init__(self, hosts: list[str], *, insert_quorum: int | None = None) -> None:
        self.hosts = hosts
        self.insert_quorum = insert_quorum

    def _build_url(self, host: str, query: str) -> str:
        return f"{host}/?query={parse.quote(query)}"

    @staticmethod
    def _normalize_host(host: str) -> str:
        normalized = host.rstrip("/")
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return normalized
        return f"http://{normalized}"

    @classmethod
    def from_env(
        cls,
        *,
        hosts: str | None = None,
        primary_host: str | None = None,
        port: str | None = None,
    ) -> "ClickHouseHttpClient":
        import os

        insert_quorum = None
        try:
            raw_insert_quorum = os.environ.get("INSERT_QUORUM")
            if raw_insert_quorum and raw_insert_quorum.strip():
                insert_quorum = int(raw_insert_quorum)
        except Exception:
            insert_quorum = None
        resolved_hosts = hosts
        if resolved_hosts is None:
            env_hosts = os.environ.get("CLICKHOUSE_HOSTS")
            if env_hosts and env_hosts.strip():
                resolved_hosts = env_hosts
        if hosts:
            resolved = [cls._normalize_host(item.strip()) for item in hosts.split(",") if item.strip()]
        elif resolved_hosts:
            resolved = [cls._normalize_host(item.strip()) for item in resolved_hosts.split(",") if item.strip()]
        else:
            host = primary_host or os.environ.get("CLICKHOUSE_HOST") or "127.0.0.1"
            resolved_port = port or os.environ.get("CLICKHOUSE_PORT") or "8123"
            resolved = [cls._normalize_host(f"{host}:{resolved_port}")]
        return cls(resolved, insert_quorum=insert_quorum)

    def _request(self, url: str, *, data: bytes | None = None) -> str:
        req = request.Request(url, method="POST" if data is not None else "GET", data=data)
        with request.urlopen(req, timeout=5) as response:
            return response.read().decode("utf-8")

    def _apply_insert_quorum(self, query: str) -> str:
        if self.insert_quorum is None:
            return query
        return f"{query} SETTINGS insert_quorum = {self.insert_quorum}"

    async def _execute_for_host(self, host: str, query: str, *, data: bytes | None = None) -> str:
        return await asyncio.to_thread(
            self._request,
            self._build_url(host, query),
            data=data,
        )

    async def _execute(self, query: str, *, data: bytes | None = None) -> str:
        last_error: Exception | None = None
        for host in self.hosts:
            try:
                return await self._execute_for_host(host, query, data=data)
            except (error.URLError, error.HTTPError, TimeoutError, OSError, RuntimeError) as exc:
                last_error = exc
                continue
        raise ClickHouseUnavailableError(str(last_error) if last_error else "No ClickHouse hosts configured")

    async def command(self, query: str, *, apply_write_settings: bool = False) -> None:
        final_query = self._apply_insert_quorum(query) if apply_write_settings else query
        await self._execute(final_query, data=b" ")

    async def command_all_hosts(self, query: str, *, apply_write_settings: bool = False) -> None:
        last_error: Exception | None = None
        successful_hosts = 0
        final_query = self._apply_insert_quorum(query) if apply_write_settings else query
        for host in self.hosts:
            try:
                await self._execute_for_host(host, final_query, data=b" ")
                successful_hosts += 1
            except (error.URLError, error.HTTPError, TimeoutError, OSError, RuntimeError) as exc:
                last_error = exc
        if successful_hosts == 0:
            raise ClickHouseUnavailableError(str(last_error) if last_error else "No ClickHouse hosts configured")

    async def query_json_rows(self, query: str) -> list[dict]:
        payload = await self._execute(f"{query} FORMAT JSON")
        return json.loads(payload)["data"]

    async def insert_json_rows(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        body = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")
        query = self._apply_insert_quorum(f"INSERT INTO {table}")
        await self._execute(f"{query} FORMAT JSONEachRow", data=body)
