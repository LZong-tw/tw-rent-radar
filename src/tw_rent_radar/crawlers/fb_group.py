"""Facebook Group crawler for rental listings."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

from tw_rent_radar.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

# Patterns that commonly appear in Taiwanese rental posts.
# Order matters — we stop at the first match.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"  # comma-formatted or plain integer

_PRICE_PATTERNS: list[re.Pattern[str]] = [
    # "12,000元/月", "12,000 元", "12000元"
    re.compile(_NUM + r"\s*元"),
    # "月租：12000", "月租 12,000"
    re.compile(r"月租[：:\s]*" + _NUM),
    # "$12,000", "$8000"
    re.compile(r"\$\s*" + _NUM),
]

# Known group name -> URL slug mappings.
GROUP_SLUGS: dict[str, str] = {
    "5911高雄租屋": "lvmh3",
}

# JavaScript to extract post text from the group page.
# Uses div[dir="auto"] which captures post body text reliably.
_JS_EXTRACT_POSTS = r"""() => {
    const posts = [];
    const seen = new Set();
    // Each post is typically a div with role="article" or inside one
    const articles = document.querySelectorAll('[role="article"]');
    for (const article of articles) {
        // Get all text blocks within the article
        const textEls = article.querySelectorAll('div[dir="auto"]');
        const textParts = [];
        for (const el of textEls) {
            const t = el.innerText.trim();
            if (t && t.length > 5) textParts.push(t);
        }
        const fullText = textParts.join('\n');
        if (!fullText || fullText.length < 10) continue;

        // Deduplicate by content hash
        const hash = fullText.substring(0, 100);
        if (seen.has(hash)) continue;
        seen.add(hash);

        // Try to find a permalink
        const links = article.querySelectorAll('a[href*="/groups/"]');
        let permalink = null;
        for (const a of links) {
            if (a.href.includes('/posts/') || a.href.includes('/permalink/')) {
                permalink = a.href.split('?')[0];
                break;
            }
        }

        // Try to find images
        const imgs = article.querySelectorAll('img[src*="scontent"]');
        const imgSrcs = Array.from(imgs).map(i => i.src).filter(s => s);

        // Get poster name (usually first link with role or strong text)
        const nameEl = article.querySelector('strong') || article.querySelector('h3 a');
        const poster = nameEl ? nameEl.innerText.trim() : null;

        posts.push({ text: fullText, permalink, imgSrcs, poster });
    }
    return posts;
}"""

# Fallback: if [role="article"] yields too few results, extract div[dir="auto"] directly.
_JS_EXTRACT_TEXTS = r"""() => {
    const results = [];
    const seen = new Set();
    const els = document.querySelectorAll('div[dir="auto"]');
    for (const el of els) {
        const t = el.innerText.trim();
        if (t && t.length > 30) {
            const hash = t.substring(0, 100);
            if (!seen.has(hash)) {
                seen.add(hash);
                results.push(t);
            }
        }
    }
    return results;
}"""


class FbGroupCrawler(BaseCrawler):
    """Scrape rental posts from a Facebook group."""

    source_name = "fb_group"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_price_from_text(text: str) -> int | None:
        """Extract a monthly rental price from unstructured Chinese text.

        Returns the first integer price found, or ``None`` when no price
        pattern is recognised.
        """
        for pattern in _PRICE_PATTERNS:
            m = pattern.search(text)
            if m:
                # Remove commas ("12,000" -> "12000") and convert.
                raw = int(m.group(1).replace(",", ""))
                # Filter out unreasonable prices (min 4 digits, 1000-100000 range)
                if 1000 <= raw <= 100000:
                    return raw
        return None

    @staticmethod
    def _generate_source_id(text: str) -> str:
        """Generate a stable source ID from post text content."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]  # noqa: S324

    def parse_post(self, post_data: dict, city: str, group_url: str | None = None) -> dict | None:
        """Parse a single Facebook group post into a listing dict.

        Parameters
        ----------
        post_data:
            Expected keys: ``text``, ``permalink`` (optional), ``imgSrcs``
            (optional list), ``poster`` (optional).
        city:
            Default city to assign.
        group_url:
            Group URL for context.

        Returns ``None`` if the post has no recognisable rental price.
        """
        text = post_data.get("text", "")
        if not text:
            return None

        price = self.parse_price_from_text(text)
        if price is None:
            return None

        # Use permalink as URL, or group URL as fallback.
        url = post_data.get("permalink") or group_url

        # Generate a stable source ID from content.
        source_id = self._generate_source_id(text)

        # Try to extract title from first non-empty line.
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        title = lines[0][:200] if lines else None

        # Images
        images = None
        img_srcs = post_data.get("imgSrcs", [])
        if img_srcs:
            images = json.dumps(img_srcs, ensure_ascii=False)

        # Contact from poster name
        contact = post_data.get("poster")

        return {
            "source": self.source_name,
            "source_id": source_id,
            "title": title,
            "price": price,
            "city": city,
            "description": text[:2000],
            "url": url,
            "images": images,
            "contact": contact,
            "raw_data": json.dumps(post_data, ensure_ascii=False),
        }

    @staticmethod
    def _resolve_group_url(group: str) -> str:
        """Resolve a group argument to a full Facebook URL.

        Accepts:
        - Full URL: ``https://www.facebook.com/groups/lvmh3``
        - Slug: ``lvmh3``
        - Known name: ``5911高雄租屋``
        """
        if group.startswith("http"):
            return group.rstrip("/")

        # Check known name mappings.
        for name, slug in GROUP_SLUGS.items():
            if name in group:
                return f"https://www.facebook.com/groups/{slug}"

        # Assume it's a slug or numeric ID.
        return f"https://www.facebook.com/groups/{group}"

    # ------------------------------------------------------------------
    # Crawl entry-point
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl a Facebook group for rental listings.

        Parameters
        ----------
        **filters:
            Optional filters:

            * ``group`` -- Facebook group URL, slug, or known name
              (e.g. ``"5911高雄租屋"``, ``"lvmh3"``, or a full URL).
            * ``city`` -- Chinese city name (default ``"高雄市"``).
            * ``scroll_count`` -- Number of scroll actions to load more posts
              (default ``15``).

        Returns
        -------
        list[dict]
            Parsed listing dicts ready for ``upsert_listing``.
        """
        group: str | None = filters.get("group")
        if not group:
            logger.warning(
                "No group specified. Use group=<url_or_slug_or_name>. "
                "Example: group='5911高雄租屋' or group='lvmh3'"
            )
            return []

        from playwright.async_api import async_playwright

        from tw_rent_radar.crawlers.fb_auth import ensure_fb_session

        city: str = filters.get("city", "高雄市")
        scroll_count: int = int(filters.get("scroll_count", 15))

        group_url = self._resolve_group_url(group)
        logger.info("Crawling Facebook group: %s", group_url)

        async with async_playwright() as pw:
            context = await ensure_fb_session(pw)
            page = await context.new_page()

            await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Click "查看更多" (See more) buttons to expand truncated posts.
            for _ in range(3):
                see_more = page.locator('div[role="button"]:has-text("查看更多")')
                count = await see_more.count()
                for i in range(count):
                    try:
                        await see_more.nth(i).click(timeout=2000)
                        await asyncio.sleep(0.3)
                    except Exception:  # noqa: BLE001
                        pass

            # Scroll to load more posts.
            for i in range(scroll_count):
                await page.evaluate("window.scrollBy(0, 2000)")
                await asyncio.sleep(1.5)

                # Periodically click "查看更多" on newly loaded posts.
                if (i + 1) % 5 == 0:
                    see_more = page.locator('div[role="button"]:has-text("查看更多")')
                    count = await see_more.count()
                    for j in range(count):
                        try:
                            await see_more.nth(j).click(timeout=2000)
                            await asyncio.sleep(0.3)
                        except Exception:  # noqa: BLE001
                            pass

            # Extract posts using article-based approach first.
            posts = await page.evaluate(_JS_EXTRACT_POSTS)
            logger.info("Extracted %d posts via [role=article]", len(posts))

            # Fallback: if article-based extraction yields too few, use text-based.
            if len(posts) < 3:
                texts = await page.evaluate(_JS_EXTRACT_TEXTS)
                logger.info("Fallback: extracted %d text blocks via div[dir=auto]", len(texts))
                for text in texts:
                    # Avoid duplicating posts already found via articles.
                    if any(text[:80] in p.get("text", "")[:80] for p in posts):
                        continue
                    posts.append({"text": text, "permalink": None, "imgSrcs": [], "poster": None})

            listings = []
            seen_ids: set[str] = set()
            for post_data in posts:
                listing = self.parse_post(post_data, city, group_url)
                if listing and listing["source_id"] not in seen_ids:
                    seen_ids.add(listing["source_id"])
                    listings.append(listing)

            logger.info("Parsed %d rental listings from group posts", len(listings))
            await context.browser.close()

        return listings
