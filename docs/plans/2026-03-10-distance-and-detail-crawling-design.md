# Distance Search & Detail Page Crawling Design

## Overview

Add geocoding-based distance search and per-platform detail page crawling to tw-rent-radar. All platforms feed into a unified schema with lat/lng, cooking policy, and gas type columns — each platform fills what it can.

## Architecture

### 1. Geocoding Layer (`src/tw_rent_radar/geo.py`)

Wraps TGOS (Taiwan Geographic Information Service) API to convert addresses to latitude/longitude coordinates.

- Called during crawl after upsert, for any listing with an `address` but no lat/lng.
- TGOS API requires a registered account and API key.
- API key stored in environment variable `TGOS_API_KEY` or in `~/.tw-rent-radar/config.json`.
- Rate-limited to respect TGOS usage policies.
- Fallback: skip geocoding if no API key configured (lat/lng remain NULL).

### 2. Detail Page Crawling (per-platform)

`BaseCrawler` gains an optional method:

```python
async def crawl_detail(self, page, url: str) -> dict:
    """Crawl a single listing's detail page. Override in subclass."""
    return {}
```

Each crawler implements `crawl_detail()` if the platform has detail pages:

| Crawler | Detail Page? | Extracts |
|---------|-------------|----------|
| 591 | Yes | cooking, gas_type, full amenities, description, detailed address |
| Rakuya | Yes | amenities, description, detailed address |
| fcrent | Partial (already in __NEXT_DATA__) | cooking/gas if available |
| FB Group | No | — |
| FB Market | No | — |

### 3. New Listing Columns

| Column | Type | Description |
|--------|------|-------------|
| `latitude` | Float | TGOS geocoded latitude |
| `longitude` | Float | TGOS geocoded longitude |
| `cooking` | String(50) | Cooking policy (可開伙 / 不可開伙 / None=unknown) |
| `gas_type` | String(50) | Gas type (天然瓦斯 / 桶裝瓦斯 / None=unknown) |

`None` means the platform didn't provide the info, not "no".

### 4. Search CLI Changes

New flags on `search` command:

```bash
# Distance filter: geocode the POI, then Haversine filter
tw-rent-radar search --near "高雄軟體園區" --within 2

# Detail field filters
tw-rent-radar search --cooking 可開伙
tw-rent-radar search --gas-type 天然瓦斯

# Combined
tw-rent-radar search --city 高雄市 --max-price 18000 --near "高雄軟體園區" --within 2 --cooking 可開伙
```

### 5. Data Flow

```
Crawl:
  list page → parse_list_item() → for each item:
    → crawl_detail(url) → merge detail fields
    → upsert_listing(... cooking, gas_type ...)
    → TGOS geocode(address) → update lat/lng

Search --near "POI" --within N:
  → TGOS geocode("POI") → target (lat, lng)
  → SQL query with basic filters (city, price, cooking, etc.)
  → Haversine filter in Python (compare each result's lat/lng to target)
  → Sort by distance ascending
  → Add "distance" column to output (in km)
```

### 6. Distance Calculation

Haversine formula in Python (no external dependency needed). Computed in-memory after SQL query — sufficient for typical dataset sizes (hundreds to low thousands of listings per city).

## Tech Decisions

- **TGOS over Google Maps**: User preference. Free, official Taiwan geographic data, best coverage for Taiwan addresses.
- **Geocode at crawl time**: Avoids repeated API calls on every search. lat/lng cached in DB.
- **Haversine over SpatiaLite**: Simpler, no C extension dependency. Good enough for filtering within a city.
- **Optional crawl_detail()**: Not all platforms have detail pages. Method returns empty dict by default.
- **None = unknown**: Distinguishes "platform didn't say" from "explicitly not allowed".

## API Key Management

TGOS API key lookup order:
1. Environment variable `TGOS_API_KEY`
2. `~/.tw-rent-radar/config.json` → `{"tgos_api_key": "..."}`
3. If neither found: skip geocoding with a warning, distance search unavailable.
