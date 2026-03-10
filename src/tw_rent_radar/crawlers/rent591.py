"""591 rental listing crawler using Playwright to extract SSR data from Nuxt."""

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

# JavaScript snippet to extract listing data from the Nuxt SSR payload.
# The site stores Pinia state in window.__NUXT__.pinia['rent-list'].
_EXTRACT_LISTINGS_JS = """() => {
    const n = window.__NUXT__;
    if (!n || !n.pinia || !n.pinia['rent-list']) return null;
    const store = n.pinia['rent-list'];
    const raw = store.dataList && store.dataList._value;
    const items = raw || store.dataList || [];
    if (!Array.isArray(items)) return null;

    // Serialize each item, avoiding circular references
    return items.map(item => {
        const safe = {};
        for (const [k, v] of Object.entries(item)) {
            if (v === null || v === undefined) {
                safe[k] = v;
            } else if (Array.isArray(v)) {
                safe[k] = v.map(x => typeof x === 'object' ? JSON.parse(JSON.stringify(x)) : x);
            } else if (typeof v === 'object') {
                try { safe[k] = JSON.parse(JSON.stringify(v)); } catch(e) { safe[k] = null; }
            } else {
                safe[k] = v;
            }
        }
        return safe;
    });
}"""


class Rent591Crawler(BaseCrawler):
    """Crawler for 591 rental listings (rent.591.com.tw).

    The 591 site is a Nuxt 3 SSR application.  Listing data is rendered
    server-side and embedded in the Pinia store at
    ``window.__NUXT__.pinia['rent-list'].dataList``.  Pagination is handled
    by navigating to ``/list?region=<id>&page=<n>``.
    """

    source_name = "591"
    list_base_url = "https://rent.591.com.tw/list"

    _EXTRACT_DETAIL_JS = """() => {
    const n = window.__NUXT__;
    if (!n || !n.pinia || !n.pinia['rent-detail-info']) return null;
    const store = n.pinia['rent-detail-info'];
    // Data may be at top level or nested inside ctx._rawValue (Vue reactivity wrapper)
    const raw = (store.ctx && store.ctx._rawValue) || store.data || store;
    try { return JSON.parse(JSON.stringify({data: raw})); }
    catch(e) { return null; }
}"""

    def parse_price(self, price_str: str) -> int | None:
        """Parse price string like '15,000' or '15,000 元/月' to int. Return None for '面議'.

        Handles formats:
          - "15,000 元/月" -> 15000
          - "22,000" -> 22000
          - "8000" -> 8000
          - "含管理費 12,500 元/月" -> 12500
          - "面議" -> None
        """
        if not price_str or "面議" in str(price_str):
            return None
        # Find all digit groups (possibly separated by commas)
        matches = re.findall(r"[\d,]+", str(price_str))
        if not matches:
            return None
        # Use the last numeric match (handles "含管理費 12,500 元/月")
        raw = matches[-1]
        return int(raw.replace(",", ""))

    def parse_detail_data(self, detail_store: dict) -> dict:
        """Extract additional fields from a 591 detail page Pinia store.

        The detail store is expected to have the structure::

            {"data": {"positionRound": {...}, "service": {...}, "remark": {...}}}

        Returns a dict with extracted fields, or empty dict if no useful data.
        """
        data = detail_store.get("data")
        if not data or not isinstance(data, dict):
            return {}

        result: dict = {}

        # Position / address
        position = data.get("positionRound")
        if position and isinstance(position, dict):
            address = position.get("address")
            if address:
                result["address"] = address
            lat = position.get("lat")
            lng = position.get("lng")
            try:
                if lat is not None:
                    result["latitude"] = float(lat)
                if lng is not None:
                    result["longitude"] = float(lng)
            except (ValueError, TypeError):
                pass

        # Service: facility and rule
        service = data.get("service")
        if service and isinstance(service, dict):
            facility = service.get("facility") or []

            # Gas type: find item with key=="gas" and active==True
            for item in facility:
                if item.get("key") == "gas" and item.get("active"):
                    result["gas_type"] = item.get("name")
                    break

            # Amenities: collect names of active items, excluding gas
            amenities = [
                item.get("name")
                for item in facility
                if item.get("active") and item.get("key") != "gas" and item.get("name")
            ]
            if amenities:
                result["amenities"] = json.dumps(amenities, ensure_ascii=False)

            # Cooking rule from service.rule
            rule = service.get("rule", "") or service.get("desc", "")
            if "不可開伙" in rule:
                result["cooking"] = "不可開伙"
            elif "可開伙" in rule:
                result["cooking"] = "可開伙"

        # Cooking fallback: check tags array (e.g. [{"id": 6, "value": "可開伙"}])
        if "cooking" not in result:
            tags = data.get("tags")
            if isinstance(tags, list):
                tag_values = " ".join(
                    t.get("value", "") if isinstance(t, dict) else str(t) for t in tags
                )
                if "不可開伙" in tag_values:
                    result["cooking"] = "不可開伙"
                elif "可開伙" in tag_values:
                    result["cooking"] = "可開伙"

        # Description from remark
        remark = data.get("remark")
        if remark and isinstance(remark, dict):
            content = remark.get("content")
            if content:
                result["description"] = content

        return result

    def parse_list_item(self, item: dict, city: str) -> dict:
        """Normalize a single listing from 591 Nuxt SSR data to Listing schema.

        Supports both the current Nuxt SSR field names and the legacy API
        field names so that existing unit tests and any transitional data
        continue to work.
        """
        # Source ID: current API uses 'id', legacy used 'post_id' / 'cases_id'
        source_id = str(item.get("id") or item.get("post_id") or item.get("cases_id", ""))

        price_str = str(item.get("price", ""))
        price = self.parse_price(price_str)

        # Area: current API has numeric 'area' and string 'area_name' (e.g. "20坪")
        area_raw = item.get("area", "")
        try:
            size = float(str(area_raw).replace("坪", "")) if area_raw else None
        except (ValueError, TypeError):
            size = None

        # District: current API embeds district in 'address' as "楠梓區-大學南路"
        # Legacy used 'section_name'.
        district = item.get("section_name", "")
        address = item.get("address", "") or item.get("location", "")
        if not district and address and "-" in address:
            # Extract district from "楠梓區-大學南路" style address
            district = address.split("-")[0].strip()

        # Rooms: current API uses 'layoutStr' (e.g. "3房2廳"), legacy used 'room'
        rooms = item.get("layoutStr") or (str(item["room"]) if item.get("room") else None)

        # Floor: current uses 'floor_name', legacy used 'floor_str'
        floor = item.get("floor_name", "") or item.get("floor_str", "")

        # Contact: current uses 'role_name', legacy used 'contact'
        contact = item.get("role_name", "") or item.get("contact", "")

        # URL: current API provides full URL, legacy needed construction
        url = item.get("url", "")
        if not url:
            url = f"https://rent.591.com.tw/{source_id}"

        # Images: current uses 'photoList', legacy used 'photo_list'
        photo_list = item.get("photoList") or item.get("photo_list", [])

        return {
            "source": self.source_name,
            "source_id": source_id,
            "title": item.get("title", ""),
            "price": price,
            "city": city,
            "district": district,
            "address": address,
            "size": size,
            "rooms": rooms,
            "type": item.get("kind_name", ""),
            "floor": floor,
            "contact": contact,
            "phone": item.get("phone", ""),
            "url": url,
            "images": json.dumps(photo_list, ensure_ascii=False),
            "description": item.get("community_name", "") or item.get("cases_name", ""),
            "amenities": None,
            "raw_data": json.dumps(item, ensure_ascii=False),
        }

    async def crawl(self, **filters) -> list[dict]:
        """Crawl 591 listings by navigating the Nuxt SSR list pages.

        Keyword arguments:
            city: str -- City name in Chinese (default: "台北市")
            max_pages: int -- Maximum number of pages to crawl (default: 5)
            fetch_details: bool -- Visit each detail page for extra fields (default: False)
        """
        city = filters.get("city", "台北市")
        max_pages = filters.get("max_pages", 5)
        fetch_details = filters.get("fetch_details", False)
        region_id = REGION_MAP.get(city, 1)

        results: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Set region cookie so the site defaults to the target city
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

            for page_num in range(1, max_pages + 1):
                list_url = f"{self.list_base_url}?region={region_id}"
                if page_num > 1:
                    list_url += f"&page={page_num}"

                logger.info("Fetching page %d: %s", page_num, list_url)

                try:
                    await page.goto(list_url, wait_until="networkidle", timeout=30000)
                except Exception:  # noqa: BLE001
                    logger.warning("Page load failed for page %d", page_num)
                    break

                # Extract listing data from the Nuxt SSR payload
                items = await page.evaluate(_EXTRACT_LISTINGS_JS)

                if not items:
                    logger.info("No more items found on page %d", page_num)
                    break

                for item in items:
                    parsed = self.parse_list_item(item, city)
                    results.append(parsed)

                logger.info("Parsed %d items from page %d", len(items), page_num)

            # Crawl detail pages for additional fields
            if fetch_details:
                for listing in results:
                    url = listing.get("url")
                    if not url:
                        continue
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        detail_store = await page.evaluate(self._EXTRACT_DETAIL_JS)
                        if detail_store:
                            detail = self.parse_detail_data(detail_store)
                            listing.update({k: v for k, v in detail.items() if v is not None})
                    except Exception:  # noqa: BLE001
                        logger.warning("Detail page failed for %s", url)
                        continue

            await browser.close()

        logger.info("Total listings crawled: %d", len(results))
        return results
