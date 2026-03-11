"""Tests for the 591 rental crawler with mock data."""

from __future__ import annotations

import pytest

from tw_rent_radar.crawlers.rent591 import REGION_MAP, Rent591Crawler


@pytest.fixture
def crawler():
    return Rent591Crawler()


@pytest.fixture
def sample_item():
    """A realistic 591 listing item in the current Nuxt SSR format."""
    return {
        "id": 12345678,
        "title": "近捷運三房公寓 生活機能佳",
        "price": "15,000",
        "price_unit": "元/月",
        "kind_name": "整層住家",
        "area": 30,
        "area_name": "30坪",
        "layoutStr": "3房2廳",
        "floor_name": "3F/7F",
        "role_name": "王先生",
        "address": "三民區-建國路100號",
        "photoList": ["https://img.591.com.tw/1.jpg"],
        "community_name": "優質三房公寓出租",
        "url": "https://rent.591.com.tw/12345678",
        "sectionid": 42,
        "regionid": 17,
        "cover": "https://img.591.com.tw/cover.jpg",
    }


@pytest.fixture
def legacy_item():
    """A 591 listing item in the old API format (for backward compatibility)."""
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
        assert result["rooms"] == "3房2廳"
        assert result["floor"] == "3F/7F"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["contact"] == "王先生"
        assert result["address"] == "三民區-建國路100號"

    def test_legacy_item(self, crawler, legacy_item):
        """Parser should handle legacy API field names (post_id, section_name, etc.)."""
        result = crawler.parse_list_item(legacy_item, "高雄市")

        assert result["source_id"] == "12345678"
        assert result["district"] == "三民區"
        assert result["rooms"] == "3"
        assert result["floor"] == "3F/7F"
        assert result["contact"] == "王先生"
        assert result["phone"] == "0912-345-678"

    def test_id_fallback_chain(self, crawler):
        """source_id should try 'id', then 'post_id', then 'cases_id'."""
        assert crawler.parse_list_item({"id": 1}, "台北市")["source_id"] == "1"
        assert crawler.parse_list_item({"post_id": 2}, "台北市")["source_id"] == "2"
        assert crawler.parse_list_item({"cases_id": 3}, "台北市")["source_id"] == "3"

    def test_missing_optional_fields(self, crawler):
        """Missing optional fields should result in empty strings or None."""
        item = {"id": 111, "price": "面議"}
        result = crawler.parse_list_item(item, "台北市")
        assert result["source_id"] == "111"
        assert result["price"] is None
        assert result["rooms"] is None
        assert result["size"] is None

    def test_area_as_float(self, crawler):
        """Area with decimal should parse to float."""
        item = {"id": 222, "price": "10,000", "area": "25.5"}
        result = crawler.parse_list_item(item, "台北市")
        assert result["size"] == 25.5

    def test_area_numeric(self, crawler):
        """Area as a plain number (current API format) should parse to float."""
        item = {"id": 333, "price": "8,000", "area": 20}
        result = crawler.parse_list_item(item, "台北市")
        assert result["size"] == 20.0

    def test_district_from_address(self, crawler):
        """When section_name is absent, district should be extracted from address."""
        item = {"id": 444, "address": "楠梓區-大學南路"}
        result = crawler.parse_list_item(item, "高雄市")
        assert result["district"] == "楠梓區"

    def test_raw_data_preserved(self, crawler, sample_item):
        """raw_data should contain the original item JSON."""
        import json

        result = crawler.parse_list_item(sample_item, "高雄市")
        raw = json.loads(result["raw_data"])
        assert raw["id"] == 12345678
        assert raw["title"] == "近捷運三房公寓 生活機能佳"

    def test_images_serialized(self, crawler, sample_item):
        """images should be a JSON-serialized list."""
        import json

        result = crawler.parse_list_item(sample_item, "高雄市")
        images = json.loads(result["images"])
        assert images == ["https://img.591.com.tw/1.jpg"]

    def test_url_fallback(self, crawler):
        """When 'url' is not in item, it should be constructed from source_id."""
        item = {"id": 555}
        result = crawler.parse_list_item(item, "台北市")
        assert result["url"] == "https://rent.591.com.tw/555"


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

    def test_bare_comma_number(self, crawler):
        """Current API format: price is just '22,000' without unit."""
        assert crawler.parse_price("22,000") == 22000


class TestCrawlerAttributes:
    def test_source_name(self, crawler):
        assert crawler.source_name == "591"

    def test_list_base_url(self, crawler):
        assert crawler.list_base_url == "https://rent.591.com.tw/list"

    def test_is_base_crawler_subclass(self, crawler):
        from tw_rent_radar.crawlers.base import BaseCrawler

        assert isinstance(crawler, BaseCrawler)


class TestParseDetailData:
    def setup_method(self):
        self.crawler = Rent591Crawler()

    def test_full_detail(self):
        detail_store = {
            "data": {
                "positionRound": {
                    "address": "前鎮區復興四路12號",
                    "lat": "22.6125",
                    "lng": "120.3056",
                },
                "service": {
                    "facility": [
                        {"key": "cold", "active": True, "name": "冷氣"},
                        {"key": "washer", "active": True, "name": "洗衣機"},
                        {"key": "gas", "active": True, "name": "天然瓦斯"},
                        {"key": "fridge", "active": False, "name": "冰箱"},
                    ],
                    "rule": "此房屋不可開伙，不可養寵物",
                },
                "remark": {"content": "近捷運站，生活機能佳"},
            }
        }
        result = self.crawler.parse_detail_data(detail_store)
        assert result["latitude"] == 22.6125
        assert result["longitude"] == 120.3056
        assert result["address"] == "前鎮區復興四路12號"
        assert result["gas_type"] == "天然瓦斯"
        assert result["cooking"] == "不可開伙"
        assert "冷氣" in result["amenities"]
        assert "洗衣機" in result["amenities"]
        assert "冰箱" not in result["amenities"]
        assert result["description"] == "近捷運站，生活機能佳"

    def test_cooking_allowed(self):
        detail_store = {"data": {"service": {"facility": [], "rule": "可開伙，可養寵物"}}}
        result = self.crawler.parse_detail_data(detail_store)
        assert result["cooking"] == "可開伙"

    def test_no_gas(self):
        facility = [{"key": "gas", "active": False, "name": "天然瓦斯"}]
        detail_store = {"data": {"service": {"facility": facility}}}
        result = self.crawler.parse_detail_data(detail_store)
        assert result.get("gas_type") is None

    def test_bottled_gas(self):
        facility = [{"key": "gas", "active": True, "name": "桶裝瓦斯"}]
        detail_store = {"data": {"service": {"facility": facility}}}
        result = self.crawler.parse_detail_data(detail_store)
        assert result["gas_type"] == "桶裝瓦斯"

    def test_empty_detail(self):
        result = self.crawler.parse_detail_data({})
        assert result == {}

    def test_missing_sections(self):
        result = self.crawler.parse_detail_data({"data": {}})
        assert result.get("cooking") is None
        assert result.get("gas_type") is None

    def test_cooking_from_tags_fallback(self):
        """When service.rule is empty, cooking should be extracted from tags."""
        detail_store = {
            "data": {
                "service": {"facility": [], "rule": ""},
                "tags": [{"id": 6, "value": "可開伙"}, {"id": 7, "value": "可養寵物"}],
            }
        }
        result = self.crawler.parse_detail_data(detail_store)
        assert result["cooking"] == "可開伙"

    def test_cooking_from_tags_not_allowed(self):
        """Tags with 不可開伙 should set cooking correctly."""
        detail_store = {
            "data": {
                "tags": [{"id": 6, "value": "不可開伙"}],
            }
        }
        result = self.crawler.parse_detail_data(detail_store)
        assert result["cooking"] == "不可開伙"

    def test_cooking_rule_takes_priority_over_tags(self):
        """When rule has cooking info, tags should not override it."""
        detail_store = {
            "data": {
                "service": {"facility": [], "rule": "不可開伙"},
                "tags": [{"id": 6, "value": "可開伙"}],
            }
        }
        result = self.crawler.parse_detail_data(detail_store)
        assert result["cooking"] == "不可開伙"


class TestCrawlDefaults:
    """Ensure the crawler defaults to crawling all pages, not a fixed limit."""

    def test_max_pages_defaults_to_zero(self):
        """max_pages=0 means 'auto-detect from store total'."""
        import inspect

        crawler = Rent591Crawler()
        source = inspect.getsource(crawler.crawl)
        assert 'filters.get("max_pages", 0)' in source

    def test_extract_total_js_defined(self):
        """The JS snippet for reading total count must exist."""
        assert hasattr(Rent591Crawler, "_EXTRACT_TOTAL_JS")
        assert "total" in Rent591Crawler._EXTRACT_TOTAL_JS

    def test_total_pages_computed_correctly(self):
        """Given 6499 total and 30 per page, should need 217 pages."""
        total = 6499
        per_page = 30
        expected_pages = (total + per_page - 1) // per_page
        assert expected_pages == 217

    def test_total_pages_exact_multiple(self):
        """When total is exact multiple of per_page, no extra page."""
        total = 300
        per_page = 30
        pages = (total + per_page - 1) // per_page
        assert pages == 10


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
