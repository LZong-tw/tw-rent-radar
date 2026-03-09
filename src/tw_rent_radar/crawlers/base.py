"""Abstract base class for all rental crawlers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCrawler(ABC):
    """Base class that all platform crawlers must inherit from."""

    source_name: str

    @abstractmethod
    async def crawl(self, **filters) -> list[dict]:
        """Crawl listings with optional filters. Returns list of listing dicts."""
        ...
