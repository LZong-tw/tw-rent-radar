# tw-rent-radar Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local-friendly, multi-platform Taiwan rental CLI tool with human (Rich table) and LLM (JSON) output modes.

**Architecture:** Python CLI using Click for commands, Playwright for browser-based crawling, SQLite+SQLAlchemy for storage. Each platform gets its own crawler class inheriting from a shared base. Output layer handles both Rich tables and JSON.

**Tech Stack:** Python 3.12, Click, SQLAlchemy, Rich, Playwright, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/tw_rent_radar/__init__.py`
- Delete: `requirements.txt`
- Delete: `api/` (entire directory)
- Delete: `crawlers/` (entire directory — old Scrapy code)
- Delete: `db/` (entire directory)
- Delete: `airflow/` (entire directory)
- Modify: `.gitignore` (add `radar.db`, `fb_session/`)

**Step 1: Delete old project files**

```bash
rm -rf api/ crawlers/ db/ airflow/ requirements.txt
```

**Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tw-rent-radar"
version = "0.1.0"
description = "Multi-platform Taiwan rental listing CLI tool"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "sqlalchemy>=2.0",
    "rich>=13.0",
    "playwright>=1.40",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
tw-rent-radar = "tw_rent_radar.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 3: Create package init**

```python
# src/tw_rent_radar/__init__.py
```

(Empty file — just marks it as a package.)

**Step 4: Create crawlers subpackage init**

```python
# src/tw_rent_radar/crawlers/__init__.py
```

**Step 5: Update .gitignore — append these lines**

```
# tw-rent-radar
radar.db
fb_session/
```

**Step 6: Create venv and install**

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
playwright install chromium
```

**Step 7: Verify install**

```bash
tw-rent-radar --help
```

Expected: fails (cli.py doesn't exist yet — that's OK, scaffolding is done).

**Step 8: Commit**

```bash
git add -A
git commit -m "chore: replace old Scrapy project with new package scaffolding"
```

---

### Task 2: Database Layer

**Files:**
- Create: `src/tw_rent_radar/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
from tw_rent_radar.db import get_engine, Listing, create_tables, Session


def test_create_tables_and_insert(tmp_path):
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        listing = Listing(
            source="591",
            source_id="12345",
            title="測試套房",
            price=10000,
            city="高雄市",
            district="三民區",
            url="https://rent.591.com.tw/12345",
        )
        session.add(listing)
        session.commit()

        result = session.query(Listing).first()
        assert result.title == "測試套房"
        assert result.price == 10000
        assert result.source == "591"


def test_upsert_deduplicates(tmp_path):
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        listing1 = Listing(source="591", source_id="12345", title="v1", price=10000)
        session.add(listing1)
        session.commit()

    with Session(engine) as session:
        from tw_rent_radar.db import upsert_listing
        upsert_listing(session, source="591", source_id="12345", title="v2", price=9000)
        session.commit()

        results = session.query(Listing).all()
        assert len(results) == 1
        assert results[0].title == "v2"
        assert results[0].price == 9000
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tw_rent_radar.db'`

**Step 3: Write db.py**

```python
# src/tw_rent_radar/db.py
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, DateTime, Integer, Real, Text, UniqueConstraint,
    create_engine as _create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session  # noqa: F401


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    source = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    title = Column(Text)
    price = Column(Integer)
    city = Column(Text)
    district = Column(Text)
    address = Column(Text)
    size = Column(Real)
    rooms = Column(Text)
    type = Column(Text)
    floor = Column(Text)
    contact = Column(Text)
    phone = Column(Text)
    url = Column(Text)
    images = Column(Text)
    description = Column(Text)
    amenities = Column(Text)
    raw_data = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("source", "source_id"),)

    def to_dict(self, fields: list[str] | None = None) -> dict:
        data = {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "price": self.price,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "size": self.size,
            "rooms": self.rooms,
            "type": self.type,
            "floor": self.floor,
            "contact": self.contact,
            "phone": self.phone,
            "url": self.url,
            "images": json.loads(self.images) if self.images else [],
            "amenities": json.loads(self.amenities) if self.amenities else [],
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if fields:
            return {k: v for k, v in data.items() if k in fields}
        return data


DEFAULT_DB_PATH = Path("radar.db")


def get_engine(db_path: str | None = None):
    path = db_path or str(DEFAULT_DB_PATH)
    return _create_engine(f"sqlite:///{path}")


def create_tables(engine):
    Base.metadata.create_all(engine)


def upsert_listing(session: Session, **data):
    existing = (
        session.query(Listing)
        .filter_by(source=data["source"], source_id=data["source_id"])
        .first()
    )
    if existing:
        for key, value in data.items():
            if key not in ("source", "source_id"):
                setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc)
        return existing
    else:
        listing = Listing(**data)
        session.add(listing)
        return listing
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/tw_rent_radar/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer with Listing model and upsert"
```

---

### Task 3: Output Layer

**Files:**
- Create: `src/tw_rent_radar/output.py`
- Create: `tests/test_output.py`

**Step 1: Write the failing test**

```python
# tests/test_output.py
import json

from tw_rent_radar.output import format_json, format_table


def test_format_json_full():
    listings = [
        {"id": 1, "title": "套房A", "price": 8000, "city": "高雄市"},
        {"id": 2, "title": "套房B", "price": 12000, "city": "台北市"},
    ]
    result = format_json(listings)
    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "套房A"


def test_format_json_with_fields():
    listings = [
        {"id": 1, "title": "套房A", "price": 8000, "city": "高雄市", "url": "https://example.com"},
    ]
    result = format_json(listings, fields=["title", "price"])
    parsed = json.loads(result)
    assert list(parsed[0].keys()) == ["title", "price"]


def test_format_table_returns_string():
    listings = [
        {"id": 1, "source": "591", "title": "套房A", "price": 8000, "city": "高雄市", "rooms": "1房", "url": "https://example.com"},
    ]
    result = format_table(listings)
    assert "套房A" in result
    assert "8,000" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_output.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write output.py**

```python
# src/tw_rent_radar/output.py
import json
from io import StringIO

from rich.console import Console
from rich.table import Table


def format_json(listings: list[dict], fields: list[str] | None = None) -> str:
    if fields:
        listings = [{k: v for k, v in item.items() if k in fields} for item in listings]
    return json.dumps(listings, ensure_ascii=False, indent=2)


TABLE_COLUMNS = ["id", "source", "title", "price", "city", "district", "rooms", "size", "url"]


def format_table(listings: list[dict], columns: list[str] | None = None) -> str:
    cols = columns or TABLE_COLUMNS
    table = Table(show_header=True, header_style="bold cyan")
    for col in cols:
        if col == "price":
            table.add_column(col, justify="right")
        elif col == "size":
            table.add_column(col, justify="right")
        else:
            table.add_column(col)

    for item in listings:
        row = []
        for col in cols:
            val = item.get(col)
            if col == "price" and val is not None:
                row.append(f"{val:,}")
            elif col == "url" and val:
                # Truncate long URLs
                row.append(val[:50] + "..." if len(val) > 50 else val)
            elif val is None:
                row.append("-")
            else:
                row.append(str(val))
        table.add_row(*row)

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=160)
    console.print(table)
    return buf.getvalue()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_output.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/tw_rent_radar/output.py tests/test_output.py
git commit -m "feat: add output layer with Rich table and JSON formatters"
```

---

### Task 4: Crawler Base Class

**Files:**
- Create: `src/tw_rent_radar/crawlers/base.py`
- Create: `tests/test_crawlers_base.py`

**Step 1: Write the failing test**

```python
# tests/test_crawlers_base.py
import pytest
from tw_rent_radar.crawlers.base import BaseCrawler


class FakeCrawler(BaseCrawler):
    source_name = "fake"

    async def crawl(self, **filters):
        return [
            {
                "source": self.source_name,
                "source_id": "1",
                "title": "Fake listing",
                "price": 5000,
            }
        ]


@pytest.mark.asyncio
async def test_crawler_returns_listings():
    crawler = FakeCrawler()
    results = await crawler.crawl()
    assert len(results) == 1
    assert results[0]["source"] == "fake"


def test_base_crawler_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseCrawler()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawlers_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write base.py**

```python
# src/tw_rent_radar/crawlers/base.py
from abc import ABC, abstractmethod


class BaseCrawler(ABC):
    source_name: str = ""

    @abstractmethod
    async def crawl(self, **filters) -> list[dict]:
        """Crawl listings. Return list of dicts matching the Listing schema."""
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawlers_base.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/tw_rent_radar/crawlers/base.py tests/test_crawlers_base.py
git commit -m "feat: add BaseCrawler abstract class"
```

---

### Task 5: CLI Skeleton

**Files:**
- Create: `src/tw_rent_radar/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
from click.testing import CliRunner
from tw_rent_radar.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "tw-rent-radar" in result.output.lower() or "Usage" in result.output


def test_search_no_results(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code == 0


def test_search_json_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--json", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code == 0
    assert result.output.strip() == "[]"


def test_stats_empty_db(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "--db", str(tmp_path / "empty.db")])
    assert result.exit_code == 0


def test_list_sources():
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "sources"])
    assert result.exit_code == 0
    assert "591" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write cli.py**

```python
# src/tw_rent_radar/cli.py
import asyncio
import json

import click
from rich.console import Console

from tw_rent_radar.db import Session, create_tables, get_engine, Listing
from tw_rent_radar.output import format_json, format_table

console = Console()

SOURCES = {
    "591": "rent.591.com.tw — 591 租屋網",
    "rakuya": "rakuya.com.tw — 樂屋網",
    "fcrent": "fcrent.tw — 方齊物業",
    "fb_group": "Facebook 租屋社團",
    "fb_market": "Facebook Marketplace",
}


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """tw-rent-radar — 台灣多平台租屋資料蒐集工具"""
    pass


# --- crawl ---


@cli.command()
@click.argument("source", type=click.Choice(list(SOURCES.keys()) + ["all"]))
@click.option("--city", help="縣市，例如 高雄市")
@click.option("--db", "db_path", default=None, hidden=True)
def crawl(source, city, db_path):
    """爬取租屋資料"""
    console.print(f"[bold]Crawling {source}...[/bold]")
    # Crawler dispatch will be added per-platform in later tasks


# --- search ---


@cli.command()
@click.option("--city", help="縣市")
@click.option("--district", help="區域")
@click.option("--max-price", type=int, help="最高月租金")
@click.option("--min-price", type=int, help="最低月租金")
@click.option("--rooms", help="房間數，例如 2")
@click.option("--type", "listing_type", help="類型：整層/套房/雅房")
@click.option("--source", help="來源平台")
@click.option("--json", "as_json", is_flag=True, help="JSON 輸出")
@click.option("--fields", help="JSON 欄位篩選，逗號分隔")
@click.option("--db", "db_path", default=None, hidden=True)
def search(city, district, max_price, min_price, rooms, listing_type, source, as_json, fields, db_path):
    """搜尋租屋物件"""
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
            query = query.filter(Listing.rooms.contains(rooms))
        if listing_type:
            query = query.filter(Listing.type == listing_type)
        if source:
            query = query.filter(Listing.source == source)

        results = query.all()
        field_list = fields.split(",") if fields else None
        listings = [r.to_dict(field_list) for r in results]

    if as_json:
        click.echo(format_json(listings, field_list))
    elif listings:
        click.echo(format_table(listings))
    else:
        console.print("[dim]No listings found.[/dim]")


# --- show ---


@cli.command()
@click.argument("listing_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="JSON 輸出")
@click.option("--db", "db_path", default=None, hidden=True)
def show(listing_id, as_json, db_path):
    """查看單一物件詳情"""
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        listing = session.query(Listing).filter_by(id=listing_id).first()
        if not listing:
            console.print(f"[red]Listing {listing_id} not found.[/red]")
            raise SystemExit(1)

        data = listing.to_dict()

    if as_json:
        click.echo(format_json([data]))
    else:
        for key, val in data.items():
            if val and key != "raw_data":
                console.print(f"[bold]{key}:[/bold] {val}")


# --- list ---


@cli.group("list")
def list_cmd():
    """列出相關資訊"""
    pass


@list_cmd.command("sources")
def list_sources():
    """列出支援的平台"""
    for key, desc in SOURCES.items():
        console.print(f"  [bold cyan]{key:12s}[/bold cyan] {desc}")


# --- stats ---


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="JSON 輸出")
@click.option("--db", "db_path", default=None, hidden=True)
def stats(as_json, db_path):
    """各平台物件數量統計"""
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        from sqlalchemy import func
        rows = (
            session.query(Listing.source, func.count(Listing.id))
            .group_by(Listing.source)
            .all()
        )
        data = {source: count for source, count in rows}
        total = sum(data.values())

    if as_json:
        click.echo(json.dumps({"sources": data, "total": total}, ensure_ascii=False, indent=2))
    else:
        for source, count in data.items():
            console.print(f"  [bold cyan]{source:12s}[/bold cyan] {count}")
        console.print(f"  [bold]{'total':12s}[/bold] {total}")


# --- db ---


@cli.group()
def db():
    """資料庫管理"""
    pass


@db.command("reset")
@click.option("--db", "db_path", default=None, hidden=True)
@click.confirmation_option(prompt="確定要清空所有資料嗎？")
def db_reset(db_path):
    """清空資料庫"""
    engine = get_engine(db_path)
    from tw_rent_radar.db import Base
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    console.print("[green]Database reset.[/green]")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: 5 passed

**Step 5: Verify CLI works end-to-end**

```bash
tw-rent-radar --help
tw-rent-radar list sources
tw-rent-radar search
tw-rent-radar stats
```

**Step 6: Commit**

```bash
git add src/tw_rent_radar/cli.py tests/test_cli.py
git commit -m "feat: add CLI with search, show, stats, list commands"
```

---

### Task 6: fcrent Crawler (Easiest Platform)

**Files:**
- Create: `src/tw_rent_radar/crawlers/fcrent.py`
- Create: `tests/test_crawlers_fcrent.py`

**Step 1: Write the failing test**

Test with a mock HTML page containing `__NEXT_DATA__` JSON, not a live request.

```python
# tests/test_crawlers_fcrent.py
import json

from tw_rent_radar.crawlers.fcrent import FcrentCrawler


SAMPLE_NEXT_DATA = {
    "props": {
        "pageProps": {
            "object": {
                "id": "YFDIpopHGnXUMhbccoBa",
                "title": "可補助|近衛武營2房1廳",
                "price": 16000,
                "city": "高雄市",
                "district": "苓雅區",
                "address": "高雄市苓雅區",
                "size": 20,
                "rooms": "2房1廳2衛",
                "type": "整層住家",
                "floor": "2F/5F",
                "contact": "許小姐",
                "phone": "0985-583-670",
                "images": ["https://example.com/img1.jpg"],
                "description": "近捷運、近輕軌",
                "amenities": ["冰箱", "洗衣機", "電視", "冷氣"],
            }
        }
    }
}


def test_parse_next_data():
    crawler = FcrentCrawler()
    html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(SAMPLE_NEXT_DATA)}</script></html>'
    result = crawler.parse_listing_page(html)
    assert result["source"] == "fcrent"
    assert result["source_id"] == "YFDIpopHGnXUMhbccoBa"
    assert result["price"] == 16000
    assert result["city"] == "高雄市"


def test_parse_next_data_missing():
    crawler = FcrentCrawler()
    html = "<html><body>No data</body></html>"
    result = crawler.parse_listing_page(html)
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawlers_fcrent.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write fcrent.py**

```python
# src/tw_rent_radar/crawlers/fcrent.py
import json
import re

from tw_rent_radar.crawlers.base import BaseCrawler


class FcrentCrawler(BaseCrawler):
    source_name = "fcrent"
    base_url = "https://fcrent.tw"

    def parse_listing_page(self, html: str) -> dict | None:
        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return None

        data = json.loads(match.group(1))
        obj = data.get("props", {}).get("pageProps", {}).get("object")
        if not obj:
            return None

        return {
            "source": self.source_name,
            "source_id": str(obj.get("id", "")),
            "title": obj.get("title"),
            "price": obj.get("price"),
            "city": obj.get("city"),
            "district": obj.get("district"),
            "address": obj.get("address"),
            "size": obj.get("size"),
            "rooms": obj.get("rooms"),
            "type": obj.get("type"),
            "floor": obj.get("floor"),
            "contact": obj.get("contact"),
            "phone": obj.get("phone"),
            "url": f"{self.base_url}/object/{obj.get('id', '')}",
            "images": json.dumps(obj.get("images", []), ensure_ascii=False),
            "description": obj.get("description"),
            "amenities": json.dumps(obj.get("amenities", []), ensure_ascii=False),
            "raw_data": json.dumps(obj, ensure_ascii=False),
        }

    async def crawl(self, **filters) -> list[dict]:
        from playwright.async_api import async_playwright

        listings = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # fcrent.tw is a small site — crawl the listing index page
            # For now, crawl a known set of URLs or discover from index
            await page.goto(self.base_url, wait_until="networkidle")
            html = await page.content()

            # Find all object links on the page
            links = await page.eval_on_selector_all(
                'a[href*="/object/"]',
                "els => els.map(e => e.href)",
            )
            unique_links = list(set(links))

            for link in unique_links:
                await page.goto(link, wait_until="networkidle")
                detail_html = await page.content()
                parsed = self.parse_listing_page(detail_html)
                if parsed:
                    listings.append(parsed)

            await browser.close()
        return listings
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawlers_fcrent.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/tw_rent_radar/crawlers/fcrent.py tests/test_crawlers_fcrent.py
git commit -m "feat: add fcrent crawler with __NEXT_DATA__ parser"
```

---

### Task 7: Wire fcrent Crawler into CLI

**Files:**
- Modify: `src/tw_rent_radar/cli.py`
- Create: `tests/test_cli_crawl.py`

**Step 1: Write the failing test**

```python
# tests/test_cli_crawl.py
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
from tw_rent_radar.cli import cli


@patch("tw_rent_radar.cli.run_crawler")
def test_crawl_fcrent(mock_run):
    mock_run.return_value = 3
    runner = CliRunner()
    result = runner.invoke(cli, ["crawl", "fcrent", "--db", ":memory:"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_crawl.py -v`
Expected: FAIL — `ImportError` (run_crawler doesn't exist)

**Step 3: Add run_crawler to cli.py**

Add this function and update the `crawl` command in `src/tw_rent_radar/cli.py`:

After the `SOURCES` dict, add:

```python
from tw_rent_radar.crawlers.fcrent import FcrentCrawler


CRAWLER_MAP = {
    "fcrent": FcrentCrawler,
}


def run_crawler(source: str, db_path: str | None, **filters) -> int:
    crawler_cls = CRAWLER_MAP.get(source)
    if not crawler_cls:
        console.print(f"[yellow]Crawler for '{source}' not yet implemented.[/yellow]")
        return 0

    crawler = crawler_cls()
    listings = asyncio.run(crawler.crawl(**filters))

    engine = get_engine(db_path)
    create_tables(engine)

    count = 0
    with Session(engine) as session:
        from tw_rent_radar.db import upsert_listing
        for item in listings:
            upsert_listing(session, **item)
            count += 1
        session.commit()

    console.print(f"[green]Saved {count} listings from {source}.[/green]")
    return count
```

Update the `crawl` command body:

```python
@cli.command()
@click.argument("source", type=click.Choice(list(SOURCES.keys()) + ["all"]))
@click.option("--city", help="縣市，例如 高雄市")
@click.option("--db", "db_path", default=None, hidden=True)
def crawl(source, city, db_path):
    """爬取租屋資料"""
    filters = {}
    if city:
        filters["city"] = city

    if source == "all":
        for src in CRAWLER_MAP:
            run_crawler(src, db_path, **filters)
    else:
        run_crawler(source, db_path, **filters)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_crawl.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add src/tw_rent_radar/cli.py tests/test_cli_crawl.py
git commit -m "feat: wire fcrent crawler into CLI crawl command"
```

---

### Task 8: 591 Crawler

**Files:**
- Create: `src/tw_rent_radar/crawlers/rent591.py`
- Create: `tests/test_crawlers_591.py`

**Step 1: Write the failing test**

```python
# tests/test_crawlers_591.py
import json

from tw_rent_radar.crawlers.rent591 import Rent591Crawler


SAMPLE_LIST_RESPONSE = {
    "data": {
        "data": [
            {
                "post_id": 12345678,
                "title": "近捷運三房公寓",
                "price": "15,000 元/月",
                "section_name": "三民區",
                "kind_name": "整層住家",
                "area": "30",
                "floor_str": "3F/7F",
                "room": "3",
                "cases_id": 12345678,
            }
        ]
    }
}


def test_parse_list_item():
    crawler = Rent591Crawler()
    item = SAMPLE_LIST_RESPONSE["data"]["data"][0]
    result = crawler.parse_list_item(item, city="高雄市")
    assert result["source"] == "591"
    assert result["source_id"] == "12345678"
    assert result["price"] == 15000
    assert result["city"] == "高雄市"
    assert result["district"] == "三民區"


def test_parse_price_formats():
    crawler = Rent591Crawler()
    assert crawler.parse_price("15,000 元/月") == 15000
    assert crawler.parse_price("8000") == 8000
    assert crawler.parse_price("含管理費 12,500 元/月") == 12500
    assert crawler.parse_price("面議") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawlers_591.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write rent591.py**

```python
# src/tw_rent_radar/crawlers/rent591.py
import json
import re

from tw_rent_radar.crawlers.base import BaseCrawler

REGION_MAP = {
    "台北市": 1, "新北市": 3, "桃園市": 6, "新竹市": 4, "新竹縣": 5,
    "苗栗縣": 21, "台中市": 8, "彰化縣": 10, "南投縣": 11,
    "雲林縣": 12, "嘉義市": 13, "嘉義縣": 14, "台南市": 15,
    "高雄市": 17, "屏東縣": 19, "宜蘭縣": 22, "花蓮縣": 23,
    "台東縣": 24, "澎湖縣": 25, "金門縣": 26, "連江縣": 27,
    "基隆市": 2,
}


class Rent591Crawler(BaseCrawler):
    source_name = "591"
    list_url = "https://rent.591.com.tw/home/search/rsList"

    def parse_price(self, price_str: str) -> int | None:
        if not price_str or "面議" in price_str:
            return None
        numbers = re.findall(r"[\d,]+", str(price_str))
        if not numbers:
            return None
        return int(numbers[0].replace(",", ""))

    def parse_list_item(self, item: dict, city: str) -> dict:
        price_val = self.parse_price(str(item.get("price", "")))
        post_id = str(item.get("post_id") or item.get("cases_id", ""))

        return {
            "source": self.source_name,
            "source_id": post_id,
            "title": item.get("title"),
            "price": price_val,
            "city": city,
            "district": item.get("section_name"),
            "rooms": f"{item.get('room', '')}房" if item.get("room") else None,
            "type": item.get("kind_name"),
            "size": float(item["area"]) if item.get("area") else None,
            "floor": item.get("floor_str"),
            "url": f"https://rent.591.com.tw/rent-detail-{post_id}.html",
            "raw_data": json.dumps(item, ensure_ascii=False),
        }

    async def crawl(self, **filters) -> list[dict]:
        from playwright.async_api import async_playwright

        city = filters.get("city", "高雄市")
        region_id = REGION_MAP.get(city, 17)
        max_pages = filters.get("max_pages", 5)

        listings = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Set region cookie
            await context.add_cookies([{
                "name": "urlJumpIp",
                "value": str(region_id),
                "domain": ".591.com.tw",
                "path": "/",
            }])

            page = await context.new_page()

            # First visit to get CSRF token
            await page.goto("https://rent.591.com.tw/", wait_until="networkidle")
            csrf_token = await page.evaluate(
                "() => document.querySelector('meta[name=\"csrf-token\"]')?.content"
            )

            for page_num in range(max_pages):
                first_row = page_num * 30
                url = (
                    f"{self.list_url}?is_new_list=1&type=1&kind=0"
                    f"&region={region_id}&firstRow={first_row}"
                )

                response = await page.evaluate(
                    """async (url) => {
                        const res = await fetch(url, {
                            headers: { 'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || '' }
                        });
                        return await res.json();
                    }""",
                    url,
                )

                items = response.get("data", {}).get("data", [])
                if not items:
                    break

                for item in items:
                    parsed = self.parse_list_item(item, city=city)
                    listings.append(parsed)

            await browser.close()
        return listings
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawlers_591.py -v`
Expected: 2 passed

**Step 5: Wire into CLI — add to CRAWLER_MAP in cli.py**

```python
from tw_rent_radar.crawlers.rent591 import Rent591Crawler

CRAWLER_MAP = {
    "fcrent": FcrentCrawler,
    "591": Rent591Crawler,
}
```

**Step 6: Commit**

```bash
git add src/tw_rent_radar/crawlers/rent591.py tests/test_crawlers_591.py src/tw_rent_radar/cli.py
git commit -m "feat: add 591 rental crawler"
```

---

### Task 9: Rakuya Crawler

**Files:**
- Create: `src/tw_rent_radar/crawlers/rakuya.py`
- Create: `tests/test_crawlers_rakuya.py`

**Step 1: Write the failing test**

```python
# tests/test_crawlers_rakuya.py
from tw_rent_radar.crawlers.rakuya import RakuyaCrawler


SAMPLE_HTML = """
<div class="item-info">
    <h3 class="item-title">三民區兩房公寓</h3>
    <span class="item-price">12,000</span>
    <span class="item-area">25 坪</span>
    <span class="item-address">高雄市三民區建工路100號</span>
    <span class="item-room">2房1廳1衛</span>
    <span class="item-type">公寓</span>
</div>
"""


def test_rakuya_crawler_has_source_name():
    crawler = RakuyaCrawler()
    assert crawler.source_name == "rakuya"
```

Note: Rakuya's actual HTML structure needs to be discovered by running the browser. This test is a placeholder. The real parsing logic will be refined after inspecting live pages during development. The important thing is the crawler class exists and follows the BaseCrawler interface.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawlers_rakuya.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write rakuya.py skeleton**

```python
# src/tw_rent_radar/crawlers/rakuya.py
import json
import re

from tw_rent_radar.crawlers.base import BaseCrawler


class RakuyaCrawler(BaseCrawler):
    source_name = "rakuya"
    base_url = "https://www.rakuya.com.tw"
    search_url = "https://www.rakuya.com.tw/rent/rent_list"

    def parse_price(self, text: str) -> int | None:
        numbers = re.findall(r"[\d,]+", text)
        if not numbers:
            return None
        return int(numbers[0].replace(",", ""))

    def parse_listing_element(self, data: dict) -> dict:
        return {
            "source": self.source_name,
            "source_id": str(data.get("id", "")),
            "title": data.get("title"),
            "price": data.get("price"),
            "city": data.get("city"),
            "district": data.get("district"),
            "address": data.get("address"),
            "size": data.get("size"),
            "rooms": data.get("rooms"),
            "type": data.get("type"),
            "floor": data.get("floor"),
            "url": data.get("url"),
            "images": json.dumps(data.get("images", []), ensure_ascii=False),
            "raw_data": json.dumps(data, ensure_ascii=False),
        }

    async def crawl(self, **filters) -> list[dict]:
        from playwright.async_api import async_playwright

        city = filters.get("city", "高雄市")
        max_pages = filters.get("max_pages", 5)

        listings = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate to rent listing page
            # Actual URL params and selectors need refinement after inspecting live site
            await page.goto(
                f"{self.search_url}?city={city}&page=1",
                wait_until="networkidle",
            )

            # TODO: Extract listing elements from page
            # This needs live site inspection to determine correct selectors
            # Placeholder: will be refined in Task 9 implementation

            await browser.close()
        return listings
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawlers_rakuya.py -v`
Expected: 1 passed

**Step 5: Wire into CLI**

Add to CRAWLER_MAP in `cli.py`:

```python
from tw_rent_radar.crawlers.rakuya import RakuyaCrawler

CRAWLER_MAP = {
    "fcrent": FcrentCrawler,
    "591": Rent591Crawler,
    "rakuya": RakuyaCrawler,
}
```

**Step 6: Commit**

```bash
git add src/tw_rent_radar/crawlers/rakuya.py tests/test_crawlers_rakuya.py src/tw_rent_radar/cli.py
git commit -m "feat: add rakuya crawler skeleton (selectors TBD from live inspection)"
```

---

### Task 10: Facebook Crawlers

**Files:**
- Create: `src/tw_rent_radar/crawlers/fb_group.py`
- Create: `src/tw_rent_radar/crawlers/fb_market.py`
- Create: `src/tw_rent_radar/crawlers/fb_auth.py`
- Create: `tests/test_crawlers_fb.py`

**Step 1: Write the failing test**

```python
# tests/test_crawlers_fb.py
from tw_rent_radar.crawlers.fb_group import FbGroupCrawler
from tw_rent_radar.crawlers.fb_market import FbMarketCrawler
from tw_rent_radar.crawlers.fb_auth import FB_SESSION_DIR


def test_fb_group_has_source_name():
    crawler = FbGroupCrawler()
    assert crawler.source_name == "fb_group"


def test_fb_market_has_source_name():
    crawler = FbMarketCrawler()
    assert crawler.source_name == "fb_market"


def test_fb_session_dir_defined():
    assert FB_SESSION_DIR is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawlers_fb.py -v`
Expected: FAIL

**Step 3: Write fb_auth.py**

```python
# src/tw_rent_radar/crawlers/fb_auth.py
from pathlib import Path

FB_SESSION_DIR = Path("fb_session")


async def ensure_fb_session(playwright) -> "BrowserContext":
    """Launch browser with saved Facebook session. Prompts login if no session exists."""
    FB_SESSION_DIR.mkdir(exist_ok=True)
    state_file = FB_SESSION_DIR / "state.json"

    browser = await playwright.chromium.launch(headless=False)

    if state_file.exists():
        context = await browser.new_context(storage_state=str(state_file))
        # Verify session is still valid
        page = await context.new_page()
        await page.goto("https://www.facebook.com/", wait_until="networkidle")
        if "login" not in page.url.lower():
            return context
        await context.close()

    # Session expired or doesn't exist — interactive login
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto("https://www.facebook.com/login", wait_until="networkidle")

    print("\n=== Facebook Login ===")
    print("Please log in to Facebook in the browser window.")
    print("Press Enter here after you've logged in successfully...")
    input()

    await context.storage_state(path=str(state_file))
    return context
```

**Step 4: Write fb_group.py**

```python
# src/tw_rent_radar/crawlers/fb_group.py
import json
import re

from tw_rent_radar.crawlers.base import BaseCrawler


class FbGroupCrawler(BaseCrawler):
    source_name = "fb_group"

    def parse_price_from_text(self, text: str) -> int | None:
        patterns = [
            r"(\d{1,3}(?:,\d{3})*)\s*(?:元|\/月|元\/月)",
            r"(?:月租|租金)[：:]\s*(\d{1,3}(?:,\d{3})*)",
            r"\$\s*(\d{1,3}(?:,\d{3})*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1).replace(",", ""))
        return None

    async def crawl(self, **filters) -> list[dict]:
        from playwright.async_api import async_playwright
        from tw_rent_radar.crawlers.fb_auth import ensure_fb_session

        group_name = filters.get("group")
        if not group_name:
            print("Usage: tw-rent-radar crawl fb_group --group '高雄租屋'")
            return []

        listings = []
        async with async_playwright() as p:
            context = await ensure_fb_session(p)
            page = await context.new_page()

            # Search for the group
            await page.goto(
                f"https://www.facebook.com/groups/search/?q={group_name}",
                wait_until="networkidle",
            )

            # TODO: Extract posts from group feed
            # Facebook's DOM structure changes frequently
            # This needs live inspection and will be refined during implementation

            await context.close()
        return listings
```

**Step 5: Write fb_market.py**

```python
# src/tw_rent_radar/crawlers/fb_market.py
import json

from tw_rent_radar.crawlers.base import BaseCrawler


class FbMarketCrawler(BaseCrawler):
    source_name = "fb_market"
    marketplace_url = "https://www.facebook.com/marketplace/category/propertyrentals"

    async def crawl(self, **filters) -> list[dict]:
        from playwright.async_api import async_playwright
        from tw_rent_radar.crawlers.fb_auth import ensure_fb_session

        city = filters.get("city", "")

        listings = []
        async with async_playwright() as p:
            context = await ensure_fb_session(p)
            page = await context.new_page()

            await page.goto(self.marketplace_url, wait_until="networkidle")

            # TODO: Extract marketplace listings
            # Needs live inspection for correct selectors

            await context.close()
        return listings
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_crawlers_fb.py -v`
Expected: 3 passed

**Step 7: Wire into CLI**

Add to CRAWLER_MAP in `cli.py`:

```python
from tw_rent_radar.crawlers.fb_group import FbGroupCrawler
from tw_rent_radar.crawlers.fb_market import FbMarketCrawler

CRAWLER_MAP = {
    "fcrent": FcrentCrawler,
    "591": Rent591Crawler,
    "rakuya": RakuyaCrawler,
    "fb_group": FbGroupCrawler,
    "fb_market": FbMarketCrawler,
}
```

Add `--group` option to crawl command:

```python
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
```

**Step 8: Commit**

```bash
git add src/tw_rent_radar/crawlers/fb_auth.py src/tw_rent_radar/crawlers/fb_group.py src/tw_rent_radar/crawlers/fb_market.py tests/test_crawlers_fb.py src/tw_rent_radar/cli.py
git commit -m "feat: add Facebook group and marketplace crawler skeletons with auth"
```

---

### Task 11: Update crawlers __init__.py and Final Integration

**Files:**
- Modify: `src/tw_rent_radar/crawlers/__init__.py`
- Create: `tests/test_integration.py`

**Step 1: Write the failing test**

```python
# tests/test_integration.py
import json

from click.testing import CliRunner
from tw_rent_radar.cli import cli
from tw_rent_radar.db import get_engine, create_tables, Session, Listing, upsert_listing


def test_full_workflow(tmp_path):
    """Insert data, then search via CLI."""
    db_path = str(tmp_path / "test.db")
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(session,
            source="591", source_id="111", title="三民區套房",
            price=8000, city="高雄市", district="三民區",
            rooms="1房", type="套房",
            url="https://rent.591.com.tw/111",
        )
        upsert_listing(session,
            source="fcrent", source_id="aaa", title="苓雅兩房",
            price=16000, city="高雄市", district="苓雅區",
            rooms="2房1廳", type="整層住家",
            url="https://fcrent.tw/object/aaa",
        )
        upsert_listing(session,
            source="591", source_id="222", title="台北套房",
            price=12000, city="台北市", district="大安區",
            rooms="1房", type="套房",
            url="https://rent.591.com.tw/222",
        )
        session.commit()

    runner = CliRunner()

    # Search by city
    result = runner.invoke(cli, ["search", "--city", "高雄市", "--json", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2

    # Search with max price
    result = runner.invoke(cli, ["search", "--max-price", "10000", "--json", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["title"] == "三民區套房"

    # Search with fields filter
    result = runner.invoke(cli, ["search", "--json", "--fields", "title,price", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 3
    assert list(data[0].keys()) == ["title", "price"]

    # Stats
    result = runner.invoke(cli, ["stats", "--json", "--db", db_path])
    assert result.exit_code == 0
    stats = json.loads(result.output)
    assert stats["total"] == 3

    # Show single listing
    result = runner.invoke(cli, ["show", "1", "--json", "--db", db_path])
    assert result.exit_code == 0

    # Table output (human mode)
    result = runner.invoke(cli, ["search", "--city", "高雄市", "--db", db_path])
    assert result.exit_code == 0
    assert "三民區套房" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_integration.py -v`
Expected: FAIL (or might pass if all prior tasks are done — run to verify)

**Step 3: Update crawlers __init__.py**

```python
# src/tw_rent_radar/crawlers/__init__.py
from tw_rent_radar.crawlers.fcrent import FcrentCrawler
from tw_rent_radar.crawlers.rent591 import Rent591Crawler
from tw_rent_radar.crawlers.rakuya import RakuyaCrawler
from tw_rent_radar.crawlers.fb_group import FbGroupCrawler
from tw_rent_radar.crawlers.fb_market import FbMarketCrawler

__all__ = [
    "FcrentCrawler",
    "Rent591Crawler",
    "RakuyaCrawler",
    "FbGroupCrawler",
    "FbMarketCrawler",
]
```

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 5: Test CLI manually**

```bash
tw-rent-radar --help
tw-rent-radar --version
tw-rent-radar list sources
tw-rent-radar stats
tw-rent-radar search --json
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: complete CLI integration with all crawlers wired up"
```

---

## Task Dependency Graph

```
Task 1 (scaffolding)
  └── Task 2 (db)
       └── Task 3 (output)
            └── Task 4 (crawler base)
                 ├── Task 5 (CLI skeleton)
                 │    └── Task 7 (wire fcrent)
                 │         └── Task 8 (591) ──────┐
                 │              └── Task 9 (rakuya) ──┐
                 │                   └── Task 10 (fb) ─┤
                 └── Task 6 (fcrent crawler)           │
                                                       └── Task 11 (integration)
```

## Notes for Implementer

- **Rakuya and Facebook crawlers are skeletons.** Their CSS selectors and DOM parsing need live browser inspection. Run `playwright codegen https://www.rakuya.com.tw/rent/rent_list` to discover selectors interactively.
- **591 API may have changed.** If the list endpoint fails, use browser DevTools Network tab on `rent.591.com.tw` to find the current API format.
- **Facebook auth is interactive.** The first `crawl fb_group` or `crawl fb_market` will open a visible browser for login. After that, the session is reused.
- **All tests use `tmp_path` or mocks** — no live network calls in tests.
