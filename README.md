# Stock Monitor

A full-featured real-time market intelligence platform for active traders and investors. Dark terminal aesthetic, Bloomberg-inspired layout — built on FastAPI, React, and Claude AI.

![backend](https://img.shields.io/badge/backend-FastAPI-009688)
![frontend](https://img.shields.io/badge/frontend-React%2018%20%2B%20Vite-61dafb)
![data](https://img.shields.io/badge/data-yfinance%20%2B%20Yahoo%20Finance-blue)
![ai](https://img.shields.io/badge/AI-Claude%20(Anthropic)-orange)
![db](https://img.shields.io/badge/persistence-SQLite-lightgrey)

---

## Overview

Stock Monitor started as a simple watchlist with live prices and has grown into a comprehensive dashboard covering market intelligence, portfolio management, deep-stock research, active trading tools, and AI-powered analysis — all in one dark-themed interface.

Today that is **88 views in 10 sidebar groups** (plus a Home dashboard, an in-app User Guide and an Investor Education module), served by **92 API routers / ~175 endpoints**, with **571 backend and 208 frontend tests**. The complete, always-current endpoint list is the interactive API reference at `http://localhost:8000/docs` once the backend is running.

---

## Feature Overview

### Markets
| Feature | Description |
|---|---|
| **Overview** | Multi-timeframe performance tables for major indices, sector ETFs, and the Magnificent 7. Top-10 gainers/losers. Global news sidebar. |
| **Analyst Picks** | Sell-side analyst upgrades/downgrades (firm, prior/new rating, price target) + AI Growth Watch List across 9 AI stack layers. |
| **Breadth** | Large-cap market breadth: above-50/200MA %, A/D ratio, H/L ratio, put/call ratio, VIX sparkline, 60-day A/D line chart. |
| **Index Heatmap** | Constituent heatmap for any index or ETF. Search any ticker dynamically or use quick-access buttons (DIA, QQQ, SPY, ARKK). Tiles sized by live market-cap weight, coloured by 1D return. Market-cap-weighted index return + top contributor/drag summary. |
| **Holdings Performance** | Returns for every holding of an index or ETF over 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, 10Y and life-to-date, ranked by YTD with a pinned benchmark row, summary stats (average, median, % up, % beating the benchmark), sector and text filters, an annualised view of the multi-year columns, CSV export and click-through charts. Full holdings for the S&P 500, Nasdaq-100, Dow 30, their ETFs (SPY, QQQ, DIA…) and the 11 sector SPDRs; other ETFs show Yahoo's top 10, flagged as partial. |
| **Sector Rotation** | Performance table and heatmap for 11 GICS sector ETFs across 1D/1W/1M/3M. |
| **Sector Momentum** | Composite momentum ranking with acceleration signals (▲▲/▲/▼/▼▼) and vs-SPY relative strength toggle. |
| **Macro Calendar** | Upcoming high-impact economic events: FOMC, CPI, PPI, PCE, NFP, GDP — with urgency badges. |
| **Yield Curve** | Live US Treasury curve (13W/5Y/10Y/30Y), inversion signal, DXY tracking, 60-day 10Y sparkline. |

### Watchlist
| Feature | Description |
|---|---|
| **Watchlist** | Live price feed via WebSocket (falls back to REST polling). Flash animations on price change. Day range, 52W range, volume, market cap, earnings countdown. Multi-list support. Price alerts (above/below, % change, 52W break, volume spike) with browser push notifications. |
| **Price Targets** | Set personal price targets with deadline, thesis note, and progress bar. Sorted by urgency. |
| **Earnings+** | Enriched earnings calendar: expected move (ATM straddle), beat-rate history, pre-earnings 5D drift for all watchlist + portfolio symbols. |
| **News Sentiment** | Fetches recent headlines for watchlist symbols and scores each Bullish / Neutral / Bearish with Claude AI (−1 to +1 score). |
| **Smart Alerts** | Condition-based alert rules scanned on demand: Volume Spike, Gap Up/Down, RSI Overbought/Oversold, Golden/Death Cross, Earnings Proximity. |

### Portfolio
| Feature | Description |
|---|---|
| **Portfolio** | Track positions with market value, unrealised P&L, and day P&L. Views: Heatmap, Table (CSV export), Equity Curve, Exposure, Risk, Optimizer, X-Ray, Performance vs SPY/QQQ, Dividends, Correlation, Rebalancer. |
| **Options P&L** | Log open options positions. Refresh live mid prices, Delta, Theta, IV via yfinance. DTE countdown with urgency badge. |
| **Trade Journal** | Log every trade by symbol/side/price/shares/strategy. Realised P&L matching. Win-rate breakdown by strategy. CSV export. |
| **Tax Lots** | Cost basis of every share lot, with simulated sales under five lot-selection methods (FIFO, LIFO, highest cost, lowest cost, minimum tax). Stored in browser localStorage. |
| **Dividend Tracker** | Dividend income, yield on cost, upcoming ex-dividend dates and long-term DRIP projections for an income portfolio. |
| **Stress Test** | Estimates how the current portfolio would have fared in historical crises, from each holding's beta and sector-specific drawdown adjustments. |
| **Attribution** | How much each position has contributed to total return since purchase, in dollars and as a share of invested capital. |
| **CPPI Allocator** | Constant Proportion Portfolio Insurance: dynamically splits capital between a risky and a safe asset so the portfolio is designed never to fall below a floor. |
| **Net Exposure** | One beta-adjusted "how much market risk am I carrying" number across stocks, options and CPPI, with Merger Arb and SPAC capital shown as separate event-driven sleeves. |

### Research
| Feature | Description |
|---|---|
| **Screener** | Technical scans (52W High, Golden/Death Cross, RSI extremes, High Rel-Vol), fundamental presets (Quality Growth, Deep Value, Dividend Income, Momentum+Quality), and Claude NLP mode ("profitable tech with >20% revenue growth"). |
| **Range Screener** | Scans a ~290-name universe for stocks trading sideways within a 30/60/90-day support/resistance band (Kaufman efficiency ratio + edge-touch counts to confirm a real range, not one outlier), flagging names near either edge with a mechanical entry/target/stop and a clickable 1-year inline chart (opens the full ChartModal) showing the range against prior swings and resets. |
| **Price Projection** | A 1-year-forward price cone (10th/25th/50th/75th/90th percentile) for any stock or ETF, built entirely from market-implied inputs: options-implied volatility across every expiry out to ~13 months, the 1-year Treasury as the risk-free rate net of dividend yield, a VIX-regime multiplier, and the issuer's own corporate-bond credit spread as a CDS proxy. Every raw input is shown beside the chart. |
| **Signals** | Multi-timeframe technical summary (1D/1W/1M/3M) for all watchlist + portfolio symbols: Trend, RSI, MACD, Bollinger Band %. |
| **Chart Compare** | Normalised return chart for up to 5 stocks over 1M/3M/6M/1Y. Fundamentals side-by-side table. |
| **Fundamentals** | Side-by-side 21-metric comparison for up to 5 stocks. Best-in-class (green) / worst-in-class (red) highlighting. |
| **Backtester** | Test MA Crossover, RSI Reversal, or Bollinger Bands strategies on historical data. Returns total return, alpha, max drawdown, Sharpe, win rate, and full trade log. |
| **Tear Sheet** | One-page company snapshot for deciding whether to invest: business overview, 5-year performance vs. the S&P 500, 10-year revenue/margin/EPS/FCF track record (SEC filings), balance-sheet quality, valuation multiples vs. the company's own 10-year P/E history, consensus estimates and revisions, earnings-beat record, analyst ratings/targets, ownership and insider activity. A Sankey diagram of the latest four quarters shows how revenue splits across income streams (products/segments, from SEC filings) and flows through costs, taxes and net income to dividends and buybacks. Ends in a cheap-or-expensive verdict (median of historical-P/E, PEG, 10-year DCF and discounted analyst-target models), 12-month bear/base/bull and 5-year annualised return scenarios, a six-pillar scorecard, and auto-generated strengths/risks. Download it as a PDF from the page. |
| **DCF Valuation** | Intrinsic value calculator: EPS, growth rate, WACC, terminal growth, margin of safety. Live 10-year projection table. Undervalued / Overvalued / Fairly Valued verdict. |
| **Unusual Options** | Scans options chains for abnormally high volume vs open interest across watchlist symbols (nearest 3 expiries). Vol/OI ≥ 10× highlighted in amber. |

### Trading
| Feature | Description |
|---|---|
| **Day Trader** | Trading plan calculator (capital, daily target %, max loss %, stop %, R:R). Six strategy playbooks (Gap & Go, Momentum, VWAP, Opening Range, Mean Reversion, Scalping). Live intraday scanner with trade alerts sidebar and pre-market movers. |
| **Trade Ideas** | Claude AI analyses your watchlist and generates bullish/bearish setups with specific entries, targets, and risk levels. |
| **Position Sizer** | Calculates share size using three simultaneous methods: Fixed Fractional, ATR-based (14), Half-Kelly. |
| **Wheel Tracker** | Tracks options wheel positions (cash-secured puts and covered calls) through the full cycle — premium collected, assignment status and annualised return. Stored in browser localStorage. |

### AI Tools
| Feature | Description |
|---|---|
| **AI Chat** | Streaming Claude conversation for open-ended market questions, strategy discussion, and educational Q&A. |
| **Digests** | A pre-market daily digest and a weekly recap of markets, portfolio P&L vs. SPY, watchlist movers, upcoming earnings/economic events, and price alerts — delivered to Telegram on a schedule you set, with preview, send-now, history, and an optional AI-written summary. |
| **Financial Advisor** | AI-generated portfolio strategy based on goal, horizon, capital, monthly contribution, risk tolerance, age, account type, and geographic focus. Includes asset allocation chart. |

### Merger Arb
| Feature | Description |
|---|---|
| **Overview** | Hub for the group: tracked deals by soonest expected close, plus the newest untracked merger filings with quick-add. |
| **Deal Dashboard** | Tracked deals with live spread, annualised return to close, days to close and a risk level; recent EDGAR tender-offer filings. |
| **Opportunity Scanner** | EDGAR scan (60 days) of tender offers, going-private deals, merger proxies, S-4s and 425s, enriched with live prices and cross-referenced to tracked deals. |
| **Deal Analyzer** | Walk-away price, upside/downside, market-implied close probability, a five-factor risk breakdown and an expected-value table across close probabilities. |
| **Arb Portfolio** | Positions against tracked deals: cost, market value, unrealised P&L, value at close, concentration by deal type and regulator. |
| **Risk Matrix** | Bubble chart of deals by days-to-close and annualised return, plus a regulator × deal-type risk grid. |
| **Alerts** | Per-deal rules: days to close, spread threshold, or a status being reached. Checked on demand. |

### SPACs
| Feature | Description |
|---|---|
| **Overview** | Hub: tracked SPACs by redemption deadline, plus newly filed SPACs with quick-add. |
| **Tracker** | SPACs with live discount/premium to trust value, annualised yield to the deadline and warrant price. |
| **Discovery** | EDGAR scan for new SPAC IPOs and de-SPAC merger announcements, with common/warrant tickers parsed from the filing. |
| **Deal Analyzer** | Redeem-at-trust floor case, warrant intrinsic/time value and breakeven, and a redeem-vs-hold scenario table. |
| **Portfolio** | Common and warrant positions tracked separately; a "Trust-Protected" figure for the redeemable common shares. |
| **Alerts** | Per-SPAC rules: deadline approaching, discount/premium threshold, deal announced. |
| **Risk Matrix** | Yield vs. days-to-deadline scatter by deal stage, with a stage × urgency grid. |

### Retirement
| Feature | Description |
|---|---|
| **FIRE Calculator** | Years to financial independence from age, savings, contributions, expenses, expected return, inflation and safe withdrawal rate. |
| **Coast FIRE & Roth** | The savings you need today to coast to retirement, and a Roth conversion ladder. |
| **Monte Carlo** | 1,000 randomised-return simulations estimating the probability the portfolio survives retirement. |
| **Social Security** | Compares claiming ages 62–70 from your full-retirement-age benefit. |
| **Early Retirement Health** | ACA Marketplace premiums and tax credits for the gap years before Medicare. |
| **Roth Conversion Planner** | Conversion strategy for the low-income years between retirement and Social Security/RMDs. |
| **Medicare Estimator** | Monthly and annual Medicare premiums including IRMAA surcharges (2025 CMS figures). |
| **Estate & RMD** | Required minimum distributions from Traditional IRA/401(k) accounts through life expectancy, and the heritable estate value at a target age. |

### Home, Learning & Help
| Feature | Description |
|---|---|
| **Home** | The landing page: portfolio value and P&L, market pulse, biggest movers, upcoming earnings, active alerts, a "What's New" feed linked to the changelog, and a ⌘K command palette that jumps to any tool by name. |
| **Investor Education** | A layered, navigable map of investing concepts (macro, market structure, asset classes, risk, valuation & analysis) with live data snapshots and deep links to the matching tools. |
| **User Guide** | In-app documentation for every view, plus the full changelog. A test checks that every sidebar view is documented. |
| **Export PDF** | Header button that saves the current page via the browser's print dialog. The Tear Sheet also has its own server-generated PDF. |
| **Sidebar pinning** | Pin frequently used views to a "Pinned" section above the groups. |

### Chart Modal (available on any ticker)
11 tabs: Chart (candlestick + volume, 1D–5Y), Fundamentals, News, Earnings (AI earnings call summary from SEC 8-K + historical EPS/revenue chart + earnings play calculator), Options chain, Strategies (AI-generated options strategies with payoff charts), Insider transactions, Analyst ratings, Institutional holders, Sentiment, SEC Filings.

**Drawing tools:** horizontal S/R lines and trend lines — persisted in localStorage per symbol.

**Technical overlays:** SMA20/50/200, Bollinger Bands, RSI sub-pane, MACD sub-pane.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI + Uvicorn (3.11+ supported) |
| Market data | yfinance 1.2 (via curl_cffi) + Yahoo Finance APIs |
| Filings & reference data | SEC EDGAR (submissions, XBRL company facts, N-PORT, full-text search), Treasury.gov yield-curve CSVs, Wikipedia (S&P 500 membership), Nasdaq (Nasdaq-100 list), optional FRED |
| AI | Anthropic Claude — `claude-sonnet-4-6` for chat, sentiment, trade ideas, earnings summaries, screener NLP and analysis; `claude-haiku-4-5` for the digest's short summary. AI Chat can use Gemini (`gemini-2.0-flash`) when a `GEMINI_API_KEY` is set |
| Frontend | React 18 + Vite 5 + Tailwind CSS v3, with per-view code splitting (`React.lazy`) |
| Charts | TradingView Lightweight Charts v5 for price charts; plain SVG for everything else (fan charts, Sankey, bar and range charts) |
| PDF | reportlab (server-side, vector charts) for the Tear Sheet |
| Persistence | SQLite (positions, alerts, journal, watchlists, deals, API cache) + localStorage (drawings, pins, tax lots, wheel tracker) |
| Real-time | WebSocket (price feed) + Server-Sent Events (AI streaming) |
| Testing | pytest (backend) and Vitest + Testing Library (frontend) |
| Font | JetBrains Mono |

Market data comes from Yahoo Finance (free tier, ~15 min delay); filings and fundamentals history from SEC EDGAR (real-time). Everything is free-tier: no paid data subscription is required.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key (required for AI features: AI Chat, Trade Ideas, News Sentiment, Earnings Summaries, Financial Advisor, NLP Screener)

### Backend

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # required for AI features (or put it in backend/.env)
python -m uvicorn main:app --port 8000
```

The backend reads `backend/.env` on startup — copy `backend/.env.example` to `backend/.env` and fill in what you need. Every setting is optional except the Anthropic key for AI features:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the AI features: AI Chat, Trade Ideas, News Sentiment, Earnings Summaries, Financial Advisor, NLP Screener, Stock Analyzer, Portfolio Review, Tax Advisor, Morning Briefing and the digest's AI summary. Everything else works without it. |
| `GEMINI_API_KEY` | Optional: AI Chat uses Gemini (`gemini-2.0-flash`) instead of Claude when set. |
| `FRED_API_KEY` | Optional: adds FRED series to Economic Indicators. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Delivery channel for scheduled digests (AI Tools → Digests walks through the 2-minute bot setup). |
| `DIGEST_SCHEDULER=0` | Turns the background digest scheduler off. |

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The dev server proxies `/api` and `/ws` to the backend on port 8000.

> **Corporate / VPN users:** If behind a proxy with a self-signed certificate, run `npm config set strict-ssl false` before `npm install`.

For a production build, run `npm run build` in `frontend/`: the backend serves the built app from `frontend/dist` (and falls back to `index.html` for client-side routes), so a single `uvicorn` process is the whole deployment. `render.yaml` describes a Render web service that does exactly that.

### Tests

```bash
cd backend  && pip install -r requirements-dev.txt && python -m pytest   # 571 tests, ~10 s, no network, isolated database
cd frontend && npm test                # 208 tests (Vitest + Testing Library)
```

The backend suite never touches `backend/stockmonitor.db` or the network (see the test notes in the project structure below). The frontend suite includes documentation checks: every sidebar view must be described in the User Guide, and every changelog "Open feature" link must point to a real tab.

### Lint gate (one-time setup)

A pre-commit hook runs `ruff check --select F` (undefined names, unused imports, duplicate definitions) on staged backend files — catches the class of bug where a refactor leaves a name undefined on a code path tests don't happen to exercise. Enable it once per clone:

```bash
git config core.hooksPath .githooks
pip install ruff   # if not already installed
```

Bypass for a specific commit with `git commit --no-verify` if you hit a false positive.

---

## Key API Endpoints

A curated tour — every route below was checked against the code. With the backend running, `http://localhost:8000/docs` is the complete interactive reference (about 175 endpoints, with request/response schemas and a "Try it out" button).

### Market Data
| Endpoint | Description |
|---|---|
| `GET /api/quotes?symbols=AAPL,MSFT` | Live price + fundamentals |
| `GET /api/chart/{symbol}?period=1d` | OHLCV bars (1d/5d/1mo/3mo/6mo/1y/2y/5y) |
| `GET /api/market/summary` | Overview page: headlines, gainers, losers, analyst upgrades/downgrades |
| `GET /api/market/performance` | Multi-timeframe returns for indices, sectors, Mag 7 |
| `GET /api/market/breadth` | A/D ratio, MA breadth, VIX, put/call ratio |
| `GET /api/market/rates` | Treasury yields (13W/5Y/10Y/30Y) + DXY |
| `GET /api/treasury/current` · `/history` · `/yield-curve` | Treasury.gov par yields, history and curve shape |
| `GET /api/market/sectors` · `GET /api/sectors/momentum` | Sector ETF performance and momentum scores |
| `GET /api/market/sentiment` · `/fed-watch` · `/economic` · `/economic-calendar` | Fear/greed composite, FOMC odds, economic indicators and the macro calendar |
| `WS /ws/quotes?symbols=AAPL,MSFT` | Real-time price feed |

### Index, ETF & Fund Holdings
| Endpoint | Description |
|---|---|
| `GET /api/holdings-performance?universe=SP500` | Returns for every holding over 1D…10Y and life-to-date, ranked by YTD. `universe` is an index (`SP500`, `NASDAQ100`, `DOW30`), an index ETF (`SPY`, `QQQ`…), a sector SPDR (`XLK`…) or any ETF (top 10 only) |
| `GET /api/holdings-performance/universes` | Presets for the picker |
| `GET /api/index-constituents?index=DOW30` | Constituent performance + market-cap weights (Index Heatmap) |
| `GET /api/etf-holdings?etf=XLK` | Top holdings for any ETF via yfinance `funds_data` |
| `GET /api/search-etf?q=technology` | Search ETFs/indices via Yahoo Finance |
| `GET /api/edgar/fund-holdings?cik=…` | Full SEC N-PORT holdings for a fund (Fund Holdings explorer) |
| `GET /api/market/etf-overlap?tickers=SPY,QQQ` | Shared holdings between ETFs |

### Watchlist, Alerts & Targets
| Endpoint | Description |
|---|---|
| `GET/POST /api/watchlist` · `DELETE /api/watchlist/{symbol}` | Watchlist symbols |
| `GET/POST /api/watchlists` · `DELETE /api/watchlists/{name}` | Named sub-lists |
| `GET/POST /api/alerts` · `PATCH /api/alerts/{id}/trigger` | Price alerts (triggering is done by the browser) |
| `GET/POST /api/alerts/smart` · `POST /api/alerts/smart/scan` | Rule-based alerts, checked on demand |
| `GET/POST /api/price-targets` | Personal price targets |
| `GET /api/earnings/upcoming` · `POST /api/earnings/rich-calendar` | Earnings dates; expected move, beat rate, pre-earnings drift |

### Portfolio
| Endpoint | Description |
|---|---|
| `GET/POST /api/portfolio` · `DELETE /api/portfolio/{id}` | Positions |
| `POST /api/portfolio/snapshot` · `GET /api/portfolio/snapshots` | Equity-curve snapshots |
| `GET /api/portfolio/risk` · `/optimize` · `/xray` · `/net-exposure` | Risk dashboard, efficient frontier, X-ray, beta-adjusted net exposure |
| `GET /api/portfolio/export` · `POST /api/portfolio/import` | CSV export / import (columns: Symbol, Shares, Avg Cost) |
| `GET/POST /api/journal` · `GET /api/journal/stats` | Trade journal with matched P&L and win-rate stats |
| `GET/POST /api/options-positions` · `GET /api/options-positions/pnl` | Options positions with live mid price and Greeks |
| `GET /api/home/summary` | Home dashboard aggregate |

### Research
| Endpoint | Description |
|---|---|
| `GET /api/tear-sheet/{symbol}` | Full company tear sheet (profile, performance, 10-year financials, quarterly income flow, valuation verdict, estimates, analysts, ownership) |
| `GET /api/tear-sheet/{symbol}/pdf` | The tear sheet as a PDF download |
| `GET /api/price-projection/{symbol}` | 1-year price cone from options, rates, VIX and credit |
| `GET /api/screener/technical?scan=golden_cross` | Technical scans |
| `GET /api/screener/fundamental?preset=quality_growth` | Fundamental presets |
| `GET /api/screener/range-bound?window=60` | Range-bound scan: support/resistance band, range score, touches, signal + entry/target/stop |
| `POST /api/screener/custom` · `POST /api/screener/nlp` | Filter-builder screener; natural-language query → Claude → filters |
| `POST /api/screener/signals` | Multi-timeframe technical signals for a list of symbols |
| `GET /api/compare/fundamentals?symbols=AAPL,MSFT` | 21-metric fundamental comparison |
| `GET /api/dcf/prefill/{symbol}` | Pre-fill DCF inputs from yfinance |
| `GET /api/options/{symbol}` · `GET /api/options/unusual` | Options chain; unusual-activity scan |
| `POST /api/backtest` | Run a strategy backtest |
| `GET /api/market/earnings-surprise` · `/earnings-strategy` · `/relative-strength` · `/seasonal` | Earnings surprise, earnings strategies, relative strength, seasonality |
| `GET /api/bonds/search` · `/api/convertibles/search` | Corporate and convertible bond research |

### Event-driven (Merger Arb & SPACs)
| Endpoint | Description |
|---|---|
| `GET/POST /api/merger/deals` · `/positions` · `/alerts` | Tracked deals, arb positions and alert rules (`PUT`/`DELETE` on `/{id}`) |
| `GET /api/merger/opportunities` · `/scan-edgar` · `/analyze` | EDGAR scans and the deal risk/reward analyzer |
| `GET/POST /api/spac/deals` · `/positions` · `/alerts` | Tracked SPACs, positions and alert rules |
| `GET /api/spac/discovery` · `/analyze` | New SPAC/de-SPAC filings; redemption and warrant analysis |

### AI
| Endpoint | Description |
|---|---|
| `POST /api/ai-chat` | Streaming Claude/Gemini chat (SSE) |
| `POST /api/financial-plan` | Financial advisor plan (SSE) |
| `POST /api/trade-ideas` | AI trade ideas for the watchlist (SSE) |
| `POST /api/ai/morning-briefing` · `/ai/portfolio-review` · `/ai/stock-analyze` | Morning briefing, portfolio review, stock analysis (SSE) |
| `POST /api/tax/advisor` | State-aware tax advice |
| `GET /api/sentiment/{symbol}` · `POST /api/news/sentiment` | News sentiment scoring (single symbol / watchlist batch) |
| `GET /api/earnings/transcript-summary/{symbol}` | AI earnings call summary from SEC 8-K |
| `GET /api/options/strategies/{symbol}` | AI-generated options strategies |

### Digests
| Endpoint | Description |
|---|---|
| `GET/PUT /api/digest/settings` | Schedule: timezone, daily on/time/weekdays-only, weekly on/day/time, AI summary |
| `GET /api/digest/status` | Delivery channels configured, scheduler running, next daily/weekly run |
| `POST /api/digest/preview` | Build a `daily`/`weekly` digest and return its data + text, without sending or logging |
| `POST /api/digest/send` | Build and deliver a digest now to every configured channel |
| `POST /api/digest/test` | Send a one-line test message to confirm the channel works |
| `GET /api/digest/history[/{id}]` | Past sends with status, or one with its full text |

---

## Project Structure

```
stockmonitor/
├── backend/
│   ├── main.py              FastAPI app (~530 lines) — modularization effort complete.
│   │                        What remains is the permanent core: _fetch_quote,
│   │                        _fetch_fundamentals, _fetch_perf_one, _fetch_screener_quotes,
│   │                        _fetch_feed and their TTLs, used by nearly every router below
│   │                        via a function-scoped deferred import, plus the Health check
│   │                        and the Serve React Build (SPA catchall) sections. Started at
│   │                        12,269 lines; extracting the core itself would just move the
│   │                        "everything imports from here" problem elsewhere, not remove it.
│   ├── database.py          SQLAlchemy models (positions, alerts, deals, journal, digest log, cache) plus
│   │                        db_session / cache_get / cache_set — the only way any router touches SQLite
│   ├── edgar_utils.py       Shared SEC/EDGAR + generic helpers (_get_cik, _edgar_req,
│   │                        _build_ticker_map, _parse_nport_xml, _fetch_opp_quote, _calc_rsi,
│   │                        _SECTOR_ETFS, SCREENER_UNIVERSE, …) — imported by main.py and
│   │                        every router below with no circular dependency
│   ├── digest_builder.py    Digest data collection (market, portfolio, watchlist, events,
│   │                        alerts, targets) — each section isolated so one failing source
│   │                        drops that section, not the digest
│   ├── digest_render.py     Structured digest → Telegram HTML / plain text
│   ├── digest_channels.py   Delivery channels (Telegram; token redacted from all errors)
│   ├── tear_sheet_pdf.py    Tear Sheet → multi-page PDF (reportlab, vector charts)
│   ├── income_flow.py       Quarterly income waterfall → Sankey graph + layout (shared by page and PDF)
│   ├── holdings_perf.py     Index/ETF universes + multi-period total returns (daily + chunked weekly history)
│   ├── sec_revenue_streams.py  Revenue by product/segment/region from SEC 10-Q/10-K XBRL (Q4 derived)
│   ├── digest_service.py    Settings, due-time + catch-up logic, at-most-once claiming,
│   │                        retries, audit log, and the background scheduler thread
│   ├── routers/             Feature areas extracted out of main.py as FastAPI APIRouters
│   │   ├── corporate_bonds.py    Research → Corporate Bonds
│   │   ├── convertible_bonds.py  Research → Convertible Bonds
│   │   ├── treasury.py           Research → Treasury Bonds
│   │   ├── merger_arb.py         Merger Arb (deals, positions, alerts, opportunity scan)
│   │   ├── spacs.py              SPACs (deals, positions, alerts, discovery)
│   │   ├── fund_holdings.py      Research → Fund Holdings (EDGAR N-PORT explorer)
│   │   ├── cppi.py               Portfolio → CPPI Allocator
│   │   ├── net_exposure.py       Portfolio → Net Exposure — imports from cppi.py/merger_arb.py/
│   │   │                          spacs.py at module level, but reaches back into main.py's
│   │   │                          _compute_portfolio_risk/_fetch_fundamentals/etc. with a
│   │   │                          function-scoped deferred import (main.py imports this router
│   │   │                          to register it, so a module-level import back would cycle)
│   │   ├── activist_tracker.py   Research → Activist Tracker (13D/13G filings)
│   │   ├── reddit_trending.py    Markets → Reddit Trending
│   │   ├── seasonal_patterns.py  Research → Seasonal Patterns
│   │   ├── etf_overlap.py        Research → ETF Overlap
│   │   ├── relative_strength.py  Research → Relative Strength
│   │   ├── backtester.py         Backtester (MA Crossover / RSI Reversal / Bollinger Bands)
│   │   ├── csv_export_import.py  Portfolio/Journal CSV export + portfolio CSV import
│   │   ├── sec_filings.py        Chart modal → SEC Filings tab
│   │   ├── unusual_options.py    Markets → Options Unusual Activity scanner
│   │   ├── portfolio_equity_curve.py  Portfolio → Equity Curve — snapshot endpoint reaches
│   │   │                          back into main.py's _fetch_quote with a function-scoped
│   │   │                          deferred import (same reason as net_exposure.py above)
│   │   ├── earnings_play_calculator.py  Chart modal → Earnings tab play calculator
│   │   ├── nlp_screener.py       Research → Screener (NLP mode) — reaches back into
│   │   │                          main.py's FilterCondition/CustomScreenRequest/
│   │   │                          run_custom_screener with a function-scoped deferred import
│   │   ├── watchlist.py          Sidebar watchlist + named sub-lists (CRUD)
│   │   ├── portfolio.py          Portfolio core CRUD + Home dashboard summary — the
│   │   │                          summary endpoint reaches back into main.py's
│   │   │                          _fetch_perf_one with a function-scoped deferred import
│   │   ├── ai_chat.py            AI Chat (general finance assistant, Gemini or Claude)
│   │   ├── financial_advisor.py  Financial Advisor (CFP-persona investment plan generator)
│   │   ├── custom_screener.py    Research → Screener (filter-builder mode) — also imported
│   │   │                          directly by nlp_screener.py for its NLP mode
│   │   ├── technical_signals.py  Research → Screener (Signals tab, multi-timeframe)
│   │   ├── options_strategy_builder.py  Chart modal → Options tab (strategy suggestions)
│   │   ├── trade_idea_generator.py      Watchlist → trade ideas panel (Claude-generated)
│   │   ├── portfolio_risk_dashboard.py  Portfolio → Risk view — _compute_portfolio_risk/
│   │   │                                 _sanitize_nan also consumed directly by net_exposure.py
│   │   ├── position_sizing.py           Trading → Position Sizer
│   │   ├── portfolio_optimizer.py       Portfolio → Optimizer (efficient frontier)
│   │   ├── rich_earnings_calendar.py    Watchlist → Earnings+
│   │   ├── options_pnl_tracker.py       Portfolio → Options P&L — _live_option_price also
│   │   │                                 consumed directly by net_exposure.py
│   │   ├── portfolio_xray.py            Portfolio → X-Ray
│   │   ├── sector_momentum.py           Markets → Sector Momentum
│   │   ├── market_breadth.py            Markets → Breadth
│   │   ├── fundamental_comparison.py    Research → Chart Compare
│   │   ├── price_target_tracker.py      Watchlist → Price Targets
│   │   ├── earnings_call_summarizer.py  Chart modal → Earnings tab (AI summary)
│   │   ├── dcf_valuation.py             Research → DCF Valuation
│   │   ├── yield_curve.py               Markets → Yield Curve
│   │   ├── ai_stocks.py                 Markets → AI Growth Watch List — _AI_STOCKS also
│   │   │                                 imported directly by ai_analyst_actions.py
│   │   ├── ai_analyst_actions.py        Markets → Analyst Picks (AI upgrades/downgrades)
│   │   ├── day_trader_scanners.py       Trading → Day Trader (gainers/losers/news)
│   │   ├── screener.py                  Research → Screener (technical + fundamental presets)
│   │   ├── options_chain.py             Chart modal → Options tab (full chain)
│   │   ├── dividends.py                 Dividend info per symbol
│   │   ├── correlation_matrix.py        Watchlist → Correlation (POST /api/portfolio/correlation;
│   │   │                                 the market-wide GET variant lives in market_correlation.py)
│   │   ├── sector_rotation.py           Markets → Sector Rotation
│   │   ├── websocket_quotes.py          /ws/quotes — real-time price feed powering the whole app
│   │   ├── smart_alerts.py              Watchlist → Smart Alerts (rule-based scanner)
│   │   ├── insider_transactions.py      Chart modal → Insider tab (per-symbol)
│   │   ├── analyst_ratings.py           Chart modal → Analysts tab (per-symbol) — cache key
│   │   │                                 "analyst:{symbol}" is scoped to this endpoint only
│   │   ├── insider_trading_feed.py      Markets → Insider Trading (market-wide feed)
│   │   ├── analyst_rating_tracker.py    Research → Analyst Ratings (multi-symbol tracker) —
│   │   │                                 cache key "analyst_tracker:{symbol}", changed during
│   │   │                                 extraction to stop colliding with analyst_ratings.py
│   │   ├── ai_news_sentiment.py         Chart modal → News tab (per-symbol AI sentiment)
│   │   ├── news_sentiment_engine.py     Watchlist → News Sentiment (multi-symbol batch) —
│   │   │                                 cache key "news_sentiment:{symbols}", changed during
│   │   │                                 extraction to stop colliding with ai_news_sentiment.py
│   │   ├── custom_news_feed.py          News → My News Feed
│   │   ├── market_sentiment_dashboard.py  Markets → Sentiment (composite fear/greed score)
│   │   ├── index_constituents.py        Markets → Index Heatmap + generic ETF search/holdings
│   │   ├── tax_advisor.py               Portfolio → Tax Advisor (AI, state-aware)
│   │   ├── short_squeeze_scanner.py     Markets → Short Squeeze
│   │   ├── ipo_lockup_calendar.py       Markets → IPO & Lockups (live EDGAR-sourced)
│   │   ├── fed_watch.py                 Markets → Fed Watch (FOMC cut/hold/hike odds)
│   │   ├── ai_morning_briefing.py       AI Tools → Morning Briefing
│   │   ├── range_screener.py            Research → Range Screener (30/60/90d support/resistance scan)
│   │   ├── tear_sheet.py                Research → Tear Sheet (one-page company snapshot + valuation verdict)
│   │   ├── tear_sheet_share.py          Tear Sheet → PDF download
│   │   ├── holdings_performance.py      Markets → Holdings Performance
│   │   ├── digest.py                    AI Tools → Digests (settings, preview, send, history)
│   │   ├── crypto_dashboard.py          Markets → Crypto
│   │   ├── ai_portfolio_review.py       AI Tools → Portfolio Review — _fetch_quote deferred
│   │   ├── economic_dashboard.py        Markets → Economic Indicators (+ optional FRED)
│   │   ├── ai_stock_analyzer.py         AI Tools → Stock Analyzer (snapshot + AI analysis)
│   │   ├── dividend_tracker.py          Portfolio → Dividend Tracker
│   │   ├── watchlist_heatmap.py         Watchlist → Heatmap
│   │   ├── earnings_surprise_tracker.py Research → Earnings Surprise
│   │   ├── earnings_strategy_analyzer.py Research → Earnings Strategy
│   │   ├── price_projection.py          Research → Price Projection (1-year cone from options/rates/VIX/credit)
│   │   ├── price_alerts.py              Watchlist → price/percent/52-week/volume alerts (CRUD)
│   │   ├── trade_journal.py             Portfolio → Trade Journal (FIFO-matched P&L, win rate by strategy)
│   │   ├── portfolio_performance.py     Portfolio → Performance vs SPY/QQQ (alpha, tracking error)
│   │   ├── portfolio_risk_data.py       SPY volatility + risk-free estimate for client-side risk maths
│   │   ├── analyst_history.py           Research → Analyst Ratings (2-year per-symbol history)
│   │   ├── chart.py                     Chart modal → Chart tab (OHLCV, period-scaled cache)
│   │   ├── news.py                      Chart modal → News tab (per-symbol headlines)
│   │   ├── earnings_history.py          Chart modal → Earnings tab (8 quarters EPS/revenue)
│   │   ├── institutional_ownership.py   Chart modal → Institutional tab
│   │   ├── premarket_movers.py          Day Trader → pre/post-market movers panel
│   │   ├── economic_calendar.py         Markets → Macro Calendar (hand-maintained event schedule;
│   │   │                                 needs periodic refreshing — currently runs through Dec 2026)
│   │   └── market_correlation.py        Markets → Correlation (GET /api/market/correlation;
│   │                                     distinct from correlation_matrix.py's POST endpoint above)
│   ├── ruff.toml            Lint gate config — see "Lint gate" below
│   ├── requirements.txt
│   ├── requirements-dev.txt Dev-only deps (ruff, pytest) — not deployed
│   ├── tests/               pytest suite (571 tests). conftest.py's autouse isolated_db
│   │                        fixture runs every test against a throwaway SQLite DB, not the
│   │                        real stockmonitor.db — every router reaches the DB only through
│   │                        db_session()/cache_get()/cache_set(), which resolve SessionLocal
│   │                        by name at call time, so patching it redirects the whole app.
│   │                        test_digest.py defines its own same-named fixture (also clears
│   │                        delivery-channel env vars); pytest uses the module's own fixture
│   │                        in place of conftest's for that file, so the two never both run.
│   └── stockmonitor.db      SQLite database (auto-created on first run)
├── frontend/
│   ├── index.html
│   ├── vite.config.js       /api + /ws proxy → localhost:8000
│   └── src/
│       ├── App.jsx          Root: sidebar nav, routing (lazy-loaded views), WebSocket, quote polling
│       ├── data/            changelog.js (single source for the User Guide changelog and the Home
│       │                    "What's New" widget), investorEducationTopics.js
│       ├── utils/           format.js shared formatters
│       └── components/
│           ├── Header.jsx               Add-ticker bar, refresh controls, WS status
│           ├── StockTable.jsx           Live watchlist table with flash animations
│           ├── ChartModal.jsx           11-tab chart modal (chart, fundamentals, news, earnings…)
│           ├── MarketSummary.jsx        Overview: indices, sectors, Mag 7, movers, news
│           ├── MarketRecommendations.jsx Analyst picks + AI Growth Watch List
│           ├── MarketBreadth.jsx        Breadth dashboard
│           ├── IndexHeatmap.jsx         Index/ETF constituent heatmap with dynamic search
│           ├── HoldingsPerformance.jsx  Holdings returns by period, ranked by YTD
│           ├── SectorDashboard.jsx      Sector rotation table + heatmap
│           ├── SectorMomentum.jsx       Sector momentum ranker
│           ├── MacroCalendar.jsx        Economic event calendar
│           ├── YieldCurve.jsx           Treasury curve + DXY
│           ├── PriceTargets.jsx         Personal price targets
│           ├── RichEarningsCalendar.jsx Earnings+ (expected move, beat rate, drift)
│           ├── NewsSentiment.jsx        AI news sentiment scoring
│           ├── SmartAlerts.jsx          Condition-based alert scanner
│           ├── PortfolioTracker.jsx     Portfolio (11 views: heatmap, risk, optimizer…)
│           ├── OptionsTracker.jsx       Options P&L tracker
│           ├── TradeJournal.jsx         Trade journal with P&L matching
│           ├── Screener.jsx             Technical/fundamental/NLP screener
│           ├── TechnicalSignals.jsx     Multi-timeframe signals dashboard
│           ├── StockComparison.jsx      Normalised return chart compare
│           ├── FundamentalComparison.jsx 21-metric side-by-side comparison
│           ├── Backtester.jsx           Strategy backtester
│           ├── DcfCalculator.jsx        DCF intrinsic value calculator
│           ├── UnusualOptions.jsx       Unusual options activity scanner
│           ├── DayTrader.jsx            Day trader dashboard + scanner
│           ├── TradeIdeas.jsx           AI-generated trade setups
│           ├── PositionSizer.jsx        Position sizing calculator
│           ├── AiBot.jsx               Streaming AI chat
│           ├── FinancialAdvisor.jsx    AI financial planning
│           ├── PriceAlerts.jsx         Alert modal + toast notifications
│           ├── EarningsCalendar.jsx    Inline earnings countdown
│           ├── UserGuide.jsx           In-app documentation
│           ├── DigestCenter.jsx        Digests — delivery setup, schedule, preview/send, history
│           ├── RangeScreener.jsx       Range Screener — 30/60/90d support/resistance scan
│           ├── TearSheet.jsx           Tear Sheet — company snapshot, valuation verdict, projected returns
│           ├── HomeDashboard.jsx, CommandPalette.jsx   Home landing page + ⌘K palette
│           ├── Markets: RedditTrending, ShortSqueeze, IpoCalendar, InsiderFeed, FedWatch, CryptoDashboard,
│           │            EconomicDashboard, MarketSentimentDashboard (.jsx)
│           ├── Research: PriceProjection, EarningsSurpriseTracker, EarningsStrategyAnalyzer, AnalystRatingTracker,
│           │             FundHoldingsExplorer, CorporateBonds, ConvertibleBonds, TreasuryBonds, ActivistTracker,
│           │             RelativeStrengthRanker, SeasonalPatterns, EtfOverlapAnalyzer (.jsx)
│           ├── Watchlist/News: WatchlistHeatmap, CorrelationMatrix, CustomNews (.jsx)
│           ├── Trading: WheelTracker.jsx
│           ├── Portfolio: TaxLotManager, DividendTracker, PortfolioRisk, EfficientFrontier, PortfolioXRay,
│           │              PortfolioStressTest, PortfolioAttribution, CppiAllocator, NetExposure (.jsx)
│           ├── Merger Arb (7): MergerArbOverview, MergerDealDashboard, MergerOpportunityScanner, MergerDealAnalyzer,
│           │                   MergerArbPortfolio, MergerRiskMatrix, MergerAlerts (.jsx)
│           ├── SPACs (7): SpacOverview, SpacTracker, SpacDiscovery, SpacDealAnalyzer, SpacPortfolio,
│           │              SpacRiskMatrix, SpacAlerts (.jsx)
│           ├── Retirement (8): FireCalculator, CoastFire, MonteCarlo, SocialSecurity, EarlyRetirementHealth,
│           │                   RothConversionPlanner, MedicareEstimator, EstateRmdProjector (.jsx)
│           ├── AI Tools: MorningBriefing, StockAnalyzer, PortfolioReview, TaxAdvisor (.jsx)
│           ├── Chart-modal panels: AnalystPanel, AnalystDetailModal, EarningsCallSummary, EarningsPlayCalc,
│           │                       FilingsPanel, FundamentalsPanel, InsiderPanel, InstitutionalPanel, NewsPanel,
│           │                       OptionsChain, OptionsStrategies, SentimentPanel (.jsx)
│           └── InvestorEducation.jsx   Investor education — onion-map landing view +
│                                        layered concept graph (data/investorEducationTopics.js),
│                                        with live data snapshots on 12 topics and deep
│                                        links out to the live tabs that match each concept
├── CHANGELOG.md             Full feature history
└── README.md
```

---

## Caching

Every backend response that costs an external call is cached in SQLite (`cache_entries`: key, JSON, fetched-at) to stay inside Yahoo's free-tier limits. The freshness window is chosen by the caller at read time, so the table below is what each feature asks for; `ARCHITECTURE.md` lists every cache key.

| Data | TTL |
|---|---|
| Live quotes | No cache (WebSocket feed / polling) |
| Chart data | 1 min (1D) · 5 min (5D) · 30 min (1M, 3M) · 1 hr (6M) · 4 hr (1Y, 2Y) · 24 hr (5Y) |
| Fundamentals | 5 min (quote panels) · 2 hr (comparison, DCF pre-fill) |
| Market overview / performance | 15 min |
| News / headlines | 5 min |
| Market breadth, sector momentum, economic indicators, Fed Watch | 30 min |
| Sector rotation, index constituents, options chain | 15 min |
| Treasury yields + DXY | 30 min (live) · 6 hr (Treasury.gov curve CSV) |
| Earnings calendar | 4 hr (upcoming) · 2 hr (Earnings+) |
| Unusual options | 10 min per symbol · 30 min scan |
| SEC filings, fund holdings | 12 hr · 6 hr |
| Earnings call summary | 24 hr |
| News sentiment | 2 hr (batch) · 1 hr (per-symbol AI) |
| Price Projection | 2 hr |
| Tear Sheet | 1 hr (assembled) · 24 hr (10-year SEC history) · 30 days (SEC revenue-by-stream facts, per filing — filings never change) |
| Holdings Performance | 15 min (table) · 26 hr (long-history anchor prices, shared across indexes) · 24 hr (index membership) |
| Merger Arb / SPAC EDGAR scans | 4 hr |

---

## Notes

- **yfinance + curl_cffi:** yfinance 1.x uses `curl_cffi` internally. The backend passes a session with `impersonate="chrome"` (required — Yahoo rejects plain curl user agents). Standard `requests` SSL overrides have no effect.
- **`yfinance.download` is not thread-safe.** It keeps its working state in module-level dictionaries, so two downloads running at once corrupt each other and hang. Code that calls it for large batches (Holdings Performance) serialises the calls behind a lock; do the same in anything new.
- **Best-effort enrichment:** several features layer optional data on a reliable core and degrade quietly rather than failing — for example the Tear Sheet's revenue-by-income-stream breakdown (read from SEC XBRL filings; companies whose filings don't reconcile to reported revenue show a single revenue node) and its 10-year history (SEC filings, falling back to Yahoo's ~4 years for foreign filers and funds).
- **Index and ETF coverage:** the S&P 500 list comes from Wikipedia, the Nasdaq-100 from Nasdaq, and the Dow 30 from a list maintained in this app, so it can lag index changes. Yahoo publishes only an ETF's top 10 holdings, so Holdings Performance shows full holdings only for those indexes, their ETFs and the sector SPDRs, and flags every other ETF as partial.
- **ANTHROPIC_API_KEY:** Required only for AI-powered features. All market data features work without it.
- **WebSocket:** Run uvicorn without `--reload` in production to avoid zombie worker processes on Windows.
- **No authentication:** the API is open and CORS allows any origin — it is built for a single user on a trusted machine. Don't expose it to the internet as-is, and don't add endpoints that send messages or spend money without guardrails.
- **Digest scheduler:** A background thread in the backend process sends the scheduled digests (set `DIGEST_SCHEDULER=0` to disable it). It only runs while the backend is up; a digest missed while the machine was off is sent on startup if within 6 hours (daily) or the same day (weekly). Each period is sent at most once, and nothing is sent or logged until a delivery channel is configured. Uses a single process — don't run it under multiple uvicorn workers.
- **SQLite DB:** Created automatically at `backend/stockmonitor.db` on first run. Contains watchlists, alerts, portfolio positions, trade journal, merger-arb and SPAC deals, price snapshots and the API cache.
- **Hand-maintained data:** the Macro Calendar's event dates (`routers/economic_calendar.py`) are entered by hand and need refreshing; the current schedule runs through December 2026.
- **Documentation upkeep:** `CHANGELOG.md` and `frontend/src/data/changelog.js` record what was built and when (past entries are never rewritten); `ARCHITECTURE.md` and this file describe the code as it is now; `PRODUCT_ENHANCEMENTS.md` tracks what is still missing; `PROJECT.md` is the original build journal from April–May 2026 and is deliberately not kept current.
