"""Tests for the Rakuya crawler."""

import json

import pytest

from tw_rent_radar.crawlers.rakuya import CITY_CODES, RakuyaCrawler


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

    def test_with_yuan_element(self):
        assert self.crawler.parse_price("25,000元") == 25000


# ------------------------------------------------------------------
# parse_size
# ------------------------------------------------------------------


class TestParseSize:
    """Unit tests for RakuyaCrawler.parse_size."""

    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_with_ping(self):
        assert self.crawler.parse_size("33.8坪") == 33.8

    def test_integer(self):
        assert self.crawler.parse_size("20坪") == 20.0

    def test_empty(self):
        assert self.crawler.parse_size("") is None

    def test_none(self):
        assert self.crawler.parse_size(None) is None

    def test_no_unit(self):
        assert self.crawler.parse_size("not a size") is None

    def test_with_spaces(self):
        assert self.crawler.parse_size("  11.66 坪") == 11.66


# ------------------------------------------------------------------
# parse_listing_card
# ------------------------------------------------------------------


class TestParseListingCard:
    """Unit tests for RakuyaCrawler.parse_listing_card."""

    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_full_card(self):
        card_data = {
            "ehid": "abc123",
            "title": "五甲自強夜市電梯套房",
            "address": "永安街",
            "price_text": "25,000元",
            "type_layout": ["整層住家/電梯大廈", "2房1廳1衛"],
            "size_floor": ["33.8坪", "6/7樓"],
            "city": "高雄市",
            "url": "https://www.rakuya.com.tw/rent/rent_item?ehid=abc123",
        }
        result = self.crawler.parse_listing_card(card_data)
        assert result["source"] == "rakuya"
        assert result["source_id"] == "abc123"
        assert result["title"] == "五甲自強夜市電梯套房"
        assert result["price"] == 25000
        assert result["city"] == "高雄市"
        assert result["address"] == "永安街"
        assert result["rooms"] == "2房1廳1衛"
        assert result["type"] == "整層住家/電梯大廈"
        assert result["size"] == 33.8
        assert result["floor"] == "6/7樓"
        assert result["url"] == "https://www.rakuya.com.tw/rent/rent_item?ehid=abc123"

    def test_missing_optional(self):
        card_data = {
            "ehid": "x",
            "title": "test",
            "price_text": "",
            "type_layout": [],
            "size_floor": [],
            "city": "台北市",
        }
        result = self.crawler.parse_listing_card(card_data)
        assert result["source_id"] == "x"
        assert result["price"] is None
        assert result["rooms"] is None
        assert result["size"] is None
        assert result["floor"] is None
        assert result["type"] is None

    def test_raw_data_preserved(self):
        card_data = {
            "ehid": "r1",
            "title": "Test",
            "price_text": "5,000",
            "type_layout": [],
            "size_floor": [],
            "city": "台北市",
        }
        result = self.crawler.parse_listing_card(card_data)
        raw = json.loads(result["raw_data"])
        assert raw["ehid"] == "r1"
        assert raw["title"] == "Test"

    def test_partial_type_layout(self):
        card_data = {
            "ehid": "p1",
            "title": "test",
            "price_text": "10,000",
            "type_layout": ["獨立套房"],
            "size_floor": ["20坪"],
            "city": "台北市",
        }
        result = self.crawler.parse_listing_card(card_data)
        assert result["type"] == "獨立套房"
        assert result["rooms"] is None
        assert result["size"] == 20.0
        assert result["floor"] is None


# ------------------------------------------------------------------
# parse_detail_page
# ------------------------------------------------------------------


class TestParseDetailPage:
    """Unit tests for RakuyaCrawler.parse_detail_page."""

    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_extract_fields(self):
        html = """
        <h1 class="txt__address">高雄市苓雅區七賢一路</h1>
        <div class="block__title"><h2>優質精緻套房</h2></div>
        <span class="txt__price-total">12,000<em class="unit">元</em></span>
        <span class="list__label">格局</span><span class="list__content">1房1廳1衛</span>
        <span class="list__label">坪數</span><span class="list__content">11.66坪</span>
        <span class="list__label">樓層/樓高</span><span class="list__content">9/10樓</span>
        <span class="list__label">類型</span><span class="list__content">獨立套房/電梯大廈</span>
        <span class="name">陳先生</span>
        """
        result = self.crawler.parse_detail_page(html)
        assert result["address"] == "高雄市苓雅區七賢一路"
        assert result["city"] == "高雄市"
        assert result["district"] == "苓雅區"
        assert result["title"] == "優質精緻套房"
        assert result["price"] == 12000
        assert result["rooms"] == "1房1廳1衛"
        assert result["size"] == 11.66
        assert result["floor"] == "9/10樓"
        assert result["type"] == "獨立套房/電梯大廈"
        assert result["contact"] == "陳先生"

    def test_empty_html(self):
        result = self.crawler.parse_detail_page("")
        assert result == {}

    def test_partial_html(self):
        html = '<h1 class="txt__address">台北市大安區忠孝東路</h1>'
        result = self.crawler.parse_detail_page(html)
        assert result["address"] == "台北市大安區忠孝東路"
        assert result["city"] == "台北市"
        assert result["district"] == "大安區"
        assert "price" not in result
        assert "title" not in result

    def test_images_extraction(self):
        html = """
        <div class="houseImages-wrapper-item"><img src="https://img.example.com/a.jpg"></div>
        <div class="houseImages-wrapper-item"><img src="https://img.example.com/b.jpg"></div>
        """
        result = self.crawler.parse_detail_page(html)
        images = json.loads(result["images"])
        assert len(images) == 2
        assert "https://img.example.com/a.jpg" in images

    def test_amenities_extraction(self):
        html = """
        <span class="list__label">設備</span><span class="list__content">冷氣,洗衣機,冰箱</span>
        <span class="list__label">傢俱</span><span class="list__content">床,衣櫃</span>
        """
        result = self.crawler.parse_detail_page(html)
        amenities = json.loads(result["amenities"])
        assert "冷氣" in amenities
        assert "洗衣機" in amenities
        assert "床" in amenities
        assert len(amenities) == 5


# ------------------------------------------------------------------
# parse_detail_page — cooking & gas_type
# ------------------------------------------------------------------


class TestParseDetailCookingGas:
    def setup_method(self):
        self.crawler = RakuyaCrawler()

    def test_gas_in_amenities(self):
        html = """
        <span class="list__label">設備</span>
        <span class="list__content">冷氣, 洗衣機, 天然瓦斯, 冰箱</span>
        """
        result = self.crawler.parse_detail_page(html)
        assert result.get("gas_type") == "天然瓦斯"

    def test_bottled_gas(self):
        html = """
        <span class="list__label">設備</span>
        <span class="list__content">桶裝瓦斯, 冷氣</span>
        """
        result = self.crawler.parse_detail_page(html)
        assert result.get("gas_type") == "桶裝瓦斯"

    def test_cooking_in_rules(self):
        html = """
        <span class="list__label">規定</span>
        <span class="list__content">可開伙</span>
        """
        result = self.crawler.parse_detail_page(html)
        assert result.get("cooking") == "可開伙"

    def test_no_cooking_no_gas(self):
        html = "<div>No relevant info</div>"
        result = self.crawler.parse_detail_page(html)
        assert result.get("cooking") is None
        assert result.get("gas_type") is None


# ------------------------------------------------------------------
# CITY_CODES
# ------------------------------------------------------------------


class TestCityCode:
    """Unit tests for the CITY_CODES mapping."""

    def test_kaohsiung(self):
        assert CITY_CODES["高雄市"] == 17

    def test_taipei(self):
        assert CITY_CODES["台北市"] == 1

    def test_taichung(self):
        assert CITY_CODES["台中市"] == 10

    def test_all_cities_present(self):
        assert len(CITY_CODES) == 22


# ------------------------------------------------------------------
# crawl (no network -- just verifies the method is async-callable)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crawl_is_async():
    """crawl() is an async method (we cannot call it without Playwright browsers)."""
    import inspect

    crawler = RakuyaCrawler()
    assert inspect.iscoroutinefunction(crawler.crawl)
