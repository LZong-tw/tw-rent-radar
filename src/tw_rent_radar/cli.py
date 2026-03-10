"""CLI entry point using Click."""

from __future__ import annotations

import asyncio
import json
import sys
from importlib.metadata import version as pkg_version

import click

# Fix Windows console encoding for Chinese characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from rich.console import Console
from sqlalchemy.orm import Session

from tw_rent_radar.crawlers import (
    FbGroupCrawler,
    FbMarketCrawler,
    FcrentCrawler,
    RakuyaCrawler,
    Rent591Crawler,
)
from tw_rent_radar.db import DEFAULT_DB_PATH, Listing, create_tables, get_engine, upsert_listing
from tw_rent_radar.geo import geocode
from tw_rent_radar.output import format_json, format_table

SOURCES = {
    "591": "rent.591.com.tw — 591 租屋網",
    "rakuya": "rakuya.com.tw — 樂屋網",
    "fcrent": "fcrent.tw — 方齊物業",
    "fb_group": "Facebook 租屋社團",
    "fb_market": "Facebook Marketplace",
}

# Maps source key to crawler class.
CRAWLER_MAP: dict = {
    "591": Rent591Crawler,
    "rakuya": RakuyaCrawler,
    "fcrent": FcrentCrawler,
    "fb_group": FbGroupCrawler,
    "fb_market": FbMarketCrawler,
}

DEFAULT_DB = DEFAULT_DB_PATH

console = Console()


def geocode_listing(session: Session, listing_id: int) -> None:
    """Geocode a listing if it has an address but no coordinates."""
    listing = session.get(Listing, listing_id)
    if listing is None or listing.latitude is not None:
        return
    if not listing.address:
        return
    full_addr = f"{listing.city or ''}{listing.address}"
    coords = geocode(full_addr)
    if coords:
        listing.latitude, listing.longitude = coords
        session.commit()


def run_crawler(source: str, db_path: str | None, **filters) -> int:
    """Dispatch to crawler class, crawl, and upsert results into the DB."""
    crawler_cls = CRAWLER_MAP.get(source)
    if crawler_cls is None:
        console.print(f"[yellow]Crawler for '{source}' not yet implemented.[/yellow]")
        return 0

    crawler = crawler_cls()
    listings = asyncio.run(crawler.crawl(**filters))

    engine = get_engine(db_path)
    create_tables(engine)

    count = 0
    with Session(engine) as session:
        for item in listings:
            result = upsert_listing(session, **item)
            geocode_listing(session, result.id)
            count += 1
        session.commit()

    console.print(f"[green]Saved {count} listings from {source}.[/green]")
    return count


@click.group()
@click.version_option(version=pkg_version("tw-rent-radar"), prog_name="tw-rent-radar")
def cli():
    """tw-rent-radar: Multi-platform Taiwan rental listing CLI tool."""
    pass


@cli.command()
@click.argument("source", type=click.Choice(list(SOURCES.keys()) + ["all"]))
@click.option("--city", help="縣市，例如 高雄市")
@click.option("--group", help="Facebook 社團名稱")
@click.option("--fetch-details", is_flag=True, help="爬取詳情頁（較慢，但取得更多資訊）")
@click.option("--db", "db_path", default=None, hidden=True)
def crawl(source, city, group, fetch_details, db_path):
    """爬取租屋資料"""
    filters = {}
    if city:
        filters["city"] = city
    if group:
        filters["group"] = group
    if fetch_details:
        filters["fetch_details"] = True

    if source == "all":
        for src in CRAWLER_MAP:
            run_crawler(src, db_path, **filters)
    else:
        run_crawler(source, db_path, **filters)


def _export_file(dicts: list[dict], path: str, field_list: list[str] | None) -> None:
    """Export listing dicts to CSV or XLSX file."""
    import csv
    from pathlib import Path

    if not dicts:
        click.echo("No listings to export.")
        return

    ext = Path(path).suffix.lower()
    cols = field_list or list(dicts[0].keys())

    if ext == ".csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dicts)
        click.echo(f"Exported {len(dicts)} listings to {path}")

    elif ext == ".xlsx":
        try:
            from openpyxl import Workbook
        except ImportError:
            raise click.ClickException("pip install openpyxl  # 需要安裝 openpyxl 才能匯出 Excel")
        wb = Workbook()
        ws = wb.active
        ws.title = "Listings"
        ws.append(cols)
        for d in dicts:
            ws.append([d.get(c) for c in cols])
        wb.save(path)
        click.echo(f"Exported {len(dicts)} listings to {path}")

    else:
        raise click.ClickException(f"Unsupported format: {ext} (use .csv or .xlsx)")


@cli.command()
@click.option("--city", default=None, help="Filter by city.")
@click.option("--district", default=None, help="Filter by district.")
@click.option("--max-price", type=int, default=None, help="Maximum price.")
@click.option("--min-price", type=int, default=None, help="Minimum price.")
@click.option("--rooms", default=None, help="Filter by rooms.")
@click.option("--type", "listing_type", default=None, help="Filter by listing type.")
@click.option("--source", default=None, help="Filter by source platform.")
@click.option("--cooking", default=None, help="Filter by cooking policy (可開伙/不可開伙).")
@click.option("--gas-type", "gas_type", default=None, help="Filter by gas type.")
@click.option("--near", default=None, help="POI or address to calculate distance from.")
@click.option("--within", type=float, default=None, help="Max distance in km (requires --near).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--fields", default=None, help="Comma-separated list of fields to show.")
@click.option("--output", "output_path", default=None, help="匯出至檔案（支援 .csv 和 .xlsx）")
@click.option("--db", "db_path", default=DEFAULT_DB, hidden=True)
def search(
    city: str | None,
    district: str | None,
    max_price: int | None,
    min_price: int | None,
    rooms: str | None,
    listing_type: str | None,
    source: str | None,
    cooking: str | None,
    gas_type: str | None,
    near: str | None,
    within: float | None,
    as_json: bool,
    fields: str | None,
    output_path: str | None,
    db_path: str,
):
    """Search stored rental listings."""
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        query = session.query(Listing)
        if city:
            query = query.filter(Listing.city == city)
        if district:
            query = query.filter(Listing.district == district)
        if max_price is not None:
            query = query.filter(Listing.price <= max_price)
        if min_price is not None:
            query = query.filter(Listing.price >= min_price)
        if rooms:
            query = query.filter(Listing.rooms == rooms)
        if listing_type:
            query = query.filter(Listing.type == listing_type)
        if source:
            query = query.filter(Listing.source == source)
        if cooking:
            query = query.filter(Listing.cooking == cooking)
        if gas_type:
            query = query.filter(Listing.gas_type == gas_type)

        listings = query.all()
        field_list = fields.split(",") if fields else None
        dicts = [item.to_dict(field_list) for item in listings]

    # Distance filtering with --near
    if near:
        from tw_rent_radar.geo import geocode as geo_lookup
        from tw_rent_radar.geo import haversine_km

        target = geo_lookup(near)
        if target is None:
            raise click.ClickException(
                f"Could not geocode '{near}'. Check API keys in ~/.tw-rent-radar/config.json"
            )

        target_lat, target_lng = target
        filtered = []
        for d in dicts:
            lat, lng = d.get("latitude"), d.get("longitude")
            if lat is None or lng is None:
                continue
            dist = haversine_km(target_lat, target_lng, lat, lng)
            d["distance_km"] = round(dist, 2)
            if within is None or dist <= within:
                filtered.append(d)
        dicts = sorted(filtered, key=lambda x: x["distance_km"])

    if output_path:
        _export_file(dicts, output_path, field_list)
    elif as_json:
        click.echo(format_json(dicts, fields=field_list))
    elif dicts:
        default_cols = ["id", "source", "title", "price", "city", "district"]
        if near:
            default_cols.append("distance_km")
        click.echo(format_table(dicts, columns=field_list or default_cols))
    else:
        click.echo("No listings found.")


@cli.command()
@click.argument("listing_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--db", "db_path", default=DEFAULT_DB, hidden=True)
def show(listing_id: int, as_json: bool, db_path: str):
    """Show details for a single listing by ID."""
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            click.echo(f"Listing {listing_id} not found.")
            return
        d = listing.to_dict()

    if as_json:
        click.echo(format_json([d]))
    else:
        for key, value in d.items():
            click.echo(f"{key}: {value}")


@cli.group("list")
def list_group():
    """List resources."""
    pass


@list_group.command("sources")
def list_sources():
    """List all supported rental platforms."""
    for key, desc in SOURCES.items():
        click.echo(f"  {key:12s} {desc}")


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--db", "db_path", default=DEFAULT_DB, hidden=True)
def stats(as_json: bool, db_path: str):
    """Show statistics about stored listings."""
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        total = session.query(Listing).count()
        by_source = {}
        for key in SOURCES:
            count = session.query(Listing).filter(Listing.source == key).count()
            if count > 0:
                by_source[key] = count

    data = {"total": total, "by_source": by_source}

    if as_json:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Total listings: {total}")
        if by_source:
            for src, count in by_source.items():
                click.echo(f"  {src}: {count}")
        else:
            click.echo("  No listings in database.")


@cli.group("db")
def db_group():
    """Database management commands."""
    pass


@db_group.command("reset")
@click.option("--db", "db_path", default=DEFAULT_DB, hidden=True)
@click.confirmation_option(prompt="This will delete all data. Are you sure?")
def db_reset(db_path: str):
    """Reset the database (delete all data)."""
    engine = get_engine(db_path)
    from tw_rent_radar.db import Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    click.echo("Database reset complete.")
