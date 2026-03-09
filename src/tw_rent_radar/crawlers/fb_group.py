"""Facebook Group crawler for rental listings."""
from __future__ import annotations

import re

from tw_rent_radar.crawlers.base import BaseCrawler

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
                return int(m.group(1).replace(",", ""))
        return None

    # ------------------------------------------------------------------
    # Crawl
    # ------------------------------------------------------------------

    async def crawl(self, **filters) -> list[dict]:
        """Crawl a Facebook group for rental listings.

        Parameters
        ----------
        group : str
            The Facebook group URL or numeric ID to crawl.

        Returns
        -------
        list[dict]
            Parsed listing dicts (empty for now — DOM selectors require
            live inspection to determine).
        """
        group: str | None = filters.get("group")
        if not group:
            print(
                "Usage: pass group=<group_url_or_id> to crawl a Facebook group.\n"
                "Example: crawler.crawl(group='https://www.facebook.com/groups/123456')"
            )
            return []

        # TODO: DOM selectors need live inspection.
        #   1. ensure_fb_session(pw) to get a browser context
        #   2. Navigate to the group URL
        #   3. Scroll & extract post elements
        #   4. For each post, parse title/price/images/description
        #   5. Return list of listing dicts
        return []
