import os
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from providers.base import ProviderConfigurationError  # noqa: E402
from providers.clickhouse import ClickHouseDataProvider  # noqa: E402
from providers.mock import MockDataProvider  # noqa: E402
from providers.registry import build_provider  # noqa: E402


class ProviderRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_build_provider_defaults_to_mock(self) -> None:
        os.environ.pop("WIDGET_PROVIDER", None)
        provider = build_provider(PROJECT_ROOT)
        self.assertIsInstance(provider, MockDataProvider)

    def test_build_provider_clickhouse(self) -> None:
        os.environ["WIDGET_PROVIDER"] = "clickhouse"
        os.environ["CLICKHOUSE_HOST"] = "clickhouse1"
        os.environ["CLICKHOUSE_PORT"] = "8123"
        provider = build_provider(PROJECT_ROOT)
        self.assertIsInstance(provider, ClickHouseDataProvider)

    def test_build_provider_rejects_unknown_provider(self) -> None:
        os.environ["WIDGET_PROVIDER"] = "unknown"
        with self.assertRaises(ProviderConfigurationError):
            build_provider(PROJECT_ROOT)
