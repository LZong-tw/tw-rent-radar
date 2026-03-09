# tw-rent-radar Design

## Overview

A local-friendly, multi-platform Taiwan rental listing CLI tool. Humans use it directly for formatted tables; LLMs invoke it with `--json` for structured data analysis — like `gh` or `glab`.

## CLI Interface

```bash
# Crawl
tw-rent-radar crawl 591 --city 高雄市
tw-rent-radar crawl rakuya --city 高雄市
tw-rent-radar crawl fcrent
tw-rent-radar crawl fb --group "高雄租屋"
tw-rent-radar crawl fb --marketplace --city 高雄市
tw-rent-radar crawl all --city 高雄市

# Search (human — table output)
tw-rent-radar search --city 高雄市 --max-price 15000 --rooms 2
tw-rent-radar search --district 三民區 --type 整層

# Search (LLM — JSON output)
tw-rent-radar search --city 高雄市 --max-price 15000 --json
tw-rent-radar search --json --fields title,price,address,url

# View single listing
tw-rent-radar show <id>
tw-rent-radar show <id> --json

# Management
tw-rent-radar list sources
tw-rent-radar stats
tw-rent-radar db reset
```

## Project Structure

```
tw-rent-radar/
├── src/
│   └── tw_rent_radar/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entry point
│       ├── db.py               # SQLite + SQLAlchemy models
│       ├── output.py           # Rich tables / JSON output
│       └── crawlers/
│           ├── __init__.py
│           ├── base.py         # Crawler base class (unified interface)
│           ├── rent591.py      # 591
│           ├── rakuya.py       # rakuya (樂屋網)
│           ├── fcrent.py       # fcrent (方齊物業)
│           ├── fb_group.py     # Facebook groups
│           └── fb_market.py    # Facebook Marketplace
├── pyproject.toml              # Package definition + CLI entry point
├── radar.db                    # SQLite (gitignored)
└── README.md
```

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python | Best crawler ecosystem |
| Crawler | Playwright | Unified handling: anti-scraping (rakuya 403), login (Facebook), SPA (591) |
| Database | SQLite + SQLAlchemy | Zero-install, single file |
| CLI | Click | Subcommand structure, parameter validation |
| Human output | Rich | Beautiful terminal tables |
| JSON output | stdlib json | `--json` flag with optional `--fields` filtering |
| Packaging | pyproject.toml + pip install -e . | Install once, use `tw-rent-radar` command globally |

## Data Schema

```sql
CREATE TABLE listings (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,          -- 591 / rakuya / fcrent / fb_group / fb_market
    source_id   TEXT NOT NULL,          -- Original platform listing ID
    title       TEXT,
    price       INTEGER,               -- Monthly rent (NTD)
    city        TEXT,
    district    TEXT,
    address     TEXT,
    size        REAL,                   -- Ping (坪)
    rooms       TEXT,                   -- e.g. "2房1廳1衛"
    type        TEXT,                   -- 整層 / 套房 / 雅房
    floor       TEXT,
    contact     TEXT,
    phone       TEXT,
    url         TEXT,
    images      TEXT,                   -- JSON array of image URLs
    description TEXT,
    amenities   TEXT,                   -- JSON array, e.g. ["冷氣","洗衣機"]
    raw_data    TEXT,                   -- Full original data as JSON
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
```

## Crawler Architecture

Each crawler implements a base class:

```python
class BaseCrawler(ABC):
    @abstractmethod
    async def crawl(self, **filters) -> list[dict]:
        """Crawl listings, return normalized dicts matching the schema."""
        ...
```

Pipeline: crawl → normalize to schema → upsert into SQLite (deduplicate on source + source_id).

## Platform-Specific Notes

### 591 (rent.591.com.tw)
- API-based listing pages (JSON response), detail pages need JS rendering
- Anti-scraping: cookie-based region selection, CSRF token
- Reference: ceshine/591scraper (2025 update)

### Rakuya (rakuya.com.tw)
- Returns 403 on direct HTTP requests
- Requires Playwright headless browser
- SSR or CSR TBD (need browser inspection)

### fcrent (fcrent.tw)
- Next.js SSR — data embedded in `__NEXT_DATA__` script tag
- Easiest to scrape: parse JSON from HTML, no browser needed (but use Playwright for consistency)
- Object ID format: 22-char random string

### Facebook Groups
- Requires login session (saved cookies)
- First-time setup: CLI guides user through browser login, saves session
- Unstructured post format — extract what's parseable (price, location from text)

### Facebook Marketplace
- Requires login session (shared with groups)
- More structured than groups (has price, location fields)
- Rate limiting required to avoid bans

## What's Kept from Original Project

- Pipeline pattern concept (crawl → normalize → store)
- Crawler base class abstraction (like Scrapy's Spider)
- Deduplication via unique constraint (source + source_id)

## What's Removed

- Scrapy → Playwright
- MongoDB → SQLite
- Flask API → not needed (CLI queries DB directly)
- Airflow → deferred (scheduling added later)
- Docker → not needed
