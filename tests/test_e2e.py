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
    """Verify 591 crawler parsing works against live API structure."""

    @pytest.mark.asyncio
    async def test_list_api_returns_data(self):
        """591 listing API should return JSON with data."""
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
            await page.goto("https://rent.591.com.tw/", wait_until="networkidle", timeout=30000)

            # Try fetching the list API
            response = await page.evaluate("""async () => {
                const csrf = document.querySelector(
                    'meta[name="csrf-token"]'
                )?.content || '';
                const res = await fetch(
                    'https://rent.591.com.tw/home/search/rsList'
                    + '?is_new_list=1&type=1&kind=0&region=17&firstRow=0',
                    { headers: { 'X-CSRF-TOKEN': csrf } }
                );
                const text = await res.text();
                try {
                    return JSON.parse(text);
                } catch (e) {
                    return { _raw: text.slice(0, 500), _status: res.status };
                }
            }""")
            await browser.close()

        # Verify structure
        assert (
            "data" in response
        ), f"API response should have 'data' key, got: {response.get('_raw', response)!r}"
        data = response["data"]
        assert "data" in data, "data should contain nested 'data' with listings"

        items = data["data"]
        if len(items) > 0:
            # Verify at least the first item has expected fields
            item = items[0]
            from tw_rent_radar.crawlers.rent591 import Rent591Crawler

            crawler = Rent591Crawler()
            parsed = crawler.parse_list_item(item, city="高雄市")
            assert parsed["source"] == "591"
            assert parsed["source_id"], "should have a source_id"


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
