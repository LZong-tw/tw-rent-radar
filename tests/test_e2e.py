"""End-to-end smoke tests that hit real websites.

Run with: pytest -m e2e -v
Skip by default (configured in pyproject.toml).
"""

import pytest
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


@pytest.mark.e2e
class TestFcrentE2E:
    """Verify fcrent.tw crawler works against live site."""

    @pytest.mark.asyncio
    async def test_main_page_has_listings(self):
        """fcrent.tw main page should have /object/ links."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://fcrent.tw", wait_until="networkidle", timeout=30000)
            links = await page.eval_on_selector_all(
                'a[href*="/object/"]',
                "els => els.map(e => e.href)",
            )
            await browser.close()
        assert len(links) > 0, "fcrent.tw should have at least 1 listing link"

    @pytest.mark.asyncio
    async def test_parse_real_listing(self):
        """Parser should extract data from a real fcrent.tw listing page."""
        from tw_rent_radar.crawlers.fcrent import FcrentCrawler

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # First find a real listing URL
            await page.goto("https://fcrent.tw", wait_until="networkidle", timeout=30000)
            links = await page.eval_on_selector_all(
                'a[href*="/object/"]',
                "els => els.map(e => e.href)",
            )
            assert len(links) > 0, "Need at least 1 listing to test"

            # Visit first listing
            await page.goto(links[0], wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()

        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)

        assert result is not None, "Parser should return data for a real listing"
        assert result["source"] == "fcrent"
        assert result["source_id"], "source_id should not be empty"
        assert result["title"], "title should not be empty"
        assert result["price"] is None or isinstance(
            result["price"], int
        ), "price should be int or None"
        assert result["url"].startswith("https://fcrent.tw/object/")


@pytest.mark.e2e
class TestRent591E2E:
    """Verify 591 crawler parsing works against live SSR data."""

    @pytest.mark.asyncio
    async def test_list_page_returns_data(self):
        """591 Nuxt SSR list page should contain listing data in __NUXT__ payload."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Set region cookie for 高雄市
            await context.add_cookies(
                [
                    {
                        "name": "urlJumpIp",
                        "value": "17",
                        "domain": ".591.com.tw",
                        "path": "/",
                    }
                ]
            )

            page = await context.new_page()
            await page.goto(
                "https://rent.591.com.tw/list?region=17",
                wait_until="networkidle",
                timeout=30000,
            )

            # Extract listing data from the Nuxt SSR payload
            items = await page.evaluate("""() => {
                const n = window.__NUXT__;
                if (!n || !n.pinia || !n.pinia['rent-list']) return null;
                const store = n.pinia['rent-list'];
                const raw = store.dataList && store.dataList._value;
                const items = raw || store.dataList || [];
                if (!Array.isArray(items)) return null;
                return items.map(item => {
                    const safe = {};
                    for (const [k, v] of Object.entries(item)) {
                        if (v === null || v === undefined) {
                            safe[k] = v;
                        } else if (Array.isArray(v)) {
                            safe[k] = v.map(
                                x => typeof x === 'object'
                                    ? JSON.parse(JSON.stringify(x)) : x
                            );
                        } else if (typeof v === 'object') {
                            try {
                                safe[k] = JSON.parse(JSON.stringify(v));
                            } catch(e) { safe[k] = null; }
                        } else {
                            safe[k] = v;
                        }
                    }
                    return safe;
                });
            }""")
            await browser.close()

        # Verify structure
        assert items is not None, "Nuxt payload should contain listing data"
        assert len(items) > 0, "Should have at least 1 listing item"

        # Verify first item has expected fields and parses correctly
        item = items[0]
        assert "id" in item, f"Item should have 'id' field, got keys: {list(item.keys())}"
        assert "title" in item, "Item should have 'title' field"
        assert "price" in item, "Item should have 'price' field"

        from tw_rent_radar.crawlers.rent591 import Rent591Crawler

        crawler = Rent591Crawler()
        parsed = crawler.parse_list_item(item, city="高雄市")
        assert parsed["source"] == "591"
        assert parsed["source_id"], "should have a source_id"
        assert parsed["title"], "should have a title"


@pytest.mark.e2e
class TestRakuyaE2E:
    """Verify rakuya.com.tw crawler works against live site."""

    @pytest.mark.asyncio
    async def test_listing_page_has_cards(self):
        """Rakuya listing page should have .obj-item cards."""
        stealth = Stealth()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await stealth.apply_stealth_async(page)

            await page.goto(
                "https://www.rakuya.com.tw/rent/rent_search?search=city&city=17",
                wait_until="networkidle",
                timeout=60000,
            )

            cards = await page.query_selector_all("div.obj-item")
            await browser.close()

        assert len(cards) > 0, "Rakuya listing page should have listing cards"

    @pytest.mark.asyncio
    async def test_parse_real_detail_page(self):
        """Parser should extract data from a real rakuya detail page."""
        from tw_rent_radar.crawlers.rakuya import RakuyaCrawler

        stealth = Stealth()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await stealth.apply_stealth_async(page)

            # Go to listing page first to find a real ehid
            await page.goto(
                "https://www.rakuya.com.tw/rent/rent_search?search=city&city=17",
                wait_until="networkidle",
                timeout=60000,
            )

            # Get first listing link
            first_card = await page.query_selector("div.obj-item a.obj-cover")
            if first_card:
                href = await first_card.get_attribute("href")
                if href:
                    detail_url = (
                        f"https://www.rakuya.com.tw{href}" if href.startswith("/") else href
                    )
                    await page.goto(detail_url, wait_until="networkidle", timeout=60000)
                    html = await page.content()

                    crawler = RakuyaCrawler()
                    result = crawler.parse_detail_page(html)

                    # Should extract at least some fields
                    assert result.get("address") or result.get(
                        "title"
                    ), "Detail page parser should extract at least address or title"

            await browser.close()
