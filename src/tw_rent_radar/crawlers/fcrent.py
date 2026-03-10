"""Crawler for fcrent.tw — a Next.js SSR rental listing site."""

from __future__ import annotations

import json
import logging
import re

from playwright.async_api import async_playwright

from tw_rent_radar.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

# Pattern to extract __NEXT_DATA__ JSON from the page HTML.
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*(.*?)\s*</script>',
    re.DOTALL,
)

# Pattern to strip HTML tags when extracting plain text from rich content.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _build_lookup(items: list[dict]) -> dict[str, str]:
    """Build id -> zhTW name lookup from a reference table."""
    return {item["id"]: item.get("name", {}).get("zhTW", "") for item in items}


class FcrentCrawler(BaseCrawler):
    """Crawl rental listings from fcrent.tw."""

    source_name = "fcrent"
    base_url = "https://fcrent.tw"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_listing_page(self, html: str) -> dict | None:
        """Extract listing data from the ``__NEXT_DATA__`` script tag.

        The real fcrent.tw __NEXT_DATA__ stores opaque IDs on the listing
        object and provides lookup tables in ``pageProps`` to resolve them
        to human-readable names.

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

        page_props = next_data.get("props", {}).get("pageProps", {})
        obj = page_props.get("object")
        if obj is None:
            return None

        # The listing ID lives in query, not on the object itself.
        source_id = next_data.get("query", {}).get("id", "")

        # Build lookups from the reference tables in pageProps.
        city_lookup = _build_lookup(page_props.get("city", []))
        district_lookup = _build_lookup(page_props.get("district", []))
        type_lookup = _build_lookup(page_props.get("type", []))
        layout_lookup = _build_lookup(page_props.get("layout", []))
        facility_lookup = _build_lookup(page_props.get("facilities", []))
        others_lookup = _build_lookup(page_props.get("others", []))

        # Resolve coordinator to contact name and phone.
        coordinator_id = obj.get("coordinator", "")
        coordinators = page_props.get("coordinators", [])
        coordinator = next((c for c in coordinators if c.get("id") == coordinator_id), {})
        contact = coordinator.get("name", {}).get("zhTW")
        phone = coordinator.get("phone")

        # Resolve city and district names from opaque IDs.
        city_name = city_lookup.get(obj.get("city", ""))
        district_name = district_lookup.get(obj.get("district", ""))

        # Parse description from rich-text contents blocks.
        contents = obj.get("contents", {}).get("zhTW", [])
        description = ""
        if isinstance(contents, list):
            parts: list[str] = []
            for block in contents:
                if isinstance(block, dict):
                    html_content = block.get("data", {}).get("html", "")
                    if html_content:
                        parts.append(_HTML_TAG_RE.sub("", html_content))
            description = "\n".join(parts)

        # Resolve amenities from facility IDs.
        amenities = [facility_lookup.get(fid, fid) for fid in obj.get("facility", [])]

        # Resolve "others" features and append to description.
        other_features = [others_lookup.get(oid, oid) for oid in obj.get("others", [])]
        if other_features:
            if description:
                description += "\n" + ", ".join(other_features)
            else:
                description = ", ".join(other_features)

        # Extract cooking and gas_type from amenities and features.
        cooking = None
        gas_type_val = None
        all_features_text = " ".join(amenities + other_features + [description])
        if "不可開伙" in all_features_text:
            cooking = "不可開伙"
        elif "可開伙" in all_features_text or "開伙" in all_features_text:
            cooking = "可開伙"
        if "天然瓦斯" in all_features_text:
            gas_type_val = "天然瓦斯"
        elif "桶裝瓦斯" in all_features_text:
            gas_type_val = "桶裝瓦斯"

        # Prefer layout name (e.g. "獨立套房") over building type.
        type_name = type_lookup.get(obj.get("type", ""))
        layout_name = layout_lookup.get(obj.get("layout", ""))
        listing_type = layout_name or type_name

        # Parse price (stored as string on the real site).
        price = None
        rent_str = obj.get("rent", "")
        if rent_str:
            try:
                price = int(rent_str)
            except (ValueError, TypeError):
                pass

        # Parse size in ping (stored as string on the real site).
        size = None
        ping_str = obj.get("ping", "")
        if ping_str:
            try:
                size = float(ping_str)
            except (ValueError, TypeError):
                pass

        return {
            "source": self.source_name,
            "source_id": source_id,
            "title": obj.get("name", {}).get("zhTW"),
            "price": price,
            "city": city_name,
            "district": district_name,
            "address": (f"{city_name}{district_name}" if city_name and district_name else None),
            "size": size,
            "rooms": obj.get("pattern"),
            "type": listing_type,
            "floor": obj.get("floor"),
            "contact": contact,
            "phone": phone,
            "url": f"{self.base_url}/object/{source_id}",
            "images": json.dumps(obj.get("picture", []), ensure_ascii=False),
            "description": description or None,
            "amenities": json.dumps(amenities, ensure_ascii=False),
            "cooking": cooking,
            "gas_type": gas_type_val,
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
