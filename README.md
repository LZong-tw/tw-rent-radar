# tw-rent-radar

多平台台灣租屋資訊命令列工具。

從多個台灣租屋平台爬取物件資料，存入本機 SQLite 資料庫，再透過終端機搜尋與篩選。同時支援人類使用（Rich 表格輸出）與 LLM 整合（`--json` 結構化輸出）。

## 功能特色

- **多平台爬取** — 591 租屋網、樂屋網、方齊物業、Facebook 社團、Facebook Marketplace
- **人類友善輸出** — Rich 格式化終端機表格，支援搜尋與篩選
- **LLM 友善輸出** — 所有查詢指令支援 `--json` 旗標，輸出結構化資料
- **本機 SQLite 儲存** — 免安裝資料庫，單一檔案（`radar.db`）
- **自動去重** — 以 `(source, source_id)` 為唯一鍵，重複爬取時更新既有紀錄
- **Playwright 驅動** — 統一處理 SPA、反爬蟲機制、需登入的網站
- **距離搜尋** — 支援 `--near` 和 `--within` 旗標，以 TGOS/Google Maps 計算物件與指定地點的距離
- **詳情頁爬取** — 使用 `--fetch-details` 取得開伙政策、瓦斯類型、完整設備清單

## 支援平台

| 平台 | 代碼 | 狀態 | 備註 |
|------|------|------|------|
| 591 租屋網 | `591` | 可用 | Nuxt 3 SSR Pinia store 擷取 |
| 樂屋網 (Rakuya) | `rakuya` | 可用 | playwright-stealth 繞過 Cloudflare |
| 方齊物業 (fcrent) | `fcrent` | 可用 | Next.js SSR，解析 `__NEXT_DATA__` |
| Facebook 租屋社團 | `fb_group` | 骨架 | 驗證流程已實作，DOM 選擇器待完成 |
| Facebook Marketplace | `fb_market` | 骨架 | 驗證流程已實作，DOM 選擇器待完成 |

## 快速開始

```bash
# 複製專案
git clone https://github.com/LZong-tw/tw-rent-radar.git
cd tw-rent-radar

# 建立虛擬環境（Python 3.12+）
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
source .venv/Scripts/activate    # Windows (Git Bash)

# 以可編輯模式安裝
pip install -e ".[dev]"

# 安裝 Playwright 瀏覽器
playwright install chromium
```

## 使用方式

### `crawl` — 爬取租屋資料

```bash
# 爬取 591 特定縣市的物件
tw-rent-radar crawl 591 --city 高雄市

# 爬取樂屋網
tw-rent-radar crawl rakuya --city 台北市

# 爬取方齊物業（不需指定縣市）
tw-rent-radar crawl fcrent

# 爬取 Facebook 社團
tw-rent-radar crawl fb_group --group "高雄租屋"

# 一次爬取所有平台
tw-rent-radar crawl all --city 高雄市

# 爬取含詳情頁資料（開伙、瓦斯、設備）
tw-rent-radar crawl 591 --city 高雄市 --fetch-details
```

### `search` — 搜尋已儲存的物件

```bash
# 人類友善表格輸出（預設）
tw-rent-radar search --city 高雄市 --max-price 15000
tw-rent-radar search --district 三民區 --type 整層
tw-rent-radar search --source 591 --min-price 8000 --max-price 20000

# JSON 輸出
tw-rent-radar search --city 高雄市 --max-price 15000 --json

# 指定輸出欄位
tw-rent-radar search --json --fields title,price,address,url

# 搜尋可開伙的物件
tw-rent-radar search --cooking 可開伙

# 搜尋天然瓦斯的物件
tw-rent-radar search --gas-type 天然瓦斯

# 搜尋距離特定地點 2 公里內的物件
tw-rent-radar search --near "高雄軟體園區" --within 2

# 組合篩選
tw-rent-radar search --city 高雄市 --max-price 18000 --cooking 可開伙 --near "高雄軟體園區" --within 2
```

### `show` — 檢視單一物件詳情

```bash
tw-rent-radar show 42
tw-rent-radar show 42 --json
```

### `stats` — 資料庫統計

```bash
tw-rent-radar stats
tw-rent-radar stats --json
```

### `list sources` — 顯示支援的平台

```bash
tw-rent-radar list sources
```

### `db reset` — 重設資料庫

```bash
tw-rent-radar db reset
```

## LLM 整合

tw-rent-radar 設計為可供 LLM 直接呼叫的命令列工具，類似 `gh` 或 `jq`。所有查詢指令支援 `--json` 結構化輸出與 `--fields` 欄位篩選。

### 使用範例

```bash
# 1. 爬取最新資料
tw-rent-radar crawl 591 --city 高雄市

# 2. 以結構化格式查詢
tw-rent-radar search --city 高雄市 --max-price 12000 --json --fields title,price,district,url

# 3. 取得特定物件詳情
tw-rent-radar show 15 --json

# 4. 查看資料庫現有資料
tw-rent-radar stats --json
```

`--json` 輸出為 JSON 陣列：

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

### 資料結構

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | int | 自動遞增主鍵 |
| `source` | string | 平台代碼（`591`、`rakuya`、`fcrent`、`fb_group`、`fb_market`） |
| `source_id` | string | 平台原始物件編號 |
| `title` | string | 物件標題 |
| `price` | int | 月租金（新台幣） |
| `city` | string | 縣市（如 `高雄市`） |
| `district` | string | 鄉鎮市區（如 `三民區`） |
| `address` | string | 完整地址 |
| `size` | float | 坪數 |
| `rooms` | string | 格局（如 `2房1廳1衛`） |
| `type` | string | 物件類型（整層住家／獨立套房／雅房） |
| `floor` | string | 樓層資訊 |
| `contact` | string | 聯絡人 |
| `phone` | string | 電話 |
| `url` | string | 原始物件網址 |
| `images` | array | 圖片網址陣列 |
| `amenities` | array | 設備清單（如 `["冷氣", "洗衣機"]`） |
| `description` | string | 物件描述 |
| `latitude` | float | 經緯度（緯度） |
| `longitude` | float | 經緯度（經度） |
| `cooking` | string | 開伙政策（可開伙／不可開伙） |
| `gas_type` | string | 瓦斯類型（天然瓦斯／桶裝瓦斯） |

## Geocoding 設定

距離搜尋功能需要 TGOS 或 Google Maps API 金鑰。在 `~/.tw-rent-radar/config.json` 設定：

```json
{
  "tgos_app_id": "你的 TGOS App ID",
  "tgos_api_key": "你的 TGOS API Key",
  "google_api_key": "你的 Google Maps API Key"
}
```

或設定環境變數：`TGOS_APP_ID`、`TGOS_API_KEY`、`GOOGLE_MAPS_API_KEY`。

TGOS 適合台灣門牌地址，Google Maps 適合 POI 名稱（如「高雄軟體園區」）。兩者互為備援。

## 開發

```bash
# 執行單元測試（預設排除 e2e 測試）
pytest

# 執行 e2e 測試（連線實際網站，需要網路）
pytest -m e2e

# 執行所有測試
pytest -m ""

# 靜態分析與格式化
ruff check src/ tests/
ruff format src/ tests/

# Pre-commit hooks（ruff + pytest，提交時自動執行）
pre-commit install
pre-commit run --all-files
```

## 專案結構

```
src/tw_rent_radar/
├── __init__.py
├── cli.py                 # Click 命令列進入點
├── db.py                  # SQLite + SQLAlchemy 模型
├── output.py              # Rich 表格／JSON 格式化輸出
└── crawlers/
    ├── __init__.py
    ├── base.py            # 爬蟲抽象基底類別
    ├── rent591.py         # 591 租屋網
    ├── rakuya.py          # 樂屋網
    ├── fcrent.py          # 方齊物業
    ├── fb_auth.py         # Facebook 連線階段管理
    ├── fb_group.py        # Facebook 租屋社團
    └── fb_market.py       # Facebook Marketplace
```

## 授權條款

MIT
