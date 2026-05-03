import asyncio
import json
import os
from pathlib import Path

import tornado.web

from handlers.base import BaseHandler
from handlers.facts import MatchFactsHandler
from handlers.fixtures import CompetitionFixturesHandler
from handlers.h2h import MatchH2HHandler, MatchH2HPlayersHandler
from handlers.squads import MatchSquadsHandler
from handlers.state import MatchStateHandler
from handlers.table import CompetitionTableHandler
from handlers.team_stats import MatchTeamStatsHandler, TeamStatsHandler
from handlers.xg_race import MatchXgRaceHandler
from providers.base import ProviderConfigurationError
from providers.registry import build_provider
from services import CacheService, ClickHouseHttpClient
from services.replay_service import ReplayService


class HealthHandler(BaseHandler):
    async def get(self) -> None:
        self.write_json({"status": "ok"})


class ReplayStepHandler(BaseHandler):
    async def post(self) -> None:
        if self.replay_service is None:
            self.write_json({"status": "disabled"}, status_code=404)
            return

        event = await self.replay_service.step()
        self.write_json({"status": "ok", "event": event})


class ReplayResetHandler(BaseHandler):
    async def post(self) -> None:
        if self.replay_service is None:
            self.write_json({"status": "disabled"}, status_code=404)
            return

        await self.replay_service.reset()
        self.write_json({"status": "ok"})


class ExamplePageHandler(tornado.web.RequestHandler):
    def initialize(self, page_path: str) -> None:
        self.page_path = Path(page_path)

    async def get(self) -> None:
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish(self.page_path.read_text(encoding="utf-8"))


class ConfigPageHandler(tornado.web.RequestHandler):
    def initialize(self, page_path: str) -> None:
        self.page_path = Path(page_path)

    async def get(self) -> None:
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish(self.page_path.read_text(encoding="utf-8"))


def make_runtime(project_root: Path) -> dict:
    provider = build_provider(project_root)
    cache_service = getattr(provider, "cache", None)
    replay_service = None
    if os.environ.get("WIDGET_PROVIDER", "mock").strip().lower() == "clickhouse":
        client = ClickHouseHttpClient.from_env(
            hosts=os.environ.get("CLICKHOUSE_HOSTS"),
            primary_host=os.environ.get("CLICKHOUSE_HOST", "127.0.0.1"),
            port=os.environ.get("CLICKHOUSE_PORT", "8123"),
        )
        cache_service = CacheService.from_env(os.environ.get("REDIS_URL"))
        replay_service = ReplayService(client, cache_service, project_root)
    return {
        "provider": provider,
        "cache_service": cache_service,
        "replay_service": replay_service,
    }


def make_app(debug: bool = False) -> tornado.web.Application:
    project_root = Path(__file__).resolve().parent.parent
    runtime = make_runtime(project_root)

    return tornado.web.Application(
        [
            (r"/api/health", HealthHandler),
            (r"/api/admin/replay/step", ReplayStepHandler),
            (r"/api/admin/replay/reset", ReplayResetHandler),
            (r"/api/v1/competition/([^/]+)/table", CompetitionTableHandler),
            (r"/api/v1/competition/([^/]+)/fixtures", CompetitionFixturesHandler),
            (r"/api/v1/match/([^/]+)/xg-race", MatchXgRaceHandler),
            (r"/api/v1/match/([^/]+)/squads", MatchSquadsHandler),
            (r"/api/v1/match/([^/]+)/team-stats", MatchTeamStatsHandler),
            (r"/api/v1/team/([^/]+)/stats", TeamStatsHandler),
            (r"/api/v1/match/([^/]+)/h2h/players", MatchH2HPlayersHandler),
            (r"/api/v1/match/([^/]+)/h2h", MatchH2HHandler),
            (r"/api/v1/match/([^/]+)/facts", MatchFactsHandler),
            (r"/api/v1/match/([^/]+)/state", MatchStateHandler),
            (
                r"/static/(.*)",
                tornado.web.StaticFileHandler,
                {"path": str(project_root / "frontend")},
            ),
            (
                r"/example",
                ExamplePageHandler,
                {"page_path": str(project_root / "frontend" / "index.html")},
            ),
            (
                r"/config",
                ConfigPageHandler,
                {"page_path": str(project_root / "configurator" / "config.html")},
            ),
        ],
        debug=debug,
        **runtime,
    )


async def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("ENV", "development").lower() == "development"
    try:
        app = make_app(debug=debug)
    except ProviderConfigurationError as exc:
        print(json.dumps({"status": "startup_error", "error": str(exc)}))
        raise
    replay_service = app.settings.get("replay_service")
    seed_on_start = os.environ.get("API_SEED_ON_START", "true").lower() == "true"
    if replay_service is not None and seed_on_start:
        await replay_service.reset_with_retry()
    app.listen(port)
    print(f"Server running at http://localhost:{port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
