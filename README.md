# tw-rent-radar 🏠

[![CI](https://github.com/LZong-tw/tw-rent-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/LZong-tw/tw-rent-radar/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tw-rent-radar.svg)](https://pypi.org/project/tw-rent-radar/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

多平台台灣租屋資訊命令列工具。

從 **5 個台灣租屋平台**一次爬取物件資料，存入本機 SQLite，透過終端機搜尋、篩選、分析，產出帶有捷運距離、品質標記、跨平台去重的 XLSX 報表。

```
tw-rent-radar crawl all --city 高雄市
tw-rent-radar search --max-price 15000 --cooking 可開伙 --near "高雄車站" --within 2
tw-rent-radar analyze --max-price 18000 --near "高雄軟體園區" --near "健身工廠" --within 3
```

## 功能特色

- **多平台爬取** — 591 租屋網、樂屋網、方齊物業、Facebook 社團、Facebook Marketplace
- **進階搜尋** — 依縣市、價格、格局、類型、開伙、瓦斯篩選
- **多點距離搜尋** — `--near` 可重複使用，`--near-mode all|any` 控制 AND/OR 邏輯
- **分析報表** — `analyze` 指令產出帶色標的 XLSX，含捷運距離、品質標記、跨平台去重、長期上架偵測
- **智慧推斷** — 從標題/描述自動推斷開伙政策和瓦斯類型
- **LLM 友善** — 所有查詢指令支援 `--json` 和 `--fields`，適合與 AI 工具整合
- **本機 SQLite** — 免安裝資料庫，單一檔案，自動去重
- **匯出** — 支援 `.csv` 和 `.xlsx` 匯出

## 支援平台

| 平台 | 代碼 | 狀態 | 策略 |
|------|------|------|------|
| 591 租屋網 | `591` | ✅ | Playwright + CSRF token + API 分頁 |
| 樂屋網 (Rakuya) | `rakuya` | ✅ | playwright-stealth 繞過 Cloudflare，二階段爬取 |
| 方齊物業 (fcrent) | `fcrent` | ✅ | Next.js `__NEXT_DATA__` JSON 解析 |
| Facebook 租屋社團 | `fb_group` | ✅ | 登入 + 滾動 + 貼文展開 + 價格解析 |
| Facebook Marketplace | `fb_market` | ✅ | 登入 + 滾動 + 卡片解析 |

## 快速開始

### 方式一：PyPI 安裝

```bash
pip install tw-rent-radar
playwright install chromium
```

### 方式二：從原始碼安裝

```bash
git clone https://github.com/LZong-tw/tw-rent-radar.git
cd tw-rent-radar
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
source .venv/Scripts/activate    # Windows (Git Bash)
pip install -e ".[dev]"
playwright install chromium
```

### Geocoding 設定（距離搜尋用）

建議使用 Google Maps Geocoding API（TGOS 不開放個人申請）。

在 `~/.tw-rent-radar/config.json` 設定：

```json
{
  "google_api_key": "你的 Google Maps API Key"
}
```

或設定環境變數 `GOOGLE_MAPS_API_KEY`。

## 使用方式

### `crawl` — 爬取租屋資料

```bash
tw-rent-radar crawl 591 --city 高雄市
tw-rent-radar crawl rakuya --city 台北市
tw-rent-radar crawl fcrent
tw-rent-radar crawl fb_group --group "5911高雄租屋"
tw-rent-radar crawl all --city 高雄市

# 爬取含詳情頁（開伙、瓦斯、設備）
tw-rent-radar crawl rakuya --city 高雄市 --fetch-details
```

### `search` — 搜尋已儲存的物件

```bash
# 基本搜尋
tw-rent-radar search --city 高雄市 --max-price 15000

# 開伙 + 天然瓦斯
tw-rent-radar search --cooking 可開伙 --gas-type 天然瓦斯

# 距離搜尋（單點）
tw-rent-radar search --near "高雄軟體園區" --within 2

# 多點距離搜尋（必須同時靠近兩個地點）
tw-rent-radar search --near "高雄軟體園區" --near "健身工廠" --near-mode all --within 3

# JSON 輸出（適合 LLM 或其他工具）
tw-rent-radar search --city 高雄市 --json --fields title,price,district,url

# 匯出
tw-rent-radar search --city 高雄市 --output results.xlsx
tw-rent-radar search --city 高雄市 --output results.csv
```

### `analyze` — 產生分析報表

```bash
# 產生帶有捷運距離、品質標記的 XLSX 報表
tw-rent-radar analyze --max-price 18000 --near "高雄軟體園區" --within 3

# 多 POI + 開伙篩選
tw-rent-radar analyze --max-price 18000 --cooking 可開伙 \
  --near "高雄軟體園區" --near "健身工廠" --within 3
```

報表包含：

| 欄位 | 說明 |
|------|------|
| `nearest_mrt` / `mrt_km` | 最近捷運站及距離 |
| `dist_*` | 到各 POI 的距離 |
| `price_per_ping` | 每坪租金 |
| `elevator` / `balcony` / `washer` / `ac` / `pet` | 品質標記 |
| `cooking` / `gas_type` | 開伙政策 / 瓦斯類型 |
| `long_listed` | 長期上架偵測（591 高瀏覽量） |
| `cross_platform_dup` | 跨平台重複物件偵測 |

### 其他指令

```bash
tw-rent-radar show 42              # 檢視單一物件
tw-rent-radar show 42 --json
tw-rent-radar stats                # 資料庫統計
tw-rent-radar list sources         # 支援的平台列表
tw-rent-radar db reset             # 重設資料庫
```

## LLM 整合

tw-rent-radar 設計為可供 LLM 直接呼叫的命令列工具。所有查詢指令支援 `--json` 結構化輸出與 `--fields` 欄位篩選。

```bash
# 爬取 → 查詢 → 取得結構化資料
tw-rent-radar crawl 591 --city 高雄市
tw-rent-radar search --city 高雄市 --max-price 12000 --json --fields title,price,district,url
```

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

## 開發

```bash
pytest                           # 單元測試
pytest -m e2e                    # E2E 測試（連線實際網站）
ruff check src/ tests/           # 靜態分析
ruff format src/ tests/          # 格式化
pre-commit install               # 安裝 Git hooks
```

## 專案結構

```
src/tw_rent_radar/
├── cli.py                 # Click 命令列（crawl, search, analyze, show, stats）
├── db.py                  # SQLite + SQLAlchemy ORM
├── analysis.py            # 分析引擎（捷運距離、品質標記、dedup、XLSX）
├── geo.py                 # Geocoding（Google Maps）+ Haversine 距離
├── output.py              # Rich 表格 / JSON 格式化
└── crawlers/
    ├── base.py            # 爬蟲 ABC + 文字推斷（開伙/瓦斯）
    ├── rent591.py         # 591 租屋網
    ├── rakuya.py          # 樂屋網
    ├── fcrent.py          # 方齊物業
    ├── fb_auth.py         # Facebook 連線管理
    ├── fb_group.py        # Facebook 租屋社團
    └── fb_market.py       # Facebook Marketplace
```

## 授權條款

MIT
