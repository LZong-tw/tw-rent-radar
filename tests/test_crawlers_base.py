"""Tests for the crawler base class."""

import pytest

from tw_rent_radar.crawlers.base import BaseCrawler, enrich_listing, infer_cooking, infer_gas


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


# ------------------------------------------------------------------
# Text inference
# ------------------------------------------------------------------


class TestInferCooking:
    def test_yes(self):
        assert infer_cooking("套房可開伙近捷運") == "可開伙"

    def test_yes_kitchen(self):
        assert infer_cooking("有廚房可料理") == "可開伙"

    def test_no(self):
        assert infer_cooking("不可開伙，禁養寵物") == "不可開伙"

    def test_no_variant(self):
        assert infer_cooking("禁止開伙") == "不可開伙"

    def test_none(self):
        assert infer_cooking("近捷運交通方便") is None

    def test_empty(self):
        assert infer_cooking("") is None

    def test_negative_priority(self):
        assert infer_cooking("不可開伙但有廚房") == "不可開伙"


class TestInferGas:
    def test_natural(self):
        assert infer_gas("天然瓦斯熱水器") == "天然瓦斯"

    def test_bottled(self):
        assert infer_gas("使用桶裝瓦斯") == "桶裝瓦斯"

    def test_none(self):
        assert infer_gas("電熱水器") is None


class TestEnrichListing:
    def test_fills_missing(self):
        listing = {"title": "套房可開伙天然瓦斯", "description": None}
        enrich_listing(listing)
        assert listing["cooking"] == "可開伙"
        assert listing["gas_type"] == "天然瓦斯"

    def test_no_overwrite(self):
        listing = {"title": "可開伙", "cooking": "不可開伙", "gas_type": None}
        enrich_listing(listing)
        assert listing["cooking"] == "不可開伙"  # Not overwritten

    def test_from_description(self):
        listing = {"title": "好房出租", "description": "禁止開伙，桶裝瓦斯"}
        enrich_listing(listing)
        assert listing["cooking"] == "不可開伙"
        assert listing["gas_type"] == "桶裝瓦斯"
