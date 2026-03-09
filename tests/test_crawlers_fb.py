"""Tests for Facebook crawlers (group + marketplace) and auth utilities."""
from __future__ import annotations

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
# crawl() returns empty list (skeleton)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fb_group_crawl_no_group_returns_empty():
    crawler = FbGroupCrawler()
    result = await crawler.crawl()
    assert result == []


@pytest.mark.asyncio
async def test_fb_market_crawl_returns_empty():
    crawler = FbMarketCrawler()
    result = await crawler.crawl()
    assert result == []
