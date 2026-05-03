from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSourceNotFoundError(FileNotFoundError):
    """Raised when the backing store has no data for the requested resource."""


class DataSourceDecodeError(RuntimeError):
    """Raised when the backing store returns unreadable structured data."""


class ProviderConfigurationError(RuntimeError):
    """Raised when the configured provider cannot be constructed."""


class WidgetDataProvider(ABC):
    @abstractmethod
    async def get_match_state(self, match_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_competition_table(self, competition_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_competition_fixtures(
        self, competition_id: str, *, status: str | None, limit: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_xg_race(self, match_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_squads(self, match_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_team_stats(self, match_id: str, *, split: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_team_stats(self, team_id: str, *, split: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_h2h(self, match_id: str, *, limit: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_h2h_players(
        self,
        match_id: str,
        *,
        home_player_id: str | None,
        away_player_id: str | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_match_facts(
        self, match_id: str, *, category: str | None, limit: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError
