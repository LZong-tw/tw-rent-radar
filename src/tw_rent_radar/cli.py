"""CLI entry point using Click."""
from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console
from sqlalchemy.orm import Session

from tw_rent_radar.crawlers import (
    FcrentCrawler, Rent591Crawler, RakuyaCrawler, FbGroupCrawler, FbMarketCrawler,
)
from tw_rent_radar.db import Listing, create_tables, get_engine, upsert_listing
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

DEFAULT_DB = "radar.db"

console = Console()


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
            upsert_listing(session, **item)
            count += 1
        session.commit()

    console.print(f"[green]Saved {count} listings from {source}.[/green]")
    return count


@click.group()
@click.version_option(version="0.1.0", prog_name="tw-rent-radar")
def cli():
    """tw-rent-radar: Multi-platform Taiwan rental listing CLI tool."""
    pass


@cli.command()
@click.argument("source", type=click.Choice(list(SOURCES.keys()) + ["all"]))
@click.option("--city", help="縣市，例如 高雄市")
@click.option("--group", help="Facebook 社團名稱")
@click.option("--db", "db_path", default=None, hidden=True)
def crawl(source, city, group, db_path):
    """爬取租屋資料"""
    filters = {}
    if city:
        filters["city"] = city
    if group:
        filters["group"] = group

    if source == "all":
        for src in CRAWLER_MAP:
            run_crawler(src, db_path, **filters)
    else:
        run_crawler(source, db_path, **filters)


@cli.command()
@click.option("--city", default=None, help="Filter by city.")
@click.option("--district", default=None, help="Filter by district.")
@click.option("--max-price", type=int, default=None, help="Maximum price.")
@click.option("--min-price", type=int, default=None, help="Minimum price.")
@click.option("--rooms", default=None, help="Filter by rooms.")
@click.option("--type", "listing_type", default=None, help="Filter by listing type.")
@click.option("--source", default=None, help="Filter by source platform.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--fields", default=None, help="Comma-separated list of fields to show.")
@click.option("--db", "db_path", default=DEFAULT_DB, hidden=True)
def search(
    city: str | None,
    district: str | None,
    max_price: int | None,
    min_price: int | None,
    rooms: str | None,
    listing_type: str | None,
    source: str | None,
    as_json: bool,
    fields: str | None,
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

        listings = query.all()
        field_list = fields.split(",") if fields else None
        dicts = [l.to_dict(field_list) for l in listings]

    if as_json:
        click.echo(format_json(dicts, fields=field_list))
    elif dicts:
        default_cols = ["id", "source", "title", "price", "city", "district"]
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
        listing = session.query(Listing).get(listing_id)
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
