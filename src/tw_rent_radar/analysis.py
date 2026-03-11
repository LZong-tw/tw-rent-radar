"""Enriched rental listing analysis with MRT distances, quality flags, and dedup."""

from __future__ import annotations

import json
from difflib import SequenceMatcher

from tw_rent_radar.geo import haversine_km

# Kaohsiung MRT stations (red + orange lines, key stops).
MRT_STATIONS: dict[str, tuple[float, float]] = {
    "前鎮高中": (22.5968, 120.3265),
    "獅甲": (22.6015, 120.3215),
    "凱旋": (22.6060, 120.3160),
    "三多商圈": (22.6115, 120.3025),
    "中央公園": (22.6270, 120.3005),
    "美麗島": (22.6315, 120.3015),
    "高雄車站": (22.6395, 120.3020),
    "左營": (22.6870, 120.3060),
    "巨蛋": (22.6690, 120.3020),
    "文化中心": (22.6200, 120.3120),
    "技擊館": (22.6230, 120.3190),
    "衛武營": (22.6215, 120.3350),
    "鳳山西站": (22.6265, 120.3440),
    "大東": (22.6310, 120.3500),
    "鳳山": (22.6290, 120.3575),
    "市議會": (22.6205, 120.2960),
    "鹽埕埔": (22.6250, 120.2860),
    "西子灣": (22.6250, 120.2715),
    "草衙": (22.5870, 120.3365),
    "小港": (22.5720, 120.3420),
}


def nearest_mrt(lat: float, lng: float) -> tuple[str, float]:
    """Return (station_name, distance_km) for the closest MRT station."""
    best_name = ""
    best_km = 999.0
    for name, (mlat, mlng) in MRT_STATIONS.items():
        dist = haversine_km(mlat, mlng, lat, lng)
        if dist < best_km:
            best_km = dist
            best_name = name
    return best_name, round(best_km, 2)


def quality_flags(listing: dict) -> dict[str, str | None]:
    """Extract quality flags (elevator, balcony, etc.) from listing text fields."""
    raw = listing.get("raw_data", "") or ""
    amenities = listing.get("amenities", "") or ""
    desc = listing.get("description", "") or ""
    title = listing.get("title", "") or ""
    all_text = f"{title} {amenities} {desc} {raw}"

    return {
        "elevator": "有" if any(k in all_text for k in ("電梯", "elevator")) else None,
        "balcony": "有" if any(k in all_text for k in ("陽台", "陽臺", "balcony")) else None,
        "washer": "有" if any(k in all_text for k in ("洗衣機", "洗衣")) else None,
        "ac": "有" if any(k in all_text for k in ("冷氣", "空調")) else None,
        "pet": "可" if any(k in all_text for k in ("可養寵", "寵物")) else None,
    }


def detect_long_listed(listing: dict) -> str | None:
    """Detect stale/long-listed 591 listings via browsenum_all."""
    raw = listing.get("raw_data", "") or ""
    if listing.get("source") != "591" or not raw:
        return None
    try:
        raw_obj = json.loads(raw) if isinstance(raw, str) else raw
        views = raw_obj.get("browsenum_all", 0)
        if isinstance(views, str):
            views = int(views)
        if views > 200:
            return f"高瀏覽({views})"
    except Exception:  # noqa: BLE001
        pass
    return None


def cross_platform_dedup(results: list[dict]) -> None:
    """Mark cross-platform duplicates in-place (title similarity + price proximity)."""
    for i, a in enumerate(results):
        for j, b in enumerate(results):
            if i >= j or a["source"] == b["source"]:
                continue
            addr_a = a.get("title", "") or ""
            addr_b = b.get("title", "") or ""
            if len(addr_a) > 5 and len(addr_b) > 5:
                ratio = SequenceMatcher(None, addr_a, addr_b).ratio()
                if ratio > 0.6 and a.get("price") and b.get("price"):
                    price_diff = abs(a["price"] - b["price"]) / max(a["price"], b["price"])
                    if price_diff < 0.15:
                        results[i]["cross_platform_dup"] = f"~#{b['id']}({b['source']})"
                        results[j]["cross_platform_dup"] = f"~#{a['id']}({a['source']})"


def enrich_listing_for_analysis(
    listing: dict,
    poi_coords: list[tuple[float, float, str]] | None = None,
    within_km: float | None = None,
) -> dict | None:
    """Enrich a single listing dict with analysis fields.

    Returns None if the listing is filtered out by distance constraints.
    """
    lat, lng = listing.get("latitude"), listing.get("longitude")

    # POI distances
    poi_dists: dict[str, float | None] = {}
    if poi_coords:
        for plat, plng, pname in poi_coords:
            if lat and lng:
                poi_dists[pname] = round(haversine_km(plat, plng, lat, lng), 2)
            else:
                poi_dists[pname] = None

    # Distance filter: must be within range of ALL POIs
    if within_km is not None and poi_dists:
        for dist in poi_dists.values():
            if dist is not None and dist > within_km:
                return None

    # Nearest MRT
    mrt_name, mrt_km = nearest_mrt(lat, lng) if lat and lng else (None, None)

    # Price per ping
    price_per_ping = None
    if listing.get("price") and listing.get("size") and listing["size"] > 0:
        price_per_ping = round(listing["price"] / listing["size"])

    flags = quality_flags(listing)
    long_listed = detect_long_listed(listing)

    result = {
        "id": listing["id"],
        "source": listing["source"],
        "title": (listing.get("title") or "")[:60],
        "price": listing["price"],
        "size": listing.get("size"),
        "price_per_ping": price_per_ping,
        "district": listing.get("district"),
        "rooms": listing.get("rooms"),
        "type": listing.get("type"),
        "floor": listing.get("floor"),
        "cooking": listing.get("cooking"),
        "gas_type": listing.get("gas_type"),
        "nearest_mrt": mrt_name,
        "mrt_km": mrt_km,
        **flags,
        "long_listed": long_listed,
        "url": listing.get("url"),
    }

    # Add POI distance columns
    for pname, dist in poi_dists.items():
        result[f"dist_{pname}"] = dist

    return result


ANALYSIS_COLUMNS = [
    "id",
    "source",
    "title",
    "price",
    "size",
    "price_per_ping",
    "district",
    "rooms",
    "type",
    "floor",
    "cooking",
    "gas_type",
    "nearest_mrt",
    "mrt_km",
    "elevator",
    "balcony",
    "washer",
    "ac",
    "pet",
    "long_listed",
    "url",
    "cross_platform_dup",
]


def write_xlsx(results: list[dict], output_path: str) -> None:
    """Write analysis results to a color-coded XLSX file."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    if not results:
        return

    # Build column list dynamically (include dist_* columns from results)
    dist_cols = sorted(k for k in results[0] if k.startswith("dist_"))
    cols = list(ANALYSIS_COLUMNS)
    # Insert distance columns after mrt_km
    mrt_idx = cols.index("mrt_km") + 1
    for dc in dist_cols:
        cols.insert(mrt_idx, dc)
        mrt_idx += 1

    wb = Workbook()
    ws = wb.active
    ws.title = "Listings"

    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for c, col_name in enumerate(cols, 1):
        cell = ws.cell(row=1, column=c, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    green = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    red = PatternFill(start_color="FCE4EC", end_color="FCE4EC", fill_type="solid")
    yellow = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
    blue_light = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")

    for r_idx, row_data in enumerate(results, 2):
        for c_idx, col_name in enumerate(cols, 1):
            val = row_data.get(col_name)
            cell = ws.cell(row=r_idx, column=c_idx, value=val)

            if col_name == "cooking":
                if val == "可開伙":
                    cell.fill = green
                elif val == "不可開伙":
                    cell.fill = red
            elif col_name == "gas_type":
                if val == "天然瓦斯":
                    cell.fill = green
                elif val == "桶裝瓦斯":
                    cell.fill = yellow
            elif col_name in ("elevator", "balcony", "washer", "ac") and val == "有":
                cell.fill = green
            elif col_name == "pet" and val == "可":
                cell.fill = green
            elif col_name == "long_listed" and val:
                cell.fill = yellow
            elif col_name == "cross_platform_dup" and val:
                cell.fill = yellow
            elif col_name == "source" and val == "fb_group":
                cell.fill = blue_light

    for c_idx, col_name in enumerate(cols, 1):
        max_len = len(str(col_name))
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=c_idx, max_col=c_idx):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)), 40))
        ws.column_dimensions[get_column_letter(c_idx)].width = max_len + 2

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{ws.max_row}"

    wb.save(output_path)
