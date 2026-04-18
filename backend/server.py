import asyncio
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


class HealthHandler(BaseHandler):
    def get(self) -> None:
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


def make_app(debug: bool = False) -> tornado.web.Application:
    project_root = Path(__file__).resolve().parent.parent

    return tornado.web.Application(
        [
            (r"/api/health", HealthHandler),
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
    )


async def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("ENV", "development").lower() == "development"
    app = make_app(debug=debug)
    app.listen(port)
    print(f"Server running at http://localhost:{port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
