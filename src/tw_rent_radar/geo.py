"""Geocoding module with TGOS + Google Maps dual-engine support."""

from __future__ import annotations

import json
import logging
import math
import os
import re

import requests

from tw_rent_radar.db import CONFIG_DIR

logger = logging.getLogger(__name__)

CONFIG_PATH = CONFIG_DIR / "config.json"


def get_config() -> dict:
    """Load config from ~/.tw-rent-radar/config.json."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _tgos_request(address: str, app_id: str, api_key: str) -> str:
    """Make a raw TGOS API request. Returns the XML response text."""
    url = "https://addr.tgos.tw/addrws/v40/QueryAddr.asmx/QueryAddr"
    params = {
        "oAPPId": app_id,
        "oAPIKey": api_key,
        "oAddress": address,
        "oSRS": "EPSG:4326",
        "oFuzzyType": 2,
        "oResultDataType": "JSON",
        "oReturnMaxCount": 1,
        "oIsOnlyFullMatch": "false",
        "oIsSupportPast": "true",
        "oIsShowCodeBase": "false",
        "oIsLockCounty": "true",
        "oIsLockTown": "false",
        "oIsLockVillage": "false",
        "oIsLockRoadSection": "false",
        "oIsLockLane": "false",
        "oIsLockAlley": "false",
        "oIsLockArea": "false",
        "oIsSameNumber_SubNumber": "true",
        "oCanIgnoreVillage": "true",
        "oCanIgnoreNeighborhood": "true",
        "oFuzzyBuffer": 0,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.text


def _parse_tgos_response(xml_text: str) -> tuple[float, float] | None:
    """Parse TGOS XML-wrapped-JSON response to (lat, lng)."""
    match = re.search(r"<string[^>]*>(.*?)</string>", xml_text, re.DOTALL)
    if not match:
        return None
    data = json.loads(match.group(1).replace("\t", ""))
    addr_list = data.get("AddressList", [])
    if not addr_list:
        return None
    first = addr_list[0]
    return (first["Y"], first["X"])  # Y=lat, X=lng


def _google_request(address: str, api_key: str) -> dict:
    """Make a Google Maps Geocoding API request. Returns the JSON response."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW", "region": "tw"}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_google_response(data: dict) -> tuple[float, float] | None:
    """Parse Google Geocoding JSON response to (lat, lng)."""
    if data.get("status") != "OK" or not data.get("results"):
        return None
    loc = data["results"][0]["geometry"]["location"]
    return (loc["lat"], loc["lng"])


def geocode(
    address: str,
    *,
    tgos_app_id: str | None = None,
    tgos_api_key: str | None = None,
    google_api_key: str | None = None,
) -> tuple[float, float] | None:
    """Geocode an address to (lat, lng). Returns None on failure.

    Strategy: Try TGOS first (best for Taiwan street addresses),
    fall back to Google Maps (best for POI/landmark names).
    """
    config = get_config()
    tgos_app_id = tgos_app_id or os.environ.get("TGOS_APP_ID") or config.get("tgos_app_id")
    tgos_api_key = tgos_api_key or os.environ.get("TGOS_API_KEY") or config.get("tgos_api_key")
    google_api_key = (
        google_api_key or os.environ.get("GOOGLE_MAPS_API_KEY") or config.get("google_api_key")
    )

    if not tgos_app_id and not google_api_key:
        logger.warning("No geocoding API keys configured. Skipping geocode.")
        return None

    # Try TGOS first
    if tgos_app_id and tgos_api_key:
        try:
            xml = _tgos_request(address, tgos_app_id, tgos_api_key)
            result = _parse_tgos_response(xml)
            if result:
                return result
        except Exception:  # noqa: BLE001
            logger.warning("TGOS geocoding failed for '%s', trying Google.", address)

    # Fall back to Google Maps
    if google_api_key:
        try:
            data = _google_request(address, google_api_key)
            result = _parse_google_response(data)
            if result:
                return result
        except Exception:  # noqa: BLE001
            logger.warning("Google geocoding also failed for '%s'.", address)

    return None
