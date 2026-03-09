"""Tests for the 591 rental crawler with mock data."""

from __future__ import annotations

import pytest

from tw_rent_radar.crawlers.rent591 import REGION_MAP, Rent591Crawler


@pytest.fixture
def crawler():
    return Rent591Crawler()


@pytest.fixture
def sample_item():
    """A realistic 591 API listing item."""
    return {
        "post_id": 12345678,
        "title": "近捷運三房公寓 生活機能佳",
        "price": "15,000 元/月",
        "section_name": "三民區",
        "kind_name": "整層住家",
        "area": "30",
        "room": "3",
        "floor_str": "3F/7F",
        "contact": "王先生",
        "phone": "0912-345-678",
        "address": "三民區建國路100號",
        "photo_list": ["https://img.591.com.tw/1.jpg"],
        "cases_name": "優質三房公寓出租",
        "location": "",
    }


class TestParseListItem:
    def test_basic_item(self, crawler, sample_item):
        result = crawler.parse_list_item(sample_item, "高雄市")

        assert result["source"] == "591"
        assert result["source_id"] == "12345678"
        assert result["title"] == "近捷運三房公寓 生活機能佳"
        assert result["price"] == 15000
        assert result["city"] == "高雄市"
        assert result["district"] == "三民區"
        assert result["type"] == "整層住家"
        assert result["size"] == 30.0
        assert result["rooms"] == "3"
        assert result["floor"] == "3F/7F"
        assert result["url"] == "https://rent.591.com.tw/rent-detail-12345678.html"
        assert result["contact"] == "王先生"
        assert result["phone"] == "0912-345-678"
        assert result["address"] == "三民區建國路100號"

    def test_cases_id_fallback(self, crawler):
        """When post_id is absent, cases_id should be used as source_id."""
        item = {"cases_id": 99999, "price": "8000", "area": "20"}
        result = crawler.parse_list_item(item, "台北市")
        assert result["source_id"] == "99999"

    def test_missing_optional_fields(self, crawler):
        """Missing optional fields should result in empty strings or None."""
        item = {"post_id": 111, "price": "面議"}
        result = crawler.parse_list_item(item, "台北市")
        assert result["source_id"] == "111"
        assert result["price"] is None
        assert result["rooms"] is None
        assert result["size"] is None

    def test_area_as_float(self, crawler):
        """Area with decimal should parse to float."""
        item = {"post_id": 222, "price": "10,000 元/月", "area": "25.5"}
        result = crawler.parse_list_item(item, "台北市")
        assert result["size"] == 25.5

    def test_raw_data_preserved(self, crawler, sample_item):
        """raw_data should contain the original item JSON."""
        import json

        result = crawler.parse_list_item(sample_item, "高雄市")
        raw = json.loads(result["raw_data"])
        assert raw["post_id"] == 12345678
        assert raw["title"] == "近捷運三房公寓 生活機能佳"

    def test_images_serialized(self, crawler, sample_item):
        """images should be a JSON-serialized list."""
        import json

        result = crawler.parse_list_item(sample_item, "高雄市")
        images = json.loads(result["images"])
        assert images == ["https://img.591.com.tw/1.jpg"]


class TestParsePrice:
    def test_standard_format(self, crawler):
        assert crawler.parse_price("15,000 元/月") == 15000

    def test_plain_number(self, crawler):
        assert crawler.parse_price("8000") == 8000

    def test_with_management_fee_prefix(self, crawler):
        assert crawler.parse_price("含管理費 12,500 元/月") == 12500

    def test_negotiable(self, crawler):
        assert crawler.parse_price("面議") is None

    def test_empty_string(self, crawler):
        assert crawler.parse_price("") is None

    def test_none_input(self, crawler):
        assert crawler.parse_price(None) is None

    def test_large_price(self, crawler):
        assert crawler.parse_price("120,000 元/月") == 120000

    def test_no_comma(self, crawler):
        assert crawler.parse_price("5000 元/月") == 5000


class TestCrawlerAttributes:
    def test_source_name(self, crawler):
        assert crawler.source_name == "591"

    def test_list_url(self, crawler):
        assert crawler.list_url == "https://rent.591.com.tw/home/search/rsList"

    def test_is_base_crawler_subclass(self, crawler):
        from tw_rent_radar.crawlers.base import BaseCrawler

        assert isinstance(crawler, BaseCrawler)


class TestRegionMap:
    def test_taipei(self):
        assert REGION_MAP["台北市"] == 1

    def test_kaohsiung(self):
        assert REGION_MAP["高雄市"] == 17

    def test_all_regions_have_int_values(self):
        for city, region_id in REGION_MAP.items():
            assert isinstance(region_id, int), f"{city} has non-int region ID"
            assert region_id > 0, f"{city} has non-positive region ID"

    def test_region_count(self):
        assert len(REGION_MAP) == 22
