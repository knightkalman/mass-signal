# Mass Signal (`mass-signal`)

A lightweight multi-ticker market monitor and responsive GitHub Pages dashboard tracking all 22 target tickers from [`trading-agent/trading-targets/tickers.md`](https://github.com/knightkalman/trading-agent/blob/main/trading-targets/tickers.md).

Built on the architecture and styling of [`nvda-signal`](https://github.com/knightkalman/nvda-signal), `mass-signal` focuses strictly on price action and intraday sparkline/trend charts. All news articles, textual commentary, and narrative feeds are omitted, leaving a clean, high-density dashboard where all 22 tickers fit on a single long scrolling page with real-time indicators.

---

## 22 Watchlist Tickers & Upstream Stage Data

The 22 tickers and their parameters derived from `trading-targets/tickers.md` and the upstream pipelines:

| # | Ticker | eToro ID | Yahoo Symbol | Asset Class | Full Name | Primary Source |
|---|--------|----------|--------------|-------------|-----------|----------------|
| 1 | **OIL** | `17` | `CL=F` | Commodities | Crude Oil (WTI) | Yahoo Finance / NYMEX |
| 2 | **NVDA** | `1137` | `NVDA` | Stocks | NVIDIA Corporation | Yahoo Finance / NASDAQ |
| 3 | **MU** | `1130` | `MU` | Stocks | Micron Technology Inc. | Yahoo Finance / NASDAQ |
| 4 | **ORCL** | `1135` | `ORCL` | Stocks | Oracle Corporation | Yahoo Finance / NYSE |
| 5 | **CAT** | `1012` | `CAT` | Stocks | Caterpillar Inc. | Yahoo Finance / NYSE |
| 6 | **GS** | `1467` | `GS` | Stocks | The Goldman Sachs Group Inc. | Yahoo Finance / NYSE |
| 7 | **INTC** | `1021` | `INTC` | Stocks | Intel Corporation | Yahoo Finance / NASDAQ |
| 8 | **MS** | `1976` | `MS` | Stocks | Morgan Stanley | Yahoo Finance / NYSE |
| 9 | **PLTR** | `7991` | `PLTR` | Stocks | Palantir Technologies Inc. | Yahoo Finance / NYSE |
| 10 | **SHOP** | `4148` | `SHOP` | Stocks | Shopify Inc. | Yahoo Finance / NYSE |
| 11 | **AMD** | `1832` | `AMD` | Stocks | Advanced Micro Devices Inc. | Yahoo Finance / NASDAQ |
| 12 | **ASML** | `4244` | `ASML` | Stocks | ASML Holding N.V. | Yahoo Finance / NASDAQ |
| 13 | **ARM** | `1365` | `ARM` | Stocks | Arm Holdings plc | Yahoo Finance / NASDAQ |
| 14 | **TXN** | `1634` | `TXN` | Stocks | Texas Instruments Incorporated | Yahoo Finance / NASDAQ |
| 15 | **COP** | `1510` | `COP` | Stocks | ConocoPhillips | Yahoo Finance / NYSE |
| 16 | **MRK** | `1027` | `MRK` | Stocks | Merck & Co., Inc. | Yahoo Finance / NYSE |
| 17 | **GOOGL** | `6434` | `GOOGL` | Stocks | Alphabet Inc. | Yahoo Finance / NASDAQ |
| 18 | **QCOM** | `1485` | `QCOM` | Stocks | QUALCOMM Incorporated | Yahoo Finance / NASDAQ |
| 19 | **AMZN** | `1005` | `AMZN` | Stocks | Amazon.com Inc. | Yahoo Finance / NASDAQ |
| 20 | **META** | `1003` | `META` | Stocks | Meta Platforms Inc. | Yahoo Finance / NASDAQ |
| 21 | **CRWD** | `5506` | `CRWD` | Stocks | CrowdStrike Holdings Inc. | Yahoo Finance / NASDAQ |
| 22 | **HOOD** | `9272` | `HOOD` | Stocks | Robinhood Markets, Inc. | Yahoo Finance / NASDAQ |

---

## Stage 1 & Stage 2 Actions and Their Sources

In the `trading-agent` orchestrator ecosystem, market data is populated across two automated stages:

### Stage 1: Mass News Sentiment Collection (`mass-news-sentiment.yml`)
- **Trigger**: Every 9 minutes via cron or manual dispatch.
- **CLI Command**: `python3 -m src.market_data.cli collect-news-sentiment --tickers-file trading-targets/tickers.md`
- **Data Fetched & Sources**:
  1. **Yahoo Finance Chart API (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`)**: Intraday prices (1m/5m), previous close, change, percentage change.
  2. **Massive Stocks API (`api.massive.com`)**: 1-minute aggregate bars for supported US tickers.
  3. **RSS Feeds (Yahoo Finance, Google News, CNBC, BBC)**: Headline streaming and article links.
  4. **Multi-Tier AI Sentiment Inference**: Copilot / Antigravity / Gemini / FMP cascades.
- **Output Artifacts**: `data/news_sentiment/{slug}-24h.json`, `reports/news_sentiment/latest-sentiment-summary.md`.

### Stage 2: General Market Data Enrichment (`market-data-enrichment.yml`)
- **Trigger**: Chained from Stage 1 or manual dispatch.
- **CLI Command**: `python3 -m src.market_data.cli fetch-and-enrich --symbol ALL --tickers-file trading-targets/tickers.md`
- **Data Fetched & Sources**:
  1. **eToro Public API (MCP / REST)**: Live bid/ask/mid quote, spread, spread percentage, instrument trading eligibility, leverage tiers, and multi-timeframe candle history.
  2. **Financial Modeling Prep (FMP) API**: Corporate earnings calendar, dividend dates, economic releases, analyst price targets.
  3. **Technical Indicators Engine**: Calculates EMA20, EMA50, SMA200, RSI14, ADX14, ATR14, RVOL, and support/resistance levels.
  4. **Signal Feeds**: Downstream integration of `oil-signal` and `nvda-signal` APIs.
- **Output Artifacts**: `data/market_snapshots/{slug}-latest.json`, `data/market_snapshots/{slug}-history.jsonl`.

---

## Datapoint Requirements & Features

### Core Dashboard Capabilities:
1. **Interactive 24h / 7d Timeframe Switcher**: Located in the top header, switching all 22 sparkline charts dynamically between the last 24 hours of trading and full 7-day trend history.
2. **"Market Closed" Weekend Intelligence**:
   - Automatically detects New York equity market close (Friday 16:00 to Monday 09:30 NY) and commodities schedules.
   - Highlights weekend non-trading intervals with shaded vertical bands (`.weekend-closed-band`), dashed boundary lines, and centered `"MARKET CLOSED"` labels.
   - Preserves continuous trend visualization using dotted weekend-carry lines bridging Friday close to the next trading session.
   - Renders a live `"Market Closed · Weekend"` status pill in the meta bar and a discreet watermark badge on charts when markets are closed.
3. **Market Matrix News Sentiment & Technicals Integration**:
   - Embedded in the header space between the ticker name and quote price for each card.
   - **24h News Sentiment**: General direction pill (`BULLISH` / `BEARISH` / `NEUTRAL` / `MIXED`), net sentiment score, and bullish/bearish story counts `(14B/10b)` from `trading-dashboard`.
   - **Technicals Column Indicators**: Dual timeframe trend icons (15m/4h `🟢/🔴`), RSI14 pill, and RVOL multiplier.

### Required Datapoints (Included):
1. **`symbol`**: Ticker symbol (e.g. `NVDA`, `OIL`, `AMD`).
2. **`name`**: Full market/company name (e.g. `NVIDIA Corporation`, `Crude Oil (WTI)`).
3. **`instrument_id`**: eToro Instrument ID (e.g. `1137`, `17`).
4. **`price`**: Current regular market price.
5. **`previous_close`**: Previous daily close price (baseline for percent calculation and coloring).
6. **`change` & `change_percent`**: Net price move and percentage.
7. **`price_timestamp`**: Timestamp of the latest quote (UTC).
8. **`history`**: Time-series array of `{"timestamp": str, "price": float}` for the chart plot.
9. **`currency`**: Price currency (USD).
10. **`asset_class`**: Identifier (`commodities` or `stocks`) for unit and market handling.

### Datapoints Omitted (Skipped):
- All RSS news items, headlines, summaries, URLs, and publisher names.
- News event markers, stems, and cluster badges on charts.
- AI sentiment rationale, catalyst tags, surprise factors, and temporal horizons.
- News review cards and textual footnotes.

---

## Local Usage

### Requirements
- Python 3.10+ (Standard library only; zero mandatory third-party dependencies).

### Run Once
```bash
python3 mass_monitor.py --once
```

### Run as Background Daemon
```bash
python3 mass_monitor.py --interval-seconds 300 --output data/mass/$(date -u +%F).jsonl
```

### Run Tests
```bash
PYTHONPATH=. pytest -v tests/
```

### View Dashboard Locally
Start a local static web server from the repository root:
```bash
python3 -m http.server 8000 --directory site
```
Then navigate to `http://localhost:8000`.

---

## GitHub Pages Deployment

The automated GitHub Actions workflow `.github/workflows/mass-monitor.yml` runs every 10 minutes:
1. Concurrently fetches intraday data across all 22 tickers.
2. Commits updated data files into `data/mass/`.
3. Packages `site/data/mass/` with `index.json`.
4. Deploys the static site to GitHub Pages.
