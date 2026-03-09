"""Tests for the Rakuya crawler."""
import json

import pytest

from tw_rent_radar.crawlers.rakuya import RakuyaCrawler


def test_rakuya_crawler_has_source_name():
    """RakuyaCrawler exposes the correct source_name."""
    crawler = RakuyaCrawler()
    assert crawler.source_name == "rakuya"


def test_rakuya_crawler_is_subclass_of_base():
    """RakuyaCrawler satisfies the BaseCrawler interface."""
    from tw_rent_radar.crawlers.base import BaseCrawler

    assert issubclass(RakuyaCrawler, BaseCrawler)


# ------------------------------------------------------------------
# parse_price
# ------------------------------------------------------------------


class TestParsePrice:
    """Unit tests for RakuyaCrawler.parse_price."""

    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_comma_separated(self):
        assert self.crawler.parse_price("12,000") == 12000

    def test_plain_number(self):
        assert self.crawler.parse_price("8000") == 8000

    def test_empty_string(self):
        assert self.crawler.parse_price("") is None

    def test_whitespace_only(self):
        assert self.crawler.parse_price("   ") is None

    def test_with_currency_symbol(self):
        assert self.crawler.parse_price("$15,500") == 15500

    def test_with_unit_suffix(self):
        assert self.crawler.parse_price("12,000元/月") == 12000

    def test_no_digits(self):
        assert self.crawler.parse_price("面議") is None


# ------------------------------------------------------------------
# parse_listing_element
# ------------------------------------------------------------------


class TestParseListingElement:
    """Unit tests for RakuyaCrawler.parse_listing_element."""

    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_basic_fields(self):
        data = {
            "id": "abc123",
            "title": "三民區兩房",
            "price": 12000,
            "city": "高雄市",
            "district": "三民區",
        }
        result = self.crawler.parse_listing_element(data)

        assert result["source"] == "rakuya"
        assert result["source_id"] == "abc123"
        assert result["title"] == "三民區兩房"
        assert result["price"] == 12000
        assert result["city"] == "高雄市"
        assert result["district"] == "三民區"

    def test_images_serialized_as_json(self):
        data = {
            "id": "x1",
            "images": ["https://img.example.com/a.jpg", "https://img.example.com/b.jpg"],
        }
        result = self.crawler.parse_listing_element(data)
        assert isinstance(result["images"], str)
        parsed = json.loads(result["images"])
        assert len(parsed) == 2

    def test_raw_data_contains_original(self):
        data = {"id": "r1", "title": "Test", "extra_field": "should be preserved"}
        result = self.crawler.parse_listing_element(data)
        raw = json.loads(result["raw_data"])
        assert raw["extra_field"] == "should be preserved"

    def test_missing_optional_fields_are_none(self):
        data = {"id": "m1"}
        result = self.crawler.parse_listing_element(data)
        assert result["source_id"] == "m1"
        assert result["title"] is None
        assert result["price"] is None
        assert result["address"] is None

    def test_numeric_id_converted_to_string(self):
        data = {"id": 99887}
        result = self.crawler.parse_listing_element(data)
        assert result["source_id"] == "99887"


# ------------------------------------------------------------------
# crawl (no network — just verifies the method is async-callable)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crawl_is_async():
    """crawl() is an async method (we cannot call it without Playwright browsers)."""
    import inspect

    crawler = RakuyaCrawler()
    assert inspect.iscoroutinefunction(crawler.crawl)
