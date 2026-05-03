from __future__ import annotations

import os
from pathlib import Path

from providers.base import ProviderConfigurationError, WidgetDataProvider
from providers.clickhouse import ClickHouseDataProvider
from providers.mock import MockDataProvider
from services import CacheService, ClickHouseHttpClient


def build_provider(project_root: Path) -> WidgetDataProvider:
    provider_name = os.environ.get("WIDGET_PROVIDER", "mock").strip().lower()
    mock_data_dir = project_root / "backend" / "mock_data"

    if provider_name == "mock":
        return MockDataProvider(mock_data_dir)

    if provider_name == "clickhouse":
        client = ClickHouseHttpClient.from_env(
            hosts=os.environ.get("CLICKHOUSE_HOSTS"),
            primary_host=os.environ.get("CLICKHOUSE_HOST", "127.0.0.1"),
            port=os.environ.get("CLICKHOUSE_PORT", "8123"),
        )
        cache = CacheService.from_env(os.environ.get("REDIS_URL"))
        return ClickHouseDataProvider(client, cache)

    raise ProviderConfigurationError(
        f"Unsupported WIDGET_PROVIDER '{provider_name}'. Expected 'mock' or 'clickhouse'."
    )
