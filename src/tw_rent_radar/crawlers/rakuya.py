"""Rakuya (樂屋網) rental listing crawler using Playwright."""

from __future__ import annotations

import json
import re

from playwright.async_api import async_playwright

from .base import BaseCrawler


class RakuyaCrawler(BaseCrawler):
    """Crawler for rakuya.com.tw rental listings.

    Rakuya returns 403 on direct HTTP requests, so Playwright headless
    browser is required to render the pages.  The DOM selectors used in
    this skeleton are provisional and will be refined after live
    inspection of the actual site markup.
    """

    source_name = "rakuya"
    base_url = "https://www.rakuya.com.tw"
    search_url = "https://www.rakuya.com.tw/rent/rent_list"

    # Mapping of city names to rakuya city query-string codes (provisional).
    CITY_CODES: dict[str, str] = {
        "台北市": "A",
        "新北市": "F",
        "桃園市": "H",
        "台中市": "B",
        "台南市": "D",
        "高雄市": "E",
    }

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def parse_price(self, text: str) -> int | None:
        """Parse a price string like '12,000' or '8000' into an integer.

        Returns ``None`` when the input is empty or contains no digits.
        """
        if not text or not text.strip():
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        if not cleaned:
            return None
        return int(cleaned)

    def parse_listing_element(self, data: dict) -> dict:
        """Normalize a raw listing dict into the Listing schema.

        Parameters
        ----------
        data:
            A dict extracted (or mocked) from the page.  Expected keys:
            ``id``, ``title``, ``price``, ``city``, ``district``,
            ``address``, ``size``, ``rooms``, ``type``, ``floor``,
            ``url``, ``images``.

        Returns
        -------
        dict
            A flat dict whose keys match the ``Listing`` model columns.
        """
        images = data.get("images")
        if isinstance(images, list):
            images = json.dumps(images, ensure_ascii=False)

        return {
            "source": self.source_name,
            "source_id": str(data.get("id", "")),
            "title": data.get("title"),
            "price": data.get("price"),
            "city": data.get("city"),
            "district": data.get("district"),
            "address": data.get("address"),
            "size": data.get("size"),
            "rooms": data.get("rooms"),
            "type": data.get("type"),
            "floor": data.get("floor"),
            "url": data.get("url"),
            "images": images,
            "raw_data": json.dumps(data, ensure_ascii=False, default=str),
        }

    # ------------------------------------------------------------------
    # Crawl entry-point
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl rakuya.com.tw listings using Playwright.

        Parameters
        ----------
        **filters:
            Optional filters.  Currently supported:

            * ``city`` – Chinese city name (e.g. ``"高雄市"``).
            * ``max_pages`` – Maximum number of result pages to visit
              (default ``1``).

        Returns
        -------
        list[dict]
            Normalized listing dicts ready for ``upsert_listing``.

        Notes
        -----
        DOM selectors are placeholders and will be updated once we can
        do a live inspection of the rendered page.
        """
        city: str | None = filters.get("city")
        max_pages: int = int(filters.get("max_pages", 1))  # noqa: F841

        url = self.search_url
        if city and city in self.CITY_CODES:
            url = f"{self.search_url}?city={self.CITY_CODES[city]}"

        listings: list[dict] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                # TODO: The selectors below are provisional placeholders.
                # After a live inspection of the rendered DOM we will
                # replace them with the real element queries.
                #
                # Example future flow:
                #   cards = await page.query_selector_all(".rent-list-item")
                #   for card in cards:
                #       raw = { ... extract fields from card ... }
                #       listings.append(self.parse_listing_element(raw))
                #   handle pagination up to max_pages ...

            finally:
                await browser.close()

        return listings
