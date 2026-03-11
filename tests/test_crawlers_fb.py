"""Tests for Facebook crawlers (group + marketplace) and auth utilities."""

from __future__ import annotations

import json

import pytest

from tw_rent_radar.crawlers.fb_group import GROUP_SLUGS, FbGroupCrawler
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


def test_parse_price_filters_unreasonable():
    """Prices outside 1000-100000 range should be rejected."""
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("只要500元") is None
    assert crawler.parse_price_from_text("售價3,500,000元") is None


def test_parse_price_rent_label():
    """租金 label with various spacing and punctuation."""
    crawler = FbGroupCrawler()
    assert crawler.parse_price_from_text("【租金】：9500") == 9500
    assert crawler.parse_price_from_text("租  金：12,000") == 12000
    assert crawler.parse_price_from_text("租金:8000元/月") == 8000


# ------------------------------------------------------------------
# Post parsing (FbGroupCrawler)
# ------------------------------------------------------------------


def test_parse_post_basic():
    crawler = FbGroupCrawler()
    post = {
        "text": "三民區套房出租\n近火車站\n月租 12,000 元\n含水電",
        "permalink": "https://www.facebook.com/groups/lvmh3/posts/123",
        "imgSrcs": ["https://example.com/img.jpg"],
        "poster": "王先生",
    }
    result = crawler.parse_post(post, "高雄市")
    assert result is not None
    assert result["source"] == "fb_group"
    assert result["price"] == 12000
    assert result["city"] == "高雄市"
    assert result["title"] == "三民區套房出租"
    assert result["contact"] == "王先生"
    assert result["url"] == post["permalink"]
    assert json.loads(result["images"]) == ["https://example.com/img.jpg"]
    assert result["description"].startswith("三民區套房出租")
    assert result["source_id"]  # non-empty hash


def test_parse_post_no_price_returns_none():
    crawler = FbGroupCrawler()
    post = {"text": "找室友一起合租，有興趣私訊", "permalink": None, "imgSrcs": [], "poster": None}
    assert crawler.parse_post(post, "高雄市") is None


def test_parse_post_empty_text_returns_none():
    crawler = FbGroupCrawler()
    assert crawler.parse_post({"text": ""}, "高雄市") is None
    assert crawler.parse_post({"text": None}, "高雄市") is None


def test_parse_post_skips_looking_to_rent():
    """Posts starting with 求租/徵室友 should be filtered out."""
    crawler = FbGroupCrawler()
    post = {
        "text": "#求租\n【租金】：5000～8000\n三民區",
        "permalink": None,
        "imgSrcs": [],
        "poster": None,
    }
    assert crawler.parse_post(post, "高雄市") is None

    post2 = {"text": "徵室友 月租 6000", "permalink": None, "imgSrcs": [], "poster": None}
    assert crawler.parse_post(post2, "高雄市") is None


def test_parse_post_fallback_url():
    """When no permalink, group_url is used as fallback."""
    crawler = FbGroupCrawler()
    post = {"text": "套房出租 8,000元/月", "permalink": None, "imgSrcs": [], "poster": None}
    result = crawler.parse_post(post, "高雄市", group_url="https://www.facebook.com/groups/lvmh3")
    assert result["url"] == "https://www.facebook.com/groups/lvmh3"


def test_generate_source_id_stable():
    """Same text should produce the same source ID."""
    text = "三民區套房出租月租12000"
    id1 = FbGroupCrawler._generate_source_id(text)
    id2 = FbGroupCrawler._generate_source_id(text)
    assert id1 == id2
    assert len(id1) == 12


def test_generate_source_id_different():
    """Different text should produce different source IDs."""
    id1 = FbGroupCrawler._generate_source_id("套房A月租12000")
    id2 = FbGroupCrawler._generate_source_id("套房B月租15000")
    assert id1 != id2


# ------------------------------------------------------------------
# Group URL resolution
# ------------------------------------------------------------------


def test_resolve_group_url_full_url():
    url = "https://www.facebook.com/groups/lvmh3/"
    assert FbGroupCrawler._resolve_group_url(url) == "https://www.facebook.com/groups/lvmh3"


def test_resolve_group_url_slug():
    assert FbGroupCrawler._resolve_group_url("lvmh3") == "https://www.facebook.com/groups/lvmh3"


def test_resolve_group_url_known_name():
    assert "lvmh3" in FbGroupCrawler._resolve_group_url("5911高雄租屋")


def test_group_slugs_has_known_groups():
    assert "5911高雄租屋" in GROUP_SLUGS


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
