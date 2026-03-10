# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

**tw-rent-radar** is a multi-platform Taiwan rental listing CLI tool. It crawls rental listings from multiple Taiwanese platforms (591, Rakuya, fcrent, Facebook Groups, Facebook Marketplace), stores them in a local SQLite database, and provides search/filter/display capabilities through a command-line interface.

Target users: people looking for rental housing in Taiwan. All rental data fields use Traditional Chinese (zh-TW) conventions.

## Tech Stack

- **Language**: Python 3.12
- **CLI framework**: Click
- **Database**: SQLite via SQLAlchemy 2.0 ORM (declarative mapped columns)
- **Web crawling**: Playwright (async) with playwright-stealth for anti-bot bypass
- **HTTP requests**: requests (for geocoding API calls)
- **Output formatting**: Rich (tables, colored console output)
- **Linting/formatting**: Ruff (linter + formatter)
- **Testing**: pytest + pytest-asyncio + pytest-timeout
- **Pre-commit**: ruff (lint + format) + pytest
- **CI**: GitHub Actions (lint, format check, unit tests; E2E on manual dispatch only)
- **Package management**: pip with setuptools; `pyproject.toml` for all config

## Project Structure

```
tw-rent-radar/
  pyproject.toml                    # Package config, dependencies, ruff/pytest settings
  .pre-commit-config.yaml           # Ruff + pytest pre-commit hooks
  .github/workflows/ci.yml          # CI: lint, format, test, e2e (manual)
  src/tw_rent_radar/
    __init__.py
    cli.py                          # Click CLI: crawl, search, show, stats, list, db commands
    db.py                           # SQLAlchemy ORM: Listing model, upsert_listing, get_engine
    output.py                       # Rich table + JSON formatting
    geo.py                          # TGOS + Google Maps geocoding, Haversine distance
    crawlers/
      __init__.py                   # Re-exports all crawler classes
      base.py                       # BaseCrawler ABC (source_name, async crawl())
      rent591.py                    # 591 crawler: Playwright + CSRF token + API pagination
      rakuya.py                     # Rakuya crawler: Playwright + stealth + HTML parsing
      fcrent.py                     # fcrent crawler: Playwright + __NEXT_DATA__ JSON extraction
      fb_auth.py                    # Facebook session management (manual login, state persistence)
      fb_group.py                   # Facebook Group crawler (skeleton + price parser)
      fb_market.py                  # Facebook Marketplace crawler (skeleton)
  tests/
    test_crawlers_base.py           # BaseCrawler ABC contract tests
    test_crawlers_591.py            # 591 parse_list_item, parse_price, region map
    test_crawlers_rakuya.py         # Rakuya parse_price, parse_size, parse_listing_card, parse_detail_page
    test_crawlers_fcrent.py         # fcrent parse_listing_page with mock __NEXT_DATA__
    test_crawlers_fb.py             # Facebook crawlers: source names, price parsing, crawl skeletons
    test_db.py                      # SQLite create/insert/upsert deduplication
    test_cli.py                     # CLI smoke tests (help, search, stats, list sources)
    test_output.py                  # JSON + Rich table formatting
    test_integration.py             # Full workflow: insert data -> search via CLI -> verify
    test_e2e.py                     # E2E tests against live websites (marked with @pytest.mark.e2e)
  docs/plans/                       # Design and implementation plan documents
```

## Common Commands

All commands run from the project root.

### Setup

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash)
pip install -e ".[dev]"
playwright install chromium --with-deps
pre-commit install
```

### Development

```bash
source .venv/Scripts/activate        # Always activate venv first

# Run the CLI
tw-rent-radar --help
tw-rent-radar crawl 591 --city "高雄市"
tw-rent-radar crawl rakuya --city "台北市"
tw-rent-radar crawl all
tw-rent-radar search --city "高雄市" --max-price 15000
tw-rent-radar search --json --fields "title,price,city"
tw-rent-radar show 1
tw-rent-radar stats --json
tw-rent-radar list sources
tw-rent-radar db reset
```

### Testing

```bash
# Unit tests (default — excludes e2e)
pytest -v

# Single test file
pytest tests/test_crawlers_591.py -v

# Single test by name
pytest -k "test_parse_price" -v

# E2E tests (hits real websites, slow, needs network)
pytest -m e2e -v --timeout=120

# All tests including e2e
pytest -m "" -v --timeout=120
```

### Linting & Formatting

```bash
ruff check src/ tests/               # Lint
ruff check src/ tests/ --fix         # Lint with auto-fix
ruff format src/ tests/              # Format
ruff format --check src/ tests/      # Format check (CI mode)
```

### Pre-commit Hooks (automatic)

1. **ruff**: lint with `--fix` + format on staged Python files
2. **pytest**: runs full unit test suite (excluding e2e)

## Data Schema

The `Listing` model in `db.py` is the single source of truth for all crawled data. All crawlers normalize their output to this schema.

| Column       | Type         | Description                                    | Chinese field context        |
|------------- |------------- |----------------------------------------------- |----------------------------- |
| `id`         | Integer (PK) | Auto-increment primary key                     |                              |
| `source`     | String(50)   | Platform identifier (591, rakuya, fcrent, etc.) | 來源平台                     |
| `source_id`  | String(100)  | Platform-specific listing ID                   | 平台物件編號                 |
| `title`      | String(500)  | Listing title                                  | 標題                         |
| `price`      | Integer      | Monthly rent in TWD                            | 租金（元/月）                |
| `city`       | String(50)   | City name                                      | 縣市（如：高雄市、台北市）   |
| `district`   | String(50)   | District name                                  | 鄉鎮市區（如：三民區）       |
| `address`    | String(500)  | Full address                                   | 地址                         |
| `size`       | Float        | Size in ping (坪)                              | 坪數                         |
| `rooms`      | String(50)   | Room layout                                    | 格局（如：2房1廳1衛）        |
| `type`       | String(50)   | Listing type                                   | 類型（如：整層住家、獨立套房）|
| `floor`      | String(50)   | Floor info                                     | 樓層（如：3F/7F）            |
| `contact`    | String(100)  | Contact person                                 | 聯絡人                       |
| `phone`      | String(50)   | Phone number                                   | 電話                         |
| `url`        | String(1000) | Listing URL on source platform                 | 物件網址                     |
| `images`     | Text (JSON)  | JSON array of image URLs                       | 圖片                         |
| `description`| Text         | Listing description                            | 描述                         |
| `amenities`  | Text (JSON)  | JSON array of amenity names                    | 設備（如：冷氣、洗衣機）     |
| `raw_data`   | Text (JSON)  | Original crawled data preserved as JSON        | 原始資料                     |
| `latitude`   | Float        | Geocoded latitude (TGOS/Google)                |                              |
| `longitude`  | Float        | Geocoded longitude (TGOS/Google)               |                              |
| `cooking`    | String(50)   | Cooking policy                                 | 開伙（可開伙/不可開伙）     |
| `gas_type`   | String(50)   | Gas type                                       | 瓦斯（天然瓦斯/桶裝瓦斯）   |
| `created_at` | DateTime     | First crawl timestamp (UTC)                    |                              |
| `updated_at` | DateTime     | Last update timestamp (UTC)                    |                              |

**Unique constraint**: `(source, source_id)` — upsert logic in `upsert_listing()` updates existing records instead of duplicating.

## Architecture Overview

### Data Flow

```
Rental Websites ──► Playwright (headless browser) ──► Crawler parsers ──► Listing dicts
                                                                              │
                                                                     upsert_listing()
                                                                              │
                                                                        SQLite (radar.db)
                                                                              │
                                                                    CLI search/show/stats
                                                                              │
                                                                   Rich table / JSON output
```

### Crawler Architecture

All crawlers inherit from `BaseCrawler` (ABC) and implement `async crawl(**filters) -> list[dict]`.

| Crawler          | Platform         | Strategy                                           |
|----------------- |----------------- |--------------------------------------------------- |
| `Rent591Crawler` | 591 租屋網       | Playwright + CSRF token + XHR API calls, paginated |
| `RakuyaCrawler`  | 樂屋網           | Playwright + stealth mode, HTML card parsing       |
| `FcrentCrawler`  | 方齊物業         | Playwright + `__NEXT_DATA__` JSON from Next.js SSR |
| `FbGroupCrawler` | Facebook 社團    | Skeleton (price parser implemented)                |
| `FbMarketCrawler`| Facebook 市集    | Skeleton                                           |

### Anti-Bot Strategies

- **591**: Uses Playwright to obtain CSRF token from the page, then makes API calls with that token via `page.evaluate(fetch)`. Region is set via cookie.
- **Rakuya**: Uses `playwright-stealth` to bypass Cloudflare Turnstile. Launches with `headless=False` to avoid detection.
- **fcrent**: Simple Playwright navigation — no significant anti-bot protection. Extracts structured data from Next.js `__NEXT_DATA__` script tag.
- **Facebook**: Uses saved browser session state (`fb_session/state.json`) with manual login fallback. Not yet fully implemented.

### CLI Structure (Click)

```
tw-rent-radar
  ├── crawl <source|all>    # Crawl and store listings (--fetch-details for detail pages)
  ├── search                # Query with filters (--near, --within, --cooking, --gas-type)
  ├── show <id>             # Display single listing details
  ├── stats                 # Show listing counts by source
  ├── list sources          # List supported platforms
  └── db reset              # Delete all stored data
```

## How to Add a New Crawler

1. **Create** `src/tw_rent_radar/crawlers/<platform>.py`
2. **Inherit** from `BaseCrawler`:
   ```python
   class NewCrawler(BaseCrawler):
       source_name = "new_platform"

       async def crawl(self, **filters) -> list[dict]:
           # Return list of dicts matching the Listing schema
           ...
   ```
3. **Normalize** output to the Listing schema (see Data Schema above). Key required fields: `source`, `source_id`, `title`, `price`, `city`. JSON-serialize lists to strings for `images` and `amenities`.
4. **Export** from `crawlers/__init__.py`:
   ```python
   from tw_rent_radar.crawlers.new_platform import NewCrawler
   ```
5. **Register** in `cli.py`:
   - Add to `SOURCES` dict (key + Chinese description)
   - Add to `CRAWLER_MAP` dict
6. **Write tests** in `tests/test_crawlers_<platform>.py`:
   - Unit test the parser with mock data (no network calls)
   - Test price/size parsing edge cases
   - Test `source_name` and `BaseCrawler` subclass contract
   - Optionally add an `@pytest.mark.e2e` test for live validation
7. **Run** `pytest tests/test_crawlers_<platform>.py -v` to verify

## Coding Conventions

- **Type hints everywhere**. Use `from __future__ import annotations` at the top of every module. Use `X | None` not `Optional[X]`.
- **Async crawlers**. All `crawl()` methods are `async`. Use `asyncio.run()` only at the CLI entry point (`cli.py`).
- **Ruff rules**: E, F, I, W selected. Line length 100. Target Python 3.12. Run `ruff check` and `ruff format` before committing.
- **Logging**: Use `logging.getLogger(__name__)` in crawlers, not `print()` (exception: user-facing messages in CLI use `click.echo()` or `console.print()`).
- **JSON serialization**: Use `ensure_ascii=False` when serializing Chinese text. Store JSON arrays/objects as `Text` columns in SQLite.
- **Error handling in crawlers**: Use broad `except Exception` with `# noqa: BLE001` for page load failures in crawl loops — skip and continue. Parse methods should return `None` for unparseable input.
- **Imports**: Group stdlib, third-party, local. Ruff `I` rule enforces sorting.

## Testing Conventions

- **Unit tests**: Use mock data, no network calls. Each crawler's parser methods are tested with realistic but hardcoded data fixtures.
- **E2E tests**: Marked with `@pytest.mark.e2e`. Hit real websites. Excluded by default via `addopts = "-m 'not e2e'"` in `pyproject.toml`. Run manually with `pytest -m e2e`.
- **Fixtures**: Use `pytest.fixture` for crawler instances and sample data. Use `tmp_path` for disposable SQLite databases.
- **Integration tests**: Test full CLI workflows (insert -> search -> verify output) using `CliRunner` with temporary databases.
- **Async tests**: Use `@pytest.mark.asyncio` decorator. `asyncio_mode = "auto"` is configured in `pyproject.toml`.
- **Test file naming**: `test_crawlers_<platform>.py` for crawler tests, `test_<module>.py` for other modules.

## Known Pitfalls

- **591 CSRF token**: The 591 API requires a CSRF token from a `<meta name="csrf-token">` tag. The token must be sent as `X-CSRF-TOKEN` header. Without it, the API returns HTML instead of JSON.
- **Rakuya Cloudflare protection**: Rakuya uses Cloudflare Turnstile. Must use `playwright-stealth` and launch with `headless=False`. The `stealth_async` function (or `Stealth().apply_stealth_async()` in newer versions) must be applied to the page before navigation.
- **fcrent __NEXT_DATA__**: fcrent.tw is a Next.js SSR site. Listing data is embedded in a `<script id="__NEXT_DATA__">` tag as JSON. The object uses opaque IDs for city, district, type, layout, facilities — these must be resolved using lookup tables in `pageProps`.
- **Facebook session**: Facebook crawlers require manual login. The session state is saved to `fb_session/state.json` and reused. If the session expires, the user is prompted to log in again via a visible browser window.
- **SQLite JSON fields**: `images`, `amenities`, and `raw_data` are stored as JSON strings in `Text` columns. Always `json.dumps()` before storing and `json.loads()` when reading. The `Listing.to_dict()` method handles this automatically.
- **Price parsing varies by platform**: Each crawler has its own `parse_price()` because platforms format prices differently (e.g., "15,000 元/月", "25,000元", "$8000", "面議"). Always return `None` for unparseable/negotiable prices.
- **Region/city code mappings**: 591 and Rakuya use different numeric codes for the same cities. Each crawler maintains its own `REGION_MAP` / `CITY_CODES` dict. These are hardcoded and may need updating if platforms change their codes.
- **Windows development environment**: This project is developed on Windows (Git Bash). Use forward slashes in paths. The venv activation is `source .venv/Scripts/activate` (not `bin/activate`).
- **Geocoding API keys**: TGOS requires registration at https://www.tgos.tw/. Google Maps requires API key from Google Cloud Console. Configure keys in `~/.tw-rent-radar/config.json` (`tgos_app_id`, `tgos_api_key`, `google_api_key`) or as environment variables (`TGOS_APP_ID`, `TGOS_API_KEY`, `GOOGLE_MAPS_API_KEY`). Without keys, geocoding is skipped and `--near` search is unavailable.
- **591 detail page rate limiting**: Fetching detail pages (`--fetch-details`) is slower — each listing requires a separate page load. Too-fast requests may trigger anti-bot measures that return randomized data.

## Writing Style

- **Language**: Write everything in English (code, comments, commit messages, docs). Chinese is used only in user-facing strings, test fixtures, and data field values.
- **Traditional Chinese terminology**: All user-facing Chinese text (README, CLI help, UI strings) MUST use Taiwan Traditional Chinese (zh-TW) terminology, NOT Simplified Chinese or Mainland Chinese terms. Reference: https://github.com/LZong-tw/tw-tech-terminology-converting-prompt — key mappings include: 數據→資料, 數據庫→資料庫, 服務器→伺服器, 應用程序→應用程式, 項目→專案, 文件→檔案, 文檔→文件, 默認→預設, 設置→設定, 支持→支援, 異步→非同步, 線程→執行緒, 接口→介面, 命令行→命令列, 程序→程式.

## Working Style
- Remove all debugging/inspecting code before committing.
- **Do NOT run E2E tests locally** unless specifically debugging a crawler against a live site. They are slow, flaky (depend on external websites), and can trigger anti-bot measures. Let CI handle them on manual dispatch.
- PRs: use `gh` CLI for GitHub operations.
- **Windows shell compatibility**: This project is developed on Windows (Git Bash). When writing shell commands, use Unix syntax (forward slashes, `/dev/null`). Avoid Windows-specific commands.
