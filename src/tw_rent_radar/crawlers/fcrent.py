"""Crawler for fcrent.tw — a Next.js SSR rental listing site."""

from __future__ import annotations

import json
import re

from playwright.async_api import async_playwright

from tw_rent_radar.crawlers.base import BaseCrawler

# Pattern to extract __NEXT_DATA__ JSON from the page HTML.
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


class FcrentCrawler(BaseCrawler):
    """Crawl rental listings from fcrent.tw."""

    source_name = "fcrent"
    base_url = "https://fcrent.tw"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_listing_page(self, html: str) -> dict | None:
        """Extract listing data from the ``__NEXT_DATA__`` script tag.

        Returns a normalized dict matching the :class:`Listing` schema, or
        *None* if the expected data is not present.
        """
        match = _NEXT_DATA_RE.search(html)
        if match is None:
            return None

        try:
            next_data = json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            return None

        obj = next_data.get("props", {}).get("pageProps", {}).get("object")
        if obj is None:
            return None

        source_id = obj.get("id", "")
        return {
            "source": self.source_name,
            "source_id": str(source_id),
            "title": obj.get("title"),
            "price": obj.get("price"),
            "city": obj.get("city"),
            "district": obj.get("district"),
            "address": obj.get("address"),
            "size": obj.get("size"),
            "rooms": obj.get("rooms"),
            "type": obj.get("type"),
            "floor": obj.get("floor"),
            "contact": obj.get("contact"),
            "phone": obj.get("phone"),
            "url": f"{self.base_url}/object/{source_id}",
            "images": json.dumps(obj.get("images", []), ensure_ascii=False),
            "description": obj.get("description"),
            "amenities": json.dumps(obj.get("amenities", []), ensure_ascii=False),
            "raw_data": json.dumps(obj, ensure_ascii=False),
        }

    # ------------------------------------------------------------------
    # Crawling
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl fcrent.tw listings using Playwright.

        1. Launch headless Chromium.
        2. Navigate to the index page and wait for network idle.
        3. Collect all ``<a href="/object/...">`` links.
        4. Visit each detail page and parse with :meth:`parse_listing_page`.
        5. Return the list of successfully parsed listing dicts.
        """
        listings: list[dict] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(self.base_url, wait_until="networkidle")

            # Gather unique listing detail URLs.
            anchors = await page.query_selector_all('a[href^="/object/"]')
            hrefs: set[str] = set()
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if href:
                    hrefs.add(href)

            for href in hrefs:
                url = f"{self.base_url}{href}"
                try:
                    await page.goto(url, wait_until="networkidle")
                    html = await page.content()
                    listing = self.parse_listing_page(html)
                    if listing is not None:
                        listings.append(listing)
                except Exception:  # noqa: BLE001
                    # Skip pages that fail to load or parse.
                    continue

            await browser.close()

        return listings
