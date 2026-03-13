"""Tests for the 591 rental crawler with mock data."""

from __future__ import annotations

import asyncio

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


class TestAntiBotDetection:
    """Ensure anti-bot detection and bypass infrastructure exists."""

    def test_diagnose_page_js_defined(self):
        assert hasattr(Rent591Crawler, "_DIAGNOSE_PAGE_JS")
        js = Rent591Crawler._DIAGNOSE_PAGE_JS
        assert "cloudflare" in js
        assert "no_nuxt" in js
        assert "'ok'" in js

    def test_diagnose_page_js_checks_cloudflare(self):
        """JS should detect Cloudflare challenge indicators."""
        js = Rent591Crawler._DIAGNOSE_PAGE_JS
        assert "challenge-form" in js
        assert "cf-wrapper" in js
        assert "Just a moment" in js

    def test_fetch_page_items_method_exists(self):
        crawler = Rent591Crawler()
        assert hasattr(crawler, "_fetch_page_items")
        import inspect

        sig = inspect.signature(crawler._fetch_page_items)
        assert "max_retries" in sig.parameters

    def test_crawl_has_forward_and_reverse_pass(self):
        """crawl() should contain both forward and reverse pass logic."""
        import inspect

        source = inspect.getsource(Rent591Crawler.crawl)
        assert "Forward pass" in source or "forward pass" in source
        assert "reverse" in source.lower()
        assert "Completeness" in source or "completeness" in source

    def test_crawl_uses_seen_ids_for_dedup(self):
        """crawl() should deduplicate listings by source_id."""
        import inspect

        source = inspect.getsource(Rent591Crawler.crawl)
        assert "seen_ids" in source

    def test_crawl_has_proactive_delay(self):
        """crawl() should add delay between pages to avoid triggering anti-bot."""
        import inspect

        source = inspect.getsource(Rent591Crawler.crawl)
        assert "asyncio.sleep" in source


# ------------------------------------------------------------------
# Mock infrastructure for Playwright-dependent tests
# ------------------------------------------------------------------


def _make_items(start_id: int, count: int) -> list[dict]:
    """Generate mock 591 listing items with sequential IDs."""
    return [
        {"id": start_id + i, "title": f"Listing {start_id + i}", "price": "10000"}
        for i in range(count)
    ]


class _MockPage:
    """Minimal mock for Playwright page to test _fetch_page_items."""

    def __init__(self, evaluate_results: list):
        self._eval_results = list(evaluate_results)
        self._eval_index = 0
        self.goto_count = 0
        self.goto_fail_until = 0  # fail goto for the first N calls

    async def goto(self, url, **kwargs):
        self.goto_count += 1
        if self.goto_count <= self.goto_fail_until:
            raise TimeoutError("simulated timeout")

    async def evaluate(self, js):
        result = self._eval_results[self._eval_index]
        self._eval_index = min(self._eval_index + 1, len(self._eval_results) - 1)
        return result

    async def wait_for_load_state(self, state, **kwargs):
        pass


class _CrawlMockPage:
    """Mock page for full crawl() tests with per-page data and anti-bot simulation."""

    def __init__(
        self,
        pages_data: dict[int, list[dict]],
        total: int,
        *,
        anti_bot_pages: set[int] | None = None,
        reverse_extra: dict[int, list[dict]] | None = None,
    ):
        self._pages_data = pages_data
        self._total = total
        self._anti_bot_pages = anti_bot_pages or set()
        self._reverse_extra = reverse_extra or {}
        self._current_page = 1
        self.visit_count: dict[int, int] = {}

    async def goto(self, url, **kwargs):
        if "page=" in url:
            self._current_page = int(url.split("page=")[1].split("&")[0])
        else:
            self._current_page = 1
        self.visit_count[self._current_page] = self.visit_count.get(self._current_page, 0) + 1

    async def evaluate(self, js):
        # _DIAGNOSE_PAGE_JS
        if "challenge-form" in js:
            if self._current_page in self._anti_bot_pages:
                return "no_nuxt"
            return "ok"
        # _EXTRACT_LISTINGS_JS
        if "dataList" in js:
            items = list(self._pages_data.get(self._current_page, []))
            visits = self.visit_count.get(self._current_page, 0)
            if visits > 1:
                items.extend(self._reverse_extra.get(self._current_page, []))
            return items
        # _EXTRACT_TOTAL_JS
        if ".total" in js:
            return self._total
        # _EXTRACT_DETAIL_JS
        if "rent-detail-info" in js:
            return None
        return None

    async def wait_for_load_state(self, state, **kwargs):
        pass


class _MockBrowserContext:
    def __init__(self, page):
        self._page = page

    async def add_cookies(self, cookies):
        pass

    async def new_page(self):
        return self._page


class _MockBrowser:
    def __init__(self, page):
        self._page = page

    async def new_context(self):
        return _MockBrowserContext(self._page)

    async def close(self):
        pass


class _MockChromium:
    def __init__(self, page):
        self._page = page

    async def launch(self, **kwargs):
        return _MockBrowser(self._page)


class _MockPlaywrightCM:
    """Mock async context manager replacing async_playwright()."""

    def __init__(self, page):
        self.chromium = _MockChromium(page)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ------------------------------------------------------------------
# _fetch_page_items behavioral tests
# ------------------------------------------------------------------


class TestFetchPageItemsBehavior:
    """Behavioral tests for _fetch_page_items with mock page."""

    @pytest.fixture(autouse=True)
    def _patch_sleep(self, monkeypatch):
        async def noop(seconds):
            pass

        monkeypatch.setattr(asyncio, "sleep", noop)

    @pytest.fixture
    def crawler(self):
        return Rent591Crawler()

    @pytest.mark.asyncio
    async def test_returns_items_on_ok_state(self, crawler):
        items = [{"id": 1, "title": "test"}]
        mock = _MockPage(evaluate_results=["ok", items])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=0)
        assert result == items

    @pytest.mark.asyncio
    async def test_returns_none_on_persistent_anti_bot(self, crawler):
        """All retries return anti-bot state → should return None."""
        mock = _MockPage(evaluate_results=["no_nuxt"])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_retries_on_anti_bot_then_succeeds(self, crawler):
        """First attempt blocked, second attempt succeeds."""
        items = [{"id": 2, "title": "found"}]
        mock = _MockPage(evaluate_results=["no_store", "ok", items])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result == items

    @pytest.mark.asyncio
    async def test_retries_on_goto_failure(self, crawler):
        """Page load fails on first try, succeeds on second."""
        items = [{"id": 3}]
        mock = _MockPage(evaluate_results=["ok", items])
        mock.goto_fail_until = 1
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result == items

    @pytest.mark.asyncio
    async def test_returns_none_when_all_gotos_fail(self, crawler):
        mock = _MockPage(evaluate_results=["ok", []])
        mock.goto_fail_until = 999
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_cloudflare_waits_and_rechecks(self, crawler):
        """Cloudflare detected → should wait and re-evaluate state."""
        items = [{"id": 4}]
        mock = _MockPage(evaluate_results=["cloudflare", "ok", items])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=0)
        assert result == items

    @pytest.mark.asyncio
    async def test_cloudflare_not_resolved_retries(self, crawler):
        """Cloudflare detected and not resolved → should retry on next attempt."""
        items = [{"id": 5}]
        mock = _MockPage(evaluate_results=["cloudflare", "cloudflare", "ok", items])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result == items

    @pytest.mark.asyncio
    async def test_null_items_despite_ok_state_retries(self, crawler):
        """State is OK but items extraction returns None → should retry."""
        items = [{"id": 6}]
        mock = _MockPage(evaluate_results=["ok", None, "ok", items])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=1)
        assert result == items

    @pytest.mark.asyncio
    async def test_returns_empty_list_as_valid(self, crawler):
        """Empty items list [] is a valid return (last page)."""
        mock = _MockPage(evaluate_results=["ok", []])
        result = await crawler._fetch_page_items(mock, "http://example.com", max_retries=0)
        assert result == []


# ------------------------------------------------------------------
# Full crawl() behavioral tests with mocked Playwright
# ------------------------------------------------------------------


class TestCrawlBehavior:
    """End-to-end behavioral tests for the crawl() method."""

    @pytest.fixture(autouse=True)
    def _patch_sleep(self, monkeypatch):
        async def noop(seconds):
            pass

        monkeypatch.setattr(asyncio, "sleep", noop)

    def _setup(self, monkeypatch, page):
        monkeypatch.setattr(
            "tw_rent_radar.crawlers.rent591.async_playwright",
            lambda: _MockPlaywrightCM(page),
        )

    @pytest.mark.asyncio
    async def test_collects_all_pages(self, monkeypatch):
        """Normal crawl: 3 pages × 30 items, no reverse pass needed."""
        pages = {1: _make_items(1, 30), 2: _make_items(31, 30), 3: _make_items(61, 30)}
        mock = _CrawlMockPage(pages, total=90)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        assert len(results) == 90
        # No reverse pass — each page visited exactly once
        assert mock.visit_count == {1: 1, 2: 1, 3: 1}

    @pytest.mark.asyncio
    async def test_dedup_by_source_id(self, monkeypatch):
        """Duplicate source_ids across pages are deduplicated."""
        pages = {1: _make_items(1, 30), 2: _make_items(25, 30)}  # ids 25-30 overlap
        mock = _CrawlMockPage(pages, total=60)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        ids = [r["source_id"] for r in results]
        assert len(ids) == len(set(ids))  # all unique
        assert len(results) == 54  # 30 + 30 - 6 duplicates

    @pytest.mark.asyncio
    async def test_anti_bot_pages_skipped(self, monkeypatch):
        """Pages with anti-bot are skipped, other pages still collected."""
        pages = {1: _make_items(1, 30), 2: _make_items(31, 30), 3: _make_items(61, 30)}
        mock = _CrawlMockPage(pages, total=90, anti_bot_pages={2})
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        ids = {r["source_id"] for r in results}
        # Page 2 blocked → forward gets 60; reverse also blocked on page 2
        assert len(results) == 60
        # Items from page 2 (ids 31-60) should be absent
        assert not ids.intersection(str(i) for i in range(31, 61))

    @pytest.mark.asyncio
    async def test_empty_items_mid_pagination_continues(self, monkeypatch):
        """Empty items mid-pagination detected as suspicious, continues to next page."""
        pages = {1: _make_items(1, 30), 2: [], 3: _make_items(61, 30)}
        mock = _CrawlMockPage(pages, total=90)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        assert len(results) == 60
        # Page 3 was reached despite page 2 being empty
        assert any(r["source_id"] == "61" for r in results)

    @pytest.mark.asyncio
    async def test_reverse_pass_finds_new_items(self, monkeypatch):
        """Reverse pass collects items missed by forward pass (pagination drift)."""
        pages = {1: _make_items(1, 30), 2: _make_items(31, 25), 3: _make_items(61, 30)}
        # 5 items "drifted" — they appear on page 2 only during reverse pass
        reverse_extra = {2: _make_items(56, 5)}
        mock = _CrawlMockPage(pages, total=90, reverse_extra=reverse_extra)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        # Forward: 30 + 25 + 30 = 85.  Gap = 5.6% → reverse triggered.
        # Reverse page 2: 25 dupes + 5 new → total 90.  Gap 0% → stop.
        assert len(results) == 90

    @pytest.mark.asyncio
    async def test_reverse_pass_stops_early_at_one_percent(self, monkeypatch):
        """Reverse pass stops as soon as gap drops to ≤ 1%."""
        pages = {
            1: _make_items(1, 30),
            2: _make_items(31, 25),
            3: _make_items(61, 25),
            4: _make_items(91, 10),
        }
        # Forward gets 90 out of 100 (10% gap). Reverse pass:
        # Page 4: 10 dupes. Page 3: 25 dupes + 5 new → 95/100 = 5% → continue.
        # Page 2: 25 dupes + 5 new → 100/100 = 0% → stop. Page 1 not visited.
        reverse_extra = {3: _make_items(86, 5), 2: _make_items(56, 5)}
        mock = _CrawlMockPage(pages, total=100, reverse_extra=reverse_extra)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        assert len(results) == 100
        # Page 1 should only be visited once (forward), not in reverse
        assert mock.visit_count[1] == 1

    @pytest.mark.asyncio
    async def test_no_reverse_pass_when_complete(self, monkeypatch):
        """When forward pass gets everything, no reverse pass runs."""
        pages = {1: _make_items(1, 30), 2: _make_items(31, 30)}
        mock = _CrawlMockPage(pages, total=60)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市")
        assert len(results) == 60
        assert sum(mock.visit_count.values()) == 2  # only forward pass

    @pytest.mark.asyncio
    async def test_max_pages_limits_crawl(self, monkeypatch):
        """max_pages parameter should cap the number of pages crawled."""
        pages = {1: _make_items(1, 30), 2: _make_items(31, 30), 3: _make_items(61, 30)}
        mock = _CrawlMockPage(pages, total=90)
        self._setup(monkeypatch, mock)

        results = await Rent591Crawler().crawl(city="高雄市", max_pages=2)
        assert len(results) == 60
        assert 3 not in mock.visit_count


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
