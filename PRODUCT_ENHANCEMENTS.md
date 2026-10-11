# Compass — Product Enhancement Roadmap

> Audience: retail investor who day-trades, invests long-term, monitors markets, and tracks portfolio risk/P&L.
> Last reviewed: 2026-10-11 — every claim below was re-checked against the code in that review (several older
> "gaps" turned out to be partly built; they are reworded rather than removed).

---

## What exists today

The app has grown from 7 tabs to **108 views across 13 sidebar groups**, plus a Home dashboard, an in-app User Guide and an Investor Education module (a layered map of investing concepts, separate from the view count). Nearly everything proposed in the original (2026-05-27) version of this roadmap has since shipped. The groups below are generated from the sidebar definition in `App.jsx`:

| Group | Views |
|-------|-------|
| **Home** | Aggregated dashboard (P&L, market pulse, movers, earnings, alerts, recents, "What's New") + ⌘K command palette |
| **Markets** | Overview, Sentiment, Reddit Trending, Index Heatmap, Holdings Performance, Breadth, Analyst Picks, Short Squeeze, Short Interest, IPO & Lockups, Insider Trading, Crypto |
| **Economy** | Regime Dashboard, Indicators, Indicator Studies, Fed Watch, Yield Curve, Macro Calendar |
| **Sectors** | Scoreboard, Rotation Map, Sector Screener, Cycle Fit, Sector Backtest |
| **Themes** | Themes Overview, Artificial Intelligence, Robotics, Quantum Computing, Space Exploration, AI Abundance, Dollar Regime Shift, Clean Energy & Nuclear, Cybersecurity, Healthcare Innovation, Fintech & Digital Payments, Defense Tech, Reshoring & Infrastructure |
| **Research** | Tear Sheet, 100-Bagger Finder, Screener, Range Screener, Price Projection, Fundamentals, DCF Valuation, Chart Compare, Backtester, Earnings Surprise, Earnings Strategy, Analyst Ratings, Fund Holdings, Corporate Bonds, Convertible Bonds, Treasury Bonds, Activist Tracker, Relative Strength, Seasonal Patterns, ETF Overlap, Signals, Unusual Options |
| **Watchlist** | Watchlist, Heatmap, Correlation, Price Targets, Earnings+, News Sentiment, Smart Alerts |
| **News** | My News Feed |
| **Trading** | Trade Ideas, Position Sizer, Wheel Tracker, Day Trader |
| **Merger Arb** | Overview, Deal Dashboard, Opportunity Scanner, Deal Analyzer, Arb Portfolio, Risk Matrix, Alerts |
| **SPACs** | Overview, Tracker, Discovery, Deal Analyzer, Portfolio, Alerts, Risk Matrix |
| **Portfolio** | Portfolio, Options P&L, Tax Lots, Dividend Tracker, Stress Test, Attribution, Trade Journal, CPPI Allocator, Net Exposure |
| **AI Tools** | Morning Briefing, Digests, Stock Analyzer, Portfolio Review, Financial Advisor, Tax Advisor, AI Chat |
| **Retirement** | FIRE Calculator, Coast FIRE & Roth, Monte Carlo, Social Security, Early Retirement Health, Roth Conversion Planner, Medicare Estimator, Estate & RMD |
| **Help** | User Guide (with changelog), Investor Education |

**Recently added (Oct 2026):** *Economy* and *Sectors* — two new top-level groups. Economy: a rule-based regime dashboard (cycle phase, growth × inflation quadrant, a recession-risk score checked against NBER dates), a 50+ indicator library from FRED with percentiles, trends, signals and long history with recession shading, and 19 indicator studies of what stocks did after a macro condition began. Sectors: a scoreboard of the 11 SPDR sectors over 1D to life-to-date with risk and calendar-year views, a relative-rotation map, a horizon screener (tactical / intermediate / strategic) with adjustable weights, cycle fit by phase and a rules-based rotation backtest. The old Sector Rotation, Sector Momentum and Economic Indicators views were folded into these (old pins and links still resolve). *Tear Sheet* — a one-page company snapshot with a cheap-or-expensive verdict (four valuation models), a 10-year financial track record built from SEC filings, projected 12-month and 5-year returns, analyst ratings, a quarterly **income-flow Sankey** (revenue by product/segment → costs → net income → dividends and buybacks, with the breakdown read from SEC XBRL), and a server-generated PDF. *Holdings Performance* — every holding of the S&P 500, Nasdaq-100, Dow 30, their ETFs or a sector SPDR over 1D to life-to-date, ranked by YTD with a benchmark row and summary stats. *Price Projection* — a 1-year price cone from options, rates, VIX and credit.

Chart modal (used across Watchlist/Portfolio/Research) includes SMA 20/50/200, Bollinger Bands, RSI(14), MACD sub-panes, a Volume Profile overlay (20-period avg volume line + >2x-average surge highlighting), and S/R + trend-line drawing tools persisted per symbol. Data sources: yfinance + Yahoo Finance APIs (market data), SEC EDGAR (filings, XBRL company facts, N-PORT), Treasury.gov (yield curve), Wikipedia and Nasdaq (index membership); AI features use Anthropic Claude.

---

## Remaining gaps

Everything below is genuinely unbuilt or only partly built, based on the code audit of 2026-10-11. Items marked *(partly built)* have a foundation worth building on.

### P1
- **Backend-evaluated price/condition alerts** — alerts (price, % change, 52-week break, volume spike, Smart Alert rules) persist to SQLite but are only ever *checked* by the browser (`PATCH /api/alerts/{id}/trigger` is called from the frontend), so nothing fires unless a tab is open. The daily/weekly Digest checks price alerts independently ("near target" lines) but does not evaluate or trigger them. A scheduled backend evaluation that pushes through the existing Telegram channel would close the gap and make four existing alert features useful when the app is closed. Previously deferred at the user's request.

### P2
- **Complete holdings for arbitrary ETFs** — Holdings Performance shows every holding for the S&P 500, Nasdaq-100, Dow 30, their index ETFs and the 11 sector SPDRs, but only Yahoo's top 10 for any other fund (ARKK, VTI, IWM, thematic and bond ETFs). The Fund Holdings explorer already reads full SEC N-PORT filings, but it maps holding *names* to tickers by fuzzy matching, which isn't reliable enough to drive a returns table; a ticker → series → N-PORT lookup with exact identifiers (CUSIP/ISIN → ticker) would fix it. *(partly built)*
- **Extended-hours prices surfaced in Watchlist/Portfolio rows** — the backend already fetches pre/post-market prices (`_fetch_premarket`, used by the Day Trader's Pre-Market Movers panel), but Watchlist and Portfolio row data don't show pre/post-market price or change inline.
- **Mobile / responsive layout** *(partly built)* — the sidebar collapses to a ☰ drawer and components use responsive utility classes, but the app is desktop-first: wide tables and dense panels have no card-view fallback on small screens.
- **Portfolio-aware digest/research sections** — analyst rating changes, insider selling, and new SEC filings for the user's actual holdings, plus distance from 52-week high/low, surfaced in the Digest or as a dedicated view. The underlying routers (analyst ratings, insider trading feed, SEC filings) already exist; they just aren't composed per-holding.
- **Broker-format import and ticker validation** *(partly built)* — Portfolio has a generic CSV import (`POST /api/portfolio/import`: columns Symbol, Shares, Avg Cost, with a few alias names), but nothing parses Schwab/Fidelity/IBKR exports directly, and imported tickers aren't validated. With ~190 hand-entered positions in the live portfolio, validating tickers at import time would also catch bad or delisted symbols.
- **Peer-relative valuation on the Tear Sheet** — the verdict compares a stock to its own history and to simple growth/DCF models; it has no sector or peer medians (P/E, EV/EBITDA, margins vs. the industry), which is the most common second question after "is it expensive?".
- **Revenue breakdown coverage** — the Tear Sheet's income-stream breakdown depends on companies tagging revenue by product/segment in a way that reconciles to reported revenue; it resolves for most large non-financials (Apple, Microsoft, Amazon, Alphabet, Disney, Visa, …) but not for banks or for filers such as JPM, XOM and NFLX, which fall back to a single revenue node. Segment *profit* (operating income by segment) isn't shown at all.
- **Short Interest follow-ups** — the list is a snapshot of FINRA's bi-monthly report, so there is no history: storing each period would allow trend lines, "rising for N periods" and squeeze-risk backtests. Borrow rates come from one broker (a second source, or a daily snapshot to chart fees, would help); the hardest-to-borrow names are often missing. Bond coverage is limited to issuers held by seven large corporate-bond ETFs, so about 1 in 9 names gets a market spread; TRACE prices (not free) would cover far more. Convertible-note economics and covenant/maturity-wall risk are not modelled, and short-interest-vs-price-move alerts are not built.
- **Themes follow-ups** — more themes are a catalog entry (candidates: water, consumer longevity, battery and EV supply chain, Japan and India equity themes, nuclear-fuel and uranium supply chain); not built: user-defined themes, a saved shortlist, thematic ETF holdings look-through, earnings dates and estimate revisions per name, and the editorial commentary needs a periodic manual review (it is dated October 2026).
- **100-Bagger Finder depth** — it scores the S&P 600/400 and any tickers on your watchlist from Yahoo's current fundamentals. Not built: micro-cap coverage (the true early-stage 100-baggers are mostly outside these indexes), a 10-year SEC-based growth and ROIC history per candidate (the Tear Sheet already has that data), insider buying and dilution signals, and saving a shortlist.
- **Economy and Sectors follow-ups** — (1) *Surfacing:* a Home widget (regime + top sectors), a Digest/Morning Briefing section, and sector context on the Tear Sheet (a stock's sector rank and cycle fit) are not built. (2) *Sector valuation:* the screener has no valuation factor because point-in-time sector multiples aren't freely available; recording a snapshot of sector P/E and yield from today onward would build that history. (3) *Breadth within a sector* (share of constituents above their 200-day average) and *industry ETFs* (semis, biotech, banks, homebuilders…) were planned and aren't included. (4) *Real-time macro data:* FRED serves revised values; point-in-time vintages (ALFRED) would make the studies and recession-risk record strictly honest about what was known when.
- **Macro Calendar dates are hand-maintained** — `routers/economic_calendar.py` holds a hard-coded schedule that currently runs through December 2026 and has to be refreshed by hand; sourcing it from the BLS/Fed calendars would remove the upkeep.
- **Backtester realism** — three strategies (MA crossover, RSI reversal, Bollinger Bands) with no commissions, slippage or position sizing, and no walk-forward or out-of-sample testing.

### P3
- **Fibonacci retracement drawing tool** — the chart modal already has S/R and trend-line drawing (persisted per-symbol to localStorage); Fibonacci levels are the one drawing type from the original roadmap still missing.
- **Trade Journal analytics beyond win rate** *(partly built)* — the journal reports win rate and P&L by strategy with FIFO-matched realised P&L; it doesn't yet compute expectancy, average win/loss, holding-period or time-of-day breakdowns, or drawdown from the trade log.
- **PDF export for the other pages** *(partly built)* — the header's Export PDF saves any page through the browser's print dialog, and the Tear Sheet has its own server-generated PDF with vector charts; the Financial Advisor plan, screeners and portfolio views have no purpose-built PDF.
- **Investor Education depth** — no quizzes or progress tracking, no glossary, and no portfolio/behavioural-finance layer yet.
- **A second market-data provider** — everything market-related rests on yfinance/Yahoo's unofficial endpoints, which can rate-limit, change shape or go down; a secondary source for quotes and history would remove that single point of failure.
- **Level 2 / order flow** — would require a brokerage API (Alpaca, IBKR, TD Ameritrade); out of scope for the yfinance-based stack. Noted for future consideration only.

---

## Suggested next build

Two candidates, depending on priority: **backend-evaluated alerts** (P1, previously deferred — the highest-value remaining gap since four existing alert features depend on it) or **peer-relative valuation on the Tear Sheet** (the natural completion of the newest feature: the SEC filings pipeline and the index universes from Holdings Performance already supply the peer sets and the financials needed to compute sector medians). The smallest self-contained item is **extended-hours row data**, since the backend plumbing already exists.
