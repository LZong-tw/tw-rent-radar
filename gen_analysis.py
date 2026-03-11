"""Generate enriched analysis XLSX for rental listings.

Usage:
    python gen_analysis.py [--within KM] [--max-price PRICE]

Filters listings by city=高雄市, proximity to work (高雄軟體園區) and gym
(健身工廠), and generates a color-coded XLSX with MRT distances, quality
flags, cross-platform dedup, and long-listed detection.
"""

from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from tw_rent_radar.db import DEFAULT_DB_PATH, Listing, create_tables, get_engine
from tw_rent_radar.geo import geocode, haversine_km

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

MAX_PRICE = 18000
WITHIN_KM = 3.0
CITY = "高雄市"
WORK_POI = "高雄軟體園區"
GYM_POI = "高雄市健身工廠"
OUTPUT = "rentals_analysis.xlsx"

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


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    # Parse simple CLI args
    max_price = MAX_PRICE
    within_km = WITHIN_KM
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--within" and i + 1 < len(args):
            within_km = float(args[i + 1])
            i += 2
        elif args[i] == "--max-price" and i + 1 < len(args):
            max_price = int(args[i + 1])
            i += 2
        else:
            i += 1

    engine = get_engine(DEFAULT_DB_PATH)
    create_tables(engine)

    work = geocode(WORK_POI)
    gym = geocode(GYM_POI)
    print(f"Work: {work}, Gym: {gym}")

    with Session(engine) as session:
        q = session.query(Listing).filter(
            Listing.city == CITY,
            Listing.price <= max_price,
            (Listing.cooking == "可開伙") | (Listing.cooking.is_(None)),
        )
        listings = q.all()
        dicts = [item.to_dict() for item in listings]

    results: list[dict] = []
    for d in dicts:
        lat, lng = d.get("latitude"), d.get("longitude")

        dist_work = dist_gym = None
        if lat and lng and work:
            dist_work = round(haversine_km(work[0], work[1], lat, lng), 2)
        if lat and lng and gym:
            dist_gym = round(haversine_km(gym[0], gym[1], lat, lng), 2)

        # Nearest MRT
        nearest_mrt = None
        mrt_km = None
        if lat and lng:
            for name, (mlat, mlng) in MRT_STATIONS.items():
                dist = haversine_km(mlat, mlng, lat, lng)
                if mrt_km is None or dist < mrt_km:
                    mrt_km = round(dist, 2)
                    nearest_mrt = name

        # Price per ping
        price_per_ping = None
        if d.get("price") and d.get("size") and d["size"] > 0:
            price_per_ping = round(d["price"] / d["size"])

        # Quality flags from text fields
        raw = d.get("raw_data", "") or ""
        amenities = d.get("amenities", "") or ""
        desc = d.get("description", "") or ""
        title = d.get("title", "") or ""
        all_text = f"{title} {amenities} {desc} {raw}"

        elevator = "有" if any(k in all_text for k in ("電梯", "elevator")) else None
        balcony = "有" if any(k in all_text for k in ("陽台", "陽臺", "balcony")) else None
        washer = "有" if any(k in all_text for k in ("洗衣機", "洗衣")) else None
        ac = "有" if any(k in all_text for k in ("冷氣", "空調")) else None
        pet = "可" if any(k in all_text for k in ("可養寵", "寵物")) else None

        # Long-listed detection (591: browsenum_all > 200)
        long_listed = None
        if d.get("source") == "591" and raw:
            try:
                raw_obj = json.loads(raw) if isinstance(raw, str) else raw
                views = raw_obj.get("browsenum_all", 0)
                if isinstance(views, str):
                    views = int(views)
                if views > 200:
                    long_listed = f"高瀏覽({views})"
            except Exception:  # noqa: BLE001
                pass

        # Distance filter
        if dist_work is not None and dist_gym is not None:
            if dist_work > within_km or dist_gym > within_km:
                continue

        results.append(
            {
                "id": d["id"],
                "source": d["source"],
                "title": (d.get("title") or "")[:60],
                "price": d["price"],
                "size": d.get("size"),
                "price_per_ping": price_per_ping,
                "district": d.get("district"),
                "rooms": d.get("rooms"),
                "type": d.get("type"),
                "floor": d.get("floor"),
                "cooking": d.get("cooking"),
                "gas_type": d.get("gas_type"),
                "nearest_mrt": nearest_mrt,
                "mrt_km": mrt_km,
                "dist_work": dist_work,
                "dist_gym": dist_gym,
                "elevator": elevator,
                "balcony": balcony,
                "washer": washer,
                "ac": ac,
                "pet": pet,
                "long_listed": long_listed,
                "url": d.get("url"),
            }
        )

    # Cross-platform dedup
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

    results.sort(key=lambda x: (x.get("dist_work") or 999))

    # Stats
    print(f"Results: {len(results)}")
    by_src: dict[str, int] = {}
    for r in results:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    print(f"By source: {by_src}")
    cooking_known = sum(1 for r in results if r.get("cooking"))
    gas_known = sum(1 for r in results if r.get("gas_type"))
    print(f"Cooking known: {cooking_known}/{len(results)}, Gas known: {gas_known}/{len(results)}")

    # Write XLSX
    _write_xlsx(results)
    print(f"Saved {OUTPUT}")


def _write_xlsx(results: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Listings"

    cols = [
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
        "dist_work",
        "dist_gym",
        "elevator",
        "balcony",
        "washer",
        "ac",
        "pet",
        "long_listed",
        "url",
        "cross_platform_dup",
    ]

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

    wb.save(OUTPUT)


if __name__ == "__main__":
    main()
