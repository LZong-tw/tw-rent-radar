"""Tests for the crawler base class."""

import pytest

from tw_rent_radar.crawlers.base import BaseCrawler


class FakeCrawler(BaseCrawler):
    source_name = "fake"

    async def crawl(self, **filters) -> list[dict]:
        return [{"source": "fake", "source_id": "1", "title": "Test"}]


@pytest.mark.asyncio
async def test_concrete_subclass_returns_listings():
    """A concrete subclass can be instantiated and returns listings."""
    crawler = FakeCrawler()
    assert crawler.source_name == "fake"
    results = await crawler.crawl()
    assert len(results) == 1
    assert results[0]["source"] == "fake"


def test_base_crawler_cannot_be_instantiated():
    """BaseCrawler itself cannot be instantiated."""
    with pytest.raises(TypeError):
        BaseCrawler()
