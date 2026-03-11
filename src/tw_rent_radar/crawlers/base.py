"""Abstract base class for all rental crawlers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


class BaseCrawler(ABC):
    """Base class that all platform crawlers must inherit from."""

    source_name: str

    @abstractmethod
    async def crawl(self, **filters) -> list[dict]:
        """Crawl listings with optional filters. Returns list of listing dicts."""
        ...


# ------------------------------------------------------------------
# Text inference utilities — extract cooking / gas from free text
# ------------------------------------------------------------------

_COOKING_NO = re.compile(r"不可(?:以)?開伙|禁止開伙|不能開伙|不得開伙")
_COOKING_YES = re.compile(r"可(?:以)?開伙|可煮食|開伙[：:]\s*可|有廚房")
_GAS_NATURAL = re.compile(r"天然瓦斯|天然氣")
_GAS_BOTTLED = re.compile(r"桶裝瓦斯|液化瓦斯")


def infer_cooking(text: str) -> str | None:
    """Infer cooking policy from free text. Returns '可開伙', '不可開伙', or None."""
    if not text:
        return None
    # Check negative first (不可開伙 contains 可開伙)
    if _COOKING_NO.search(text):
        return "不可開伙"
    if _COOKING_YES.search(text):
        return "可開伙"
    return None


def infer_gas(text: str) -> str | None:
    """Infer gas type from free text. Returns '天然瓦斯', '桶裝瓦斯', or None."""
    if not text:
        return None
    if _GAS_NATURAL.search(text):
        return "天然瓦斯"
    if _GAS_BOTTLED.search(text):
        return "桶裝瓦斯"
    return None


def enrich_listing(listing: dict) -> dict:
    """Fill in missing cooking/gas_type by scanning title + description text.

    Mutates and returns the same dict.
    """
    if listing.get("cooking") and listing.get("gas_type"):
        return listing

    text_parts = []
    for key in ("title", "description", "amenities"):
        val = listing.get(key)
        if val:
            text_parts.append(str(val))
    text = " ".join(text_parts)

    if not listing.get("cooking"):
        listing["cooking"] = infer_cooking(text)
    if not listing.get("gas_type"):
        listing["gas_type"] = infer_gas(text)
    return listing
