"""591 rental listing crawler using Playwright for CSRF and API calls."""

from __future__ import annotations

import json
import logging
import re

from playwright.async_api import async_playwright

from tw_rent_radar.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

REGION_MAP = {
    "台北市": 1,
    "新北市": 3,
    "桃園市": 6,
    "新竹市": 4,
    "新竹縣": 5,
    "苗栗縣": 21,
    "台中市": 8,
    "彰化縣": 10,
    "南投縣": 11,
    "雲林縣": 12,
    "嘉義市": 13,
    "嘉義縣": 14,
    "台南市": 15,
    "高雄市": 17,
    "屏東縣": 19,
    "宜蘭縣": 22,
    "花蓮縣": 23,
    "台東縣": 24,
    "澎湖縣": 25,
    "金門縣": 26,
    "連江縣": 27,
    "基隆市": 2,
}


class Rent591Crawler(BaseCrawler):
    """Crawler for 591 rental listings (rent.591.com.tw)."""

    source_name = "591"
    list_url = "https://rent.591.com.tw/home/search/rsList"

    def parse_price(self, price_str: str) -> int | None:
        """Parse price string like '15,000 元/月' to int. Return None for '面議'.

        Handles formats:
          - "15,000 元/月" -> 15000
          - "8000" -> 8000
          - "含管理費 12,500 元/月" -> 12500
          - "面議" -> None
        """
        if not price_str or "面議" in str(price_str):
            return None
        # Find all digit groups (possibly separated by commas)
        # We want the last number-like sequence in the string
        matches = re.findall(r"[\d,]+", str(price_str))
        if not matches:
            return None
        # Use the last numeric match (handles "含管理費 12,500 元/月")
        raw = matches[-1] if len(matches) == 1 else matches[-1]
        # For "含管理費 12,500 元/月", matches would be ["12", "500"]
        # but with our regex [\d,]+ it captures "12,500" as one match
        return int(raw.replace(",", ""))

    def parse_list_item(self, item: dict, city: str) -> dict:
        """Normalize a single listing from 591 API response to Listing schema.

        Maps 591 API fields to the Listing model fields.
        """
        source_id = str(item.get("post_id") or item.get("cases_id", ""))
        price_str = str(item.get("price", ""))
        price = self.parse_price(price_str)

        # Area can be a string like "30" or a number
        area_raw = item.get("area", "")
        try:
            size = float(str(area_raw)) if area_raw else None
        except (ValueError, TypeError):
            size = None

        return {
            "source": self.source_name,
            "source_id": source_id,
            "title": item.get("title", ""),
            "price": price,
            "city": city,
            "district": item.get("section_name", ""),
            "address": item.get("address", "") or item.get("location", ""),
            "size": size,
            "rooms": str(item.get("room", "")) if item.get("room") else None,
            "type": item.get("kind_name", ""),
            "floor": item.get("floor_str", ""),
            "contact": item.get("contact", ""),
            "phone": item.get("phone", ""),
            "url": f"https://rent.591.com.tw/rent-detail-{source_id}.html",
            "images": json.dumps(item.get("photo_list", []), ensure_ascii=False),
            "description": item.get("cases_name", ""),
            "amenities": None,
            "raw_data": json.dumps(item, ensure_ascii=False),
        }

    async def crawl(self, **filters) -> list[dict]:
        """Crawl 591 listings using Playwright for CSRF and API calls.

        Keyword arguments:
            city: str -- City name in Chinese (default: "台北市")
            max_pages: int -- Maximum number of pages to crawl (default: 5)
        """
        city = filters.get("city", "台北市")
        max_pages = filters.get("max_pages", 5)
        region_id = REGION_MAP.get(city, 1)

        results: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # 1. Set region cookie
            await context.add_cookies(
                [
                    {
                        "name": "urlJumpIp",
                        "value": str(region_id),
                        "domain": ".591.com.tw",
                        "path": "/",
                    }
                ]
            )

            page = await context.new_page()

            # 2. Visit rent.591.com.tw to get CSRF token
            await page.goto("https://rent.591.com.tw/", wait_until="domcontentloaded")
            csrf_token = await page.evaluate(
                "() => {"
                "  const meta = document.querySelector('meta[name=\"csrf-token\"]');"
                "  return meta ? meta.getAttribute('content') : '';"
                "}"
            )
            logger.info("CSRF token obtained: %s...", csrf_token[:10] if csrf_token else "empty")

            # 3. Loop through pages
            for page_num in range(max_pages):
                offset = page_num * 30
                api_url = (
                    f"{self.list_url}?is_new_list=1&type=1"
                    f"&region={region_id}&firstRow={offset}&totalRows=0"
                )

                logger.info("Fetching page %d (offset=%d)", page_num + 1, offset)

                # 4. Fetch list API with CSRF header via page.evaluate(fetch)
                response_text = await page.evaluate(
                    """(url) => {
                        return fetch(url, {
                            headers: {
                                'X-CSRF-TOKEN': '"""
                    + csrf_token
                    + """',
                                'X-Requested-With': 'XMLHttpRequest'
                            },
                            credentials: 'include'
                        })
                        .then(r => r.text())
                        .catch(e => JSON.stringify({error: e.message}));
                    }""",
                    api_url,
                )

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse API response on page %d", page_num + 1)
                    break

                if "data" not in data:
                    logger.warning(
                        "No data in API response on page %d: %s",
                        page_num + 1,
                        str(data)[:200],
                    )
                    break

                items = data["data"].get("data", [])
                if not items:
                    logger.info("No more items found on page %d", page_num + 1)
                    break

                # 5. Parse each item
                for item in items:
                    parsed = self.parse_list_item(item, city)
                    results.append(parsed)

                logger.info("Parsed %d items from page %d", len(items), page_num + 1)

            await browser.close()

        logger.info("Total listings crawled: %d", len(results))
        return results
