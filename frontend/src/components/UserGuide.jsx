import { useState, useMemo, useRef, useEffect } from 'react'
import { CHANGELOG_BLOCKS } from '../data/changelog'

// ── Content definition ────────────────────────────────────────────────────────

const GUIDE = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: '◆',
    blocks: [
      { type: 'p', text: 'Stock Monitor is a real-time market intelligence platform for retail investors and active traders. It combines live price data, technical analysis, portfolio tracking, and AI-powered research into a single dark-themed dashboard.' },
      { type: 'h3', text: 'First-Time Setup' },
      { type: 'steps', items: [
        'Add tickers to your watchlist using the TICKER input in the top header bar, then click "+ Add" (or press Enter).',
        'Navigate to Portfolio → Portfolio to log your positions so the app can track P&L and exposure.',
        'Set price alerts by clicking the bell icon (🔔) on any watchlist row.',
        'Allow browser notifications when prompted — alerts fire even when you switch tabs.',
      ]},
      { type: 'h3', text: 'Navigation' },
      { type: 'p', text: 'The left sidebar organises all features into 13 groups. All groups start collapsed — click a group header to expand it. Only the group containing your current view opens automatically. Click any item to load that view. Home is pinned above the groups and the User Guide button is pinned below them. On mobile, tap ☰ to open the sidebar drawer.' },
      { type: 'p', text: 'Hover any item inside a group to reveal a ☆ button on its right — click it to pin that item. Pinned items collect in a "Pinned" section above the groups (with a filled ★ to unpin), so your most-used views are always one click away without expanding anything. Pins are saved locally and start empty.' },
      { type: 'table', headers: ['Group', 'What\'s Inside'], rows: [
        ['Markets', 'Overview, Sentiment, Reddit Trending, Index Heatmap, Holdings Performance, Breadth, Analyst Picks, Short Squeeze, IPO & Lockups, Insider Trading, Crypto'],
        ['Economy', 'Regime Dashboard, Indicators, Indicator Studies, Fed Watch, Yield Curve, Macro Calendar'],
        ['Sectors', 'Scoreboard, Rotation Map, Sector Screener, Cycle Fit, Sector Backtest'],
        ['Themes', 'Themes Overview, Artificial Intelligence, Robotics, Quantum Computing, Space Exploration'],
        ['Research', 'Tear Sheet, 100-Bagger Finder, Screener, Range Screener, Price Projection, Fundamentals, DCF Valuation, Chart Compare, Backtester, Earnings Surprise, Earnings Strategy, Analyst Ratings, Fund Holdings, Corporate Bonds, Convertible Bonds, Treasury Bonds, Activist Tracker, Relative Strength, Seasonal Patterns, ETF Overlap, Signals, Unusual Options'],
        ['Watchlist', 'Watchlist, Heatmap, Correlation, Price Targets, Earnings+, News Sentiment, Smart Alerts'],
        ['News', 'My News Feed'],
        ['Trading', 'Trade Ideas, Position Sizer, Wheel Tracker, Day Trader'],
        ['Merger Arb', 'Overview, Deal Dashboard, Opportunity Scanner, Deal Analyzer, Arb Portfolio, Risk Matrix, Alerts'],
        ['SPACs', 'Overview, Tracker, Discovery, Deal Analyzer, Portfolio, Alerts, Risk Matrix'],
        ['Portfolio', 'Portfolio, Options P&L, Tax Lots, Dividend Tracker, Stress Test, Attribution, Trade Journal, CPPI Allocator, Net Exposure'],
        ['AI Tools', 'Morning Briefing, Digests, Stock Analyzer, Portfolio Review, Financial Advisor, Tax Advisor, AI Chat'],
        ['Retirement', 'FIRE Calculator, Coast FIRE & Roth, Monte Carlo, Social Security, Early Retirement Health, Roth Conversion Planner, Medicare Estimator, Estate & RMD'],
      ]},
      { type: 'h3', text: 'Home & Quick Search' },
      { type: 'p', text: 'Home (pinned at the top of the sidebar) is the app\'s landing page — it opens by default. It shows your portfolio value, day P&L and total P&L, a market pulse strip (SPY/QQQ/DIA + VIX), your biggest portfolio and watchlist movers today, earnings reporting in the next 7 days, active price alerts, a "What\'s New" card highlighting the 3 most recent feature additions, and a "Recently Visited" row of the tabs you use most.' },
      { type: 'p', text: 'Press ⌘K (Mac) or Ctrl+K (Windows/Linux) anywhere in the app — or click the Search button in the header — to open the command palette. Start typing to fuzzy-search all 90+ tools by name or group, use ↑/↓ to move the selection, and Enter to jump straight there. With an empty query it shows your recently visited tabs.' },
      { type: 'h3', text: 'Live Price Feed' },
      { type: 'p', text: 'Prices update via WebSocket during market hours. The green dot in the header means the live feed is connected. If it turns grey the app falls back to REST polling at your chosen refresh interval (5s to 5m). Price changes flash green (up) or red (down) in the Watchlist.' },
      { type: 'tip', text: 'Tip: set the refresh interval to 5s during active trading hours and 5m when you\'re monitoring passively to reduce API calls.' },
      { type: 'h3', text: 'Export to PDF' },
      { type: 'p', text: 'Click "Export PDF" in the header (next to the refresh button) on any page to save its contents to a PDF, via your browser\'s native print dialog — choose "Save as PDF" as the destination. Available on every page.' },
      { type: 'tip', text: 'The export preserves the app\'s exact dark theme and colors rather than converting to a light print layout. If a Chart Modal or the Command Palette is open when you export, whichever is on top gets captured, but a long modal isn\'t guaranteed to print in full — close it first for a full-page export of the underlying tab.' },
    ],
  },
  {
    id: 'market',
    title: 'Markets',
    icon: '◫',
    blocks: [
      { type: 'h3', text: 'Market Overview' },
      { type: 'p', text: 'A single-page snapshot of market health. Sortable tables show multi-timeframe performance (1D, 5D, 1M, 3M, 6M, 1Y, YTD) for major indices & ETFs, sector ETFs, and the Magnificent 7. Below the tables, top 10 gainers and losers update with each refresh. The right sidebar shows the latest market headlines with external links.' },
      { type: 'bullets', items: [
        'Click any column header to sort ascending / descending.',
        'Click any row to open the full chart modal for that ticker.',
        'Use the ↻ button or set a refresh interval to keep data current.',
      ]},
      { type: 'h3', text: 'Analyst Picks' },
      { type: 'p', text: 'Two sections: AI-powered analyst upgrades/downgrades, and a curated AI Growth Watch List covering the full AI technology stack (Chips, Memory, Networking, Cloud, Models, Applications, and more).' },
      { type: 'bullets', items: [
        'Filter the watch list by AI layer using the pill buttons at the top.',
        'Click any stock row to open its chart modal.',
        'Analyst actions show firm, prior rating, new rating, and price target — click for a detail modal.',
      ]},
      { type: 'h3', text: 'Market Breadth' },
      { type: 'p', text: 'Scans a large-cap universe to measure overall market health beyond just index prices.' },
      { type: 'table', headers: ['Metric', 'What it means'], rows: [
        ['Above 50-day MA %', 'Percentage of stocks trading above their 50-day moving average. Above 70% = broad bull market. Below 30% = broad weakness.'],
        ['Above 200-day MA %', 'Long-term trend. Above 60% = healthy bull market.'],
        ['H/L Ratio', 'New 52-week highs vs lows. Above 0.6 = bullish breadth.'],
        ['A/D Ratio', 'Advances ÷ Declines. Above 1.5 = strong up day, below 0.7 = broad selling.'],
        ['Put/Call Ratio', 'Options market sentiment. Above 1.2 = fear/hedging; below 0.7 = complacency/greed.'],
        ['VIX', 'CBOE Volatility Index. Below 15 = calm, 15–25 = normal, 25–30 = elevated, above 30 = fear.'],
      ]},
      { type: 'p', text: 'The Advance/Decline Line chart shows 60 days of cumulative market momentum. Divergence from index prices is an early warning signal.' },
      { type: 'h3', text: 'Yield Curve & Rates' },
      { type: 'p', text: 'Tracks the US Treasury yield curve and Dollar Index, updated every 30 minutes.' },
      { type: 'bullets', items: [
        'The yield curve chart plots 13-week, 5-year, 10-year, and 30-year yields. A downward-sloping line (inverted) historically precedes recessions.',
        'The 10Y − 13W spread in basis points is the key inversion signal. A red "INVERTED" badge appears when this spread goes negative.',
        'DXY (US Dollar Index): rising dollar typically pressures commodities and international earnings.',
        'The 60-day 10Y sparkline shows the direction of long-term rate pressure.',
      ]},
      { type: 'h3', text: 'Macro Calendar' },
      { type: 'p', text: 'Upcoming high-impact economic events: FOMC decisions, CPI, PPI, PCE, NFP (jobs report), and GDP releases.' },
      { type: 'bullets', items: [
        'Filter by event type using the icon buttons (All, FOMC, CPI, PPI, Jobs, PCE, GDP).',
        'Events within 3 days show a red urgency badge; 4–7 days amber; 8+ days blue.',
        'Past events are greyed out and labelled "Passed".',
      ]},
      { type: 'tip', text: 'Tip: check the Macro Calendar before opening a new position — unexpected CPI or FOMC surprises cause outsized market moves.' },
      { type: 'h3', text: 'Index / ETF Heatmap' },
      { type: 'p', text: 'A constituent-level heatmap and performance table for any index or ETF. Tiles are sized by real-time market-cap weight, coloured by 1-day return, and show the stock\'s actual weight percentage inside the index.' },
      { type: 'h3', text: 'Selecting an Index' },
      { type: 'p', text: 'Two ways to choose what to display:' },
      { type: 'bullets', items: [
        'Quick-access buttons: DIA (Dow 30), QQQ (Nasdaq 100), SPY (S&P Top 100), ARKK (ARK Innovation) — click to load instantly.',
        'Search box: type any ETF or index ticker or name (e.g. "XLK", "SOXX", "GLD", "iShares"). A live dropdown shows matching results with type badges (ETF / INDEX). Select to load its constituent heatmap.',
      ]},
      { type: 'h3', text: 'Heatmap View' },
      { type: 'p', text: 'All constituents are displayed as a single flat grid sorted by weight — the largest position in the index occupies the widest tile in the top-left.' },
      { type: 'table', headers: ['Tile element', 'What it shows'], rows: [
        ['Tile width', 'Proportional to the stock\'s live market-cap weight in the index.'],
        ['Background colour', 'Green shades = positive 1D return; red shades = negative; grey = flat. Deeper colour = larger magnitude.'],
        ['Symbol (top)', 'Ticker symbol in bold.'],
        ['Weight % (middle)', 'Actual index weight derived from live market cap (or fund-reported weight for dynamic ETFs).'],
        ['1D % (bottom)', 'Day-over-day price change percentage.'],
        ['Tooltip (hover)', 'Full name, sector, weight, market cap, price, 1D return, and weighted contribution to the index.'],
      ]},
      { type: 'h3', text: 'Summary Bar' },
      { type: 'p', text: 'Four cards above the heatmap provide a quick read on the whole index:' },
      { type: 'table', headers: ['Card', 'Meaning'], rows: [
        ['Index 1D Return', 'Market-cap-weighted sum of all constituents\' 1D returns — this is what the index itself moved.'],
        ['Advancing / Declining', 'Number of constituents up vs down on the day.'],
        ['Top Contributor', 'The stock adding the most percentage points to the index return (weight × 1D).'],
        ['Top Drag', 'The stock subtracting the most from the index return.'],
      ]},
      { type: 'h3', text: 'Table View' },
      { type: 'p', text: 'Switch to Table for a sortable spreadsheet of all constituents. Columns include: Symbol, Name, Sector, Weight %, Market Cap, Price, 1D%, 1D Contribution, 5D%, 1M%, 3M%, 6M%, 1Y%, YTD%.' },
      { type: 'bullets', items: [
        'Click any column header to sort ascending / descending.',
        '"est" badge next to a weight means live market-cap data could not be fetched and an approximation is shown.',
        '1D Contribution = weight × 1D return / 100 — shows how many basis points each stock contributed to the index.',
        'Click any row to open the full chart modal for that stock.',
      ]},
      { type: 'tip', text: 'Tip: use the Index Heatmap with QQQ or SPY before trading to see which mega-caps are dragging or leading the market. A concentrated red tile on AAPL or NVDA (both >5% weight) can explain broad market weakness even when most stocks are green.' },
      { type: 'h3', text: 'Holdings Performance' },
      { type: 'p', text: 'See how every holding of an index or ETF has performed across 1 day, 1 week, 1 month, 3 months, 6 months, year-to-date, 1 year, 3, 5 and 10 years, and life-to-date (since each stock\'s first trade), ranked by YTD return so the year\'s leaders sit on top. Found under Markets → Holdings Performance.' },
      { type: 'table', headers: ['Control', 'What it does'], rows: [
        ['S&P 500 / Nasdaq-100 / Dow 30', 'Every constituent of the index. The S&P 500 takes about 30–60 seconds the first time (it downloads decades of price history for ~500 stocks), then loads instantly from cache.'],
        ['Sector ETFs', 'The 11 Select Sector SPDRs (XLK, XLF, XLV…), shown as their S&P 500 sector members.'],
        ['Any ETF', 'Type a ticker. Index ETFs like SPY, IVV, VOO, QQQ and DIA show every holding of their index. Other ETFs (ARKK, VTI, IWM…) show only the top 10 holdings Yahoo publishes — flagged on the page, since a complete list isn\'t freely available.'],
        ['Click a column header', 'Sorts by that period (and again to reverse). Stocks without that much history always sink to the bottom.'],
        ['Annualise 3Y+', 'Switches the 3Y, 5Y, 10Y and LTD columns from cumulative to per-year returns, which makes a stock with 4 years of history comparable to one with 40.'],
        ['Sector / Filter', 'Narrow to a sector or search by symbol or name; the Average, Median, % up and % beating-benchmark rows recompute for what is shown.'],
        ['Export CSV', 'Downloads exactly the rows shown, in the current order and mode.'],
      ]},
      { type: 'bullets', items: [
        'Returns are total returns: dividends are reinvested. The pinned blue row is the benchmark (SPY for the S&P 500, QQQ for the Nasdaq-100, the fund itself for an ETF).',
        'A dash means the stock hadn\'t been listed that long. Hover an LTD cell to see its start date. Click any symbol to open its chart.',
      ]},
      { type: 'tip', text: 'Tip: sort by 1D or 1W to see what is moving now, YTD for the year\'s winners, and then compare against the "% beating SPY" row — in many years only a third of the index beats it.' },
      { type: 'h3', text: 'Fed Watch' },
      { type: 'p', text: 'Tracks FOMC meeting dates and derives rate-change probabilities from 30-day Fed Funds futures (CME ZQ contracts). The target range is fetched live from the 13-week T-bill rate, so it updates automatically when the Fed moves.' },
      { type: 'table', headers: ['Element', 'What it shows'], rows: [
        ['Current Target', 'Live Fed Funds target range (e.g. 3.75%–4.00%) derived from the 13-week T-bill.'],
        ['Next Meeting highlight', 'Date, days until meeting, and cut/hold/hike probability gauges.'],
        ['Meeting grid', 'Full calendar of all FOMC meetings with implied rate and probabilities for each.'],
        ['Probability gauges', 'Circular dials showing Cut %, Hold %, and Hike % derived from futures pricing.'],
        ['Rate history chart', '52-week 13-week T-bill rate chart showing the rate trend.'],
        ['Rate move reference', 'Table of scenarios (double cut, cut, hold, hike) and typical market impact.'],
      ]},
      { type: 'p', text: 'Implied rate = 100 − ZQ futures price. Probability of cut = (current midpoint − implied rate) ÷ 0.25 × 100. This is a simplified version of the CME FedWatch methodology.' },
      { type: 'tip', text: 'Tip: a high cut probability for the next meeting is generally bullish for growth/tech stocks and bonds. Check Fed Watch before trading rate-sensitive positions (utilities, REITs, financials).' },
      { type: 'h3', text: 'Short Squeeze Scanner' },
      { type: 'p', text: 'Scans a universe of ~120 high-short-interest stocks and scores each one on squeeze potential. Results are sorted by score, refreshed every 30 minutes.' },
      { type: 'table', headers: ['Score Component', 'Weight', 'What it measures'], rows: [
        ['Short % of Float', '40 pts', 'What percentage of available shares are sold short. Above 20% is elevated; above 40% is extreme.'],
        ['Days to Cover', '30 pts', 'Shares short ÷ average daily volume. Higher = shorts need more days to exit = more pain if squeezed.'],
        ['Price Momentum', '20 pts', 'Today\'s % change. Positive price action on high short interest suggests squeeze may be starting.'],
        ['SI Change (MoM)', '10 pts', 'Month-over-month change in shares short. Rising SI builds pressure; falling SI means shorts are covering.'],
      ]},
      { type: 'table', headers: ['Level', 'Score Range', 'Interpretation'], rows: [
        ['EXTREME', '70–100', 'Very high squeeze potential. All four factors are elevated simultaneously.'],
        ['HIGH',    '50–69',  'Strong squeeze setup. Multiple factors are elevated.'],
        ['MEDIUM',  '30–49',  'Elevated short interest but momentum or DTC is moderate.'],
        ['LOW',     '10–29',  'Some short interest present but squeeze conditions are not aligned.'],
      ]},
      { type: 'bullets', items: [
        'Click any column header to sort the table (score, short %, days to cover, etc.).',
        'Filter by level using the pill buttons (ALL / EXTREME / HIGH / MEDIUM / LOW).',
        'Add custom symbols in the input box to include them in the scan alongside the built-in universe.',
        'SI Change (MoM) positive (red) = shorts are adding — pressure building. Negative (green) = shorts covering.',
        'Note: short interest is reported bi-monthly by FINRA — data may be up to 2 weeks stale.',
      ]},
      { type: 'tip', text: 'Warning: short squeezes are highly unpredictable and can reverse violently. A high squeeze score is a risk signal, not a buy signal. Always size positions conservatively and set hard stops.' },
      { type: 'h3', text: 'IPO & Lockup Calendar' },
      { type: 'p', text: 'Live from SEC EDGAR — no longer a hand-maintained list. Two feeds: recently-priced IPOs with a lockup-expiration countdown (built from 424B4 final-prospectus filings), and an upcoming pipeline of companies that have filed to go public but haven\'t priced yet (built from S-1 registrations). SPACs are excluded from both — see the SPACs module for those.' },
      { type: 'table', headers: ['Column', 'What it tells you'], rows: [
        ['Day-1 Open', 'The stock\'s first trading day opening price — used as a proxy for the underwriting offer price, since EDGAR\'s search index doesn\'t expose the actual offer price.'],
        ['Since IPO %', 'Percentage gain or loss vs. Day-1 Open. Green = above, red = below.'],
        ['Days Since IPO', 'How long the stock has been trading publicly (measured from the 424B4 filing date).'],
        ['Lockup Progress bar', 'How far through the (assumed 180-day) lockup period the stock is. Red = expiring ≤14 days, orange = ≤30 days, yellow = ≤60 days.'],
        ['Days to Lockup', 'Countdown to lockup expiry. Negative = already expired.'],
      ]},
      { type: 'bullets', items: [
        '"Upcoming — Filed, Not Yet Priced" panel: S-1 registrations from the last 60 days, searchable by ticker or company. Click EDGAR to read the actual filing.',
        'Active Lockups tab: stocks where insiders are still restricted from selling.',
        'Expired tab: stocks where the lockup has passed — insiders may have sold.',
        'Summary cards show how many lockups are active, expiring within 30 days, and already expired.',
        'Stocks with strong post-IPO gains and an imminent lockup carry the highest insider-selling risk.',
      ]},
      { type: 'tip', text: 'Tip: combine IPO & Lockup Calendar with the Short Squeeze Scanner. A stock with high short interest and an imminent lockup expiry faces two opposing forces — shorts betting on post-lockup selling vs bulls expecting momentum to continue.' },
      { type: 'tip', text: 'The 180-day lockup is the standard underwriting default, not a disclosed fact per company — actual terms occasionally differ. Day-1 Open is a close proxy for the offer price but can diverge meaningfully on IPOs that pop or drop hard on debut.' },
      { type: 'h3', text: 'Insider Trading Feed' },
      { type: 'p', text: 'A market-wide scanner of SEC Form 4 filings showing open-market purchases and sales by corporate insiders across ~150 large and mid-cap companies. Found under Markets → Insider Trading.' },
      { type: 'steps', items: [
        'Select a time window (7d / 14d / 30d / 60d) — the feed shows all filings within that period.',
        'Use the filter tabs to focus: Buys Only (most actionable), C-Suite (highest-conviction insiders), $500k+ (significant dollar size), Cluster Buys (multiple insiders at the same stock).',
        'Search by ticker, insider name, or company name using the search box.',
        'Click any column header to sort — sorting by Value descending surfaces the largest purchases first.',
        'Hit ↻ Refresh to reload fresh data (results are cached for 4 hours per time window).',
      ]},
      { type: 'table', headers: ['Badge', 'Meaning'], rows: [
        ['[C]', 'C-Suite insider — CEO, CFO, COO, President, CTO, or Chairman. Their purchases carry more weight than director purchases.'],
        ['×N', 'Cluster buy — N different insiders have bought this stock in the selected window. Cluster buys are historically the strongest bullish signal.'],
        ['▲ Buy (green)', 'Open-market purchase: insider spent their own cash to buy shares. The most discretionary and bullish signal.'],
        ['▼ Sale (red)', 'Insider sale. Less informative — executives sell for many reasons (diversification, liquidity, taxes). Only significant if unusually large or widespread.'],
      ]},
      { type: 'table', headers: ['Filter', 'When to use it'], rows: [
        ['Buys Only', 'Default for signal hunting — removes sales noise and shows only purchases.'],
        ['C-Suite', 'Highest-conviction filter: CEOs and CFOs buying is a strong vote of confidence in the business.'],
        ['$500k+', 'Filters for meaningful dollar size — small $5k purchases by directors are common but less significant than a CFO buying $2M.'],
        ['Cluster Buys', 'The strongest signal: when multiple insiders independently buy the same stock in a short window, it suggests the company may be meaningfully undervalued.'],
      ]},
      { type: 'bullets', items: [
        'Excluded from the feed: stock grants, option exercises, gifts, and automatic 10b5-1 plan transactions. Only discretionary open-market trades are shown.',
        'The Largest Buy callout card highlights the single largest open-market purchase in the selected window.',
        'Summary cards show total buy count, sale count, total buy value, and number of cluster buy stocks.',
        'Coverage spans ~150 companies across all major sectors — not a complete market scan of all 8,000+ public companies.',
        'First load takes 20–30 seconds while the backend fetches from ~150 tickers in parallel; subsequent loads within 4 hours are instant.',
      ]},
      { type: 'tip', text: 'Tip: the strongest insider buy signals combine cluster (×2 or more), C-Suite status, and $500k+ dollar size — use all three filters together for the highest-conviction opportunities. Cross-reference with Fundamentals and the Short Squeeze Scanner for a fuller picture.' },
      { type: 'tip', text: 'Disclaimer: insider transactions are reported retrospectively (often with a 2-business-day delay after the trade) and do not guarantee future stock performance. This feed is for informational and educational purposes only — not investment advice.' },
      { type: 'h3', text: 'Reddit Trending' },
      { type: 'p', text: 'Most-mentioned tickers across finance subreddits, sourced from ApeWisdom (a free, unauthenticated aggregation service — Reddit itself blocks direct scraping). Found under Markets → Reddit Trending.' },
      { type: 'steps', items: [
        'Filter by source: All Stocks (aggregated across finance subreddits, crypto excluded), r/wallstreetbets, r/stocks, or r/options.',
        'The main table is sortable by rank, mentions, mentions change, rank change, upvotes, price, or 5-day return.',
        '"Rising Attention" and "Cooling Attention" panels surface the biggest 24h rank movers in each direction.',
        'Search by ticker or company name.',
      ]},
      { type: 'tip', text: 'Important: this measures attention volume and momentum, not bullish/bearish sentiment. ApeWisdom doesn\'t classify whether mentions are positive or negative, so a ticker can spike from good news, bad news, or an unrelated meme. Treat "Rising Attention" as "worth checking why," not a buy or sell signal.' },
      { type: 'h3', text: 'Crypto Dashboard' },
      { type: 'p', text: 'Live prices, market caps, 24-hour and 7-day performance for the top 20 cryptocurrencies by market cap. Found under Markets → Crypto.' },
      { type: 'bullets', items: [
        'BTC and ETH hero cards show price, 24h change, 7d change, market cap, and 24h volume with directional colour coding (green = up, red = down).',
        'The Market Overview card shows total crypto market cap, BTC dominance %, and ETH dominance % with progress bars.',
        'The Fear & Greed Index gauge (0–100) reflects overall crypto market sentiment: 0 = Extreme Fear, 100 = Extreme Greed, sourced from alternative.me.',
        'The full coins table is sortable by any column — click a header to sort. Defaults to market cap descending.',
        'Data is cached for 5 minutes. Click ↻ Refresh to force a reload.',
        'Prices via Yahoo Finance; Fear & Greed via alternative.me. For informational purposes only.',
      ]},
    ],
  },
  {
    id: 'economy',
    title: 'Economy',
    icon: '◔',
    blocks: [
      { type: 'p', text: 'Three views that turn macro data into something you can act on, plus Fed Watch, Yield Curve and Macro Calendar. Data comes from FRED (the St. Louis Fed) with no API key, and goes back to 1948 for the oldest series.' },
      { type: 'h3', text: 'Regime Dashboard' },
      { type: 'p', text: 'Where the economy sits in the cycle right now, in three readings built from the Indicators page by fixed rules (nothing is fitted).' },
      { type: 'table', headers: ['Reading', 'How it is built'], rows: [
        ['Cycle phase', 'Early recovery, Mid-cycle, Late cycle, Slowdown or Recession risk, from the level of a growth composite and whether it is rising or falling. A high recession-risk score overrides it.'],
        ['Growth & inflation quadrant', 'Goldilocks (growth up, inflation down), Overheating (both up), Slowdown (both down) or Stagflation (growth down, inflation up), from the three-month direction of each composite. The dot shows today with a 12-month trail.'],
        ['Recession-risk score (0-100)', 'A weighted blend of ten warning signs: inverted yield curve, Sahm rule, jobless claims, CFNAI, credit spreads, payrolls, industrial production, financial conditions, bank lending standards and building permits. Each contributes a stress level by a stated rule; the table shows all ten.'],
      ]},
      { type: 'bullets', items: [
        'The bottom-left table shows how the score behaved around every US recession since 1973: its peak, when it first crossed 40 and how many months before the recession began. It is a conditions gauge, not a timing tool: it has also lingered after recessions and crossed 40 without one.',
        'Growth and inflation scores compare each reading with that indicator\'s own history up to that date, so the 1990s are not judged against the 2020s.',
        'Click any key-indicator tile to open the Indicators page.',
      ]},
      { type: 'h3', text: 'Indicators' },
      { type: 'p', text: 'More than 50 macro and micro indicators across growth, labor, inflation, rates, credit, housing, consumers and global markets. Each row shows the latest reading, the three-month and one-year change, where it ranks in its own history (percentile), its trend, a two-year sparkline and a Supportive / Neutral / Cautionary signal for stocks with the reason.' },
      { type: 'bullets', items: [
        'Click a row for the full history with US recessions shaded, a 5/10/20-year/Max range, warning levels or comfort bands drawn on the chart, and plain-English notes on what it is, why markets care and how to read it.',
        'Filter by category, signal or timing (leading, coincident or lagging), or search by name.',
        'The signal is a rule, not a forecast: a warning level first, then a comfort band, then whether the trend is moving the way that has historically been better for stocks. Improving from an extreme tail is shown as Neutral, not Supportive.',
        'Because FRED stores revised history, some past relationships look cleaner than they did at the time. Series that have not updated recently are marked "stale".',
      ]},
      { type: 'h3', text: 'Indicator Studies' },
      { type: 'p', text: 'What has the market actually done after a macro condition appeared? Nineteen studies (yield curve inverted or un-inverted, Sahm rule triggered, jobless claims surging, inflation above 5%, Fed cutting or hiking, wide credit spreads, tight financial conditions, high real yields, low sentiment, weak factory surveys, dollar or oil spikes, permits collapsing, unemployment rising, elevated recession risk and more).' },
      { type: 'bullets', items: [
        'Each study shows the S&P 500 over the next 1, 3, 6, 12 and 36 months against what any random month delivered, with sample sizes, % of episodes that were higher and the worst case.',
        'Returns are measured from the start of each episode, not every month in the state, so overlapping months do not inflate the sample. Entry is delayed by the data\'s publication lag so a study never trades on numbers nobody had yet.',
        'The sector panel shows each sector\'s average 12-month return relative to SPY across the episodes since 1999. Studies with fewer than 4 episodes are flagged as anecdotal.',
      ]},
      { type: 'tip', text: 'Tip: if a condition is flagged "Active now", read its table twice: first for the average, then for the worst episode. The average rarely tells you what the bad outcome looked like.' },
      { type: 'p', text: 'Fed Watch, Yield Curve and Macro Calendar are documented under Markets above; they now live in this group.' },
    ],
  },
  {
    id: 'sectors',
    title: 'Sectors',
    icon: '◕',
    blocks: [
      { type: 'p', text: 'A US sector-ETF strategy toolkit built on the eleven SPDR sector funds (XLK, XLF, XLV, XLY, XLP, XLE, XLI, XLB, XLU, XLRE, XLC) against SPY. Prices are total return (dividends reinvested). Real Estate starts in late 2015 and Communication Services in mid-2018, so longer periods show a dash for them.' },
      { type: 'h3', text: 'Scoreboard' },
      { type: 'p', text: 'Every sector over 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, 10Y and life-to-date, with SPY and equal-weight S&P 500 rows underneath.' },
      { type: 'bullets', items: [
        'Switch between Returns, Risk (volatility, max drawdown, return per unit of risk, beta, up- and down-capture) and Calendar years views. Sort by any column.',
        '"vs SPY" shows excess return instead of total return. "Annualise 3Y+" converts multi-year columns to per-year figures.',
        'Leaders and laggards bars rank sectors for any period; the relative-strength table shows how each sector\'s ratio to SPY has changed and whether it is in an uptrend (price vs 50- and 200-day averages).',
        'Holdings → opens Markets → Holdings Performance for that sector fund, ranked by YTD.',
        'Risk figures use the trailing three years of monthly data (max drawdown uses daily prices), and a sector with a shorter life is flagged.',
      ]},
      { type: 'h3', text: 'Rotation Map' },
      { type: 'p', text: 'A relative-rotation view. Horizontal: is the sector stronger or weaker than SPY\'s trend (RS-Ratio, 100 = in line)? Vertical: is that strength speeding up or slowing (RS-Momentum)? The four quadrants are Leading, Weakening, Lagging and Improving; sectors tend to travel clockwise.' },
      { type: 'bullets', items: [
        'Weekly data. Choose no trail, 4 weeks or 8 weeks to see where each sector has been heading. Hover a sector (on the map or in the list) to highlight it.',
        'A sector can stay in one quadrant for months, and rotations do not always complete: use it to see leadership changing, not to time a trade.',
      ]},
      { type: 'h3', text: 'Sector Screener' },
      { type: 'p', text: 'Ranks the sectors for the horizon you care about: Tactical (1-3 months), Intermediate (3-12 months) or Strategic (1-5+ years). Every factor is scored 0-100 by ranking the sectors against each other, then blended with weights suited to that horizon.' },
      { type: 'table', headers: ['Factor', 'What it measures'], rows: [
        ['Price momentum', 'Excess return versus SPY over horizon-appropriate windows (annualised for multi-year ones).'],
        ['Trend', 'Price vs its 50- and 200-day averages and how far above or below the 200-day it is.'],
        ['Rotation', 'RS-Ratio and RS-Momentum from the Rotation Map.'],
        ['Risk-adjusted return', 'Return per unit of volatility over 3 years (1 year for Tactical).'],
        ['Resilience', 'Smaller maximum drawdown scores higher.'],
        ['Seasonality', 'Average excess return in the coming three calendar months across history.'],
        ['Cycle fit', 'Sector excess return in the current cycle phase (from Cycle Fit). Only used when economic data is available and the phase has at least 6 months of evidence.'],
      ]},
      { type: 'bullets', items: [
        'Click a sector to see each factor\'s rank, weight and points. The coloured bar shows what built the score.',
        'Move the weight sliders to try your own blend; Reset returns to the horizon\'s defaults. Weights are relative.',
        'Overweight is a score of 62 or more, Underweight 38 or less. Scores are relative attractiveness, not expected returns.',
        'Valuation is deliberately left out: point-in-time sector valuation history is not freely available, and a screen on today\'s multiples against revised history would mislead.',
      ]},
      { type: 'h3', text: 'Cycle Fit' },
      { type: 'p', text: 'The average monthly return of each sector minus SPY in each cycle phase (or growth/inflation quadrant) since 1999. Hover a cell for the number of months, the number of separate stretches and the share of months the sector beat SPY. Fewer than 24 months shows the count. The column for the current phase is marked.' },
      { type: 'tip', text: 'Tip: Energy leading in Late cycle or Utilities in Slowdown can come down to one or two episodes. Check the hover detail before relying on a cell.' },
      { type: 'h3', text: 'Sector Backtest' },
      { type: 'p', text: 'A simple rule-based rotation tested since 2000: each month-end buy the top N sectors by momentum, trend and risk using only data known then, hold for a month, and optionally retreat to Staples, Utilities and Health Care while SPY is below its 10-month average. Compared with SPY and equal-weight sectors, with a trading cost per side.' },
      { type: 'bullets', items: [
        'Change the number of sectors, the cost and the defensive switch. If a small change flips the result from a win to a loss, the edge is probably not robust.',
        'The results table shows CAGR, volatility, return per risk, max drawdown, worst month and total return; below it, how often the strategy beat SPY, annual turnover and the sectors for next month.',
        'It is hypothetical, ignores taxes and slippage, and covers only a few market cycles. Rules chosen after seeing the data flatter any backtest.',
      ]},
    ],
  },
  {
    id: 'watchlist',
    title: 'Watchlist',
    icon: '◎',
    blocks: [
      { type: 'h3', text: 'Watchlist Heatmap' },
      { type: 'p', text: 'A treemap of all your watchlist symbols, sized by market cap and coloured by return. Found under Watchlist → Heatmap. The 1D view is instant and live (no extra fetch needed — it uses the same real-time data as the Watchlist table). Extended periods (5D/1M/3M) are fetched on demand and cached for 5 minutes.' },
      { type: 'table', headers: ['Control', 'What it does'], rows: [
        ['Period (1D/5D/1M/3M)', '1D is live. Selecting 5D/1M/3M triggers a backend fetch for the selected symbols\' historical returns. The first load takes a few seconds; subsequent loads within 5 minutes are instant.'],
        ['Mkt Cap / Equal sizing', 'Mkt Cap: tile size is proportional to each company\'s market capitalisation — Apple and Microsoft will be the largest tiles. Equal: all tiles the same size, making it easier to compare smaller positions.'],
        ['Heatmap / Table view', 'Heatmap shows the visual treemap. Table shows a sortable spreadsheet with all period columns side by side. Click any column header in Table view to sort.'],
      ]},
      { type: 'p', text: 'Colour scale: dark red ≤ −5% → light red −1% → grey 0 → light green +1% → dark green ≥ +5%. Hover any tile to see a full tooltip with name, price, market cap, sector, and all available period returns.' },
      { type: 'bullets', items: [
        'Summary cards show total symbols, advancing count, declining count, top gainer, and biggest loser for the selected period.',
        'Tiles are sorted largest-first (top-left) so the most market-cap-significant stocks are always prominent.',
        'A green dot next to the 1D button confirms live data is active.',
        'The Table view shows 5D/1M/3M columns only once extended data is loaded — columns appear automatically after the first non-1D period is selected.',
        'A coloured sidebar stripe in each table row matches the heatmap colour for that stock\'s return.',
      ]},
      { type: 'tip', text: 'Tip: use the heatmap at the start of the trading day to immediately see which of your watchlist stocks are moving — red concentration in one area (e.g. all your tech names red) signals sector-wide weakness, while isolated red tiles suggest stock-specific news.' },
      { type: 'h3', text: 'Correlation Matrix' },
      { type: 'p', text: 'Color-coded grid showing how closely any set of stocks move together over a selected lookback period. Found under Watchlist → Correlation. Helps you spot hidden concentration risk — if most of your positions are highly correlated, a single market shock hits everything at once.' },
      { type: 'steps', items: [
        'Enter symbols manually or click "⬇ Watchlist" to import all your watchlist symbols.',
        'Choose a lookback period: 1M, 3M, 6M, 1Y, or 2Y. Longer periods smooth out noise; shorter periods reflect recent relationships.',
        'Click "▶ Run Correlation." The backend fetches daily closes and computes Pearson correlation for every pair.',
        'Hover any cell to see an exact tooltip with the two symbols and their correlation value.',
        'Sort the matrix "By Connectivity" (most cross-correlated symbols first) or A–Z.',
      ]},
      { type: 'table', headers: ['Color', 'Meaning'], rows: [
        ['Dark green (≥0.9)', 'Very high positive correlation — the two stocks move almost in lockstep.'],
        ['Light green (0.3–0.7)', 'Moderate positive correlation — tend to move in the same direction but not always.'],
        ['Pale (near 0)', 'Near-zero correlation — largely independent movements. Excellent diversification.'],
        ['Light red (negative)', 'Negative correlation — one tends to rise when the other falls. Rare in equities outside of inverse ETFs.'],
      ]},
      { type: 'tip', text: 'Tip: correlation is not stable — it tends to spike toward 1.0 during market crises as all risky assets sell off together. A portfolio that looks diversified in normal markets may offer little protection in a crash. Run the matrix during periods of stress to see how your diversification actually holds up.' },
      { type: 'h3', text: 'Managing Your Watchlist' },
      { type: 'p', text: 'The watchlist is the core of the app. All features that reference "your symbols" (Signals, Sentiment, Earnings+, Trade Ideas) draw from it.' },
      { type: 'steps', items: [
        'Add a ticker: type it in the header input and press Enter or click "+ Add".',
        'Remove a ticker: click the × on the right side of any watchlist row.',
        'Create named lists: click "+ New List" to organise symbols into separate watchlists (e.g. "Tech", "Options Plays"). Switch between lists using the list pills above the table.',
        'Delete a list: switch to it and click the × next to its name. The default list cannot be deleted.',
      ]},
      { type: 'h3', text: 'Watchlist Table Columns' },
      { type: 'table', headers: ['Column', 'Description'], rows: [
        ['Price', 'Last trade price. Flashes green on uptick, red on downtick.'],
        ['Chg ($) / Chg (%)', 'Day change in dollars and percentage, colour-coded.'],
        ['Day Range', 'Low–high bar showing where the current price sits within the day\'s range.'],
        ['Volume', 'Today\'s volume in millions.'],
        ['52W Range', 'Bar showing current price position within the 52-week high/low range.'],
        ['Mkt Cap', 'Market capitalisation.'],
        ['Earnings', 'Days until next earnings report (badge turns red when ≤ 3 days).'],
      ]},
      { type: 'p', text: 'Click any row to open the full chart modal for detailed analysis.' },
      { type: 'h3', text: 'Price Alerts' },
      { type: 'p', text: 'Click the 🔔 icon on any watchlist row to open the alert manager for that symbol.' },
      { type: 'bullets', items: [
        'Price alert: fires when the stock crosses above or below a specific price.',
        'Percent change alert: fires when the day\'s move exceeds a % threshold.',
        '52-week break: fires when the price breaks the 52-week high or low.',
        'Volume spike: fires when volume exceeds a multiple of the 20-day average.',
        'Alerts persist in the database and survive page reloads.',
        'Allow browser notifications for alerts to fire even when you\'re on another tab.',
        'Triggered alerts show a toast notification bottom-right and are marked in the alert list.',
      ]},
      { type: 'h3', text: 'Price Targets' },
      { type: 'p', text: 'Set personal price targets with optional deadlines and notes. Found under Watchlist → Price Targets.' },
      { type: 'steps', items: [
        'Fill in the symbol, target price, optional deadline date, and a note (e.g. your trade thesis).',
        'Click "+ Add". The target appears as a card showing current vs target price with a progress bar.',
        'Cards are sorted by distance to target (most urgent first).',
        'A "Target Reached!" badge appears when the current price meets or exceeds your target.',
        'Click ✕ on a card to remove the target.',
      ]},
      { type: 'table', headers: ['Indicator', 'Meaning'], rows: [
        ['▲ Long (green)', 'Target is above current price — bullish thesis.'],
        ['▼ Short (red)', 'Target is below current price — bearish thesis.'],
        ['Days badge red < 7d', 'Deadline approaching imminently.'],
        ['Days badge amber 7–30d', 'Moderate urgency.'],
        ['Passed (grey)', 'Deadline has passed without reaching target.'],
      ]},
      { type: 'h3', text: 'Earnings+' },
      { type: 'p', text: 'An enriched earnings calendar for your watchlist and portfolio symbols, showing historical context beyond just the date.' },
      { type: 'table', headers: ['Column', 'What it tells you'], rows: [
        ['EPS Estimate', 'Consensus analyst EPS estimate for the upcoming quarter.'],
        ['Beat Rate', 'Percentage of past quarters where EPS beat the estimate, with a progress bar.'],
        ['Pre-Drift 5d', 'Average stock return in the 5 days before earnings — shows if the stock typically runs into results.'],
        ['Expected Move ±%', 'Options-implied expected move (ATM straddle ÷ price) — the market\'s priced-in reaction.'],
      ]},
      { type: 'h3', text: 'Smart Alerts' },
      { type: 'p', text: 'Condition-based alert rules you scan on demand. Found under Watchlist → Smart Alerts.' },
      { type: 'table', headers: ['Alert Type', 'Triggers when'], rows: [
        ['Volume Spike', 'Today\'s volume exceeds N × the 20-day average (configurable multiplier).'],
        ['Gap Up / Gap Down', 'Today\'s open is N% above/below the prior close.'],
        ['RSI Overbought', 'RSI(14) crosses above 70.'],
        ['RSI Oversold', 'RSI(14) crosses below 30.'],
        ['Golden Cross', '50-day MA crosses above 200-day MA.'],
        ['Death Cross', '50-day MA crosses below 200-day MA.'],
        ['Earnings Proximity', 'Earnings are within N days.'],
      ]},
      { type: 'steps', items: [
        'Add a rule: select symbol, alert type, and set the parameter (e.g. multiplier = 2.5).',
        'Click "Scan" to check all rules against current data.',
        'Triggered alerts appear in the results section with a detail message.',
        'Delete rules you no longer need by clicking × on the rule row.',
      ]},
      { type: 'tip', text: 'Tip: Smart Alerts complement the automatic Price Alerts (bell icon on watchlist rows). Price Alerts fire automatically; Smart Alerts require a manual scan click and support more complex technical conditions.' },
      { type: 'h3', text: 'News Sentiment' },
      { type: 'p', text: 'Click "Analyze Sentiment" to fetch recent headlines for all watchlist symbols and score them with Claude AI.' },
      { type: 'bullets', items: [
        'Each card shows a Bullish / Neutral / Bearish badge, a score from −1 to +1, a one-line AI summary, and the most recent headline.',
        'The score bar is centre-anchored: green extends right (bullish), red extends left (bearish).',
        'Results are cached for 2 hours. Click the button again to refresh.',
      ]},
    ],
  },
  {
    id: 'portfolio',
    title: 'Portfolio',
    icon: '▣',
    blocks: [
      { type: 'h3', text: 'Adding Positions' },
      { type: 'steps', items: [
        'Open Portfolio → Portfolio.',
        'Use the "Add Position" form: enter a ticker, number of shares, and your average cost basis.',
        'Click Add. The position appears in all views immediately.',
        'To remove a position, find it in the Table view and click the × button.',
      ]},
      { type: 'h3', text: 'Portfolio Views' },
      { type: 'p', text: 'Switch between views using the buttons at the top of the Portfolio tab.' },
      { type: 'table', headers: ['View', 'What you see'], rows: [
        ['Heatmap', 'Treemap of positions sized by market value, coloured by day change %. Green = up, red = down. Click any block to open the chart modal.'],
        ['Table', 'Full position table with Symbol, Shares, Avg Cost, Price, Market Value, Unrealised P&L ($/%),  Day P&L, and Portfolio Weight. Click headers to sort. Click "↓ CSV" to download.'],
        ['Equity Curve', 'Your total portfolio value over time vs cost basis. Requires at least two saved daily snapshots (click "Save Snapshot" each day).'],
        ['Exposure', 'Donut charts breaking down your portfolio by sector, market cap size (Mega/Large/Mid/Small), and geographic region. Answers: "am I too concentrated in tech?"'],
        ['Risk', 'Portfolio-level risk metrics: Beta, Concentration (Herfindahl index), Top-3 Weight, VaR 95% 1-day, Sharpe Ratio estimate.'],
        ['Optimizer', 'Efficient Frontier chart — plots the risk/return trade-off and finds the minimum-volatility and maximum-Sharpe portfolios given your current holdings.'],
        ['X-Ray', 'Sector, cap-style, and country exposure donut charts — similar to Exposure but with more granularity.'],
        ['Performance', 'Cumulative return vs SPY and QQQ benchmarks, with alpha and tracking error.'],
        ['Dividends', 'Dividend yield, annual income projection, and payment frequency per position.'],
        ['Correlation', 'Colour-coded pairwise correlation heatmap. Red = highly correlated (concentration risk). Green = diversifying.'],
        ['Rebalancer', 'Enter target weights per position to see how much to buy/sell to reach your target allocation.'],
      ]},
      { type: 'h3', text: 'Risk Metrics Explained' },
      { type: 'table', headers: ['Metric', 'Interpretation'], rows: [
        ['Portfolio Beta', 'Market sensitivity. 1.0 = moves with the market. >1.2 = aggressive, <0.8 = defensive.'],
        ['Herfindahl Index', 'Concentration measure. Below 0.15 = well diversified. Above 0.25 = high concentration.'],
        ['Top-3 Weight', 'If your top 3 positions exceed 60% of the portfolio, a single bad trade can be very damaging.'],
        ['VaR 95% (1-day)', 'Estimated maximum 1-day loss at 95% confidence based on portfolio beta and market volatility.'],
        ['Sharpe Ratio', 'Return per unit of risk. Above 1.0 is good, above 2.0 is excellent.'],
      ]},
      { type: 'h3', text: 'Options P&L' },
      { type: 'p', text: 'Track open options positions with live Greeks and P&L. Found under Portfolio → Options P&L.' },
      { type: 'steps', items: [
        'Add a position: enter Symbol, Type (Call/Put), Strike, Expiry, Quantity (negative for short), and Entry Premium per share.',
        'Click "Refresh P&L" to fetch live mid prices, Delta, Theta, and IV from yfinance.',
        'P&L = (Current Mid − Entry) × Quantity × 100 (one contract = 100 shares).',
        'DTE badge turns red when fewer than 7 days remain — time to decide: close, roll, or let expire.',
      ]},
      { type: 'h3', text: 'Tax Lot Manager' },
      { type: 'p', text: 'Track the cost basis of every share lot you own and simulate sales to minimise tax. Found under Portfolio → Tax Lots. Data stored in browser localStorage.' },
      { type: 'steps', items: [
        'Click "+ Add Lot" and enter: ticker, number of shares, cost basis per share, and purchase date. Add notes for context (e.g. "RSU vest", "DRIP purchase").',
        'Each lot shows its holding period in days and whether it qualifies as long-term (≥365 days, lower LTCG rate) or short-term (ordinary income rate).',
        'Filter the lot table by ticker using the dropdown to see only one position at a time.',
        'Use the Sell Optimizer at the bottom to simulate a sale: enter ticker, shares to sell, current price, and lot selection method. Click "Simulate Sale" to see gain/loss and estimated tax.',
        'Compare methods (Min Tax, FIFO, LIFO, Highest Cost, Lowest Cost) to see which lots produce the lowest tax bill.',
      ]},
      { type: 'table', headers: ['Lot Selection Method', 'Strategy'], rows: [
        ['Min Tax (recommended)', 'Automatically selects the lots that minimise total federal tax — prefers long-term losses, then long-term gains at 0% rate, then high-cost lots to reduce gain.'],
        ['FIFO', 'Sells oldest lots first. Brokerage default — often the worst tax outcome for appreciated positions.'],
        ['LIFO', 'Sells newest lots first. Useful if newest lots have higher cost basis (loss harvesting).'],
        ['Highest Cost First', 'Sells the most expensive lots first to minimise taxable gain. Often optimal for profitable positions.'],
        ['Lowest Cost First', 'Sells cheapest lots first — maximises gain. Useful if you want to realise losses in other positions to offset.'],
      ]},
      { type: 'tip', text: 'Tip: if you hold shares bought in different years with different cost bases, specific lot identification (telling your broker exactly which shares to sell) can save thousands in taxes vs the default FIFO method. Confirm with your broker that specific ID is enabled before trading.' },
      { type: 'h3', text: 'Dividend Tracker' },
      { type: 'p', text: 'Track dividend income, yield on cost, upcoming ex-dividend dates, and long-term DRIP projections for your income portfolio. Found under Portfolio → Dividend Tracker. Positions are stored in browser localStorage — separate from the main Portfolio, so you can focus on just your dividend stocks.' },
      { type: 'steps', items: [
        'Add positions manually using the form: enter a ticker, number of shares, and your average cost per share. Click "+ Add".',
        'Or click "⬇ Import from Portfolio" to automatically pull all positions from the main Portfolio tracker into the Dividend Tracker.',
        'The backend fetches live dividend data for each symbol: annual dividend rate, current yield, ex-dividend date, payout frequency, and last 8 dividend payments.',
        'Switch tabs to explore Holdings (full detail table), Ex-Div Calendar (next 90 days), and DRIP Projection.',
        'Remove any position using the ✕ button in the Holdings table.',
      ]},
      { type: 'table', headers: ['Summary Card', 'What it shows'], rows: [
        ['Annual Income', 'Total projected annual dividend income across all positions (shares × annual dividend rate).'],
        ['Monthly Income', 'Annual income ÷ 12 — useful for income planning.'],
        ['Avg Yield on Cost', 'Weighted average of (annual div ÷ your avg cost) across paying positions. This is your actual income rate on invested capital.'],
        ['Current Yield', 'Annual income ÷ current portfolio market value — the market\'s current yield on your holdings.'],
      ]},
      { type: 'table', headers: ['Holdings Column', 'What it tells you'], rows: [
        ['Ann Div/Share', 'Annual dividend per share (e.g. $2.48/year). Multiplied by your shares = annual income.'],
        ['Current Yield', 'Annual div ÷ current market price. Changes as price moves.'],
        ['Yield on Cost', 'Annual div ÷ your avg cost. Green ≥5%, Blue 3–5%, Yellow 1–3%, Red <1%. This is the more important metric — it measures your actual return on capital deployed.'],
        ['Annual Income', 'Projected annual dividend income from this position.'],
        ['% of Income', 'This position\'s share of your total dividend income. Progress bar shows concentration.'],
        ['Ex-Div Date', 'The last date you must own shares to receive the next payment. Orange = within 7 days, Yellow = within 30 days.'],
        ['Frequency', 'Monthly, quarterly, semi-annual, or annual — computed from spacing of recent dividend history.'],
      ]},
      { type: 'h3', text: 'Ex-Dividend Calendar' },
      { type: 'p', text: 'Shows all upcoming ex-dividend dates within the next 90 days across your positions, sorted chronologically. For each event, it shows the date, days until, the estimated payment you\'ll receive for your share count, and the payout frequency. Orange highlights = ex-date within 7 days (action needed if you don\'t yet own shares).' },
      { type: 'tip', text: 'Important: you must own shares BEFORE the ex-dividend date to receive that payment. Buying on or after the ex-date means you miss that period\'s dividend. Payments typically arrive 2–4 weeks after the ex-date.' },
      { type: 'h3', text: 'DRIP Projection' },
      { type: 'p', text: 'Models long-term dividend income growth assuming all dividends are reinvested (DRIP = Dividend Reinvestment Plan). Shows your projected portfolio value, annual income, and monthly income at years 1, 3, 5, 10, and 20.' },
      { type: 'bullets', items: [
        'Assumes constant dividend yield (current portfolio yield) and dividends reinvested at year-end.',
        'Add a monthly contribution to model additional capital beyond DRIP.',
        'The Growth % column shows how much larger your annual income has become vs today.',
        'This is a simplified model — it does not assume dividend growth rates or price appreciation beyond DRIP reinvestment.',
      ]},
      { type: 'tip', text: 'Tip: Yield on Cost is the key metric for long-term dividend investors. If you bought JNJ at $100 and it now pays $5/year, your YoC is 5% regardless of what the current market yield is. Over time, dividend growth amplifies this further — a stock bought at a 3% yield that grows dividends at 7%/year reaches 6% YoC in 10 years.' },
      { type: 'h3', text: 'Portfolio Stress Test' },
      { type: 'p', text: 'Estimates how your current portfolio would fare during historical market crises, using each stock\'s beta and sector-specific drawdown adjustments. Found under Portfolio → Stress Test. No additional data fetching needed — it reuses existing portfolio positions and live quotes.' },
      { type: 'steps', items: [
        'Add positions to the main Portfolio first. Stress Test reads them automatically on load.',
        'Select one of four historical crisis scenarios — or use Custom to set your own market drawdown percentage.',
        'The tool calculates each stock\'s estimated drawdown as: beta × market decline + sector adjustment (clamped between -2% and -82%).',
        'Browse results by Position (full per-stock table), By Sector (sector-level aggregation), or Vulnerability Chart (horizontal bar chart of dollar losses).',
        'The three insight cards at the bottom highlight Most Vulnerable, Most Resilient, and Biggest Dollar Risk positions.',
      ]},
      { type: 'table', headers: ['Scenario', 'S&P 500 Drop', 'Duration', 'Avg Recovery', 'Key Dynamic'], rows: [
        ['2008 Financial Crisis', '-38%', '6 months', '~4.3 years', 'Financials and Real Estate worst hit; Utilities and Staples held up'],
        ['2020 COVID Crash', '-34%', '5 weeks', '~5 months', 'Energy crushed; Tech and Healthcare surged; fastest-ever recovery'],
        ['2022 Rate Shock', '-25%', '10 months', '~2 years', 'High-multiple growth stocks hit hardest; Energy rallied 24%'],
        ['2000 Dot-com Bust', '-49%', '30 months', '~7 years', 'Tech and Telecom fell 40-78%; Value and Staples largely spared'],
        ['Custom', 'User-defined', 'N/A', 'N/A', 'Uniform beta × drawdown for all positions; no sector adjustments'],
      ]},
      { type: 'table', headers: ['Column', 'What it shows'], rows: [
        ['Beta', 'Sensitivity to market moves. Beta > 1 = more volatile than market. Beta < 1 = more stable. Defaults to 1.0 when unavailable.'],
        ['Est. Drop', 'This position\'s estimated drawdown in the selected scenario, color-coded: gray <10%, yellow 10-20%, orange 20-35%, red 35-50%, dark red 50%+.'],
        ['Est. Loss', 'Dollar loss in this position at the stressed price (current value × drawdown %).'],
        ['Stressed Val', 'What this position would be worth at the scenario low.'],
        ['P&L at Low', 'Your unrealised P&L relative to your cost basis after the drawdown — shows whether you\'d still be positive even at the crisis low.'],
      ]},
      { type: 'tip', text: 'Tip: "P&L at Low" reveals which positions have a large enough cushion to survive a crisis while still keeping you above water. A stock you bought at a 50% discount to its current price might show a stressed P&L that\'s still positive even in a 2008-style crash — and that\'s a position you can hold through a downturn with confidence.' },
      { type: 'h3', text: 'Portfolio Attribution' },
      { type: 'p', text: 'Shows how much each position has contributed to your total return since purchase — in dollars and as a percentage of your total invested capital. Found under Portfolio → Attribution. No additional data needed; it reads your existing portfolio and live quote prices.' },
      { type: 'steps', items: [
        'The tool loads automatically on opening — no input required.',
        'Switch between By Position (full per-stock sortable table), Waterfall (visual bar chart), and By Sector (sector-level aggregation).',
        'Sort any column in the By Position view by clicking its header.',
        'The Waterfall view shows each position\'s dollar P&L as a horizontal bar — positive contributors extend right (green), detractors extend left (red).',
        'The Bottom panel shows top 3 contributors and top 3 detractors side by side.',
      ]},
      { type: 'table', headers: ['Column', 'What it means'], rows: [
        ['Weight %', 'This position\'s cost basis as a % of total portfolio cost basis — how much capital you allocated.'],
        ['P&L $', 'Current value minus cost basis in dollars. Unrealised.'],
        ['P&L %', 'Dollar P&L ÷ position cost basis — the return on this specific holding.'],
        ['Contribution %', 'Dollar P&L ÷ TOTAL portfolio cost basis — how many percentage points this position added or removed from your overall return. This is the key attribution metric.'],
      ]},
      { type: 'tip', text: 'Tip: a position can have a high P&L % (great stock pick) but low Contribution % (you didn\'t allocate much). Conversely, a modestly performing position with a large allocation contributes more to your total return than a spectacular small bet. Attribution shows you where your returns actually came from — not just which stocks went up.' },
      { type: 'h3', text: 'Trade Journal' },
      { type: 'p', text: 'Log every trade you execute to track performance over time. Found under Portfolio → Trade Journal.' },
      { type: 'steps', items: [
        'Fill in Symbol, Side (Buy/Sell), Price, Shares, Strategy, Date, and optional Notes.',
        'The journal computes realised P&L by matching buy and sell trades for the same symbol.',
        'Summary cards show total P&L, win rate, total entries, and closed trades.',
        'The by-strategy table breaks down win rate and P&L per strategy so you can see which setups work.',
        'Filter by strategy or search by symbol. Export to CSV with the "↓ CSV" button.',
      ]},
      { type: 'h3', text: 'CPPI Allocator' },
      { type: 'p', text: 'Constant Proportion Portfolio Insurance — a systematic strategy that dynamically splits capital between a risky asset (e.g. SPY) and a safe asset (cash/bonds) so the portfolio is designed to never fall below a floor value. Found under Portfolio → CPPI Allocator.' },
      { type: 'steps', items: [
        'Start a strategy by picking a risky asset symbol, initial capital, floor % (the portion of capital to protect), multiplier, safe-asset annual yield, and a rebalance band %.',
        'On start, exposure is set to multiplier × (portfolio value − floor), clamped between 0% and 100% of the portfolio; the rest sits in the safe asset.',
        'The dashboard tracks live portfolio value, floor (which grows at the safe rate), cushion, target vs. actual risky exposure, and drift.',
        'When drift exceeds the rebalance band, a banner recommends a specific buy/sell trade — click "Rebalance Now" to execute it and log the event.',
        'Every rebalance (including the initial allocation) is recorded in the Rebalance Log with price, portfolio value, floor, and trade size.',
        'Use "Backtest CPPI" below the live dashboard to simulate the strategy over historical data (6M-5Y) for any symbol and compare it to buy & hold, including max drawdown and whether the floor was ever breached by an overnight gap.',
        '"Reset strategy…" clears the current strategy and its history so you can start a new one.',
      ]},
      { type: 'tip', text: 'Tip: a higher multiplier increases upside participation but also increases gap risk — a large overnight drop in the risky asset can push the portfolio below the floor before a rebalance can happen. The backtest\'s "Floor Breached" stat flags this. Multipliers of 3-5 with a floor of 85-95% are typical starting points.' },
      { type: 'h3', text: 'Net Exposure' },
      { type: 'p', text: 'Rolls Stocks, Options, and CPPI into a single beta-adjusted "how much market risk am I actually carrying right now" number. Found under Portfolio → Net Exposure.' },
      { type: 'steps', items: [
        'Stocks: reuses the Portfolio Risk beta calc — market value × portfolio beta gives a SPY-equivalent dollar exposure.',
        'Options: delta is computed with Black-Scholes from each position\'s strike, expiry, and implied volatility (yfinance doesn\'t reliably supply live Greeks), converted to share-equivalent exposure, then beta-weighted by the underlying.',
        'CPPI: the active strategy\'s current risky-sleeve dollar value, beta-weighted by its risky asset.',
        'Merger Arb and SPACs are listed as separate "event-driven" capital, not folded into Net Market Exposure — their risk is deal completion or trust redemption, not market direction, so beta-adjusting them would misrepresent what they actually expose you to.',
        'The Exposure / Capital stat shows leverage: over 100% means you\'re effectively levered to the market (net beta-adjusted exposure exceeds capital deployed); under 100% means you\'re de-levered.',
      ]},
      { type: 'tip', text: 'Tip: Stock VaR (95%/99%) on this page is stocks-only, not a unified cross-strategy VaR — combining VaR across stocks, options, and event-driven strategies correctly requires their correlation matrix, which isn\'t modeled here. Treat it as one input, not the whole risk picture.' },
    ],
  },
  {
    id: 'themes',
    title: 'Themes',
    icon: '✦',
    blocks: [
      { type: 'p', text: 'Thematic investing groups companies by a long-term force reshaping the economy rather than by sector. This group has an overview and one page for each theme: Artificial Intelligence, Robotics, Quantum Computing and Space Exploration. Every theme page has the same layout, so once you know one you know them all.' },
      { type: 'h3', text: 'Themes Overview' },
      { type: 'p', text: 'One card per theme with its basket\'s 3-month, 1-year and 3-year performance against SPY, the median analyst upside and the strongest setups, then a side-by-side table (1M to 5Y), where the leaders and laggards are, and how many core, supplier, other and speculative names each theme holds. Click a card or row to open the theme.' },
      { type: 'h3', text: 'Artificial Intelligence, Robotics, Quantum Computing and Space Exploration' },
      { type: 'table', headers: ['Section', 'What it shows'], rows: [
        ['Basket performance', 'An equal-weight basket of the theme\'s companies against SPY over the last year (rebased to 100) with returns from 1 month to 5 years, volatility and the worst peak-to-trough fall.'],
        ['Next 3-12 months', 'Median and market-cap-weighted analyst upside (the gap between 12-month price targets and today\'s price), the share of analysts at Buy, and the near-term catalysts and risks.'],
        ['The next 3-10 years', 'Median revenue growth, share of companies that are profitable, median forward P/E, and the long-term drivers and risks.'],
        ['What compounding would mean', 'What $10,000 grows to at 8%, 15% and 25% a year after 1, 3, 5 and 10 years, beside the basket\'s own 3- and 5-year record. Arithmetic, not a forecast.'],
        ['The value chain', 'The theme split into layers (for AI: chips, manufacturing, data-center infrastructure, power, platforms, software) with every company placed in its layer: this is where you find who else benefits. Dashed outline marks speculative names; the number is the 3-month change.'],
        ['Companies', 'Every name with market cap, returns, analyst upside, growth, risk level and setup score. Filter by Core leaders, Picks & shovels, Other beneficiaries or Emerging & speculative. Click a row for the reasoning, the score breakdown, analyst target range, cautions and a chart.'],
        ['Candidates to research', 'The six highest setup scores in the theme, as a place to start, with a theme ETF row for a diversified alternative.'],
      ]},
      { type: 'h3', text: 'The setup score' },
      { type: 'p', text: 'A transparent 0-100 score that compares names within a theme: theme exposure 20, momentum versus SPY 20, analyst upside 20, growth 20, financial strength 10, valuation versus growth 10. Very-high-risk names (small, unprofitable or cash-burning) are marked down 15% and high-risk names 7%, and a very-high-risk name or one that has fallen 40%+ in a year can never be better than "Mixed". Labels: Stronger setup (68+), Mixed (52+), Weaker setup.' },
      { type: 'bullets', items: [
        'The first load reads fundamentals for about 80 companies (roughly a minute, with a progress bar). It serves all five pages and is cached for a day. If Yahoo is limiting requests you will see prices and performance with a note that analyst data is catching up.',
        'Companies shown as "No data" were delisted, renamed or are not yet trading. The commentary is written by hand and dated; the numbers are live.',
        'The 100-bagger traits shown in each detail panel are the same score used by Research → 100-Bagger Finder.',
      ]},
      { type: 'tip', text: 'Tip: read a theme top to bottom: first how much has already happened (basket performance), then what analysts and the numbers say (outlook), then the value chain for the less obvious beneficiaries, and only then the candidates. The best-performing themes are often the most crowded.' },
    ],
  },
  {
    id: 'research',
    title: 'Research',
    icon: '⊕',
    blocks: [
      { type: 'h3', text: '100-Bagger Finder' },
      { type: 'p', text: 'Screens for stocks that share the traits of past 100x compounders. A 100-bagger needs about 26% a year for 20 years (58% for 10, 17% for 30), so the company must start small and keep growing for a very long time. Found under Research → 100-Bagger Finder.' },
      { type: 'table', headers: ['Trait (weight)', 'What scores well'], rows: [
        ['Room to grow (20)', 'Small market cap. Under about $3B scores highest; above $100B scores zero because 100x would be a $10T+ company.'],
        ['Growth (25)', 'Revenue growth, blending the multi-year compound rate (60%) with the latest year (40%). 35%+ scores 100. Growth above 50% is capped when extrapolating.'],
        ['Return on equity (15)', '25%+ is excellent. ROE inflated by heavy debt is discounted 30%.'],
        ['Margins (10)', 'High gross margin (pricing power), healthy operating margin, bonus for widening margins, penalty for narrowing.'],
        ['Balance sheet (10)', 'Net cash or low debt, positive free cash flow.'],
        ['Owner-operators (10)', 'Insiders owning 10%+ scores well; 20%+ scores 100.'],
        ['Valuation (10)', 'P/E relative to growth (PEG); price/sales relative to growth when there are no earnings.'],
      ]},
      { type: 'bullets', items: [
        'Pick a universe: S&P SmallCap 600, S&P MidCap 400, or My watchlist. The first scan of an index takes about a minute (a progress bar shows it); the data is then cached for a day.',
        'Each row shows the score, tier (Strong fit 70+, Promising 55+, Partial 40+, Weak), market cap, growth, ROE, gross margin, insider ownership, debt, years to 100x if growth continued, and seven trait dots. A ⚠ marks cautions such as negative free cash flow or shrinking revenue.',
        'Click a row for the factor-by-factor breakdown with the reason for each score, the trait checklist, the cautions and the arithmetic of what 100x would require. A company that has never been profitable in the available years is capped at 60.',
        'Filter by fit, market cap, sector or text, hide stocks with cautions, sort by any column and export CSV. Stocks above $120B are left out (the count is shown).',
      ]},
      { type: 'tip', text: 'Tip: this scores traits, it does not predict winners. The S&P indexes hold only profitable, established companies, so many future 100-baggers will be too small to appear; add tickers you find elsewhere to your watchlist and screen them with "My watchlist".' },
      { type: 'h3', text: 'Screener' },
      { type: 'p', text: 'Find stocks matching technical or fundamental criteria across a large-cap universe. Three modes:' },
      { type: 'table', headers: ['Mode', 'How to use'], rows: [
        ['Technical', 'Pick a scan: 52-Week High, Golden Cross, Death Cross, RSI Oversold (<30), RSI Overbought (>70), High Relative Volume. Click Run.'],
        ['Fundamental', 'Pick a preset screen: Quality Growth, Deep Value, Dividend Income, or Momentum + Quality. Click Run.'],
        ['Custom', 'Type a natural-language query ("profitable tech companies with revenue growth over 20%") or add filter rows manually. Claude translates NLP to filters.'],
      ]},
      { type: 'tip', text: 'Tip: Custom mode NLP query examples — "large cap financials with low P/E and high dividend yield", "beaten-down growth stocks with insider buying", "mega cap tech with expanding margins".' },
      { type: 'h3', text: 'Range Screener' },
      { type: 'p', text: 'Finds names trading sideways between a support and resistance level over the last 30/60/90 days — rather than trending — and shows where the price sits in that range right now, for a range-trading (buy support, sell resistance) approach. Found under Research → Range Screener.' },
      { type: 'p', text: 'For each name and window, it detects the high and low of the window, then measures two things: how "range-bound" it is, and how many times price has come back to each edge:' },
      { type: 'table', headers: ['Metric', 'What it means'], rows: [
        ['Score', 'How choppy vs. trending the window was, from an efficiency-ratio calculation (net price change ÷ the sum of every day\'s move). 100 = pure back-and-forth with no net progress; 0 = a steady trend in one direction. It ranks names — a high score isn\'t a guarantee the range holds going forward.'],
        ['Touches', 'How many days price came within 15% of the window low / within 15% of the window high. More touches on both sides means the support and resistance levels are more established, not just one outlier spike or dip.'],
        ['Position', 'Where the current price sits between the low (0%) and high (100%) of the range.'],
        ['Signal', '"Near support" (bottom 20% of the range) or "near resistance" (top 20%) — the two zones this screener treats as actionable. Everything else is "mid-range".'],
        ['Chart', 'A small inline line chart of the last year of closing prices — wider than the window itself, so you can see prior swings and range resets, not just the currently detected band. Dashed lines mark the selected window\'s low and high at their real level within that year. Green when near support, red when near resistance, grey otherwise. Click it to open the full candlestick chart with every period (1D–5Y) and the usual overlays.'],
      ]},
      { type: 'steps', items: [
        'Choose a window (30/60/90 days) and, optionally, tighten the width/touches/score filters or the signal dropdown.',
        'Leave Symbols blank to scan the built-in ~290-name universe, or enter your own comma-separated list to scan just those.',
        'Click "Run screen". The first scan of the default universe can take up to ~15 seconds; the backend caches it for 30 minutes, so repeat scans (or another window) are instant until that expires.',
        'For rows flagged "near support" or "near resistance", Entry/Target/Stop are mechanical levels derived from the detected range (buy near the low with a stop just under it, or the mirror for resistance) — not a recommendation. Click a column header to sort.',
      ]},
      { type: 'tip', text: 'Tip: the score is far more discriminating for symbols that actually trend than for ones that don\'t — most stocks score fairly high over any given 60-day window just from normal daily noise. Width % and Touches are usually the more useful filters for narrowing down to genuinely tradeable ranges.' },
      { type: 'tip', text: 'Disclaimer: this is a mechanical pattern screen, not investment advice. A range can break down in either direction at any time — confirm with your own analysis and size positions accordingly.' },
      { type: 'h3', text: 'Tear Sheet' },
      { type: 'p', text: 'Enter any stock ticker to get a one-page investment snapshot: what the company does, how the stock has performed against the S&P 500, how its revenue, margins, earnings and free cash flow have trended, how healthy its balance sheet is, what you are paying for it, what analysts expect, and whether it looks cheap or expensive. Found under Research → Tear Sheet. Use Download PDF to keep a copy.' },
      { type: 'table', headers: ['Section', 'What it tells you'], rows: [
        ['Is it cheap or expensive?', 'A verdict (Significantly undervalued → Significantly overvalued) from the median of four fair-value models: historical P/E (median of up to 10 years), PEG = 1, a 10-year free-cash-flow DCF, and the discounted analyst target. The chart shows each model against today\'s price; the spread between models matters as much as the median. If fewer than two models can run (loss-making companies, funds) it says so instead of guessing.'],
        ['Scorecard', 'Six 0–100 pillars — Growth, Profitability, Financial health, Valuation, Analyst sentiment, Momentum — plus an overall score and auto-generated strengths and risks.'],
        ['Past performance', '1M to 5Y returns vs. the S&P 500, a growth-of-100 chart, price with 50/200-day moving averages, 52-week range position, max drawdown and volatility.'],
        ['Quarterly income flow', 'A Sankey diagram for each of the last four quarters (pick one with the tabs): revenue splits across your income streams (products, business segments or regions, read from the company\'s SEC filings when they reconcile to reported revenue), then flows through cost of revenue, operating expenses, taxes and net income, and finally out as dividends, buybacks and retained earnings. Band widths are proportional to dollars. Loss-making quarters show the shortfall in red; if payouts exceed earnings the difference is shown as drawn from cash reserves. A table below compares margins, dividends and buybacks across the four quarters.'],
        ['Financial track record', 'Up to ten fiscal years of revenue, margins, EPS and free cash flow with year-over-year growth and CAGRs, from SEC filings (Yahoo Finance fills gaps and supplies balance-sheet items). Foreign companies that don\'t file 10-Ks show the ~4 years Yahoo provides. Banks leave free cash flow blank, and companies that report in a different currency than they trade in are labelled and skip the per-share valuation models.'],
        ['Valuation multiples', 'P/E, PEG, P/S, P/B, EV/EBITDA, FCF yield and dividend yield; P/E at each fiscal year-end (up to 10) vs. today; and forward earnings yield vs. the 10-year Treasury.'],
        ['Projected earnings & returns', '12-month bear/base/bull prices from next-year consensus EPS (low/average/high) at the current forward P/E (20% lower in the bear case, 10% higher in the bull case), and 5-year annualised returns if earnings compound at consensus growth and the P/E compresses, blends toward its history, or stays put.'],
        ['Estimates & analysts', 'Consensus EPS and revenue, estimate revisions over 30/90 days, last quarters\' beats and misses, rating distribution now vs. 3 months ago, price-target range and recent upgrades/downgrades.'],
        ['Ownership', 'Institutional and insider holdings, short interest, and six months of insider buying and selling.'],
      ]},
      { type: 'table', headers: ['Export option', 'What it does'], rows: [
        ['Download PDF', 'Builds a clean, light-theme multi-page PDF of the whole tear sheet (charts included) and saves it as <TICKER>_TearSheet_<date>.pdf.'],
        ['Print', 'Your browser\'s print dialog, for printing the on-screen page directly.'],
      ]},
      { type: 'tip', text: 'Tip: simple models disagree most for high-growth companies — a PEG = 1 or DCF value will often sit far below the market price for a business with a long growth runway. Read the verdict as "what the numbers support under conservative assumptions", then judge whether the growth story justifies paying more.' },
      { type: 'tip', text: 'Disclaimer: a rules-based screen using Yahoo Finance data, not investment advice. Data can be delayed or missing, and ETFs and funds have no company financials.' },
      { type: 'h3', text: 'Price Projection' },
      { type: 'p', text: 'Enter any stock or ETF ticker to see a 1-year-forward price cone (10th/25th/50th/75th/90th percentile bands) built entirely from market-implied inputs, not a forecast of Claude\'s own. Found under Research → Price Projection.' },
      { type: 'table', headers: ['Input', 'What it does'], rows: [
        ['Options-implied volatility', 'ATM implied vol pulled from every available expiration out to ~13 months, interpolated at each monthly horizon — the market\'s own forward-looking volatility, rather than one flat number stretched out with the square-root-of-time rule. Falls back to trailing 1-year realized volatility for symbols with no listed options.'],
        ['Risk-free rate', 'The current 1-year Treasury yield (Research → Treasury Bonds), net of the security\'s own dividend yield, sets the median path\'s drift — the standard risk-neutral assumption used across options pricing.'],
        ['VIX regime', 'Current VIX vs. its trailing 1-year median scales the volatility input up or down — an elevated-VIX market widens the cone beyond what the single name\'s own options currently price in.'],
        ['Credit spread (CDS proxy)', 'True single-name CDS data is proprietary (Markit/Bloomberg/ICE) and not available from any free source, so this reuses the issuer\'s own corporate-bond credit spread over Treasuries (Research → Corporate Bonds\' YTM-vs-Treasury calc). A wide spread only pulls the lower percentiles (p10/p25) down further, since credit spreads price default/distress risk — an asymmetric, downside-only effect. Shows "Not available" for issuers with no fund-held bonds (most companies, and all ETFs).'],
      ]},
      { type: 'tip', text: 'Disclaimer: this is a probabilistic model of what the options, rates, and credit markets currently imply — not a price target, forecast, or investment advice. It assumes those markets are pricing efficiently and that returns are lognormal, both simplifications. The full methodology is restated at the bottom of the page alongside every raw input used.' },
      { type: 'h3', text: 'Technical Signals' },
      { type: 'p', text: 'Multi-timeframe technical summary for every symbol in your watchlist and portfolio. Found under Research → Signals.' },
      { type: 'p', text: 'Each cell shows three indicators stacked:' },
      { type: 'table', headers: ['Indicator', 'How to read'], rows: [
        ['Trend (▲/▼/◆)', '▲ Bullish, ▼ Bearish, ◆ Neutral — based on price vs moving averages.'],
        ['RSI (14)', 'Green if < 30 (oversold), red if > 70 (overbought), grey if neutral.'],
        ['MACD', 'Arrow up = bullish crossover, arrow down = bearish crossover.'],
        ['BB%', 'Position within Bollinger Bands. Above 80% = overbought, below 20% = oversold.'],
      ]},
      { type: 'p', text: 'Timeframes: 1D (daily), 1W (weekly), 1M (monthly), 3M (quarterly). Use weekly/monthly signals to confirm trade direction before acting on daily signals.' },
      { type: 'h3', text: 'Chart Compare' },
      { type: 'p', text: 'Normalised return chart to compare up to 5 stocks over 1M, 3M, 6M, or 1Y. All lines start at 0% so you can see relative outperformance directly.' },
      { type: 'steps', items: [
        'Type a ticker and press Enter (or click Add) to add a stock.',
        'Add up to 5 stocks — each gets a distinct colour.',
        'Change the period with the buttons at the top.',
        'The table below the chart shows key fundamentals side by side.',
        'Click × next to a ticker to remove it.',
      ]},
      { type: 'h3', text: 'Fundamental Comparison' },
      { type: 'p', text: 'Side-by-side 21-metric fundamental comparison for up to 5 stocks. Enter symbols comma- or space-separated and click Compare.' },
      { type: 'bullets', items: [
        'Green cell = best in class for that metric.',
        'Red cell = worst in class.',
        'For valuation ratios (P/E, P/S, EV/EBITDA, Debt/Equity), lower is better.',
        'For profitability metrics (margins, ROE, ROA), higher is better.',
      ]},
      { type: 'h3', text: 'DCF Valuation' },
      { type: 'p', text: 'Discounted Cash Flow calculator to estimate intrinsic value. Found under Research → DCF Valuation.' },
      { type: 'steps', items: [
        'Enter a ticker and click "Load Data" — EPS, growth rate, and beta pre-fill from yfinance.',
        'Review and adjust inputs: EPS growth rate (5-year), terminal growth rate (default 2.5%), discount rate/WACC (auto-calculated from beta), margin of safety (default 25%), and years.',
        'The intrinsic value and buy-below price update live as you change any input.',
        'The 10-year projection table shows EPS and present value for each year.',
        'Verdict: Undervalued (green) if price < intrinsic − margin; Overvalued (red) if price > intrinsic + 15%; Fairly Valued (amber) otherwise.',
      ]},
      { type: 'tip', text: 'Tip: the DCF is highly sensitive to growth rate assumptions. Run it with a conservative (half the yfinance estimate), base, and optimistic scenario to get a valuation range rather than a single number.' },
      { type: 'h3', text: 'Earnings Surprise Tracker' },
      { type: 'p', text: 'Tracks the last 8 quarters of EPS beat/miss history, average EPS surprise %, post-earnings price drift (+1D and +5D), and beat streaks for any stock. Found under Research → Earnings Surprise.' },
      { type: 'steps', items: [
        'Type one or more tickers in the input field (comma or space separated) and click "+ Add", or click "⬇ Watchlist" to import all your watchlist symbols at once.',
        'Click "▶ Run Analysis". The backend fetches 2 years of price history and earnings history per symbol in parallel. Allow 15–30 seconds for large symbol lists.',
        'Each symbol appears as a card showing: Beat Rate ring, beat streak badge, Avg EPS Surprise %, Avg +1D and +5D post-earnings drift, and the last quarter\'s result.',
        'Click "▼ Details" on any card to expand the full 8-quarter table with individual dates, EPS estimate vs actual, surprise %, and drift for each quarter.',
        'Remove individual symbols with the ✕ button, or click "Clear all" to reset.',
      ]},
      { type: 'table', headers: ['Metric', 'What it means', 'How to use it'], rows: [
        ['Beat Rate %', 'Percentage of the last 8 quarters where EPS actual ≥ estimate. Ring color: green ≥75%, amber ≥50%, red <50%.', 'High beat rate (≥75%) means the company consistently outperforms Wall Street\'s models — analysts may be systematically too conservative.'],
        ['Beat Streak', 'Number of consecutive recent quarters with an EPS beat. 🔥 badge appears for 2+ streaks; colour escalates at 4+.', 'A long streak raises the bar — the market may already price in a beat, making the reaction muted or asymmetric on misses.'],
        ['Avg EPS Surprise %', '(Actual − Estimate) ÷ |Estimate| × 100, averaged over available quarters.', 'Companies with consistently large positive surprises often have management teams that guide conservatively ("sandbagging").'],
        ['Avg +1D Drift', 'Average stock return from market close on earnings day to the next day\'s close.', 'Positive avg drift means the stock historically gaps up or rallies after results. Combine with expected move (Earnings+ tab) to assess risk/reward.'],
        ['Avg +5D Drift', 'Average stock return over the 5 trading days following earnings.', 'Some stocks gap and hold (+1D and +5D both positive); others give back initial gains. Stocks with strong +5D but weak +1D can be bought on post-earnings dips.'],
        ['EPS Surprise Bars', 'Mini SVG bar chart — green bars = beat, red = miss. Oldest quarter on the left, most recent on the right.', 'A bar chart that\'s all green is a sandbagging company. Alternating bars suggest cyclical estimation errors.'],
      ]},
      { type: 'tip', text: 'Tip: before trading around earnings, look for the combination of high beat rate + positive avg +5D drift. This pattern suggests the market consistently underestimates the company AND the initial move tends to continue — making momentum plays after the print more reliable.' },
      { type: 'tip', text: 'Disclaimer: past earnings patterns do not guarantee future results. Revenue estimate data is not available from the free yfinance data source; only EPS is compared. Post-earnings drift is calculated from daily close prices, not intraday gaps.' },
      { type: 'h3', text: 'Backtester' },
      { type: 'p', text: 'Test a trading strategy on historical data for any symbol.' },
      { type: 'table', headers: ['Strategy', 'Parameters'], rows: [
        ['MA Crossover', 'Fast and slow MA periods. Buys when fast crosses above slow, sells on cross below.'],
        ['RSI Reversal', 'RSI period, oversold (buy) and overbought (sell) thresholds.'],
        ['Bollinger Bands', 'Period and standard deviation multiplier. Buys at lower band, sells at upper band.'],
      ]},
      { type: 'bullets', items: [
        'Results show: Total Return, Alpha vs Buy & Hold, Max Drawdown, Sharpe Ratio, Win Rate, and number of trades.',
        'The equity curve chart overlays the strategy return vs a simple buy-and-hold benchmark.',
        'The trade log lists every entry and exit with price, value, and P&L.',
      ]},
      { type: 'h3', text: 'Unusual Options Activity' },
      { type: 'p', text: 'Scans options chains for contracts with abnormally high volume relative to open interest — a signal that informed traders may be positioning.' },
      { type: 'bullets', items: [
        'Your watchlist symbols pre-populate the input. Edit or add more symbols (max 10).',
        'Click Scan. The scanner checks the nearest 3 expiries for each symbol.',
        'A contract appears if: Volume ≥ 2× Open Interest, OR Volume ≥ 1,000 on a fresh contract (OI = 0).',
        'Sort by Volume (default), Vol/OI Ratio, or Symbol.',
        'Filter to Calls only or Puts only.',
        'Vol/OI Ratio ≥ 10× is highlighted amber — extremely unusual activity.',
        'ITM contracts (in the money) are shown slightly brighter.',
      ]},
      { type: 'tip', text: 'Tip: unusual call activity on a stock you hold can be a bullish confirmation signal. Unusual put activity may indicate hedging or bearish positioning by informed players.' },
      { type: 'h3', text: 'Earnings Strategy Analyzer' },
      { type: 'p', text: 'Identifies the historically best trading strategy for each stock around its earnings announcement — pre-run, buy the beat, buy the dip, or hold through — based on 3 years of actual earnings data. Found under Research → Earnings Strategy.' },
      { type: 'steps', items: [
        'Scanner mode: enter symbols or click "⬇ Scan Watchlist" to analyze all watchlist stocks at once. Takes 10–30 seconds for larger lists.',
        'The scanner table shows every stock sorted by days to next earnings, with beat rate, average earnings move, pre-run tendency, and the recommended strategy with its historical win rate.',
        'Click any row (or "Deep Dive →") to open the full single-stock analysis.',
        'Deep Dive mode: shows 4 strategy cards, a drift chart of all historical earnings events, and a full trade history table.',
        'Quick Deep Dive: use the input bar at the top of the page to jump directly to any ticker without re-running the full scan.',
      ]},
      { type: 'table', headers: ['Strategy', 'When to use', 'Entry', 'Exit'], rows: [
        ['Pre-Earnings Run', 'Stock historically runs up before earnings (positive avg pre-10D)', '10 trading days before earnings date', '1 trading day before earnings'],
        ['Buy the Beat', 'Stock has high beat rate AND tends to continue higher after beating', '1 day after earnings, only if EPS beat', '10 trading days after earnings'],
        ['Buy the Dip', 'Stock historically bounces after earnings sell-offs (mean reversion)', '1 day after earnings, only if stock dropped ≥3%', '10 trading days after earnings'],
        ['Hold Through', 'Want full earnings-window exposure (highest risk/reward)', '5 days before earnings', '5 days after earnings'],
      ]},
      { type: 'table', headers: ['Column / Metric', 'What it means'], rows: [
        ['Beat Rate', '% of quarters where EPS actual ≥ EPS estimate over the last 3 years.'],
        ['Avg Move', 'Average absolute price move on the earnings announcement (reaction day), regardless of direction.'],
        ['Pre-Run 10D', 'Average price change in the 10 trading days leading up to each earnings announcement.'],
        ['Best Win %', 'Win rate of the best-performing strategy for this stock across historical setups.'],
        ['Best Avg Ret', 'Average return per trade for the best strategy.'],
        ['Signal', 'STRONG BUY (≥70% win rate, ≥2% avg) / BUY (≥60%, ≥1%) / NEUTRAL / WEAK / AVOID / NO DATA.'],
        ['EV (Expected Value)', 'Win rate × avg return — the single best measure of strategy quality. Higher EV = better edge.'],
        ['Earnings Reaction', 'In the drift chart/table, this is the price move from the day-before close to the day-after close — captures the full earnings gap regardless of whether the report was AMC or BMO.'],
      ]},
      { type: 'tip', text: 'Tip: the Pre-Earnings Run strategy is often overlooked. Many stocks exhibit a reliable 2–4% run in the 10 days before earnings as investors position ahead of the announcement. By selling before the report, you capture the run without taking the binary risk of the earnings event itself.' },
      { type: 'h3', text: 'Analyst Rating Tracker' },
      { type: 'p', text: 'Tracks upgrade, downgrade, and initiation activity from Wall Street analyst firms across your entire watchlist over the last 90 days. Found under Research → Analyst Ratings.' },
      { type: 'steps', items: [
        'The Activity Feed view shows all analyst actions chronologically — date, firm, action type, rating change, and stock price at time of the rating.',
        'Filter by Action (All / Upgrades / Downgrades / Initiations) and Sentiment (All / Positive / Negative) to focus on specific signal types.',
        'The "+5d Return" column shows how the stock performed in the 5 trading days after the rating — a quick read on whether analysts called it right.',
        '"Since Rating" shows the cumulative return from the rating date to today.',
        'Switch to By Stock view for a per-symbol summary: consensus rating, analyst count, price target range bar, and 90-day upgrade/downgrade balance.',
        'Click any row to open a deep-dive panel with the full rating history and all metrics for that stock.',
      ]},
      { type: 'table', headers: ['Column / Field', 'Description'], rows: [
        ['Consensus', 'Aggregated analyst rating: Strong Buy (1.0–1.5), Buy (1.5–2.5), Hold (2.5–3.5), Sell (3.5–4.5), Strong Sell (4.5–5.0). Based on the recommendationMean from Yahoo Finance.'],
        ['Upside', 'Percentage difference between the average analyst price target and the current stock price. Positive = target above current price.'],
        ['Target Range', 'Low–Avg–High price target bar. White dot = current price, filled bar = average target. Lets you see where the stock sits relative to analyst expectations.'],
        ['90d Activity', 'Green/red bar showing the upgrade/downgrade balance over the last 90 days.'],
        ['+5d Return', 'Price performance in the 5 trading days after the analyst action. Useful for back-checking if the upgrade/downgrade was prescient.'],
        ['Since Rating', 'Cumulative return from the rating date to today. Positive = stock rose after the analyst\'s call.'],
      ]},
      { type: 'tip', text: 'Tip: a cluster of upgrades or initiations in a short time window is a stronger signal than a single action. Watch for 3+ firms changing their view on the same stock within 2 weeks — that often precedes a sustained move.' },
      { type: 'h3', text: 'Fund Holdings Explorer' },
      { type: 'p', text: 'Pulls official portfolio holdings directly from SEC EDGAR N-PORT filings — the mandatory monthly disclosure all registered ETFs and mutual funds submit to the SEC. Found under Research → Fund Holdings.' },
      { type: 'steps', items: [
        'Type a fund name or ticker in the search box (e.g., "SPY", "ARK Innovation", "Vanguard") — the app searches EDGAR for matching N-PORT filers.',
        'Click a Popular quick-pick chip (SPY, QQQ, IVV, VTI, ARKK, etc.) to jump straight to that fund without searching.',
        'Once a fund is loaded, the Fund Header shows the filing period, net assets, total assets, and holding count. This is the official "as of" date for the holdings.',
        'Use the Category filter pills (Equity, Debt, Derivative, etc.) to narrow the table to specific asset types.',
        'Search within holdings by name, ticker, or CUSIP using the filter box.',
        'Sort any column — Weight, Fair Value, 52W Range position, 1M/3M/6M/1Y performance — by clicking the header.',
        'Adjust "Live market data enriched for top N" to control how many holdings receive price and performance data from Yahoo Finance (larger N = slower first load but more data).',
        'Holdings are cached for 6 hours — click the fund again after 6 hours to see an updated filing.',
      ]},
      { type: 'table', headers: ['Column', 'Description'], rows: [
        ['Weight %', 'Percentage of net assets — the official weight from the N-PORT filing. Bar length is proportional to the largest holding.'],
        ['Fair Value', 'Dollar fair value of the position as reported in the N-PORT filing.'],
        ['52W Range', 'Red-to-green gradient bar from 52-week low to 52-week high. White dot = current price. Shows where the stock sits in its annual range.'],
        ['From High', 'Percentage below the 52-week high. E.g., −15% means the stock is 15% off its yearly peak.'],
        ['1M / 3M / 6M / 1Y', 'Price performance over each period. Green = positive, red = negative. Only available for equity holdings with a valid ticker.'],
        ['Category', 'Asset class from the N-PORT form: Equity (EC), Debt (DBT), Derivative (DERIV), ABS, MBS, Short-Term, Real Estate, Other.'],
        ['CUSIP', 'Shown when no ticker is available. Common for bond holdings and private securities.'],
      ]},
      { type: 'tip', text: 'Tip: the N-PORT filing period is typically 60 days before the public can see it (regulatory delay). So a fund\'s December holdings appear in late February. Weight figures show what the fund held at the reporting date, not necessarily today.' },
      { type: 'h3', text: 'Corporate Bonds' },
      { type: 'p', text: 'Investment-grade and high-yield corporate bond research by issuer, built entirely on free SEC data since there\'s no free per-CUSIP bond pricing API. Found under Research → Corporate Bonds.' },
      { type: 'steps', items: [
        'Search by ticker or company name to find an issuer\'s bonds.',
        'Bonds are found by scanning the latest N-PORT holdings of 7 major bond ETFs (LQD, VCIT, VCSH, USIG for investment grade; HYG, JNK, USHY for high yield) for matches to the issuer.',
        'Click a bond to see CUSIP, ISIN, coupon rate & type (fixed/floating), maturity date, default flag, and every tracked fund currently holding it with its weight, market value, and an approximate clean price (market value ÷ par balance × 100).',
        'If no tracked fund currently holds the issuer\'s bonds, the app falls back to the issuer\'s own 424B2/424B3/424B5/FWP prospectus filings, extracting "X.XX% Notes due YYYY" terms from the cover page — clearly labeled as terms at issuance, not live pricing, with a link to the source filing.',
        'A separate Ratings Mentions panel full-text-searches the issuer\'s own 8-K/10-K/10-Q filings for rating-action language (agency name + downgraded/upgraded/affirmed/etc. in the same sentence), shown as excerpts with filing date and a link to the source filing.',
        'A "vs. Treasury Curve" panel shows an approximate yield-to-maturity for the bond, the Treasury par curve interpolated at that exact maturity, and the spread in basis points — plus a small chart plotting the bond\'s YTM against the Treasury curve at its actual years-to-maturity. Only available for fund-held bonds, since computing YTM needs a live price.',
      ]},
      { type: 'tip', text: 'There\'s no free, live per-CUSIP bond pricing feed, so everything here is either (a) what a tracked bond ETF actually holds as of its last N-PORT filing, or (b) terms and ratings actions pulled straight from the issuer\'s own EDGAR filings — never a live quote. The YTM behind the credit-spread panel has no accrued-interest adjustment, so treat spreads as directional, not exact to the basis point.' },
      { type: 'h3', text: 'Convertible Bonds' },
      { type: 'p', text: 'Convertible corporate bond research by issuer, mirroring Corporate Bonds. Found under Research → Convertible Bonds.' },
      { type: 'steps', items: [
        'Search by ticker or company name to find an issuer\'s convertible bonds.',
        'Bonds are found by scanning the latest N-PORT holdings of 3 major convertible bond ETFs (ICVT, CWB, FCVT) for matches to the issuer — same approach as Corporate Bonds.',
        'Click a bond to see CUSIP, ISIN, coupon, maturity, and every tracked fund currently holding it (weight, market value, approximate clean price).',
        'Conversion Terms are pulled from the issuer\'s own XBRL-tagged filings: conversion price, conversion ratio, shares issuable on conversion, call-trigger stock-price % and trading-day thresholds, if-converted value over principal, and outstanding balance — each with its source filing and as-of date. Coverage varies by issuer since these aren\'t mandatory tags the way balance-sheet items are.',
        'If no tracked fund or prospectus match exists but the issuer has disclosed conversion terms anyway (common for older or already-converted issues), the page shows an issuer profile with those XBRL terms and ratings mentions directly instead of an empty result.',
        'Credit Rating Mentions works exactly like Corporate Bonds — full-text search of the issuer\'s own 8-K/10-K/10-Q filings for rating-action language.',
      ]},
      { type: 'tip', text: 'Conversion price and ratio are a defined part of the US-GAAP XBRL taxonomy — unlike credit ratings, which aren\'t standardized at all — so when an issuer tags them, it\'s real structured data straight from their own filing, not a text-mined guess.' },
      { type: 'h3', text: 'Treasury Bonds' },
      { type: 'p', text: 'Current U.S. Treasury yields, historical trends, and the full yield curve — a standalone page, separate from Corporate/Convertible Bonds since Treasuries have a genuinely free official source. Found under Research → Treasury Bonds.' },
      { type: 'steps', items: [
        'The Current Rates table shows all 14 tracked maturities (1 Month through 30 Year) with today\'s yield and the 1-day change. Click a row to load that maturity into the Historical Trend chart below.',
        'The Yield Curve chart plots yield against maturity, overlaying Today against ~1 Month Ago and ~1 Year Ago on one chart — hover anywhere to see all three curves\' values at that maturity in a tooltip.',
        'The Historical Trend chart shows one maturity\'s yield over time — pick the maturity via the Current Rates table or the pills above the chart, and the time range (1M/6M/1Y/5Y/10Y/Max) via the range buttons.',
        'A 2s10s badge (10Y − 2Y spread) sits next to the Yield Curve heading — green "Normal" when positive, red "Inverted" when the 2-Year yields more than the 10-Year, the classic recession-watch signal.',
      ]},
      { type: 'tip', text: 'Data comes straight from the U.S. Treasury\'s own "Daily Treasury Par Yield Curve Rates" — the same source FRED\'s DGS* series are derived from — fetched directly with no API key required, unlike the Economic Dashboard\'s FRED-based series.' },
      { type: 'h3', text: 'Activist Tracker' },
      { type: 'p', text: 'Scans EDGAR for Schedule 13D and 13G filings — the mandatory disclosure whenever an investor crosses 5% beneficial ownership of a public company. Found under Research → Activist Tracker.' },
      { type: 'steps', items: [
        '13D is filed by investors who may seek to influence or control the company (activists, strategic buyers) — far lower volume and higher signal than 13G.',
        '13G is filed by passive holders (index funds, insurers, banks) with no intent to influence control. High volume — dominated by routine crossings from Vanguard, BlackRock, and similar managers — and defaults to hidden via the 13D-only filter.',
        'Each row shows the subject company and the reporting person/fund, parsed from EDGAR\'s combined filer listing, plus live price and 5-day change for context.',
        'Toggle "New filings only" to hide amendments (13D/A, 13G/A) and see just fresh 5%+ stakes. An amendment reflects a change to an existing position (bigger or smaller stake, or a stated-intent change) — not necessarily a new one.',
        'Search by ticker, company, or filer name (e.g. search a known activist fund\'s name to see its recent activity across companies).',
      ]},
      { type: 'tip', text: 'A 13D alone doesn\'t confirm an activist campaign — read the filing (via the EDGAR link) for the actual stated purpose. Item 4 of the form describes the filer\'s intent.' },
      { type: 'h2', text: 'Merger Arb' },
      { type: 'h3', text: 'Overview' },
      { type: 'p', text: 'Starter page for the Merger Arb group — a launching pad showing active tracked deals and newly filed, not-yet-tracked opportunities in one screen. Found under Merger Arb → Overview (first item in the group).' },
      { type: 'steps', items: [
        'The "Active Deals In Progress" table lists every tracked deal sorted by soonest expected close. Click a row to jump straight into the Deal Analyzer with that deal preloaded, or click "Dashboard" to jump to that row on the Deal Dashboard (it scrolls to and briefly highlights it).',
        'The "Upcoming — Newly Filed, Not Yet Tracked" table shows the most recent untracked EDGAR filings from the Opportunity Scanner feed. Click "+ Add" to pre-fill a new deal record, or "Open Scanner" to see the full feed.',
        '"View Risk Matrix" jumps to the aggregate risk/reward view across your whole tracked book.',
      ]},
      { type: 'h3', text: 'Deal Dashboard' },
      { type: 'p', text: 'Tracks active merger and acquisition deals in your arb universe. Shows live bid-ask spreads, annualised return, days to close, and risk rating for every deal. Found under Merger Arb → Deal Dashboard.' },
      { type: 'steps', items: [
        'Click "+ Add Deal" to enter a deal manually: provide the target ticker, acquirer, offer price, deal type (cash / stock / mixed), announce date, and expected close date.',
        'Set the regulatory body (DOJ, FTC, EU, CFIUS, etc.) — this feeds directly into the risk scoring model.',
        'Once saved, the dashboard fetches the live stock price and calculates the spread automatically.',
        'Click 📈 on any row to open the 90-day spread history chart for that deal.',
        'Click "Edit" to update deal details (status, notes, expected close) as a deal progresses.',
        'Use the EDGAR Tender Offer Scanner to discover recent SC TO-T and SC 13E-3 filings and pre-populate a new deal record.',
      ]},
      { type: 'table', headers: ['Column', 'What it shows'], rows: [
        ['Target', 'Target company ticker and name.'],
        ['Acquirer', 'Name of the acquiring company.'],
        ['Type', 'Cash (all-cash offer), Stock (share-for-share exchange), or Mixed.'],
        ['Offer', 'The per-share merger consideration.'],
        ['Price', 'Current market price fetched live from Yahoo Finance.'],
        ['Spread', 'Offer − Current Price (dollar) and (offer − price) / price × 100 (percent). Positive spread = market is pricing in some deal risk.'],
        ['Ann. Ret.', 'Annualised spread return: spreadPct / daysToClose × 365. The headline arb yield.'],
        ['Days', 'Calendar days until the expected close date. Overdue appears in orange when past due.'],
        ['Status', 'Current deal stage: Pending Regulatory, Pending Shareholder Vote, Pending Financing, Closing, Terminated, or Closed.'],
        ['Risk', 'Low / Medium / High — computed from deal type, spread size, regulatory body, deal value, and days remaining.'],
      ]},
      { type: 'tip', text: 'Risk scoring: cash deals start lower-risk than stock or mixed deals. DOJ/FTC review adds more risk than EU or CFIUS. Spreads above 10% or negative annualised returns flag High risk regardless of other factors.' },
      { type: 'h3', text: 'Opportunity Scanner' },
      { type: 'p', text: 'Discovers new deals from EDGAR before you add them to the Deal Dashboard. Scans a broader set of merger-indicative filings than the Dashboard\'s own EDGAR panel — tender offers, going-private filings, and merger proxies/stock registrations that catch deals earlier in the process. Found under Merger Arb → Opportunity Scanner.' },
      { type: 'steps', items: [
        'The scanner pulls SC TO-T, SC 13E-3, DEFM14A, PREM14A, S-4, and 425 filings from the last 60 days on EDGAR full-text search.',
        'Each row shows the filer\'s ticker (parsed from EDGAR\'s display name) with live price and 5-day / 1-month price change for context.',
        'Filter by form type, search by ticker or company name, or toggle "Hide already tracked" to focus on new opportunities.',
        'Rows already in your Deal Dashboard are flagged "Tracked". Click "+ Add" on an untracked row to open the Add Deal form pre-filled with the ticker, company name, and filing date — fill in the offer price and remaining terms from the filing.',
      ]},
      { type: 'tip', text: 'EDGAR full-text search doesn\'t expose deal economics (offer price, structure) — only the filing metadata. Use the EDGAR link on each row to read the actual filing before adding a deal.' },
      { type: 'h3', text: 'Deal Analyzer' },
      { type: 'p', text: 'A risk/reward deep-dive on a single deal: breaks down the risk score into its components and computes the probability of deal completion the market is currently pricing in, plus expected value across a range of close probabilities. Found under Merger Arb → Deal Analyzer.' },
      { type: 'steps', items: [
        'Choose "Tracked Deal" to analyze one of your Deal Dashboard entries, or "Ad-hoc Deal" to analyze a deal without adding it to your tracker first.',
        'The analyzer estimates a "walk-away price" — where the stock would likely trade if the deal fell through — from the pre-announcement trading price when an announce date is given, or a 15% discount to the current price as a fallback. Override it manually if you have a better estimate.',
        'Market-Implied P(close) is the probability of completion baked into the current spread: solves for p where p × offer + (1 − p) × walk-away = current price.',
        'The risk factor bars show exactly which inputs (deal structure, spread size, regulatory body, deal size, time horizon) are driving the overall risk score.',
        'The expected-value scenario table shows your return at assumed close probabilities from 50% to 95% — it crosses zero near the market-implied probability.',
      ]},
      { type: 'h3', text: 'Arb Portfolio' },
      { type: 'p', text: 'Size real positions in your tracked deals and track cost basis, live unrealized P&L, and concentration risk across the book. Found under Merger Arb → Arb Portfolio.' },
      { type: 'steps', items: [
        'Click "+ Add Position" and select a deal already on your Deal Dashboard, then enter shares, entry price, and entry date.',
        'Each row shows cost basis, live market value, unrealized P&L ($ and %), and the value/gain if the deal closes at the offer price.',
        'Summary cards roll up total cost basis, market value, unrealized P&L, and a market-value-weighted average annualized return across the whole book.',
        'Concentration bars show how your capital is spread across deal types (cash / stock / mixed) and regulatory bodies — useful for spotting over-concentration in one regulator or structure.',
      ]},
      { type: 'h3', text: 'Risk Matrix' },
      { type: 'p', text: 'Visual risk/reward map of your tracked deal universe. Found under Merger Arb → Risk Matrix.' },
      { type: 'steps', items: [
        'The scatter plot places each deal by days-to-close (x-axis) and annualized return (y-axis); bubble size reflects deal value and color reflects risk level.',
        'The Regulator × Deal Type grid shows how many deals fall in each combination and their average risk score — cells shade green/yellow/red by average risk.',
        '"Highest Risk Deals" and "Best Annualized Return" panels surface the extremes in your book at a glance.',
      ]},
      { type: 'h3', text: 'Alerts' },
      { type: 'p', text: 'Merger-arb-specific alert rules for days-to-close, spread thresholds, and status changes on tracked deals. Found under Merger Arb → Alerts. Separate from the general Smart Alerts (Watchlist → Smart Alerts) since these read spread, days to close, and status directly from the Deal Dashboard rather than price history.' },
      { type: 'steps', items: [
        'Pick a tracked deal and an alert type, set any parameters, then "+ Add Rule". Click "Scan N Rules" to check them all against live data.',
        'Days to Close Threshold fires when the days remaining to expected close falls at or below your threshold (including overdue).',
        'Spread Threshold fires when the live spread crosses your chosen level in the chosen direction — e.g. "at or above 8%" to flag a widening spread (elevated perceived risk, or a wider entry), or "at or below 1%" to flag a deal nearly fully priced in.',
        'Status Reached fires as soon as a deal\'s status matches the one you pick — e.g. watch for "Closing" as the completion catalyst, or "Terminated" as the downside one.',
      ]},
      { type: 'tip', text: 'Like SPAC Alerts and the general Smart Alerts, this checks whether the condition is true right now each time you scan — it isn\'t a background push notification and doesn\'t track "already seen." Remove a rule once you\'ve acted on it, or leave it to keep confirming the condition on each scan.' },
      { type: 'h2', text: 'SPACs' },
      { type: 'p', text: 'SPAC arbitrage is a different trade from merger arb: instead of a fixed offer price and deal-completion risk, a SPAC\'s common stock has a floor at its trust value — shareholders can redeem for trust value (plus accrued interest) at a shareholder vote or by the deadline, regardless of the proposed deal. Buying below trust captures that discount as a largely bounded-downside yield, with optional leveraged upside via warrants if you hold through a well-received business combination.' },
      { type: 'h3', text: 'Overview' },
      { type: 'p', text: 'Starter page for the SPACs group — a launching pad showing tracked SPACs and newly filed, not-yet-tracked opportunities in one screen. Found under SPACs → Overview (first item in the group).' },
      { type: 'steps', items: [
        'The "Tracked SPACs" table lists every tracked SPAC sorted by soonest redemption deadline. Click a row to jump straight into the Deal Analyzer with that SPAC preloaded, or click "Tracker" to jump to that row on the Tracker (it scrolls to and briefly highlights it).',
        'The "Upcoming — Newly Filed, Not Yet Tracked" table shows the most recent untracked EDGAR filings from the Discovery feed. Click "+ Add" to pre-fill a new SPAC record, or "Open Discovery" to see the full feed.',
        '"View Risk Matrix" jumps to the aggregate yield-vs-deadline view across your whole tracked book.',
      ]},
      { type: 'h3', text: 'Tracker' },
      { type: 'p', text: 'Tracks SPACs against trust value, redemption deadlines, and warrant pricing. Found under SPACs → Tracker.' },
      { type: 'steps', items: [
        'Click "+ Add SPAC" to enter a SPAC manually: ticker, trust value per share (from the most recent 10-Q/8-K disclosure — defaults to $10.00), redemption deadline, and status.',
        'Add the warrant ticker, strike (commonly $11.50), and ratio (shares received per warrant exercised — commonly 0.5, i.e. one whole share per two warrants) if you want warrant metrics.',
        'Discount/Premium and Annualized Yield are computed live once saved — the table sorts by annualized yield (best arb opportunities first) by default.',
        'Update trust value periodically from new filings — it isn\'t fetched live since trust NAV isn\'t continuously reported.',
      ]},
      { type: 'table', headers: ['Column', 'What it shows'], rows: [
        ['Trust Value', 'Per-share cash held in trust, as of the date you last entered it.'],
        ['Price', 'Current market price fetched live from Yahoo Finance.'],
        ['Disc/Prem', '(price − trust) / trust × 100. Negative = trading below trust (the arb entry you want); positive = trading above trust.'],
        ['Ann. Yield', 'Annualized return on your cost basis if bought now and redeemed for trust value at the deadline: (trust − price) / price × 100, annualized over days to deadline.'],
        ['Deadline', 'Days remaining until the redemption/liquidation deadline. Under 45 days highlighted — a key catalyst window.'],
        ['Warrant', 'Warrant ticker and live price, if tracked.'],
      ]},
      { type: 'h3', text: 'Discovery' },
      { type: 'p', text: 'Scans EDGAR for new SPAC IPO filings and de-SPAC merger announcements. Found under SPACs → Discovery.' },
      { type: 'steps', items: [
        'New SPAC IPOs come from S-1 filings mentioning "blank check"; de-SPAC announcements come from 425 / DEFM14A / S-4 filings mentioning "trust account" — a 60-day window, refreshed every 4 hours.',
        'SPAC filings conventionally list all three tickers together (common, units, warrant) in EDGAR\'s filer name — Discovery auto-parses the common and warrant tickers from that (units ending in U, warrants ending in W).',
        'Filter by category, search by ticker or company, or hide filings you already track. Click "+ Add" to pre-fill a new Tracker entry — trust value defaults to $10.00 until you update it from the actual filing.',
      ]},
      { type: 'tip', text: 'Keyword matching on full-text search isn\'t perfect — a company can mention "blank check" or "trust account" without being a SPAC. Verify via the EDGAR link before adding.' },
      { type: 'h3', text: 'Deal Analyzer' },
      { type: 'p', text: 'Discount-to-trust capture yield, warrant economics, and a redeem-vs-hold scenario table for a single SPAC. Found under SPACs → Deal Analyzer.' },
      { type: 'steps', items: [
        'Choose "Tracked SPAC" to analyze one from your Tracker, or "Ad-hoc SPAC" to analyze one without adding it first.',
        'Annualized Yield-to-Deadline is the floor case: your return if you buy now and redeem for trust value at the deadline.',
        'If a warrant ticker is set, the warrant panel shows live price, intrinsic value, time value, and the common-stock breakeven price for the warrant.',
        'The scenario table spans redemption/flat-to-trust through a range of post-deal outcomes (weak aftermarket up to +200% to trust), showing both common and warrant returns — illustrating the asymmetric payoff: bounded downside at trust, leveraged upside via warrants if the business combination does well.',
      ]},
      { type: 'h3', text: 'Portfolio' },
      { type: 'p', text: 'Size common and warrant positions in tracked SPACs and track cost basis, unrealized P&L, and how much of the book is protected by the trust-value floor. Found under SPACs → Portfolio.' },
      { type: 'steps', items: [
        'Click "+ Add Position", select a tracked SPAC, then choose Common or Warrant (warrant is only selectable if that SPAC has a warrant ticker set on the Tracker).',
        'Each row shows live cost basis, market value, and unrealized P&L for that position — common and warrant prices are tracked independently.',
        'Trust Floor is shown per common position and rolled up in the "Trust-Protected" summary card and floor-value panel — the amount recoverable via redemption regardless of deal outcome.',
        'Warrant positions never show a floor value: warrants carry no redemption right and can go to zero if the deal falls through or the stock never clears the strike.',
      ]},
      { type: 'h3', text: 'Alerts' },
      { type: 'p', text: 'SPAC-specific alert rules for redemption deadlines, discount/premium thresholds, and deal announcements on tracked SPACs. Found under SPACs → Alerts. Separate from the general Smart Alerts (Watchlist → Smart Alerts) since these read trust value, deadline, and status directly from the SPAC Tracker rather than price history.' },
      { type: 'steps', items: [
        'Pick a tracked SPAC and an alert type, set any parameters, then "+ Add Rule". Click "Scan N Rules" to check them all against live data.',
        'Deadline Approaching fires when the days remaining to the redemption deadline falls at or below your threshold (including overdue).',
        'Discount/Premium Threshold fires when the live discount/premium to trust crosses your chosen level in the chosen direction — e.g. "at or below −3%" to catch attractive entries, or "at or above 0%" to flag when a SPAC has moved to a premium.',
        'Deal Announced fires as soon as status moves away from "Searching for Target" — the single biggest catalyst for a SPAC.',
      ]},
      { type: 'tip', text: 'Like the general Smart Alerts, this checks whether the condition is true right now each time you scan — it isn\'t a background push notification and doesn\'t track "already seen." Remove a rule once you\'ve acted on it, or leave it to keep confirming the condition on each scan.' },
      { type: 'h3', text: 'Risk Matrix' },
      { type: 'p', text: 'Visual map of annualized yield vs. deadline timing across your tracked SPAC universe. Found under SPACs → Risk Matrix. SPACs don\'t get a synthetic risk score the way Merger Arb deals do — there\'s no regulatory/deal-type risk model that applies — so this maps the two things that actually drive the arb: how attractive the entry is and how soon the catalyst (deadline or deal) arrives.' },
      { type: 'steps', items: [
        'The scatter plot places each SPAC by days-to-deadline (x-axis) and annualized yield (y-axis); bubble size reflects the magnitude of its discount/premium to trust, and color reflects deal stage (Searching, Deal Announced, Shareholder Vote, Redemption Period, Closing).',
        'The Deal Stage × Deadline Urgency grid buckets your book by how close each SPAC is to its deadline (Urgent <45d, Moderate 45–120d, Distant >120d) crossed with deal stage, showing count and average annualized yield per cell.',
        '"Nearest Deadlines" and "Best Annualized Yield" panels surface the extremes in your book at a glance.',
      ]},
      { type: 'h3', text: 'Relative Strength Ranker' },
      { type: 'p', text: 'Ranks any list of stocks by how much they have outperformed or underperformed SPY over 5 timeframes. Found under Research → Relative Strength. RS > 1.0 means the stock returned more than the market; RS < 1.0 means it lagged.' },
      { type: 'steps', items: [
        'Enter symbols manually or click "⬇ Watchlist" to import your watchlist.',
        'Click "▶ Rank" — the tool fetches 1 year of daily history for each symbol plus SPY.',
        'Results appear in a sortable table. Click any column header to sort.',
        'Use the filter buttons to show only Leaders (RS ≥ 1.0) or Laggards (RS < 1.0).',
        'The "Highlight period" buttons shade the selected period\'s column and set the bar chart scale.',
      ]},
      { type: 'table', headers: ['Column', 'What it shows'], rows: [
        ['RS Score', 'Composite: unweighted average of RS ratios across 1W, 1M, 3M, 6M, 1Y. Higher = stronger relative performer.'],
        ['RS 1W … RS 1Y', 'stock % return ÷ SPY % return for that period. Values > 1.0 = beat market. Negative = moved against market.'],
        ['Return (small)', 'The stock\'s raw percentage return for that period, shown in smaller text below the RS ratio.'],
        ['Label badge', 'Leader (≥1.0), Outperform, Mixed (0.5–1.0), Lagging, or Weak (<0).'],
      ]},
      { type: 'tip', text: 'Tip: stocks with consistently high RS across multiple periods (1M, 3M, 6M all > 1.0) show sustained momentum — a classic signal used in factor investing. Stocks with high 1W RS but low 3M RS may be bouncing from a downtrend, not truly outperforming.' },
      { type: 'h3', text: 'Seasonal Patterns' },
      { type: 'p', text: 'Shows month-by-month historical return tendencies for any stock, averaged over up to 20 years of data. Found under Research → Seasonal Patterns.' },
      { type: 'steps', items: [
        'Enter a ticker symbol and select how many years of history to use (5, 7, 10, 15, or 20).',
        'Click "▶ Analyze" or click one of the preset buttons (AAPL, MSFT, NVDA, SPY, etc.) to load immediately.',
        'Toggle between Chart view (12-month bar chart) and Table view (detailed month-by-month breakdown).',
        'The table includes: Avg Return, Win Rate (% of years that month was positive), Best Year, Worst Year, and a box plot distribution.',
      ]},
      { type: 'table', headers: ['Card', 'What it shows'], rows: [
        ['Best Month', 'The calendar month with the highest average historical return.'],
        ['Worst Month', 'The calendar month with the lowest average historical return.'],
        ['Positive Months', 'Count of months with a positive average return (out of 12).'],
        ['Current Month', 'Highlights the ongoing month and its historical average — useful for context on today\'s moves.'],
      ]},
      { type: 'tip', text: 'Tip: "Sell in May" is a seasonal pattern — it shows up in many stocks as weaker May–September returns. But check the win rate: a -1% avg return with a 45% win rate is very different from -3% with a 25% win rate. The latter is a much stronger signal to be cautious.' },
      { type: 'h3', text: 'ETF Overlap Analyzer' },
      { type: 'p', text: 'Reveals shared holdings between 2–4 ETFs to expose hidden concentration risk when you own multiple funds. Found under Research → ETF Overlap.' },
      { type: 'steps', items: [
        'Enter 2–4 ETF tickers comma-separated, or click a preset (Big 3 Tech ETFs, Growth vs Value, etc.).',
        'Click "▶ Analyze Overlap." The tool fetches top holdings for each ETF from Yahoo Finance and finds shared positions.',
        'The ETF cards show top 8 holdings with weight bars for each fund.',
        'The Shared Holdings table lists every stock that appears in more than one ETF, sorted by combined weight across all funds.',
        'Each row shows the weight in each ETF and a colored bar indicating exposure.',
      ]},
      { type: 'tip', text: 'Tip: QQQ and VGT overlap by ~70% in their top 10 holdings. Owning both is much less diversified than it appears — you\'re mostly doubling down on Apple, Microsoft, and NVIDIA. Use this tool before buying a second tech ETF to see if it actually adds diversification.' },
    ],
  },
  {
    id: 'trading',
    title: 'Trading',
    icon: '⚡',
    blocks: [
      { type: 'h3', text: 'Day Trader' },
      { type: 'p', text: 'A full intraday trading dashboard with planning tools, live scanner, and strategy playbooks.' },
      { type: 'h3', text: 'Trading Plan Calculator' },
      { type: 'p', text: 'Fill in your session parameters at the top to generate a personalised trading plan:' },
      { type: 'table', headers: ['Input', 'Purpose'], rows: [
        ['Capital', 'Total account size available for trading today.'],
        ['Daily Target %', 'Your profit target for the session as a % of capital.'],
        ['Max Daily Loss %', 'Your stop-out threshold — stop trading if this is hit.'],
        ['Planned Trades', 'How many setups you plan to take.'],
        ['Stop Loss %', 'Per-trade stop as a % of entry price.'],
        ['Risk/Reward', 'Your minimum acceptable reward per unit of risk (e.g. 2 = 2:1 R:R).'],
      ]},
      { type: 'p', text: 'The plan calculates: capital per trade, dollar target per trade, stop loss dollar amount, win rate needed to reach your target, and how many wins required.' },
      { type: 'h3', text: 'Strategy Playbooks' },
      { type: 'p', text: 'Six pre-defined intraday strategies with full setup criteria, entry/exit rules, and risk notes:' },
      { type: 'bullets', items: [
        'Gap & Go — pre-market gap plays with volume confirmation.',
        'Momentum — continuation trades on high relative volume.',
        'VWAP Reversion — mean-reversion trades around the VWAP line.',
        'Opening Range — breakout/breakdown from the first 15-minute range.',
        'Mean Reversion (Fade) — counter-trend trades on overextended moves.',
        'Scalping — quick in/out on level 2 momentum.',
      ]},
      { type: 'h3', text: 'Live Scanner' },
      { type: 'p', text: 'The candidate table auto-refreshes and shows stocks with significant intraday moves, volume surges, and pre-market gaps. Each row includes a calculated position size based on your trading plan.' },
      { type: 'bullets', items: [
        'Trade alerts sidebar: real-time alerts ranked by severity (SURGE, MOMENTUM, STRENGTH, SELL-OFF, etc.).',
        'Pre-market movers: top gainers and losers before the open with catalyst identification.',
        'News feed: timestamped headlines relevant to top movers.',
        'Click any symbol\'s chart icon to open the full chart modal.',
      ]},
      { type: 'h3', text: 'Trade Ideas' },
      { type: 'p', text: 'Click "Generate Ideas" for Claude AI to analyse your current watchlist and generate specific trade setups with entries, targets, and risk levels.' },
      { type: 'bullets', items: [
        'Ideas are generated based on current quotes and alert data from your watchlist.',
        'Output includes bullish setups (long entries), bearish setups (short/put entries), and key catalysts to watch.',
        'Click Stop at any time to interrupt generation.',
        'Results are not saved — regenerate each session for fresh ideas based on current prices.',
      ]},
      { type: 'tip', text: 'Disclaimer: AI-generated trade ideas are for informational purposes only and are not financial advice. Always apply your own analysis and risk management.' },
      { type: 'h3', text: 'Wheel Strategy Tracker' },
      { type: 'p', text: 'Tracks your options wheel positions — cash-secured puts (CSP) and covered calls (CC) — through the full cycle. Found under Trading → Wheel Tracker. All data is stored in browser localStorage, no account login needed.' },
      { type: 'steps', items: [
        'Click "+ Add Position" and fill in: ticker, phase (CSP or CC), strike price, premium per contract, number of contracts, and expiration date.',
        'The form instantly calculates the annualised return on capital for the position.',
        'After entry: track time to expiry and premium collected. When assigned, change status to "Assigned" and add a CC leg.',
        'When closed or expired, mark as "Closed / Expired" to archive the position.',
        'Use the filter tabs (Open / Assigned / Closed / All) to focus on active positions.',
      ]},
      { type: 'table', headers: ['Column', 'Meaning'], rows: [
        ['Phase', 'Cash-Secured Put (Step 1) or Covered Call (Step 2) of the wheel.'],
        ['Strike', 'The option strike price you sold.'],
        ['Premium', 'Credit received per share (per contract ÷ 100).'],
        ['Total', 'Total cash collected = premium × 100 × contracts.'],
        ['Ann. Yield', 'Annualised return on capital: (total premium ÷ capital at risk) ÷ days × 365.'],
        ['Status', 'Open: active. Assigned: shares delivered. Closed/Expired: cycle complete.'],
      ]},
      { type: 'tip', text: 'Tip: for CSPs, the capital at risk is strike × 100 × contracts (the cash you must hold to secure the put). Aim for annualised yields of 12–30% on high-quality underlyings.' },
      { type: 'h3', text: 'Position Sizer' },
      { type: 'p', text: 'Calculates how many shares to buy based on your risk parameters. Found under Trading → Position Sizer.' },
      { type: 'steps', items: [
        'Enter: Symbol, Account Size, Risk Per Trade (%), Entry Price, and Stop Price.',
        'Three sizing methods are calculated simultaneously:',
      ]},
      { type: 'table', headers: ['Method', 'Formula', 'Best for'], rows: [
        ['Fixed Fractional', 'Risk$ / (Entry − Stop)', 'Standard risk-based sizing for any setup.'],
        ['ATR-based (14)', 'Risk$ / ATR(14)', 'Volatility-adjusted sizing — smaller size on volatile stocks.'],
        ['Half-Kelly', 'Partial Kelly criterion using win rate and R:R', 'Long-term position sizing if you track win rate accurately.'],
      ]},
      { type: 'tip', text: 'Tip: always use the smaller of Fixed Fractional and ATR-based as a sanity check. If the ATR size is much smaller it means the stock is too volatile for your stop distance.' },
    ],
  },
  {
    id: 'merger-arb',
    title: 'Merger Arb',
    icon: '⇄',
    blocks: [
      { type: 'p', text: 'Merger arbitrage is buying a takeover target for less than the deal will pay, and earning the spread if the deal closes. The group has seven views that share one list of tracked deals. Prices are live; deal terms, status and dates are entered by you (or added from the scanner).' },
      { type: 'table', headers: ['View', 'What it does'], rows: [
        ['Overview', 'The hub. Lists every tracked deal by soonest expected close, plus the newest filings you aren\'t tracking yet (with quick-add). Click a deal to open it in the Deal Analyzer, or "Dashboard" to jump to its row.'],
        ['Deal Dashboard', 'Your tracked deals with live spread, annualised return to expected close, days to close and a risk level. Add a deal with the target ticker, acquirer, deal type (cash, stock or mixed), offer price, dates, status (pending regulatory, shareholder vote, financing, closing, terminated, closed), deal value and regulator. A panel below lists recent tender-offer filings from SEC EDGAR.'],
        ['Opportunity Scanner', 'Scans EDGAR over the last 60 days for merger-related filings (tender offers, going-private transactions, merger proxies, S-4s and 425 communications), pulls the ticker, adds the live price and 5-day / 1-month change, marks deals you already track, and lets you add one with a click. Filter by form type, search, or hide tracked deals.'],
        ['Deal Analyzer', 'Risk / reward for one deal, tracked or ad hoc: an estimated walk-away price (from pre-announcement trading, or a 15% discount if unavailable), upside and downside, the market-implied probability the deal closes, a point breakdown of the risk factors, and an expected-value table across close probabilities from 50% to 95%.'],
        ['Arb Portfolio', 'Your positions against tracked deals: cost basis, market value, unrealised P&L, value if the deal closes, and concentration by deal type and by regulator.'],
        ['Risk Matrix', 'A bubble chart of tracked deals (days to close against annualised return; bubble size is deal value, colour is risk level) and a regulator-by-deal-type grid shaded by average risk.'],
        ['Alerts', 'Rules tied to a specific deal: days to close below a threshold (fires when overdue too), spread above or below a level, or the deal reaching a status such as Closing or Terminated. Click Scan to check them; there is no background polling.'],
      ]},
      { type: 'bullets', items: [
        'The risk score adds up five factors: deal structure, spread size, regulatory scrutiny, deal size and time horizon. The Deal Dashboard and Deal Analyzer use the same breakdown.',
        'Net Exposure (Portfolio) counts arb capital as a separate event-driven sleeve rather than market beta, because its risk is the deal failing, not the market falling.',
      ]},
      { type: 'tip', text: 'Disclaimer: the implied close probability and risk scores are mechanical estimates from the inputs you provide. Deal terms change, and a failed deal can cost far more than the spread offered.' },
    ],
  },
  {
    id: 'spacs',
    title: 'SPACs',
    icon: '◎',
    blocks: [
      { type: 'p', text: 'A SPAC (blank-check company) holds investors\' money in a trust and has a deadline to merge with a target. Its shares can usually be redeemed for the trust value plus interest, which puts a floor under the price. When a SPAC trades below trust value, buying it and redeeming earns the discount with limited downside; its warrants add leveraged upside if a deal works. This is a different trade from merger arbitrage, so it has its own group.' },
      { type: 'table', headers: ['View', 'What it does'], rows: [
        ['Overview', 'The hub: tracked SPACs by soonest redemption deadline (click one to open it in the Deal Analyzer or the Tracker) and the newest untracked filings from Discovery with quick-add.'],
        ['Tracker', 'Your SPACs with live discount or premium to trust value, annualised yield to the deadline, days to the redemption deadline and warrant price, sorted by yield so the best opportunities come first.'],
        ['Discovery', 'Scans EDGAR over 60 days for new SPAC IPOs (S-1 blank-check filings) and for de-SPAC merger announcements (425, DEFM14A and S-4 filings mentioning a trust account). Common and warrant tickers are parsed from the filing, and a SPAC can be added to the Tracker in one click.'],
        ['Deal Analyzer', 'The floor case (return if you buy now and redeem at trust by the deadline), warrant intrinsic value, time value and breakeven, and a redeem-versus-hold table from a weak aftermarket up to +200% over trust for both the common stock and the warrants.'],
        ['Portfolio', 'Common stock and warrant positions, tracked separately with their own live prices. The summary shows cost, market value, unrealised P&L and a Trust-Protected figure: the redemption value of your common shares, recoverable whatever happens to the deal. Warrants are excluded from it, since they carry no redemption right and can go to zero.'],
        ['Alerts', 'Rules per SPAC: deadline within N days (fires when overdue too), discount or premium to trust above or below a level, or a deal being announced. Click Scan to check them.'],
        ['Risk Matrix', 'A scatter of annualised yield against days to deadline, with bubble size for the discount and colour for the deal stage, plus a stage-by-urgency grid and quick lists of the nearest deadlines and the best yields. There is no synthetic risk score here: it simply maps entry attractiveness against catalyst timing.'],
      ]},
      { type: 'tip', text: 'Disclaimer: trust values, deadlines and warrant terms are entered by you, so the yields are only as good as those inputs. Redemption rights, extensions and sponsor terms vary by SPAC; read its filings.' },
    ],
  },
  {
    id: 'ai-tools',
    title: 'AI Tools',
    icon: '✦',
    blocks: [
      { type: 'h3', text: 'Morning Briefing' },
      { type: 'p', text: 'A daily AI-generated market briefing personalised to your watchlist. Found under AI Tools → Morning Briefing. On load, live snapshot cards show the current price and daily change for S&P 500, Nasdaq, Dow, Russell 2000, VIX, and the 10-year Treasury yield. Click "Generate Morning Briefing" to pull live market data and stream a structured Claude analysis.' },
      { type: 'h3', text: 'How to Use' },
      { type: 'steps', items: [
        'The market snapshot cards load automatically — no action required.',
        'Review your watchlist (pre-filled with common tickers). Click "Edit" to add or remove symbols. Changes are saved to localStorage and persist across sessions.',
        'Click "Generate Morning Briefing". The backend collects live index prices, 11 sector ETF returns, watchlist stock prices, and recent news headlines, then streams them to Claude.',
        'The briefing streams in 6 structured sections (see below). A spinner shows while Claude is writing.',
        'The finished briefing is cached in localStorage for the trading day. Revisiting the page shows the cached version instantly. Click "Refresh Briefing" to regenerate with fresh data.',
      ]},
      { type: 'h3', text: 'Briefing Sections' },
      { type: 'table', headers: ['Section', 'What it covers'], rows: [
        ['Market Pulse', 'Executive summary of the day\'s market tone: risk-on vs risk-off, the dominant macro regime, and the single most important theme to carry into the session.'],
        ['Index & Sector Breakdown', 'Narrative interpretation of index and sector performance data — rotation signals, what\'s leading/lagging, and what that tells us about investor positioning.'],
        ['Watchlist Spotlight', 'For each watchlist symbol: momentum, key technical support/resistance levels, and any news catalysts. Specific price levels are called out.'],
        ['Key News & Market Implications', 'Top 4–5 market-relevant headlines with a 1–2 sentence note on the trading implication of each.'],
        ['Risk Radar', '2–3 specific risks or wildcards that could catch the market off-guard today — each with the trigger event and scenario.'],
        ['Today\'s Action Checklist', '5 bullet-point action items: concrete things to watch or do today, with tickers and levels where possible.'],
      ]},
      { type: 'bullets', items: [
        'Watchlist supports up to 15 symbols. Type a ticker in the "Add ticker…" input and press Enter or comma to add.',
        'The snapshot cards auto-refresh when you navigate to the page — market data is not cached.',
        'The briefing cache is per-day: generating on Monday stores a Monday briefing; the cache resets automatically on Tuesday.',
        'Sector data is ranked best-to-worst so Claude can identify rotation themes.',
      ]},
      { type: 'tip', text: 'Tip: generate the briefing before the market opens (pre-market) for an early read on overnight sentiment, or right at the open for the most current data.' },
      { type: 'tip', text: 'Disclaimer: Morning Briefing output is generated by AI and is for informational purposes only — not personalised financial advice. Always verify key data points before acting.' },
      { type: 'h3', text: 'Digests (Daily & Weekly)' },
      { type: 'p', text: 'A scheduled recap of your markets, portfolio, watchlist, upcoming events, and alerts, delivered to your phone through Telegram — so you get the picture without opening the app. Found under AI Tools → Digests. The daily digest is built to be read before the open; the weekly digest is a Sunday-evening look back at the week and ahead at the next one.' },
      { type: 'h3', text: 'Setting Up Delivery' },
      { type: 'steps', items: [
        'In Telegram, message @BotFather, send /newbot, and copy the bot token it gives you.',
        'Send any message to your new bot, then open https://api.telegram.org/bot<TOKEN>/getUpdates in a browser and copy the number at chat → id.',
        'Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to backend/.env and restart the backend. The Delivery card turns to "connected"; click "Send test message" to confirm.',
        'Set your timezone and turn on the daily and/or weekly digest, pick the times, and click "Save schedule". The card shows when each will next run.',
      ]},
      { type: 'h3', text: "What's In Each Digest" },
      { type: 'table', headers: ['Section', 'Daily', 'Weekly'], rows: [
        ['Markets', 'Last session for S&P 500, Nasdaq 100, Dow, Russell 2000; VIX; 10-year yield; best and worst three sectors', 'Same, over the past 5 sessions'],
        ['Your portfolio', 'Value, unrealized P&L, last-session P&L and return vs. SPY, top movers by dollar impact', 'Past-5-session P&L and return vs. SPY, best and worst holdings'],
        ['Watchlist movers', 'Top gainers and losers on your default watchlist', 'Same, over the week'],
        ['Events', 'Economic releases and earnings (holdings and watchlist) in the next 2 days', 'The next 7 days'],
        ['Alerts', 'Price alerts already past their target while the app was closed, ones within 3% of triggering, and ones that triggered in the last day', 'Same, over the last 7 days'],
        ['Price targets', '—', 'Targets within 5% of the current price, or with a deadline inside 14 days'],
      ]},
      { type: 'bullets', items: [
        'Preview daily / Preview weekly builds a digest on demand without sending it. "Send daily now" / "Send weekly now" deliver one immediately. History lists every digest sent, with its status, and opens the full text.',
        'The optional AI summary is a short paragraph at the top written by Claude from the same numbers. If your Anthropic key is missing or rejected, the digest is sent without it — nothing else changes.',
        'Digests are sent by the backend, so it must be running. If it was off at the scheduled time, a daily digest still goes out when the backend starts within 6 hours of it, and a weekly one the same day. Each period is sent at most once.',
        'A failed delivery is retried every 10 minutes, up to 3 attempts. With no delivery channel set up, nothing is sent and nothing is logged.',
        'Positions Yahoo can\'t price (delisted tickers, or symbols in a non-Yahoo format) are listed in the portfolio section and carried at cost rather than silently dropped.',
        'Price alerts are normally checked by your browser while the app is open. The digest checks them independently, so it catches alerts that crossed while you were away.',
      ]},
      { type: 'tip', text: 'Tip: the first digest after a while can take up to a minute because it looks up earnings dates for every holding and watchlist symbol; those are cached, so later ones take a few seconds.' },
      { type: 'h3', text: 'AI Stock Analyzer' },
      { type: 'p', text: 'Deep-dive single-stock research report powered by Claude. Enter any ticker to get a 7-section analysis: business overview, competitive moat, financial snapshot, valuation, bull case, bear case, and a clear verdict. Found under AI Tools → Stock Analyzer.' },
      { type: 'steps', items: [
        'Type a ticker in the input field (e.g. AAPL, NVDA, META) and click "Analyze →" or press Enter.',
        'The backend fetches comprehensive data from Yahoo Finance (price, fundamentals, margins, valuation multiples, technicals, analyst consensus) and caches it for 15 minutes.',
        'A snapshot card immediately shows price, 52-week range, P/E, forward P/E, RSI, moving averages, margins, and analyst targets.',
        'Claude then streams a full research report using only the actual numbers from the snapshot — no generic statements.',
        'Recent tickers appear as quick-access pills below the input field (stored in your browser).',
        'Click "Copy report" at the top of the analysis to copy the full markdown text.',
      ]},
      { type: 'table', headers: ['Section', 'What Claude covers'], rows: [
        ['Business Overview', 'What the company does, its revenue model, and what differentiates it in its sector and industry.'],
        ['Competitive Position & Moat', 'Pricing power, switching costs, network effects, cost advantages, regulatory moats. Names specific competitors and takes a stance on moat width.'],
        ['Financial Snapshot', 'Revenue trajectory, margin trends, balance sheet (cash vs debt, D/E ratio), free cash flow, and ROE analysis. Flags red flags or standout strengths.'],
        ['Valuation', 'P/E, forward P/E, P/S, EV/EBITDA vs sector norms. PEG ratio discussion. Clear verdict: cheap, fair, or expensive.'],
        ['Bull Case', '3 specific reasons to own the stock with timeframes and actual metric references.'],
        ['Bear Case & Key Risks', '3 most significant risks — valuation risk, competitive threats, macro sensitivity, company-specific issues.'],
        ['Verdict', 'Bullish / Neutral / Bearish with conviction level. The #1 catalyst to watch and the price/metric that would change the view.'],
      ]},
      { type: 'tip', text: 'Tip: the Stock Analyzer works best for US large/mid-cap stocks with full Yahoo Finance coverage. ETFs and very small companies may have incomplete fundamental data (missing P/E, margins, etc.) — the AI will note what data is unavailable.' },
      { type: 'tip', text: 'Disclaimer: AI Stock Analyzer output is generated by Claude claude-sonnet-4-6 and is for informational and educational purposes only — not personalised investment advice. Always do your own due diligence before investing.' },
      { type: 'h3', text: 'AI Portfolio Review' },
      { type: 'p', text: 'Claude analyzes your entire portfolio and streams a 6-section personalized review covering concentration risk, sector exposure, valuation, and specific rebalancing recommendations. Found under AI Tools → Portfolio Review.' },
      { type: 'steps', items: [
        'Add positions in Portfolio → Portfolio first. The review reads your holdings directly from the database.',
        'Click "Generate AI Review" on the Portfolio Review screen. The backend fetches live quotes for all your positions, computes weights, P&L, and sector breakdown, then streams the analysis.',
        'The preview table shows all your holdings sorted by invested amount with estimated portfolio weights.',
        'Click "■ Stop Generating" to interrupt the stream at any time.',
        'The review is not cached — click again to regenerate with fresh data.',
      ]},
      { type: 'table', headers: ['Section', 'What Claude covers'], rows: [
        ['Portfolio Overview', 'Total value, number of positions, overall character (growth/value/concentrated/diversified), and the single largest holding.'],
        ['Concentration & Risk Assessment', 'Single-stock concentration >20%, sector overweights vs. S&P 500 benchmark, correlation clusters, and market-cap skew.'],
        ['Sector & Style Analysis', 'Sector weights vs. S&P 500, growth vs. value tilt, large vs. small cap mix, domestic vs. international exposure.'],
        ['Performance & Valuation Snapshot', 'P/E, beta, and YTD data for each position. Flags overvalued, undervalued, and high-volatility names.'],
        ['Rebalancing Recommendations', '3–5 specific, actionable recommendations with dollar amounts or percentages and rationale.'],
        ['Action Checklist', '5 concrete action items with specific tickers, price levels, or events to act on this week or month.'],
      ]},
      { type: 'tip', text: 'Tip: run Portfolio Review after adding all your positions. With a large portfolio (100+ tickers), the backend enriches each position with live quotes and sector data — allow 15–30 seconds for the review to begin streaming.' },
      { type: 'tip', text: 'Disclaimer: AI Portfolio Review is generated by Claude claude-sonnet-4-6 and is for informational purposes only — not personalised investment advice. Consult a registered investment advisor before making rebalancing decisions.' },
      { type: 'h3', text: 'AI Chat (AI Advisor)' },
      { type: 'p', text: 'An open-ended chat interface powered by Claude. Ask any question about markets, trading strategies, stock analysis, or economic concepts.' },
      { type: 'bullets', items: [
        'Type your question and press Enter or click Send.',
        'Responses stream in real time — click Stop to interrupt.',
        'Suggested prompts appear as clickable pills to get you started.',
        'Responses are formatted as markdown: headers, bullet points, code blocks.',
        'Previous messages stay visible in the session. Clear the chat with the reset button.',
      ]},
      { type: 'p', text: 'Example questions:' },
      { type: 'bullets', items: [
        '"What is the risk/reward of buying NVDA calls before earnings?"',
        '"Explain the difference between a golden cross and a death cross."',
        '"How do I calculate position size using the ATR method?"',
        '"What sectors historically outperform when the Fed cuts rates?"',
      ]},
      { type: 'tip', text: 'Disclaimer: AI Chat is for educational and informational purposes only — not personalised financial advice.' },
      { type: 'h3', text: 'Financial Advisor' },
      { type: 'p', text: 'Generates a structured, personalised portfolio strategy and asset allocation plan based on your financial profile.' },
      { type: 'steps', items: [
        'Select your Investment Goal: Retirement, Home Purchase, Education Fund, Wealth Building, Income Generation, or Capital Preservation.',
        'Set your Investment Horizon (1–40 years) using the slider.',
        'Enter Starting Capital and Monthly Contribution.',
        'Set Risk Tolerance: Conservative, Moderate, or Aggressive.',
        'Set Current Age (affects lifecycle allocation recommendations).',
        'Choose Account Type: Taxable, Roth IRA, Traditional IRA, 401(k), or Multiple.',
        'Choose Geographic Focus: US-Focused, Global Diversified, or Emerging Markets Tilt.',
        'Click "Generate Plan". The plan streams as markdown with an embedded asset allocation chart.',
      ]},
      { type: 'p', text: 'The generated plan includes: recommended asset allocation with percentages, specific ETF/fund suggestions by asset class, rationale based on your inputs, tax considerations by account type, and a projected growth narrative.' },
      { type: 'h3', text: 'Tax Advisor' },
      { type: 'p', text: 'AI-powered tax optimisation tool for Married Filing Jointly (MFJ) households. Enter your financial profile and Claude generates a personalised, dollar-quantified tax-saving plan covering federal and state taxes. Found under AI Tools → Tax Advisor.' },
      { type: 'h3', text: 'Input Sections' },
      { type: 'table', headers: ['Section', 'Fields'], rows: [
        ['Location & Filing', 'State of residence (all 50 states + DC), qualifying children, spouses aged 50+, self-employed checkbox, employer health insurance, HSA-eligible plan.'],
        ['Annual Income', 'W-2 wages, self-employment income, short-term capital gains, long-term capital gains, qualified dividends, rental income, other income. Live gross total updates as you type.'],
        ['Retirement & Tax-Advantaged', 'Traditional 401(k), Roth 401(k), IRA, HSA, FSA contributions — each with the 2025 contribution limit shown as a hint.'],
        ['Deductions & Credits', 'Mortgage interest, property taxes (SALT cap noted), charitable giving, student loan interest, child/dependent care expenses.'],
      ]},
      { type: 'h3', text: 'AI Analysis — 8 Sections' },
      { type: 'table', headers: ['Section', 'What Claude covers'], rows: [
        ['📊 Tax Snapshot', 'Estimated AGI, federal tax, LTCG rate, state tax, total burden, and effective rate — before optimisation.'],
        ['🎯 Priority Actions', 'Ranked list of specific moves by estimated dollar savings (e.g. "max HSA = save $2,490 in federal tax").'],
        ['💼 Retirement Optimisation', 'Gaps in 401k/IRA/HSA contributions, Roth vs Traditional analysis, backdoor Roth eligibility, catch-up contributions.'],
        ['📉 Deduction Strategy', 'Standard vs itemised comparison, bunching charitable gifts, SALT cap workarounds.'],
        ['💰 Investment Tax Efficiency', 'LTCG rate optimisation, tax-loss harvesting opportunities, asset location (what to hold in taxable vs tax-deferred).'],
        ['🏠 State Tax Tips', 'State-specific strategies — deductions, credits, and quirks unique to your state.'],
        ['⚠️ Watch-Out Situations', 'AMT exposure, NIIT (3.8% on investment income above $250k), Roth conversion phase-outs.'],
        ['📅 Year-End Checklist', 'Time-sensitive actions to take before Dec 31.'],
      ]},
      { type: 'tip', text: 'Tip: run the Tax Advisor alongside the Roth Conversion Planner (Retirement group) — together they show how converting Traditional IRA funds affects your federal bracket, state tax, and ACA premium subsidy in early retirement.' },
      { type: 'tip', text: 'Disclaimer: AI Tax Advisor output is educational and informational only — not personalised tax advice. Consult a CPA or tax professional before filing or making major tax decisions.' },
    ],
  },
  {
    id: 'news',
    title: 'News',
    icon: '▤',
    blocks: [
      { type: 'p', text: 'The News section delivers a personalised news feed built from topics you choose. Unlike the per-symbol news in the chart modal, this feed aggregates articles across your whole area of interest in one place.' },
      { type: 'h3', text: 'My News Feed' },
      { type: 'p', text: 'Found under News → My News Feed. Select any combination of preset market topics and custom ticker symbols. Your selections are saved in browser localStorage and pre-loaded on every visit.' },
      { type: 'h3', text: 'Preset Topics' },
      { type: 'table', headers: ['Topic', 'Data source'], rows: [
        ['S&P 500', '^GSPC — S&P 500 index news'],
        ['Nasdaq', '^IXIC — Nasdaq Composite news'],
        ['Dow Jones', '^DJI — Dow Jones Industrial Average news'],
        ['Technology', 'QQQ — Nasdaq 100 ETF news'],
        ['Financials', 'XLF — Financial Select Sector SPDR'],
        ['Healthcare', 'XLV — Health Care Select Sector SPDR'],
        ['Energy', 'XLE — Energy Select Sector SPDR'],
        ['Consumer', 'XLY — Consumer Discretionary Select SPDR'],
        ['Industrials', 'XLI — Industrial Select Sector SPDR'],
        ['Real Estate', 'VNQ — Vanguard Real Estate ETF'],
        ['Utilities', 'XLU — Utilities Select Sector SPDR'],
        ['Communications', 'XLC — Communication Services SPDR'],
        ['Materials', 'XLB — Materials Select Sector SPDR'],
        ['Rates / Fed', '^TNX — 10-Year Treasury Yield news'],
        ['Gold', 'GC=F — Gold futures news'],
        ['Oil', 'CL=F — Crude Oil futures news'],
        ['Crypto', 'BTC-USD — Bitcoin news'],
      ]},
      { type: 'h3', text: 'Custom Tickers' },
      { type: 'p', text: 'Type any stock ticker (e.g. AAPL, NVDA, TSLA) in the custom ticker input and press Enter or click "+ Add". The feed will include news from that symbol alongside your preset topics. Click × on a custom ticker chip to remove it.' },
      { type: 'h3', text: 'Filtering' },
      { type: 'p', text: 'The filter bar above the news cards lets you narrow to a single topic. Click a topic pill to show only articles tagged to that source. Click "All" or the same pill again to return to the full feed.' },
      { type: 'bullets', items: [
        'Each topic pill shows the article count in parentheses.',
        'Articles are sorted newest-first across all selected topics.',
        'Duplicate articles (same URL from multiple sources) are deduplicated automatically.',
        'Up to 60 articles are shown per refresh.',
      ]},
      { type: 'h3', text: 'Refreshing' },
      { type: 'p', text: 'Click the Refresh button to re-fetch the latest articles. The feed also auto-refreshes when you change your topic selection. The "Updated X ago" timestamp shows when the current feed was last loaded.' },
      { type: 'tip', text: 'Tip: add the tickers you\'re actively trading as custom topics so breaking news for those positions appears in your feed alongside broader market context.' },
    ],
  },
  {
    id: 'charts',
    title: 'Chart Modal',
    icon: '◈',
    blocks: [
      { type: 'p', text: 'Open the chart modal by clicking any ticker in the Watchlist, Portfolio heatmap, or Market Summary tables. The modal has 11 tabs.' },
      { type: 'h3', text: 'Chart Tab' },
      { type: 'p', text: 'Interactive candlestick chart with volume histogram. Use the period buttons to switch timeframes:' },
      { type: 'bullets', items: [
        '1D = intraday (5-minute candles), 5D, 1M, 3M, 6M, 1Y, 2Y, 5Y.',
        'Drag to pan; scroll/pinch to zoom.',
        'Click outside the modal or press Escape to close.',
      ]},
      { type: 'h3', text: 'Technical Indicators' },
      { type: 'table', headers: ['Toggle', 'What it adds', 'Colour'], rows: [
        ['SMA20', '20-day Simple Moving Average overlay', 'Amber'],
        ['SMA50', '50-day Simple Moving Average overlay', 'Blue'],
        ['SMA200', '200-day Simple Moving Average overlay', 'Purple'],
        ['BB', 'Bollinger Bands (20-period, 2 SD) — upper, mid, and lower bands', 'Blue (transparent)'],
        ['RSI', 'RSI(14) sub-pane below the chart with 30/70 reference lines', 'Violet'],
        ['MACD', 'MACD histogram + signal line sub-pane', 'Blue/Amber'],
        ['VOL', '20-period average volume line on the volume histogram; bars with volume > 2× the average light up in full-brightness green/red instead of the default faded shade', 'Yellow'],
      ]},
      { type: 'tip', text: 'Tip: a common combo — turn on SMA50 + SMA200 to identify the long-term trend, then enable RSI to find oversold entries within an uptrend. Turn on VOL alongside any setup to confirm a breakout or reversal is backed by real volume.' },
      { type: 'h3', text: 'Drawing Tools' },
      { type: 'bullets', items: [
        '─ S/R: click once on the chart to draw a horizontal support/resistance line at that price. The price label shows on the left edge.',
        '╱ Trend: click once to set the start point, click again to complete the trend line.',
        'Drawings are saved to your browser\'s local storage and reappear the next time you open the same symbol.',
        '✕ Clear: removes all drawings for the current symbol.',
      ]},
      { type: 'h3', text: 'Other Tabs' },
      { type: 'table', headers: ['Tab', 'Contents'], rows: [
        ['Fundamentals', 'P/E, EV/EBITDA, margins, ROE, debt ratios, growth rates, dividends — key valuation and quality metrics.'],
        ['News', 'Recent headlines for the symbol with sentiment indicators and external links.'],
        ['Earnings', 'Three sections: (1) Earnings Call Summary — AI summary of the latest SEC 8-K filing including beat/miss, guidance, management tone, key themes, and a notable quote. (2) Earnings Play Calculator — expected move and options strategy sizing. (3) Historical earnings chart — last 8 quarters of EPS and revenue estimates vs actuals.'],
        ['Options', 'Full options chain for the nearest expiry: calls and puts with strike, bid/ask, volume, OI, delta, and IV. ITM strikes are highlighted.'],
        ['Strategies', 'AI-generated options strategy recommendations (covered call, protective put, straddle, etc.) based on current price and IV, with payoff visualisation.'],
        ['Insider', 'Recent insider transactions (Form 4 filings) — who bought or sold, how many shares, and at what price.'],
        ['Analyst', 'Analyst ratings, price targets, and recent upgrades/downgrades. Shows consensus rating and average 12-month target.'],
        ['Institutional', 'Top institutional holders, ownership percentage, and recent changes in holdings.'],
        ['Sentiment', 'Short interest %, put/call ratio, and news sentiment score for the symbol.'],
        ['Filings', 'Recent SEC filings (10-K, 10-Q, 8-K) with links to the original documents on EDGAR.'],
      ]},
      { type: 'h3', text: 'Earnings Call Summary' },
      { type: 'p', text: 'The AI earnings summary fetches the most recent 8-K filing from SEC EDGAR, strips the HTML, and sends it to Claude for analysis. It extracts:' },
      { type: 'bullets', items: [
        'Quarter and filing date.',
        'EPS/Revenue beat or miss vs estimates.',
        'Guidance for the next period vs analyst consensus.',
        'Management tone: Bullish / Neutral / Cautious / Bearish.',
        'Key themes discussed (AI adoption, margin expansion, etc.).',
        'Risks mentioned by management.',
        'A notable verbatim quote from the call.',
        'A link to the original SEC filing.',
      ]},
    ],
  },
  {
    id: 'retirement',
    title: 'Retirement',
    icon: '⏱',
    blocks: [
      { type: 'p', text: 'Eight tools for FIRE (Financial Independence, Retire Early) and retirement planning — covering accumulation, withdrawal risk, fund access, Social Security optimisation, healthcare gap coverage, Roth conversion strategy, Medicare cost planning, and estate/RMD projection.' },
      { type: 'h3', text: 'FIRE Calculator' },
      { type: 'p', text: 'Enter your current age, target retirement age (55 / 60 / 65 presets), annual expenses, current savings, monthly contribution, expected return, inflation, and Safe Withdrawal Rate. The calculator shows:' },
      { type: 'bullets', items: [
        'FIRE Number = annual expenses ÷ SWR (default 4%, the Trinity Study baseline).',
        'Progress bar: current savings vs FIRE number.',
        'Years to FIRE and projected year/age when portfolio crosses the threshold.',
        'Portfolio value and monthly income at your target retirement age.',
        'Retirement age comparison table: portfolio, % of FIRE #, monthly income, and status at ages 50–70.',
        'SVG projection chart showing portfolio growth curve against the FIRE target line.',
      ]},
      { type: 'h3', text: 'Coast FIRE & Roth Conversion Ladder' },
      { type: 'p', text: 'Two tools on one screen:' },
      { type: 'bullets', items: [
        'Coast FIRE: the amount you need invested today so that compound growth alone reaches your FIRE number by retirement — no further contributions required. Shows by-age table comparing coast numbers at each retirement age.',
        'Roth Conversion Ladder: for retiring before age 59½. Converts Traditional IRA/401k → Roth IRA each year; converted principal becomes penalty-free after a 5-year waiting period. The calculator shows suggested annual conversion amount, marginal tax bracket impact, estimated annual tax, and a year-by-year conversion schedule.',
      ]},
      { type: 'h3', text: 'Monte Carlo Simulator' },
      { type: 'p', text: 'Runs 1,000 simulations with randomised annual returns (Box-Muller normal distribution) to estimate the probability your portfolio survives your full retirement.' },
      { type: 'bullets', items: [
        'Inputs: starting portfolio, annual withdrawal, years in retirement, mean return, return standard deviation, inflation.',
        'Output: portfolio survival rate (%), median ending balance, worst-10% ending balance.',
        'Fan chart: 10th/25th/50th/75th/90th percentile paths over the full retirement horizon.',
        'Percentile table: final balance and % change vs starting portfolio for each scenario.',
        'Rule of thumb: 4% SWR with 7% mean / 15% std historically achieves ~90% success over 30 years.',
      ]},
      { type: 'h3', text: 'Social Security Optimizer' },
      { type: 'p', text: 'Enter your Full Retirement Age (FRA) benefit from your SSA.gov statement and compare all claiming ages from 62 to 70.' },
      { type: 'bullets', items: [
        'Claiming at 62: permanent reduction (~30% below FRA for those born 1960+).',
        'Claiming at FRA (67): 100% of your earned benefit, no reduction or bonus.',
        'Claiming at 70: +24% vs FRA (8%/year delayed credits for each year past FRA).',
        'Breakeven analysis: the age at which delaying overtakes claiming early in cumulative lifetime benefits.',
        'Cumulative chart: running total by claiming age — where lines cross is the breakeven point.',
        'Combined income column: SS monthly benefit + your portfolio withdrawal for a full retirement income picture.',
      ]},
      { type: 'h3', text: 'Early Retirement Health (ACA Estimator)' },
      { type: 'p', text: 'Estimates ACA Marketplace health insurance premiums and Premium Tax Credits for a family of 2 retiring early — covering the gap years between retirement (age 55) and Medicare eligibility (age 65).' },
      { type: 'bullets', items: [
        'Inputs: Age of Person 1, Age of Person 2, Annual MAGI (gross income), and annual income growth rate.',
        'Premium basis: 2025 CMS age-rating curve applied to a $310/month age-21 benchmark Silver plan. Premiums scale with age (age 64 = 3× age 21).',
        'Subsidy calculation: ARP/IRA extended rules — your required contribution is 0–8.5% of MAGI on a sliding scale based on % of Federal Poverty Level (FPL). ACA pays the rest.',
        'When one person turns 65 they shift to Medicare — only the younger person\'s premium remains in the ACA calculation.',
        'Outputs: Year 1 full premium, Year 1 subsidy, Year 1 net cost, 10-year total cost, and a year-by-year table through Medicare eligibility.',
        'SVG chart showing annual premium vs out-of-pocket cost for each gap year.',
        'Planning notes: Roth-vs-traditional withdrawal impact on MAGI, income management strategies to maximise subsidies.',
      ]},
      { type: 'tip', text: 'Tip: Roth IRA withdrawals are not counted as MAGI for ACA purposes, while Roth conversions are. Keeping MAGI below 400% FPL ($81,760 for a family of 2 in 2025) ensures you qualify for subsidies under the extended ARP rules.' },
      { type: 'h3', text: 'Roth Conversion Planner' },
      { type: 'p', text: 'Plans the optimal Roth IRA conversion strategy during the age 55–65 gap window — the low-income years between retirement and Social Security / RMDs when your tax bracket is at its lowest.' },
      { type: 'bullets', items: [
        'Inputs: Filing status (MFJ or Single), Traditional IRA balance, expected annual growth rate, other annual income, target tax bracket (12%, 22%, or 24%), and current age.',
        'Conversion room: the amount you can convert each year to stay within your target bracket without spilling into the next one.',
        'Year-by-year table: conversion amount, tax cost, running Roth balance, and remaining Traditional balance — projected to age 65.',
        'RMD impact: compares Traditional IRA balance at age 73 with and without conversions, showing the RMD reduction and estimated lifetime tax savings.',
        'Balance chart: SVG showing both balances growing to age 75 under both scenarios.',
        'Quick-reference bracket table for MFJ and Single filers.',
      ]},
      { type: 'table', headers: ['Why convert 55–65?', 'Explanation'], rows: [
        ['Low income window', 'No salary, no Social Security yet, no RMDs — your taxable income is at its career low.'],
        ['Fill the bracket', 'Convert just enough each year to reach the top of the 12% or 22% bracket without triggering the next rate.'],
        ['Reduce future RMDs', 'RMDs starting at 73 are calculated on your Traditional balance — smaller balance = smaller mandatory withdrawals.'],
        ['Tax torpedo prevention', 'Large RMDs + Social Security + Medicare IRMAA can stack into very high effective rates at 73+. Conversions now prevent that.'],
        ['5-year rule', 'Converted amounts are accessible penalty-free after 5 years, giving access before age 59½.'],
      ]},
      { type: 'tip', text: 'Tip: coordinate Roth conversions with the ACA Early Retirement Health calculator. Converting too much in a year raises your MAGI and reduces your ACA subsidy — find the sweet spot between conversion benefit and subsidy cost.' },
      { type: 'h3', text: 'Medicare Estimator' },
      { type: 'p', text: 'Estimates your monthly and annual Medicare premium costs including IRMAA income-based surcharges. Found under Retirement → Medicare Estimator. Uses 2025 CMS figures.' },
      { type: 'bullets', items: [
        'Enter your Modified AGI (MAGI) — Medicare uses income from 2 years prior. For example, if enrolling in 2026, Medicare looks at your 2024 MAGI.',
        'Select "Just me" or "Both spouses" to scale premiums.',
        'Toggle Part D (drug coverage), Medigap supplement (Plan G average), and standalone dental to see total monthly cost.',
        'The IRMAA bracket table highlights your current bracket — helps you plan income to avoid crossing into the next tier.',
        'The 20-year cost projection shows cumulative Medicare spending to age 85, assuming 2% annual premium inflation.',
      ]},
      { type: 'table', headers: ['Component', 'What it covers', '2025 base cost'], rows: [
        ['Part A', 'Hospital stays, skilled nursing. Free if you or spouse worked 40+ quarters.', 'Typically $0 premium'],
        ['Part B', 'Doctor visits, outpatient care. Mandatory for most.', '$185/mo (standard)'],
        ['Part D', 'Prescription drugs. Optional but penalty applies if delayed.', '~$55/mo avg base'],
        ['Medigap (Plan G)', 'Fills most Part A/B cost-sharing gaps. Most popular supplement.', '~$180/mo avg at 65'],
        ['Dental', 'Not included in Medicare. Separate standalone plan needed.', '~$50/mo avg'],
      ]},
      { type: 'tip', text: 'Tip: IRMAA thresholds are adjusted annually for inflation. A Roth conversion in a high-income year can push your MAGI above an IRMAA tier — use the Roth Conversion Planner to model the combined impact of conversion tax plus IRMAA surcharge.' },
      { type: 'h3', text: 'Estate & RMD Projector' },
      { type: 'p', text: 'Projects your Required Minimum Distributions (RMDs) from Traditional IRA/401(k) accounts through life expectancy, and models the heritable estate value at a target age. Found under Retirement → Estate & RMD.' },
      { type: 'steps', items: [
        'Enter your current age, Traditional IRA/401(k) balance, Roth IRA balance, and taxable account balance.',
        'Set Social Security income, any pension, expected portfolio return, inflation rate, and annual spending rate.',
        'Set your RMD start age (73 for those born 1951–1959 under SECURE 2.0; 75 for those born 1960+).',
        'Set your projection age (e.g. 90) to see estate value at that point.',
        'Optionally enable federal estate tax (40% on amounts above the $13.61M 2025 exemption).',
      ]},
      { type: 'bullets', items: [
        'The line chart shows Traditional, Roth, and Taxable balances side-by-side as they grow, get depleted by RMDs and spending, and converge.',
        'The year-by-year table shows each age\'s RMD amount, estimated federal tax on the RMD, marginal tax rate, and annual spend.',
        'RMD start age row is highlighted with a ★ marker in the table.',
        'RMDs are calculated using the IRS Uniform Lifetime Table — balance ÷ ULT divisor for that age.',
        '"Lifetime RMD Tax" summarises the total federal tax paid on RMDs over the projection horizon.',
      ]},
      { type: 'table', headers: ['Why RMDs matter for planning', 'Detail'], rows: [
        ['Forced income', 'RMDs are added to ordinary income regardless of whether you need the money — pushing you into higher brackets.'],
        ['Medicare IRMAA impact', 'High RMDs can push MAGI above IRMAA thresholds, increasing Part B and D premiums.'],
        ['Social Security taxation', 'Up to 85% of SS becomes taxable when combined income exceeds $44k (MFJ). RMDs raise this combined figure.'],
        ['Estate planning', 'Large Traditional IRA balances pass to heirs as ordinary income. Roth IRAs pass tax-free — a key reason to convert.'],
        ['Reduce RMDs now', 'Roth conversions during 55–65 low-income window reduce the Traditional balance subject to RMDs at 73.'],
      ]},
      { type: 'tip', text: 'Tip: use this tool alongside the Roth Conversion Planner. The RMD Projector shows how large your RMDs will be if you don\'t convert; the Conversion Planner shows how much to convert each year to shrink them. Together they quantify the lifetime tax savings of a conversion strategy.' },
    ],
  },
  {
    id: 'changelog',
    title: 'Changelog',
    icon: '◉',
    blocks: CHANGELOG_BLOCKS,
  },
  {
    id: 'tips',
    title: 'Tips & Shortcuts',
    icon: '◇',
    blocks: [
      { type: 'h3', text: 'Keyboard Shortcuts' },
      { type: 'table', headers: ['Key', 'Action'], rows: [
        ['Escape', 'Close any open modal (chart, alert).'],
        ['Enter', 'Submit forms (add ticker, add alert, run screener, send chat message).'],
        ['⌘K / Ctrl+K', 'Open the command palette to jump to any tool by name.'],
      ]},
      { type: 'h3', text: 'Data Caching' },
      { type: 'p', text: 'The app caches API responses in SQLite to avoid rate limits and reduce latency. Cache durations:' },
      { type: 'table', headers: ['Data', 'Cache Duration'], rows: [
        ['Live quotes', 'No cache — real-time via WebSocket (refreshed every few seconds) or REST polling.'],
        ['Chart data', 'Scales with the period: 1 minute (1D), 5 minutes (5D), 30 minutes (1M, 3M), 1 hour (6M), 4 hours (1Y, 2Y), 24 hours (5Y).'],
        ['Fundamentals', '5 minutes (quote panels); 2 hours (side-by-side comparison, DCF pre-fill).'],
        ['Market overview and performance', '15 minutes.'],
        ['News / headlines', '5 minutes.'],
        ['Market Breadth, Fed Watch, sector Scoreboard, Rotation Map, Screener', '30 minutes.'],
        ['Index Heatmap, Options chain', '15 minutes.'],
        ['Economy indicators and Regime Dashboard', '30 minutes for the computed tables; the FRED series behind them 6 hours.'],
        ['Indicator Studies, Cycle Fit, Sector Backtest', '6 hours; long monthly price history 24 hours.'],
        ['Themes pages', '15 minutes for performance; company fundamentals and analyst targets 24 hours.'],
        ['100-Bagger Finder', '24 hours per stock (scoring is recomputed on each request).'],
        ['Treasury yields and DXY', '30 minutes (live rates); 6 hours (Treasury.gov curve data).'],
        ['Earnings calendar', '4 hours (upcoming dates); 2 hours (Earnings+).'],
        ['Unusual Options Activity', '10 minutes per symbol; 30 minutes for the watchlist scan.'],
        ['SEC filings', '12 hours.'],
        ['Earnings call summary', '24 hours.'],
        ['News sentiment', '2 hours (watchlist batch); 1 hour (per-symbol AI).'],
        ['Tear Sheet', '1 hour; its 10-year SEC history 24 hours; SEC revenue-by-stream data 30 days (filings never change).'],
        ['Holdings Performance', '15 minutes for the table; 26 hours for the long-history prices that 3Y to life-to-date returns need.'],
      ]},
      { type: 'h3', text: 'Common Workflows' },
      { type: 'h3', text: 'Morning Market Check (5 minutes)' },
      { type: 'steps', items: [
        'Markets → Overview: scan index futures and sector performance.',
        'Markets → Breadth: check VIX and A/D ratio for overall risk-on/risk-off.',
        'Sectors → Scoreboard: sort by 1D or 1W to see which sectors are leading or lagging today.',
        'Watchlist: review overnight moves and earnings badges.',
        'Watchlist → Smart Alerts: click Scan to see if any rules triggered overnight.',
      ]},
      { type: 'h3', text: 'Evaluating a New Stock (10 minutes)' },
      { type: 'steps', items: [
        'Research → Tear Sheet: read the one-page snapshot first — business, 10-year track record, valuation verdict, analyst ratings and where the revenue goes. Download the PDF if you want to keep it.',
        'Add to watchlist → click the row to open the chart modal.',
        'Chart tab: check SMA50/200 trend, RSI level, and volume pattern.',
        'Earnings tab: read the AI earnings call summary for the last quarter.',
        'Analyst tab: check consensus rating and price target distribution.',
        'Research → DCF Valuation: run your own intrinsic value estimate with assumptions you choose.',
        'Research → Fundamentals: compare vs 2–3 sector peers.',
      ]},
      { type: 'h3', text: 'Finding the Leaders in an Index or Sector' },
      { type: 'steps', items: [
        'Markets → Holdings Performance: open the S&P 500 (or a sector ETF such as XLK) — it is ranked by year-to-date return.',
        'Click the 1M or 3M header to see what has momentum now, or switch on "Annualise 3Y+" to compare long-run winners fairly.',
        'Look at the "% beating SPY" row to see how broad the strength is.',
        'Click a symbol for its chart, then open Research → Tear Sheet to check whether the move is backed by earnings.',
      ]},
      { type: 'h3', text: 'Pre-Earnings Positioning' },
      { type: 'steps', items: [
        'Watchlist → Earnings+: check the Beat Rate and Expected Move for the symbol.',
        'Chart → Options tab: review the ATM straddle price to verify the expected move.',
        'Chart → Strategies tab: see AI-suggested options plays for the event.',
        'Trading → Position Sizer: calculate position size based on your risk budget.',
        'Set a Smart Alert (Watchlist → Smart Alerts) for Earnings Proximity so you don\'t miss the report date.',
      ]},
    ],
  },
]

// ── Renderer ──────────────────────────────────────────────────────────────────

function Block({ block, onNavigate }) {
  switch (block.type) {
    case 'p':
      return <p className="text-gray-400 text-sm leading-relaxed">{block.text}</p>

    case 'h3':
      return (
        <h3 className="text-white font-semibold text-sm mt-5 mb-2 flex items-center gap-2 flex-wrap">
          {block.text}
          {block.tabId && onNavigate && (
            <button
              onClick={() => onNavigate(block.tabId)}
              className="text-[10px] font-medium text-emerald-500 hover:text-emerald-400 border border-emerald-700/40 hover:border-emerald-600 rounded px-1.5 py-0.5 transition-colors normal-case tracking-normal"
            >
              Open feature →
            </button>
          )}
          {block.tabIds?.length > 0 && onNavigate && block.tabIds.map(t => (
            <button
              key={t.id}
              onClick={() => onNavigate(t.id)}
              className="text-[10px] font-medium text-emerald-500 hover:text-emerald-400 border border-emerald-700/40 hover:border-emerald-600 rounded px-1.5 py-0.5 transition-colors normal-case tracking-normal"
            >
              {t.label} →
            </button>
          ))}
        </h3>
      )

    case 'tip':
      return (
        <div className="bg-sky-900/20 border border-sky-800/40 rounded-lg px-3 py-2.5 text-sky-300 text-xs leading-relaxed">
          {block.text}
        </div>
      )

    case 'steps':
      return (
        <ol className="space-y-1.5">
          {block.items.map((item, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-gray-400 leading-relaxed">
              <span className="text-emerald-500 font-semibold tabular-nums shrink-0 w-4 text-right">{i + 1}.</span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      )

    case 'bullets':
      return (
        <ul className="space-y-1.5">
          {block.items.map((item, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-gray-400 leading-relaxed">
              <span className="text-gray-600 shrink-0 mt-1">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )

    case 'table':
      return (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900/80 border-b border-gray-800">
                {block.headers.map(h => (
                  <th key={h} className="text-left px-3 py-2 text-gray-500 text-xs font-semibold uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, ri) => (
                <tr key={ri} className={`border-b border-gray-800/50 ${ri % 2 ? 'bg-gray-900/20' : ''}`}>
                  {row.map((cell, ci) => (
                    <td key={ci} className={`px-3 py-2 text-xs leading-relaxed ${ci === 0 ? 'text-gray-300 font-medium whitespace-nowrap' : 'text-gray-500'}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

    default:
      return null
  }
}

function Section({ section, query, onNavigate }) {
  const matchesQuery = !query ||
    section.title.toLowerCase().includes(query) ||
    section.blocks.some(b =>
      (b.text || '').toLowerCase().includes(query) ||
      (b.items || []).some(i => i.toLowerCase().includes(query)) ||
      (b.rows || []).some(r => r.some(c => c.toLowerCase().includes(query))) ||
      (b.headers || []).some(h => h.toLowerCase().includes(query))
    )

  if (!matchesQuery) return null

  return (
    <section id={section.id} className="scroll-mt-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-emerald-400 text-base">{section.icon}</span>
        <h2 className="text-white font-bold text-base">{section.title}</h2>
      </div>
      <div className="space-y-3">
        {section.blocks.map((block, i) => <Block key={i} block={block} onNavigate={onNavigate} />)}
      </div>
    </section>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function UserGuide({ onNavigate, initialSection } = {}) {
  const [query, setQuery] = useState('')
  const contentRef = useRef(null)
  const q = query.toLowerCase().trim()

  function scrollTo(id) {
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Jump straight to a section (e.g. Changelog) when opened from elsewhere in
  // the app, such as the Home dashboard's "What's New" widget.
  useEffect(() => {
    if (initialSection) scrollTo(initialSection)
  }, [initialSection])

  const visibleIds = useMemo(() => {
    if (!q) return GUIDE.map(s => s.id)
    return GUIDE
      .filter(s =>
        s.title.toLowerCase().includes(q) ||
        s.blocks.some(b =>
          (b.text || '').toLowerCase().includes(q) ||
          (b.items || []).some(i => i.toLowerCase().includes(q)) ||
          (b.rows || []).some(r => r.some(c => c.toLowerCase().includes(q)))
        )
      )
      .map(s => s.id)
  }, [q])

  return (
    <div className="flex gap-0 h-full min-h-0">

      {/* TOC sidebar */}
      <aside className="hidden lg:flex flex-col w-44 shrink-0 border-r border-gray-800 overflow-y-auto py-4">
        <div className="text-gray-600 text-[10px] uppercase tracking-widest px-4 mb-3">Contents</div>
        {GUIDE.map(s => (
          <button
            key={s.id}
            onClick={() => scrollTo(s.id)}
            className={`w-full text-left px-4 py-1.5 text-xs transition-colors flex items-center gap-2 ${
              visibleIds.includes(s.id)
                ? 'text-gray-400 hover:text-emerald-400'
                : 'text-gray-700'
            }`}
          >
            <span className="text-gray-700 text-[10px]">{s.icon}</span>
            {s.title}
          </button>
        ))}
      </aside>

      {/* Content */}
      <div ref={contentRef} className="flex-1 overflow-y-auto px-6 py-5 space-y-10">

        {/* Header */}
        <div>
          <div className="text-gray-500 text-[10px] uppercase tracking-widest mb-1">Documentation</div>
          <h1 className="text-white font-bold text-xl mb-1">Stock Monitor — User Guide</h1>
          <p className="text-gray-500 text-sm">Complete reference for all features and workflows.</p>
        </div>

        {/* Search */}
        <div className="sticky top-0 bg-gray-950/90 backdrop-blur-sm py-2 -mx-6 px-6 z-10 border-b border-gray-800/50">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search the guide…"
            className="w-full max-w-sm bg-gray-800 border border-gray-700 text-white placeholder-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-sky-600"
          />
          {q && (
            <span className="ml-3 text-gray-600 text-xs">
              {visibleIds.length} section{visibleIds.length !== 1 ? 's' : ''} match
            </span>
          )}
        </div>

        {/* Sections */}
        {visibleIds.length === 0 ? (
          <div className="py-16 text-center text-gray-600 text-sm">No results for "{query}"</div>
        ) : (
          GUIDE.map(s => <Section key={s.id} section={s} query={q} onNavigate={onNavigate} />)
        )}

        <div className="text-gray-700 text-xs pb-8">
          Stock Monitor · Built with FastAPI + React + Claude AI · Data from Yahoo Finance & SEC EDGAR
        </div>
      </div>
    </div>
  )
}
