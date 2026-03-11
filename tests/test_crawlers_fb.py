"""Tests for Facebook crawlers (group + marketplace) and auth utilities."""

from __future__ import annotations

import json

import pytest

from tw_rent_radar.crawlers.fb_group import FbGroupCrawler
from tw_rent_radar.crawlers.fb_market import FbMarketCrawler

# ------------------------------------------------------------------
# Source name sanity checks
# ------------------------------------------------------------------


def test_fb_group_has_source_name():
    crawler = FbGroupCrawler()
    assert crawler.source_name == "fb_group"


def test_fb_market_has_source_name():
    crawler = FbMarketCrawler()
    assert crawler.source_name == "fb_market"


# ------------------------------------------------------------------
# Auth module
# ------------------------------------------------------------------


def test_fb_session_dir_defined():
    from tw_rent_radar.crawlers.fb_auth import FB_SESSION_DIR

    assert FB_SESSION_DIR is not None


# ------------------------------------------------------------------
# Price parsing (FbGroupCrawler)
# ------------------------------------------------------------------


def test_parse_price_from_text():
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("月租 12,000 元") == 12000
    assert crawler.parse_price_from_text("$8000/月") == 8000
    assert crawler.parse_price_from_text("租金：15,000元/月") == 15000
    assert crawler.parse_price_from_text("好房出租") is None


def test_parse_price_comma_separated():
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("每月 25,000 元整") == 25000


def test_parse_price_no_comma():
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("月租：8500") == 8500


def test_parse_price_dollar_sign_with_comma():
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("只要$12,000就能入住") == 12000


# ------------------------------------------------------------------
# Price parsing (FbMarketCrawler)
# ------------------------------------------------------------------


def test_market_parse_price_ntd():
    assert FbMarketCrawler.parse_price("NT$12,000") == 12000


def test_market_parse_price_ntd_no_comma():
    assert FbMarketCrawler.parse_price("NT$8000") == 8000


def test_market_parse_price_dollar():
    assert FbMarketCrawler.parse_price("$25,000") == 25000


def test_market_parse_price_plain_number():
    assert FbMarketCrawler.parse_price("15000") == 15000


def test_market_parse_price_empty():
    assert FbMarketCrawler.parse_price("") is None
    assert FbMarketCrawler.parse_price("免費") is None


# ------------------------------------------------------------------
# Card parsing (FbMarketCrawler)
# ------------------------------------------------------------------


def test_market_parse_card_basic():
    crawler = FbMarketCrawler()
    card = {
        "itemId": "123456789",
        "href": "https://www.facebook.com/marketplace/item/123456789/",
        "lines": ["NT$12,000", "精美套房出租", "高雄市"],
        "imgSrc": "https://example.com/img.jpg",
    }
    result = crawler.parse_card(card, "高雄市")
    assert result is not None
    assert result["source"] == "fb_market"
    assert result["source_id"] == "123456789"
    assert result["title"] == "精美套房出租"
    assert result["price"] == 12000
    assert result["city"] == "高雄市"
    assert result["address"] == "高雄市"
    assert result["url"] == card["href"]
    assert json.loads(result["images"]) == ["https://example.com/img.jpg"]


def test_market_parse_card_detects_city_from_location():
    crawler = FbMarketCrawler()
    card = {
        "itemId": "999",
        "href": "https://www.facebook.com/marketplace/item/999/",
        "lines": ["NT$8,000", "台北好房", "台北市大安區"],
        "imgSrc": None,
    }
    result = crawler.parse_card(card, "高雄市")
    assert result["city"] == "台北市"
    assert result["images"] is None


def test_market_parse_card_no_item_id():
    crawler = FbMarketCrawler()
    card = {"itemId": None, "lines": ["NT$5,000", "test"], "href": None, "imgSrc": None}
    assert crawler.parse_card(card, "高雄市") is None


def test_market_parse_card_minimal_lines():
    crawler = FbMarketCrawler()
    card = {
        "itemId": "111",
        "href": "https://www.facebook.com/marketplace/item/111/",
        "lines": ["NT$6,000"],
        "imgSrc": None,
    }
    result = crawler.parse_card(card, "台中市")
    assert result["price"] == 6000
    assert result["title"] is None
    assert result["address"] is None
    assert result["city"] == "台中市"


# ------------------------------------------------------------------
# crawl() — group requires group param
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fb_group_crawl_no_group_returns_empty():
    crawler = FbGroupCrawler()
    result = await crawler.crawl()
    assert result == []
