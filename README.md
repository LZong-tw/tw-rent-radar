# tw-rent-radar

Multi-platform Taiwan rental listing CLI tool.

Crawl listings from multiple Taiwanese rental platforms into a local SQLite database, then search and filter them from the terminal. Designed for both human use (Rich tables) and LLM integration (`--json` structured output).

## Features

- **Multi-platform crawling** -- 591, Rakuya, fcrent, Facebook Groups, Facebook Marketplace
- **Human-friendly output** -- Rich-formatted terminal tables with search and filtering
- **LLM-friendly output** -- `--json` flag on every query command for structured data
- **Local SQLite storage** -- zero-install database, single file (`radar.db`)
- **Deduplication** -- upsert on `(source, source_id)` so re-crawling updates existing records
- **Playwright-based** -- handles SPAs, anti-scraping, and login-gated sites uniformly

## Supported Platforms

| Platform | Key | Status | Notes |
|----------|-----|--------|-------|
| 591 租屋網 | `591` | Working | API-based with CSRF token handling |
| 樂屋網 (Rakuya) | `rakuya` | Working | Playwright stealth mode for Cloudflare bypass |
| 方齊物業 (fcrent) | `fcrent` | Working | Next.js SSR, parses `__NEXT_DATA__` |
| Facebook 租屋社團 | `fb_group` | Skeleton | Auth flow implemented, DOM selectors TBD |
| Facebook Marketplace | `fb_market` | Skeleton | Auth flow implemented, DOM selectors TBD |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/<your-username>/tw-rent-radar.git
cd tw-rent-radar

# Create a virtual environment (Python 3.12+)
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
source .venv/Scripts/activate    # Windows (Git Bash)

# Install in editable mode
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

## Usage

### `crawl` -- Crawl rental listings

```bash
# Crawl 591 listings for a specific city
tw-rent-radar crawl 591 --city 高雄市

# Crawl Rakuya
tw-rent-radar crawl rakuya --city 台北市

# Crawl fcrent (no city filter needed)
tw-rent-radar crawl fcrent

# Crawl a Facebook group
tw-rent-radar crawl fb_group --group "高雄租屋"

# Crawl all platforms at once
tw-rent-radar crawl all --city 高雄市
```

### `search` -- Search stored listings

```bash
# Human-readable table output (default)
tw-rent-radar search --city 高雄市 --max-price 15000
tw-rent-radar search --district 三民區 --type 整層
tw-rent-radar search --source 591 --min-price 8000 --max-price 20000

# JSON output
tw-rent-radar search --city 高雄市 --max-price 15000 --json

# Select specific fields
tw-rent-radar search --json --fields title,price,address,url
```

### `show` -- View a single listing

```bash
tw-rent-radar show 42
tw-rent-radar show 42 --json
```

### `stats` -- Database statistics

```bash
tw-rent-radar stats
tw-rent-radar stats --json
```

### `list sources` -- Show supported platforms

```bash
tw-rent-radar list sources
```

### `db reset` -- Reset the database

```bash
tw-rent-radar db reset
```

## For LLM Integration

tw-rent-radar is designed to work as a CLI tool that LLMs can invoke directly, similar to `gh` or `jq`. Every query command supports `--json` for structured output and `--fields` for selecting specific columns.

### Example workflow

```bash
# 1. Crawl fresh data
tw-rent-radar crawl 591 --city 高雄市

# 2. Query with structured output
tw-rent-radar search --city 高雄市 --max-price 12000 --json --fields title,price,district,url

# 3. Get details on a specific listing
tw-rent-radar show 15 --json

# 4. Check what data is available
tw-rent-radar stats --json
```

The `--json` output returns a JSON array of objects:

```json
[
  {
    "title": "三民區套房 近火車站",
    "price": 8500,
    "district": "三民區",
    "url": "https://rent.591.com.tw/rent-detail-12345678.html"
  }
]
```

### Data schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `source` | string | Platform key (`591`, `rakuya`, `fcrent`, `fb_group`, `fb_market`) |
| `source_id` | string | Original platform listing ID |
| `title` | string | Listing title |
| `price` | int | Monthly rent in NTD |
| `city` | string | City name (e.g. `高雄市`) |
| `district` | string | District name (e.g. `三民區`) |
| `address` | string | Full address |
| `size` | float | Size in ping (坪) |
| `rooms` | string | Layout (e.g. `2房1廳1衛`) |
| `type` | string | Listing type (整層 / 套房 / 雅房) |
| `floor` | string | Floor info |
| `contact` | string | Contact name |
| `phone` | string | Phone number |
| `url` | string | Original listing URL |
| `images` | array | Image URLs |
| `amenities` | array | Amenities list (e.g. `["冷氣", "洗衣機"]`) |
| `description` | string | Listing description |

## Development

```bash
# Run unit tests (excludes e2e tests by default)
pytest

# Run e2e tests (hits real websites, requires network)
pytest -m e2e

# Run all tests
pytest -m ""

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Pre-commit hooks (ruff + pytest, runs automatically on commit)
pre-commit install
pre-commit run --all-files
```

## Project Structure

```
src/tw_rent_radar/
├── __init__.py
├── cli.py                 # Click CLI entry point
├── db.py                  # SQLite + SQLAlchemy models
├── output.py              # Rich tables / JSON formatting
└── crawlers/
    ├── __init__.py
    ├── base.py            # Abstract base crawler class
    ├── rent591.py         # 591 租屋網
    ├── rakuya.py          # 樂屋網
    ├── fcrent.py          # 方齊物業
    ├── fb_auth.py         # Facebook session/cookie management
    ├── fb_group.py        # Facebook 租屋社團
    └── fb_market.py       # Facebook Marketplace
```

## License

MIT
