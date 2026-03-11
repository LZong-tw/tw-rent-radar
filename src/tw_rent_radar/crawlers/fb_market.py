"""Facebook Marketplace crawler for rental listings."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from tw_rent_radar.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

# Facebook Marketplace uses city slugs in the URL path.
CITY_SLUGS: dict[str, str] = {
    "台北市": "taipei",
    "新北市": "newtaipei",
    "基隆市": "keelung",
    "桃園市": "taoyuan",
    "新竹市": "hsinchu",
    "新竹縣": "hsinchu",
    "苗栗縣": "miaoli",
    "台中市": "taichung",
    "彰化縣": "changhua",
    "南投縣": "nantou",
    "雲林縣": "yunlin",
    "嘉義市": "chiayi",
    "嘉義縣": "chiayi",
    "台南市": "tainan",
    "高雄市": "kaohsiung",
    "屏東縣": "pingtung",
    "宜蘭縣": "yilan",
    "花蓮縣": "hualien",
    "台東縣": "taitung",
    "澎湖縣": "penghu",
    "金門縣": "kinmen",
    "連江縣": "lienchiang",
}

# JavaScript to extract listing cards from the Marketplace page.
_JS_EXTRACT = r"""() => {
    const anchors = document.querySelectorAll('a[href*="/marketplace/item/"]');
    return Array.from(anchors).map(a => {
        const lines = a.innerText.trim().split('\n').filter(l => l.trim());
        const match = a.href.match(/\/marketplace\/item\/(\d+)/);
        const itemId = match ? match[1] : null;
        const img = a.querySelector('img');
        const imgSrc = img ? img.src : null;
        return { itemId, href: a.href.split('?')[0], lines, imgSrc };
    });
}"""


class FbMarketCrawler(BaseCrawler):
    """Scrape rental listings from Facebook Marketplace (Taiwan)."""

    source_name = "fb_market"

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_price(text: str) -> int | None:
        """Parse FB Marketplace price like ``'NT$12,000'`` into integer.

        Returns ``None`` when the input is empty or has no digits.
        """
        if not text:
            return None
        m = re.search(r"NT\$\s*([\d,]+)", text)
        if not m:
            m = re.search(r"\$\s*([\d,]+)", text)
        if not m:
            m = re.search(r"([\d,]+)", text)
        if not m:
            return None
        cleaned = m.group(1).replace(",", "")
        return int(cleaned) if cleaned else None

    def parse_card(self, card_data: dict, city: str) -> dict | None:
        """Parse a single Marketplace card dict into a listing dict.

        Parameters
        ----------
        card_data:
            Expected keys: ``itemId``, ``href``, ``lines`` (list of strings),
            ``imgSrc``.
        city:
            Default city to assign if the card doesn't indicate one.

        Returns ``None`` if the card lacks an item ID.
        """
        item_id = card_data.get("itemId")
        if not item_id:
            return None

        lines = card_data.get("lines", [])
        price_text = lines[0] if len(lines) > 0 else ""
        title = lines[1] if len(lines) > 1 else None
        location = lines[2] if len(lines) > 2 else None

        price = self.parse_price(price_text)

        # Detect city from location text when available.
        detected_city = city
        if location:
            for cn_city in CITY_SLUGS:
                bare = cn_city.rstrip("市縣")
                if bare in location:
                    detected_city = cn_city
                    break

        images = None
        img_src = card_data.get("imgSrc")
        if img_src:
            images = json.dumps([img_src], ensure_ascii=False)

        return {
            "source": self.source_name,
            "source_id": item_id,
            "title": title,
            "price": price,
            "city": detected_city,
            "address": location,
            "url": card_data.get("href"),
            "images": images,
            "raw_data": json.dumps(card_data, ensure_ascii=False),
        }

    # ------------------------------------------------------------------
    # Crawl entry-point
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl Facebook Marketplace for rental listings.

        Parameters
        ----------
        **filters:
            Optional filters:

            * ``city`` -- Chinese city name (default ``"高雄市"``).
            * ``scroll_count`` -- Number of scroll actions to load more items
              (default ``10``).

        Returns
        -------
        list[dict]
            Normalised listing dicts ready for ``upsert_listing``.
        """
        from playwright.async_api import async_playwright

        from tw_rent_radar.crawlers.fb_auth import ensure_fb_session

        city: str = filters.get("city", "高雄市")
        slug = CITY_SLUGS.get(city, "kaohsiung")
        scroll_count: int = int(filters.get("scroll_count", 10))

        url = f"https://www.facebook.com/marketplace/{slug}/propertyrentals"

        async with async_playwright() as pw:
            context = await ensure_fb_session(pw)
            page = await context.new_page()

            logger.info("Navigating to %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            for _ in range(scroll_count):
                await page.evaluate("window.scrollBy(0, 2000)")
                await asyncio.sleep(1.5)

            items = await page.evaluate(_JS_EXTRACT)
            logger.info("Found %d marketplace cards", len(items))

            listings = []
            for card_data in items:
                listing = self.parse_card(card_data, city)
                if listing:
                    listings.append(listing)

            await context.browser.close()

        return listings
