"""Rakuya (樂屋網) rental listing crawler using Playwright with stealth mode."""

from __future__ import annotations

import json
import logging
import re

from .base import BaseCrawler

logger = logging.getLogger(__name__)

CITY_CODES: dict[str, int] = {
    "台北市": 1,
    "新北市": 2,
    "基隆市": 3,
    "桃園市": 5,
    "新竹市": 6,
    "新竹縣": 7,
    "苗栗縣": 8,
    "台中市": 10,
    "彰化縣": 11,
    "南投縣": 12,
    "雲林縣": 13,
    "嘉義市": 14,
    "嘉義縣": 15,
    "台南市": 16,
    "高雄市": 17,
    "屏東縣": 18,
    "宜蘭縣": 19,
    "花蓮縣": 20,
    "台東縣": 21,
    "澎湖縣": 22,
    "金門縣": 23,
    "連江縣": 24,
}


class RakuyaCrawler(BaseCrawler):
    """Crawler for rakuya.com.tw rental listings.

    Uses Playwright with stealth mode to bypass Cloudflare Turnstile
    protection.  Listing pages are paginated; detail pages can optionally
    be visited for richer information (contact, amenities, images).
    """

    source_name = "rakuya"
    base_url = "https://www.rakuya.com.tw"

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def parse_price(self, text: str) -> int | None:
        """Parse a price string like ``'25,000元'`` or ``'8000'`` into an integer.

        Returns ``None`` when the input is empty or contains no digits.
        """
        if not text or not text.strip():
            return None
        numbers = re.findall(r"[\d,]+", text)
        if not numbers:
            return None
        cleaned = numbers[0].replace(",", "")
        if not cleaned:
            return None
        return int(cleaned)

    def parse_size(self, text: str) -> float | None:
        """Parse a size string like ``'33.8坪'`` into a float.

        Returns ``None`` when the input is empty or has no recognisable value.
        """
        if not text:
            return None
        match = re.search(r"([\d.]+)\s*坪", text)
        return float(match.group(1)) if match else None

    # ------------------------------------------------------------------
    # Listing card parser (unit-testable with mock data)
    # ------------------------------------------------------------------

    def parse_listing_card(self, card_data: dict) -> dict:
        """Normalise a listing card's extracted data into the Listing schema.

        Parameters
        ----------
        card_data:
            Expected keys: ``ehid``, ``title``, ``address``, ``price_text``,
            ``type_layout`` (list of up to 2 strings), ``size_floor`` (list of
            up to 2 strings), ``city``, ``url``.
        """
        type_layout = card_data.get("type_layout", [])
        listing_type = type_layout[0] if len(type_layout) > 0 else None
        rooms = type_layout[1] if len(type_layout) > 1 else None

        size_floor = card_data.get("size_floor", [])
        size = self.parse_size(size_floor[0]) if len(size_floor) > 0 else None
        floor = size_floor[1] if len(size_floor) > 1 else None

        return {
            "source": self.source_name,
            "source_id": card_data.get("ehid", ""),
            "title": card_data.get("title"),
            "price": self.parse_price(card_data.get("price_text", "")),
            "city": card_data.get("city"),
            "address": card_data.get("address"),
            "size": size,
            "rooms": rooms,
            "type": listing_type,
            "floor": floor,
            "url": card_data.get("url"),
            "raw_data": json.dumps(card_data, ensure_ascii=False),
        }

    # ------------------------------------------------------------------
    # Detail page parser (unit-testable with mock HTML)
    # ------------------------------------------------------------------

    def parse_detail_page(self, html: str) -> dict:
        """Parse detail page HTML for additional fields.

        Returns a dict of fields to merge into the listing.
        """
        result: dict = {}

        # Title
        title_match = re.search(
            r'class="block__title"[^>]*>\s*<h2[^>]*>(.*?)</h2>', html, re.DOTALL
        )
        if title_match:
            result["title"] = title_match.group(1).strip()

        # Address
        addr_match = re.search(r'<h1[^>]*class="txt__address"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if addr_match:
            address = re.sub(r"<[^>]+>", "", addr_match.group(1)).strip()
            result["address"] = address
            city_match = re.match(r"(.*?[市縣])(.*?[區鄉鎮市])", address)
            if city_match:
                result["city"] = city_match.group(1)
                result["district"] = city_match.group(2)

        # Price
        price_match = re.search(r'class="txt__price-total"[^>]*>(.*?)</span>', html, re.DOTALL)
        if price_match:
            result["price"] = self.parse_price(price_match.group(1))

        # Info table: label/content pairs
        info_pairs = re.findall(
            r'class="list__label"[^>]*>(.*?)</span>\s*<span[^>]*class="list__content"[^>]*>'
            r"(.*?)</span>",
            html,
            re.DOTALL,
        )
        for label, content in info_pairs:
            label = re.sub(r"<[^>]+>", "", label).strip()
            content = re.sub(r"<[^>]+>", "", content).strip()
            if "格局" in label:
                result["rooms"] = content
            elif "坪數" in label:
                result["size"] = self.parse_size(content)
            elif "樓層" in label:
                result["floor"] = content
            elif "類型" in label:
                result["type"] = content

        # Contact name
        name_match = re.search(r'class="name"[^>]*>(.*?)</span>', html, re.DOTALL)
        if name_match:
            result["contact"] = re.sub(r"<[^>]+>", "", name_match.group(1)).strip()

        # Images
        img_matches = re.findall(
            r'class="houseImages-wrapper-item"[^>]*>.*?<img[^>]+src="([^"]+)"',
            html,
            re.DOTALL,
        )
        if img_matches:
            result["images"] = json.dumps(img_matches, ensure_ascii=False)

        # Amenities (設備 and 傢俱)
        amenities: list[str] = []
        for label, content in info_pairs:
            label_clean = re.sub(r"<[^>]+>", "", label).strip()
            if "設備" in label_clean or "傢俱" in label_clean:
                items = [i.strip() for i in content.split(",") if i.strip()]
                amenities.extend(items)
        if amenities:
            result["amenities"] = json.dumps(amenities, ensure_ascii=False)

        # Extract cooking and gas_type from amenities or info pairs
        all_content = " ".join(re.sub(r"<[^>]+>", "", content).strip() for _, content in info_pairs)
        if "天然瓦斯" in all_content:
            result["gas_type"] = "天然瓦斯"
        elif "桶裝瓦斯" in all_content:
            result["gas_type"] = "桶裝瓦斯"

        if "不可開伙" in all_content:
            result["cooking"] = "不可開伙"
        elif "可開伙" in all_content:
            result["cooking"] = "可開伙"

        return result

    # ------------------------------------------------------------------
    # Crawl entry-point
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl rakuya.com.tw listings using Playwright with stealth mode.

        Parameters
        ----------
        **filters:
            Optional filters:

            * ``city`` -- Chinese city name (default ``"高雄市"``).
            * ``max_pages`` -- Maximum result pages to visit (default ``3``).
            * ``fetch_details`` -- Visit each detail page for richer data
              (default ``False``).

        Returns
        -------
        list[dict]
            Normalised listing dicts ready for ``upsert_listing``.
        """
        from playwright.async_api import async_playwright

        try:
            from playwright_stealth import stealth_async
        except ImportError:
            from playwright_stealth import Stealth

            async def stealth_async(page):  # type: ignore[misc]
                await Stealth().apply_stealth_async(page)

        city: str = filters.get("city", "高雄市")
        city_code = CITY_CODES.get(city, 17)
        max_pages: int = int(filters.get("max_pages", 3))
        fetch_details: bool = bool(filters.get("fetch_details", False))

        listings: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await stealth_async(page)

            for page_num in range(1, max_pages + 1):
                url = (
                    f"{self.base_url}/rent/rent_search?search=city&city={city_code}&page={page_num}"
                )
                await page.goto(url, wait_until="networkidle")

                cards = await page.query_selector_all("div.obj-item")
                if not cards:
                    break

                for card in cards:
                    ehid_el = await card.query_selector("a.obj-cover")
                    ehid = await ehid_el.get_attribute("data-ehid") if ehid_el else None
                    href = await ehid_el.get_attribute("href") if ehid_el else None

                    title_el = await card.query_selector(".obj-title h6 a")
                    title = await title_el.inner_text() if title_el else None

                    addr_el = await card.query_selector(".obj-address")
                    address = await addr_el.inner_text() if addr_el else None

                    price_el = await card.query_selector(".obj-price span")
                    price_text = await price_el.inner_text() if price_el else ""

                    type_layout_els = await card.query_selector_all(
                        ".obj-data li:nth-child(2) span"
                    )
                    type_layout = [await el.inner_text() for el in type_layout_els]

                    size_floor_els = await card.query_selector_all(".obj-data li:nth-child(3) span")
                    size_floor = [await el.inner_text() for el in size_floor_els]

                    card_data = {
                        "ehid": ehid,
                        "title": title,
                        "address": address,
                        "price_text": price_text,
                        "type_layout": type_layout,
                        "size_floor": size_floor,
                        "city": city,
                        "url": f"{self.base_url}{href}" if href else None,
                    }

                    listing = self.parse_listing_card(card_data)

                    if fetch_details and listing["url"]:
                        await page.goto(listing["url"], wait_until="networkidle")
                        detail_html = await page.content()
                        detail_data = self.parse_detail_page(detail_html)
                        listing.update({k: v for k, v in detail_data.items() if v is not None})

                    listings.append(listing)

            await browser.close()

        return listings
