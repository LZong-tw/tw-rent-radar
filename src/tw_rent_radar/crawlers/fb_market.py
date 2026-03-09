"""Facebook Marketplace crawler for rental listings."""
from __future__ import annotations

from tw_rent_radar.crawlers.base import BaseCrawler


class FbMarketCrawler(BaseCrawler):
    """Scrape rental listings from Facebook Marketplace (Taiwan)."""

    source_name = "fb_market"
    marketplace_url = (
        "https://www.facebook.com/marketplace/category/propertyrentals"
    )

    async def crawl(self, **filters) -> list[dict]:
        """Crawl Facebook Marketplace for rental listings.

        Parameters
        ----------
        city : str, optional
            City slug to filter results (e.g. ``"taipei"``).

        Returns
        -------
        list[dict]
            Parsed listing dicts (empty for now — DOM selectors require
            live inspection to determine).
        """
        # TODO: DOM selectors need live inspection.
        #   1. ensure_fb_session(pw) to get a browser context
        #   2. Navigate to marketplace_url (optionally append city filter)
        #   3. Scroll & extract listing cards
        #   4. For each card, parse title/price/location/images
        #   5. Return list of listing dicts
        return []
