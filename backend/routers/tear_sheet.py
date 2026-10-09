"""Company Tear Sheet — Research → Tear Sheet.

One-page investment snapshot for a single stock: business profile, price
performance vs. the S&P 500, 10-year financial history, balance-sheet quality,
valuation multiples (vs. the company's own history), consensus estimates and
revisions, earnings track record, analyst ratings/targets, ownership, and a
rule-based valuation verdict (is it cheap or expensive?).

Data comes from yfinance, the 10-year Treasury yield (routers/treasury.py) for
the earnings-yield comparison, and SEC EDGAR XBRL filings for the 10-year financial
history (yfinance only serves ~4 fiscal years; non-SEC filers fall back to it). The independent
yfinance calls run in parallel threads — sequentially a cold tear sheet takes
~15s, in parallel ~4s.

Valuation methodology (all inputs are returned alongside the result so
nothing is a black box; see `methodologyNote`):
  - Historical P/E:   median fiscal-year-end P/E over up to 10 years x
                      trailing EPS.
  - PEG = 1 (Lynch):  fair P/E = consensus growth %, capped, x forward EPS.
  - DCF:              10-year free-cash-flow DCF, growth fading to 3%, discount
                      rate from beta (clamped 7-12%).
  - Analyst target:   mean 12-month target discounted one year at the DCF rate.
The verdict is the median of whichever methods could be computed, compared to
the current price. This is a rules-based screen, not investment advice.
"""
import asyncio
import logging
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pandas as pd
import yfinance as yf
from fastapi import APIRouter

from database import cache_get, cache_set
from edgar_utils import _session, _safe_float, _dividend_yield_fraction

logger = logging.getLogger(__name__)
router = APIRouter()

_TEAR_SHEET_TTL = timedelta(hours=1)

_TERMINAL_GROWTH = 0.03
_DCF_YEARS = 10
_MIN_MODELS_FOR_VERDICT = 2
_PERIOD_LABELS = {"0q": "Current Qtr", "+1q": "Next Qtr", "0y": "Current FY", "+1y": "Next FY"}

_METHODOLOGY_NOTE = (
    "Rules-based screen, not investment advice. Fair values come from four simple "
    "models (historical P/E, PEG = 1, a 10-year free-cash-flow DCF, and the discounted "
    "analyst target); the verdict is the median of those that could be computed. Every "
    "model is sensitive to its growth and multiple assumptions — treat the spread between "
    "them as seriously as the median. 12-month scenarios apply the current forward P/E "
    "(de-rated 20% in the bear case, 10% richer in the bull case) to next fiscal year's "
    "consensus low/average/high EPS."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _scale(x, lo, hi):
    """Linear map of x from [lo, hi] onto 0-100, clamped. None passes through."""
    if x is None:
        return None
    if hi == lo:
        return 50.0
    return _clamp((x - lo) / (hi - lo) * 100.0, 0.0, 100.0)


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _round(x, n=2):
    return None if x is None else round(x, n)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        logger.debug("tear sheet sub-fetch failed: %s", e)
        return default


def _df_ok(df) -> bool:
    return df is not None and isinstance(df, pd.DataFrame) and not df.empty


# ── Financial statements ──────────────────────────────────────────────────────

def _stmt_value(df, label, col):
    if not _df_ok(df) or label not in df.index or col not in df.columns:
        return None
    return _safe_float(df.loc[label, col])


_HISTORY_FIELDS = ("revenue", "grossProfit", "operatingIncome", "netIncome", "eps", "shares",
                   "operatingCashFlow", "freeCashFlow", "totalDebt", "cash", "equity")


def _yf_history_rows(income, cashflow, balance) -> list[dict]:
    """Raw per-fiscal-year rows (oldest first) from yfinance's annual statements,
    which only reach back ~4 years."""
    if not _df_ok(income):
        return []
    rows = []
    for c in sorted(income.columns):
        if _stmt_value(income, "Total Revenue", c) is None and _stmt_value(income, "Net Income", c) is None:
            continue  # yfinance sometimes returns an all-NaN oldest column
        rows.append({
            "fiscalYear": str(pd.Timestamp(c).date()),
            "revenue": _stmt_value(income, "Total Revenue", c),
            "grossProfit": _stmt_value(income, "Gross Profit", c),
            "operatingIncome": _stmt_value(income, "Operating Income", c),
            "netIncome": _stmt_value(income, "Net Income", c),
            "eps": _stmt_value(income, "Diluted EPS", c),
            "shares": _stmt_value(income, "Diluted Average Shares", c),
            "operatingCashFlow": _stmt_value(cashflow, "Operating Cash Flow", c),
            "freeCashFlow": _stmt_value(cashflow, "Free Cash Flow", c),
            "totalDebt": _stmt_value(balance, "Total Debt", c),
            "cash": _stmt_value(balance, "Cash Cash Equivalents And Short Term Investments", c),
            "equity": _stmt_value(balance, "Stockholders Equity", c),
        })
    return rows


def _finalize_history(rows: list[dict], limit: int) -> list[dict]:
    """Add margins and YoY growth to raw rows, then keep the newest `limit`.
    Growth is computed before trimming so the oldest kept year still has one."""
    out = []
    for raw in rows:
        r = {k: raw.get(k) for k in ("fiscalYear", *_HISTORY_FIELDS)}
        rev = r["revenue"]
        for key, name in (("grossProfit", "grossMargin"), ("operatingIncome", "operatingMargin"),
                          ("netIncome", "netMargin"), ("freeCashFlow", "fcfMargin")):
            r[name] = r[key] / rev if r[key] is not None and rev else None
        out.append(r)
    for i, r in enumerate(out):
        prev = out[i - 1] if i else None
        for key, name in (("revenue", "revenueGrowth"), ("netIncome", "netIncomeGrowth"),
                          ("eps", "epsGrowth"), ("freeCashFlow", "fcfGrowth")):
            p = prev.get(key) if prev else None
            cur = r.get(key)
            r[name] = (cur - p) / abs(p) if prev and cur is not None and p not in (None, 0) else None
    return out[-limit:]


def _financial_history(income, cashflow, balance, limit: int = 4) -> list[dict]:
    """Fiscal years from yfinance only, oldest first, with derived margins and YoY growth."""
    return _finalize_history(_yf_history_rows(income, cashflow, balance), limit)


# ── SEC EDGAR long-run history ────────────────────────────────────────────────
# yfinance serves ~4 fiscal years of statements. EDGAR's XBRL "companyfacts" feed has
# every 10-K a filer ever tagged, so it supplies the 10-year track record for US filers.

_HISTORY_YEARS = 10
_EDGAR_TTL = timedelta(hours=24)
# Per metric, tags in priority order; a company's tag often changes across years
# (e.g. Apple: SalesRevenueNet -> Revenues -> RevenueFromContract...), so gaps are
# filled from later tags in the list.
_EDGAR_CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "grossProfit": ["GrossProfit"],
    "operatingIncome": ["OperatingIncomeLoss"],
    "netIncome": ["NetIncomeLoss", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "operatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}


def _annual_points(concept_facts: dict) -> dict[str, tuple[str, float]]:
    """{period_end_date: (filed_date, value)} for full-fiscal-year 10-K facts only. companyfacts mixes
    quarterly and year-to-date durations under the same tag, so keep ~1-year spans
    (350-380 days covers 52/53-week years) and, when a year was restated in a later
    filing, the most recently filed value."""
    units = concept_facts.get("units", {})
    unit = next((u for u in ("USD", "USD/shares", "shares") if u in units), None)
    if unit is None:
        return {}
    best: dict[str, tuple[str, float]] = {}
    for x in units[unit]:
        if x.get("fp") != "FY" or not str(x.get("form", "")).startswith("10-K"):
            continue
        start, end = x.get("start"), x.get("end")
        if not start or not end:
            continue
        try:
            days = (pd.Timestamp(end) - pd.Timestamp(start)).days
        except (ValueError, TypeError):
            continue
        if not 350 <= days <= 380:
            continue
        filed = x.get("filed", "")
        if end not in best or filed > best[end][0]:
            val = _safe_float(x.get("val"))
            if val is not None:
                best[end] = (filed, val)
    return best


def _split_factor_after(splits: pd.Series | None, filed: str) -> float:
    """Cumulative split ratio for splits that happened after `filed`: a per-share figure
    reported in a filing doesn't reflect later splits (Apple's pre-2020 10-Ks show EPS
    4x today's), so EPS is divided and share counts multiplied by this."""
    if splits is None or len(splits) == 0 or not filed:
        return 1.0
    idx = splits.index.tz_localize(None) if getattr(splits.index, "tz", None) is not None else splits.index
    later = splits[idx > pd.Timestamp(filed)]
    factor = 1.0
    for ratio in later:
        if ratio and ratio > 0:
            factor *= float(ratio)
    return factor


def _edgar_rows_from_facts(us_gaap: dict, years: int, splits: pd.Series | None = None) -> list[dict]:
    """Raw per-fiscal-year rows (oldest first) from a companyfacts us-gaap block."""
    series: dict[str, dict[str, float]] = {}
    for metric, concepts in _EDGAR_CONCEPTS.items():
        merged: dict[str, tuple[str, float]] = {}
        for concept in concepts:
            if concept in us_gaap:
                for end, point in _annual_points(us_gaap[concept]).items():
                    merged.setdefault(end, point)
        series[metric] = {}
        for end, (filed, val) in merged.items():
            if metric == "eps":
                val = val / _split_factor_after(splits, filed)
            elif metric == "shares":
                val = val * _split_factor_after(splits, filed)
            series[metric][end] = val
    ends = sorted(set(series["revenue"]) | set(series["netIncome"]))[-years:]
    rows = []
    for end in ends:
        ocf, capex = series["operatingCashFlow"].get(end), series["capex"].get(end)
        rows.append({
            "fiscalYear": end,
            "revenue": series["revenue"].get(end),
            "grossProfit": series["grossProfit"].get(end),
            "operatingIncome": series["operatingIncome"].get(end),
            "netIncome": series["netIncome"].get(end),
            "eps": series["eps"].get(end),
            "shares": series["shares"].get(end),
            "operatingCashFlow": ocf,
            "freeCashFlow": ocf - abs(capex) if ocf is not None and capex is not None else None,
        })
    return rows


def _edgar_annual_history(sym: str, splits: pd.Series | None = None, years: int = _HISTORY_YEARS + 1) -> list[dict]:
    """Up to `years` fiscal years from SEC EDGAR; [] for non-SEC filers, funds, or on any failure."""
    key = f"tearsheet_edgar:{sym}"
    cached = cache_get(key, _EDGAR_TTL)
    if cached is not None:
        return cached
    from edgar_utils import _get_cik, _edgar_req
    cik = _get_cik(sym)
    if not cik:
        return []
    facts = _edgar_req(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json").json()
    rows = _edgar_rows_from_facts(facts.get("facts", {}).get("us-gaap", {}), years, splits)
    if rows:
        cache_set(key, rows)
    return rows


def _merge_history(edgar_rows: list[dict], yf_rows: list[dict], limit: int = _HISTORY_YEARS) -> list[dict]:
    """EDGAR is the backbone (long history, one consistent source); yfinance fills any field
    EDGAR didn't tag for a year and supplies balance-sheet items. A year yfinance has that
    EDGAR lacks (a 10-K filed but not yet tagged) is appended if it is newer than EDGAR's last."""
    if not edgar_rows:
        return _finalize_history(yf_rows, limit)

    def match(row):
        end = pd.Timestamp(row["fiscalYear"])
        for y in yf_rows:
            if abs((pd.Timestamp(y["fiscalYear"]) - end).days) <= 10:
                return y
        return None

    merged = []
    for e in edgar_rows:
        y = match(e) or {}
        merged.append({"fiscalYear": e["fiscalYear"],
                       **{k: e.get(k) if e.get(k) is not None else y.get(k) for k in _HISTORY_FIELDS}})
    last_end = pd.Timestamp(edgar_rows[-1]["fiscalYear"])
    merged += [y for y in yf_rows if pd.Timestamp(y["fiscalYear"]) - last_end > pd.Timedelta(days=10)]
    return _finalize_history(merged, limit)


def _build_history(income, cashflow, balance, edgar_rows, limit: int = _HISTORY_YEARS) -> list[dict]:
    return _merge_history(edgar_rows or [], _yf_history_rows(income, cashflow, balance), limit)


def _blank_cash_flow_metrics(history: list[dict]) -> None:
    """Free cash flow, operating cash flow and gross profit don't mean anything for a bank
    (deposits, lending and trading run through operating cash flow), so show dashes."""
    for r in history:
        for k in ("freeCashFlow", "operatingCashFlow", "fcfMargin", "fcfGrowth", "grossProfit", "grossMargin"):
            r[k] = None


def _pick_fcf(ttm_fcf, latest_fy_fcf):
    """Yahoo's trailing free cash flow is occasionally off by multiples (e.g. quoting $42B
    for a company whose latest 10-K shows $97B). Trust it unless it disagrees with the
    latest filed fiscal year by more than 2x either way, then fall back to the filing."""
    if ttm_fcf is None:
        return latest_fy_fcf
    if latest_fy_fcf is not None and latest_fy_fcf > 0 and ttm_fcf > 0:
        ratio = ttm_fcf / latest_fy_fcf
        if ratio < 0.5 or ratio > 2.0:
            return latest_fy_fcf
    return ttm_fcf


def _cagr(first, last, years):
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1


# ── Price history ─────────────────────────────────────────────────────────────

def _naive_close(hist, col: str = "Close") -> pd.Series | None:
    if hist is None or hist.empty or "Close" not in hist:
        return None
    s = hist[col if col in hist else "Close"].dropna()
    if s.empty:
        return None
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    return s


def _period_return(s: pd.Series | None, days: int):
    if s is None or len(s) < 2:
        return None
    target = s.index[-1] - pd.Timedelta(days=days)
    if s.index[0] > target + pd.Timedelta(days=7):
        return None  # not enough history for this lookback
    sub = s[:target]
    if sub.empty:
        return None
    base = sub.iloc[-1]
    return float(s.iloc[-1] / base - 1) if base else None


def _ytd_return(s: pd.Series | None):
    if s is None or len(s) < 2:
        return None
    prior = s[: pd.Timestamp(year=s.index[-1].year - 1, month=12, day=31)]
    if prior.empty:
        return None
    return float(s.iloc[-1] / prior.iloc[-1] - 1)


def _max_drawdown(s: pd.Series | None):
    if s is None or len(s) < 2:
        return None
    return float((s / s.cummax() - 1).min())


def _annual_vol(s: pd.Series | None, days: int = 252):
    if s is None or len(s) < 30:
        return None
    r = s.pct_change().dropna().tail(days)
    return float(r.std() * math.sqrt(252)) if len(r) > 20 else None


def _last_years(s: pd.Series | None, years: int) -> pd.Series | None:
    if s is None or s.empty:
        return s
    return s[s.index >= s.index[-1] - pd.DateOffset(years=years)]


def _price_performance(stock: pd.Series | None, spy: pd.Series | None) -> dict:
    periods = [("1M", 30), ("3M", 91), ("6M", 182), ("1Y", 365), ("3Y", 365 * 3), ("5Y", 365 * 5 - 10)]
    returns = []
    for label, days in periods:
        s_ret, b_ret = _period_return(stock, days), _period_return(spy, days)
        returns.append({
            "period": label, "stock": s_ret, "spy": b_ret,
            "relative": s_ret - b_ret if s_ret is not None and b_ret is not None else None,
        })
    ytd_s, ytd_b = _ytd_return(stock), _ytd_return(spy)
    returns.insert(3, {"period": "YTD", "stock": ytd_s, "spy": ytd_b,
                       "relative": ytd_s - ytd_b if ytd_s is not None and ytd_b is not None else None})

    series = None
    if stock is not None and len(stock) > 20:
        ma50 = stock.rolling(50).mean()
        ma200 = stock.rolling(200).mean()
        frame = pd.DataFrame({"close": stock, "ma50": ma50, "ma200": ma200})
        if spy is not None:
            frame["spy"] = spy.reindex(stock.index, method="ffill")
        weekly = frame.resample("W").last().dropna(subset=["close"])
        first_close = weekly["close"].iloc[0]
        first_spy = weekly["spy"].dropna().iloc[0] if "spy" in weekly and weekly["spy"].notna().any() else None
        series = {
            "dates": [d.strftime("%Y-%m-%d") for d in weekly.index],
            "close": [_round(v) for v in weekly["close"]],
            "ma50": [_round(v) if pd.notna(v) else None for v in weekly["ma50"]],
            "ma200": [_round(v) if pd.notna(v) else None for v in weekly["ma200"]],
            "stockRebased": [_round(v / first_close * 100, 1) for v in weekly["close"]],
            "spyRebased": ([_round(v / first_spy * 100, 1) if pd.notna(v) else None for v in weekly["spy"]]
                           if first_spy else None),
        }
    ma200_last = None
    if stock is not None and len(stock) >= 200:
        ma200_last = float(stock.tail(200).mean())
    return {
        "returns": returns,
        "maxDrawdown5y": _max_drawdown(stock),
        "volatility1y": _annual_vol(stock),
        "ma200": ma200_last,
        "series": series,
    }


def _historical_pes(stock: pd.Series | None, history: list[dict]) -> list[dict]:
    """P/E at each fiscal year-end = close at (or before) FY end / that year's diluted EPS."""
    out = []
    if stock is None:
        return out
    for h in history:
        eps = h.get("eps")
        if not eps or eps <= 0:
            continue
        end = pd.Timestamp(h["fiscalYear"])
        sub = stock[:end]
        if sub.empty or (end - sub.index[-1]).days > 10:
            continue
        out.append({"fiscalYear": h["fiscalYear"], "price": _round(float(sub.iloc[-1])),
                    "eps": eps, "pe": _round(float(sub.iloc[-1]) / eps, 1)})
    return out


# ── Estimates / analysts ──────────────────────────────────────────────────────

def _estimate_rows(df, is_revenue=False) -> list[dict]:
    if not _df_ok(df):
        return []
    rows = []
    for period, label in _PERIOD_LABELS.items():
        if period not in df.index:
            continue
        r = df.loc[period]
        rows.append({
            "period": period, "label": label,
            "avg": _safe_float(r.get("avg")), "low": _safe_float(r.get("low")),
            "high": _safe_float(r.get("high")),
            "yearAgo": _safe_float(r.get("yearAgoRevenue" if is_revenue else "yearAgoEps")),
            "analysts": int(r["numberOfAnalysts"]) if _safe_float(r.get("numberOfAnalysts")) is not None else None,
            "growth": _safe_float(r.get("growth")),
        })
    return rows


def _revisions(eps_trend) -> list[dict]:
    if not _df_ok(eps_trend):
        return []
    out = []
    for period in ("0y", "+1y"):
        if period not in eps_trend.index:
            continue
        r = eps_trend.loc[period]
        cur, ago90, ago30 = (_safe_float(r.get(k)) for k in ("current", "90daysAgo", "30daysAgo"))
        out.append({
            "period": period, "label": _PERIOD_LABELS[period], "current": cur,
            "change30d": (cur / ago30 - 1) if cur is not None and ago30 else None,
            "change90d": (cur / ago90 - 1) if cur is not None and ago90 else None,
        })
    return out


def _earnings_track(earn_hist) -> dict:
    quarters = []
    if _df_ok(earn_hist):
        for idx, r in earn_hist.iterrows():
            quarters.append({
                "quarter": str(pd.Timestamp(idx).date()),
                "epsActual": _safe_float(r.get("epsActual")),
                "epsEstimate": _safe_float(r.get("epsEstimate")),
                "surprisePct": _safe_float(r.get("surprisePercent")),
            })
    quarters = quarters[-8:]
    scored = [q for q in quarters if q["epsActual"] is not None and q["epsEstimate"] is not None]
    beats = sum(1 for q in scored if q["epsActual"] > q["epsEstimate"])
    return {"quarters": quarters, "beats": beats, "total": len(scored),
            "avgSurprisePct": _avg([q["surprisePct"] for q in scored])}


def _analyst_section(info, targets, recs, updown, price) -> dict:
    mean_t = _safe_float((targets or {}).get("mean")) or _safe_float(info.get("targetMeanPrice"))
    dist_now = dist_3m = None
    if _df_ok(recs):
        def row(period):
            m = recs[recs["period"] == period]
            if m.empty:
                return None
            r = m.iloc[0]
            return {k: int(_safe_float(r.get(k)) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
        dist_now, dist_3m = row("0m"), row("-3m")
    changes = []
    if _df_ok(updown):
        for idx, r in updown.head(8).iterrows():
            pt = _safe_float(r.get("currentPriceTarget"))
            prior = _safe_float(r.get("priorPriceTarget"))
            changes.append({
                "date": str(pd.Timestamp(idx).date()), "firm": str(r.get("Firm", "")),
                "action": str(r.get("Action", "")), "from": str(r.get("FromGrade", "")),
                "to": str(r.get("ToGrade", "")),
                "target": pt or None, "priorTarget": prior or None,
            })
    return {
        "recommendation": info.get("recommendationKey"),
        "recommendationMean": _safe_float(info.get("recommendationMean")),
        "analystCount": info.get("numberOfAnalystOpinions"),
        "targetMean": mean_t,
        "targetMedian": _safe_float((targets or {}).get("median")) or _safe_float(info.get("targetMedianPrice")),
        "targetHigh": _safe_float((targets or {}).get("high")) or _safe_float(info.get("targetHighPrice")),
        "targetLow": _safe_float((targets or {}).get("low")) or _safe_float(info.get("targetLowPrice")),
        "upsideToMean": (mean_t / price - 1) if mean_t and price else None,
        "distribution": dist_now,
        "distribution3mAgo": dist_3m,
        "recentChanges": changes,
    }


def _insider_section(insider_purchases) -> dict | None:
    if not _df_ok(insider_purchases):
        return None
    first = insider_purchases.columns[0]
    lookup = {str(r[first]): r for _, r in insider_purchases.iterrows()}

    def shares(label):
        r = lookup.get(label)
        return _safe_float(r.get("Shares")) if r is not None else None

    def trans(label):
        r = lookup.get(label)
        return _safe_float(r.get("Trans")) if r is not None else None
    return {
        "boughtShares6m": shares("Purchases"), "soldShares6m": shares("Sales"),
        "netShares6m": shares("Net Shares Purchased (Sold)"),
        "buyTransactions6m": trans("Purchases"), "sellTransactions6m": trans("Sales"),
    }


# ── Valuation models ──────────────────────────────────────────────────────────

def _discount_rate(beta) -> float:
    b = beta if beta is not None else 1.0
    return _clamp(0.045 + b * 0.05, 0.07, 0.12)


def _dcf_value_per_share(fcf, shares, growth, discount, cash, debt):
    """10-year FCF DCF: `growth` for years 1-5, fading linearly to 3% by year 10,
    then a Gordon-growth terminal value. Returns per-share equity value or None."""
    if not fcf or fcf <= 0 or not shares or shares <= 0 or growth is None:
        return None
    g0 = _clamp(growth, 0.0, 0.15)
    pv, cf = 0.0, fcf
    for yr in range(1, _DCF_YEARS + 1):
        if yr <= 5:
            g = g0
        else:
            g = g0 + (_TERMINAL_GROWTH - g0) * (yr - 5) / (_DCF_YEARS - 5)
        cf *= 1 + g
        pv += cf / (1 + discount) ** yr
    terminal = cf * (1 + _TERMINAL_GROWTH) / (discount - _TERMINAL_GROWTH)
    pv += terminal / (1 + discount) ** _DCF_YEARS
    equity = pv + (cash or 0.0) - (debt or 0.0)
    return equity / shares if equity > 0 else None


def _fair_values(price, eps_ttm, eps_fwd, growth, hist_pes, fcf, shares, beta, cash, debt, target_mean) -> list[dict]:
    """Each entry: {method, value, basis}; value is None when the model can't run."""
    out = []
    discount = _discount_rate(beta)

    pes = [h["pe"] for h in hist_pes if h.get("pe")]
    if len(pes) >= 2 and eps_ttm and eps_ttm > 0:
        # Median, not mean: one depressed-EPS year (e.g. a tax-reform charge) can print a
        # triple-digit P/E and would otherwise drag the whole average up.
        median_pe = statistics.median(pes)
        out.append({"method": "Historical P/E", "value": _round(median_pe * eps_ttm),
                    "basis": f"{median_pe:.1f}x median FY-end P/E ({len(pes)} yrs) × ${eps_ttm:.2f} trailing EPS"})
    else:
        out.append({"method": "Historical P/E", "value": None, "basis": "Needs 2+ years of positive EPS"})

    eps_for_peg = eps_fwd or eps_ttm
    if growth is not None and growth > 0 and eps_for_peg and eps_for_peg > 0:
        fair_pe = _clamp(growth * 100, 8, 40)
        out.append({"method": "PEG = 1", "value": _round(fair_pe * eps_for_peg),
                    "basis": f"{fair_pe:.1f}x (growth {growth * 100:.1f}%) × ${eps_for_peg:.2f} forward EPS"})
    else:
        out.append({"method": "PEG = 1", "value": None, "basis": "Needs positive earnings growth and EPS"})

    dcf = _dcf_value_per_share(fcf, shares, growth if growth is not None else 0.05, discount, cash, debt)
    if dcf is not None:
        gtxt = _clamp(growth if growth is not None else 0.05, 0, 0.15) * 100
        out.append({"method": "DCF (FCF)", "value": _round(dcf),
                    "basis": f"{gtxt:.1f}% growth fading to 3%, {discount * 100:.1f}% discount rate"})
    else:
        out.append({"method": "DCF (FCF)", "value": None, "basis": "Needs positive free cash flow"})

    if target_mean:
        out.append({"method": "Analyst target", "value": _round(target_mean / (1 + discount)),
                    "basis": f"${target_mean:.2f} 12-month mean target, discounted 1 yr at {discount * 100:.1f}%"})
    else:
        out.append({"method": "Analyst target", "value": None, "basis": "No analyst coverage"})
    return out


def _verdict(price, fair_values) -> dict:
    vals = [f["value"] for f in fair_values if f.get("value") and f["value"] > 0]
    # One model alone (typically just the analyst target, for unprofitable or fund
    # tickers) isn't enough to call a stock cheap or expensive.
    if len(vals) < _MIN_MODELS_FOR_VERDICT or not price:
        return {"label": "Not enough data to judge", "tone": "neutral", "fairValue": None, "premium": None,
                "low": _round(min(vals)) if vals else None, "high": _round(max(vals)) if vals else None,
                "methodsUsed": len(vals)}
    fair = statistics.median(vals)
    premium = price / fair - 1  # +ve = trading above fair value
    if premium <= -0.25:
        label, tone = "Significantly undervalued", "good"
    elif premium <= -0.10:
        label, tone = "Undervalued", "good"
    elif premium < 0.10:
        label, tone = "Fairly valued", "neutral"
    elif premium < 0.25:
        label, tone = "Overvalued", "bad"
    else:
        label, tone = "Significantly overvalued", "bad"
    return {"label": label, "tone": tone, "fairValue": _round(fair), "premium": premium,
            "low": _round(min(vals)), "high": _round(max(vals)), "methodsUsed": len(vals)}


def _scenarios_12m(price, eps_cur, eps_next, dividend_yield) -> list[dict]:
    """12-month price scenarios: next-FY consensus EPS (low/avg/high) x the current
    forward P/E (price / current-FY EPS), de-rated 20% in the bear case and 10% richer in bull."""
    if not price or not eps_cur or eps_cur <= 0 or not eps_next:
        return []
    fwd_pe = price / eps_cur
    spec = [("Bear", eps_next.get("low"), 0.80), ("Base", eps_next.get("avg"), 1.0), ("Bull", eps_next.get("high"), 1.10)]
    out = []
    for name, eps, mult in spec:
        if eps is None or eps <= 0:
            continue
        target = eps * fwd_pe * mult
        out.append({"scenario": name, "eps": _round(eps), "peMultiple": _round(fwd_pe * mult, 1),
                    "price": _round(target),
                    "priceReturn": target / price - 1,
                    "totalReturn": target / price - 1 + (dividend_yield or 0.0)})
    return out


def _five_year_returns(price, eps_ttm, growth, pe_now, pe_hist_median, dividend_yield) -> list[dict]:
    """Annualised 5-year return if EPS compounds at `growth` and the stock exits at a
    de-rated / blended / unchanged P/E. Dividends approximated as a flat yield."""
    if not price or not eps_ttm or eps_ttm <= 0 or growth is None or not pe_now or pe_now <= 0:
        return []
    g = _clamp(growth, 0.0, 0.25)
    anchor = _avg([pe_now, pe_hist_median]) if pe_hist_median else pe_now
    exits = [("P/E compresses", anchor * 0.7), ("Blend of now & history", anchor), ("P/E unchanged", pe_now)]
    out = []
    for name, pe in exits:
        end_price = eps_ttm * (1 + g) ** 5 * pe
        total = (end_price + price * (dividend_yield or 0.0) * 5) / price
        out.append({"scenario": name, "exitPe": _round(pe, 1), "endPrice": _round(end_price),
                    "annualisedReturn": total ** (1 / 5) - 1 if total > 0 else None})
    return out


# ── Scorecard ─────────────────────────────────────────────────────────────────

def _scorecard(m: dict) -> dict:
    growth = _avg([_scale(m.get("revenueGrowth"), -0.10, 0.30), _scale(m.get("epsGrowthFwd"), -0.10, 0.30)])
    profit = _avg([_scale(m.get("netMargin"), 0.0, 0.25), _scale(m.get("operatingMargin"), 0.0, 0.35),
                   _scale(m.get("roe"), 0.0, 0.30)])
    nd_ebitda = m.get("netDebtToEbitda")
    health = _avg([
        None if nd_ebitda is None else _scale(-nd_ebitda, -4.0, 1.0),
        _scale(m.get("currentRatio"), 0.5, 2.0),
        _scale(m.get("interestCoverage"), 1.0, 15.0),
    ])
    valuation = None if m.get("premium") is None else _scale(-m["premium"], -0.40, 0.30)
    rec_mean = m.get("recommendationMean")
    analyst = _avg([None if rec_mean is None else _scale(-rec_mean, -4.0, -1.0), _scale(m.get("upside"), -0.15, 0.30)])
    momentum = _avg([_scale(m.get("relative1y"), -0.30, 0.30), 70.0 if m.get("above200") else (30.0 if m.get("above200") is False else None),
                     _scale(m.get("rangePosition"), 0.0, 1.0)])
    pillars = [("Growth", growth), ("Profitability", profit), ("Financial health", health),
               ("Valuation", valuation), ("Analyst sentiment", analyst), ("Momentum", momentum)]
    scored = [p[1] for p in pillars if p[1] is not None]
    return {
        "pillars": [{"name": n, "score": _round(s, 0)} for n, s in pillars],
        "overall": _round(sum(scored) / len(scored), 0) if scored else None,
    }


def _flags(m: dict) -> dict:
    strengths, risks = [], []

    def add(cond, bucket, text):
        if cond:
            bucket.append(text)
    rg, nm = m.get("revenueGrowth"), m.get("netMargin")
    add(rg is not None and rg > 0.10, strengths, f"Revenue growing {rg * 100:.0f}% year over year" if rg else "")
    add(rg is not None and rg < 0, risks, f"Revenue shrinking {abs(rg) * 100:.0f}% year over year" if rg else "")
    add(nm is not None and nm > 0.15, strengths, f"High net margin ({nm * 100:.0f}%)" if nm else "")
    add(nm is not None and nm < 0, risks, "Currently unprofitable (negative net margin)")
    add(m.get("roe") is not None and m["roe"] > 0.20, strengths, f"Strong return on equity ({m['roe'] * 100:.0f}%)" if m.get("roe") else "")
    nd = m.get("netDebtToEbitda")
    add(nd is not None and nd < 0, strengths, "Net cash position (cash exceeds debt)")
    add(nd is not None and nd > 3, risks, f"Leverage is high ({nd:.1f}x net debt / EBITDA)" if nd else "")
    cr = m.get("currentRatio")
    add(cr is not None and cr < 1, risks, f"Current ratio {cr:.2f} — short-term liabilities exceed short-term assets" if cr else "")
    add(m.get("fcfPositive") is True, strengths, "Generates positive free cash flow")
    add(m.get("fcfPositive") is False, risks, "Burning cash (negative free cash flow)")
    prem = m.get("premium")
    add(prem is not None and prem <= -0.10, strengths, f"Trades {abs(prem) * 100:.0f}% below blended fair value" if prem else "")
    add(prem is not None and prem >= 0.25, risks, f"Trades {prem * 100:.0f}% above blended fair value" if prem else "")
    add(m.get("peVsHistory") is not None and m["peVsHistory"] > 0.4, risks,
        f"P/E is {m['peVsHistory'] * 100:.0f}% above its own median fiscal-year-end P/E" if m.get("peVsHistory") else "")
    up = m.get("upside")
    add(up is not None and up > 0.15, strengths, f"Analysts see {up * 100:.0f}% upside to the mean target" if up else "")
    add(up is not None and up < -0.05, risks, f"Trades above the mean analyst target ({up * 100:.0f}% implied)" if up else "")
    if m.get("above200") is False:
        risks.append("Trading below its 200-day moving average")
    if m.get("beat_rate") is not None and m["beat_rate"] >= 0.75:
        strengths.append("Consistently beats EPS estimates")
    sf = m.get("shortPercentOfFloat")
    add(sf is not None and sf > 0.10, risks, f"High short interest ({sf * 100:.0f}% of float)" if sf else "")
    beta = m.get("beta")
    add(beta is not None and beta > 1.5, risks, f"High market sensitivity (beta {beta:.2f})" if beta else "")
    dd = m.get("maxDrawdown5y")
    add(dd is not None and dd < -0.5, risks, f"Fell {abs(dd) * 100:.0f}% peak-to-trough in the last 5 years" if dd else "")
    return {"strengths": [s for s in strengths if s], "risks": [r for r in risks if r]}


# ── Orchestration ─────────────────────────────────────────────────────────────

def _ten_year_yield() -> float | None:
    try:
        from routers.treasury import treasury_current
        for r in treasury_current().get("rates", []):
            if r.get("key") == "10yr" and r.get("yield") is not None:
                return r["yield"] / 100.0
    except Exception as e:
        logger.warning("tear sheet: treasury fetch failed: %s", e)
    return None


def _fetch_raw(sym: str) -> dict:
    t = yf.Ticker(sym, session=_session)
    jobs = {
        "info": lambda: t.info,
        "income": lambda: t.income_stmt,
        "cashflow": lambda: t.cashflow,
        "balance": lambda: t.balance_sheet,
        "earn_est": lambda: t.earnings_estimate,
        "rev_est": lambda: t.revenue_estimate,
        "eps_trend": lambda: t.eps_trend,
        "earn_hist": lambda: t.earnings_history,
        "targets": lambda: t.analyst_price_targets,
        "recs": lambda: t.recommendations,
        "updown": lambda: t.upgrades_downgrades,
        "insider": lambda: t.insider_purchases,
        "calendar": lambda: t.calendar,
        # Close = split-adjusted only (right for P/E); Adj Close adds dividends (right for returns)
        "hist": lambda: t.history(period="10y", interval="1d", auto_adjust=False),
        "splits": lambda: t.splits,
        "edgar": lambda: _edgar_annual_history(sym, _safe(lambda: t.splits)),
        "spy": lambda: yf.Ticker("SPY", session=_session).history(period="5y", interval="1d", auto_adjust=True),
        "tnx": _ten_year_yield,
    }
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {k: pool.submit(_safe, fn) for k, fn in jobs.items()}
        return {k: f.result() for k, f in futures.items()}


def _build_tear_sheet(sym: str, raw: dict) -> dict:
    info = raw.get("info") or {}
    stock = _naive_close(raw.get("hist"))                       # split-adjusted, for P/E
    stock_total = _naive_close(raw.get("hist"), "Adj Close")    # dividend-adjusted, for returns
    spy = _naive_close(raw.get("spy"))
    price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    if price is None and stock is not None:
        price = float(stock.iloc[-1])
    if price is None:
        return {"symbol": sym, "error": "No price data available for this symbol."}

    history = _build_history(raw.get("income"), raw.get("cashflow"), raw.get("balance"), raw.get("edgar"))
    is_bank = "bank" in (info.get("industry") or "").lower()
    if is_bank:
        _blank_cash_flow_metrics(history)
    # A foreign ADR can report in one currency and trade in another (TSM: TWD statements,
    # USD shares). Per-share models would then compare unlike currencies, so they are skipped.
    fin_cur, trade_cur = info.get("financialCurrency"), info.get("currency")
    mismatch = bool(fin_cur and trade_cur and str(fin_cur).upper() != str(trade_cur).upper())
    # 10 years of prices let historical P/E span the whole track record; the
    # performance section (returns, charts, drawdown, MAs) stays on the last 5.
    stock5, spy5 = _last_years(stock_total, 5), _last_years(spy, 5)
    perf = _price_performance(stock5, spy5)
    hist_pes = [] if mismatch else _historical_pes(stock, history)
    earn_rows = _estimate_rows(raw.get("earn_est"))
    rev_rows = _estimate_rows(raw.get("rev_est"), is_revenue=True)
    by_period = {r["period"]: r for r in earn_rows}
    cur_fy, next_fy = by_period.get("0y"), by_period.get("+1y")

    eps_ttm = _safe_float(info.get("trailingEps"))
    eps_cur = cur_fy["avg"] if cur_fy else None
    eps_fwd = _safe_float(info.get("forwardEps")) or (next_fy["avg"] if next_fy else None)
    # Average the current- and next-FY consensus growth: either one alone swings on a
    # single lumpy year (e.g. +18% then +9%) and would bias the PEG and DCF models.
    growth = _avg([(cur_fy or {}).get("growth"), (next_fy or {}).get("growth")])
    if growth is None:
        growth = _safe_float(info.get("earningsGrowth")) or _safe_float(info.get("revenueGrowth"))

    shares = _safe_float(info.get("sharesOutstanding"))
    cash = _safe_float(info.get("totalCash"))
    debt = _safe_float(info.get("totalDebt"))
    fcf = _safe_float(info.get("freeCashflow"))
    if fcf is None and history:
        fcf = history[-1].get("freeCashFlow")
    fcf = _pick_fcf(fcf, history[-1].get("freeCashFlow") if history else None)
    if is_bank:
        fcf = None  # a bank's operating cash flow is dominated by trading and lending flows
    if mismatch:
        eps_ttm = eps_cur = eps_fwd = fcf = None
    beta = _safe_float(info.get("beta"))
    div_yield = _dividend_yield_fraction(info)
    market_cap = _safe_float(info.get("marketCap"))
    ev = _safe_float(info.get("enterpriseValue"))
    ebitda = _safe_float(info.get("ebitda"))

    analysts = _analyst_section(info, raw.get("targets"), raw.get("recs"), raw.get("updown"), price)
    fair_values = _fair_values(price, eps_ttm, eps_fwd, growth, hist_pes, fcf, shares, beta, cash, debt,
                               analysts["targetMean"])
    verdict = _verdict(price, fair_values)
    scenarios = _scenarios_12m(price, eps_cur or eps_ttm, None if mismatch else next_fy, div_yield)

    pe_now = _safe_float(info.get("trailingPE")) or (price / eps_ttm if eps_ttm and eps_ttm > 0 else None)
    pes = [h["pe"] for h in hist_pes]
    pe_hist_median = statistics.median(pes) if len(pes) >= 2 else None
    five_year = _five_year_returns(price, eps_ttm, growth, pe_now, pe_hist_median, div_yield)

    earnings_yield_fwd = (eps_fwd / price) if eps_fwd and price else None
    fcf_yield = (fcf / market_cap) if fcf is not None and market_cap else None
    ten_y = raw.get("tnx")

    w52_hi, w52_lo = _safe_float(info.get("fiftyTwoWeekHigh")), _safe_float(info.get("fiftyTwoWeekLow"))
    range_pos = (price - w52_lo) / (w52_hi - w52_lo) if w52_hi and w52_lo and w52_hi > w52_lo else None

    interest = _stmt_value(raw.get("income"), "Interest Expense",
                           sorted(raw["income"].columns)[-1]) if _df_ok(raw.get("income")) else None
    ebit = _stmt_value(raw.get("income"), "EBIT", sorted(raw["income"].columns)[-1]) if _df_ok(raw.get("income")) else None
    interest_cov = ebit / abs(interest) if ebit is not None and interest else None
    net_debt_ebitda = ((debt or 0) - (cash or 0)) / ebitda if ebitda and ebitda > 0 and debt is not None else None

    track = _earnings_track(raw.get("earn_hist"))
    rel_1y = next((r["relative"] for r in perf["returns"] if r["period"] == "1Y"), None)

    revs = [h["revenue"] for h in history]
    span = len(history) - 1
    cagr_rev = _cagr(revs[0], revs[-1], span) if span >= 1 else None
    cagr_eps = _cagr(history[0]["eps"], history[-1]["eps"], span) if span >= 1 else None

    metrics = {
        "revenueGrowth": _safe_float(info.get("revenueGrowth")), "epsGrowthFwd": growth,
        "netMargin": _safe_float(info.get("profitMargins")), "operatingMargin": _safe_float(info.get("operatingMargins")),
        "roe": _safe_float(info.get("returnOnEquity")), "netDebtToEbitda": net_debt_ebitda,
        "currentRatio": _safe_float(info.get("currentRatio")), "interestCoverage": interest_cov,
        "premium": verdict["premium"], "recommendationMean": analysts["recommendationMean"],
        "upside": analysts["upsideToMean"], "relative1y": rel_1y,
        "above200": (price > perf["ma200"]) if perf["ma200"] else None, "rangePosition": range_pos,
        "fcfPositive": (fcf > 0) if fcf is not None else None,
        "peVsHistory": (pe_now / pe_hist_median - 1) if pe_now and pe_hist_median else None,
        "beat_rate": (track["beats"] / track["total"]) if track["total"] >= 4 else None,
        "shortPercentOfFloat": _safe_float(info.get("shortPercentOfFloat")), "beta": beta,
        "maxDrawdown5y": perf["maxDrawdown5y"],
    }

    cal = raw.get("calendar") if isinstance(raw.get("calendar"), dict) else {}
    earn_dates = cal.get("Earnings Date") or []
    return {
        "symbol": sym,
        "asOf": str(pd.Timestamp.now().date()),
        "currencyNote": {"financial": str(fin_cur).upper(), "trading": str(trade_cur).upper()} if mismatch else None,
        "bankNote": is_bank,
        "profile": {
            "name": info.get("longName") or info.get("shortName") or sym,
            "sector": info.get("sector"), "industry": info.get("industry"),
            "country": info.get("country"), "exchange": info.get("fullExchangeName") or info.get("exchange"),
            "website": info.get("website"), "employees": info.get("fullTimeEmployees"),
            "description": info.get("longBusinessSummary"), "quoteType": info.get("quoteType"),
        },
        "snapshot": {
            "price": price, "changePct": _safe_float(info.get("regularMarketChangePercent")),
            "marketCap": market_cap, "enterpriseValue": ev,
            "week52High": w52_hi, "week52Low": w52_lo, "rangePosition": range_pos,
            "beta": beta, "avgVolume": _safe_float(info.get("averageVolume")),
            "nextEarnings": str(earn_dates[0]) if earn_dates else None,
            "exDividendDate": str(cal["Ex-Dividend Date"]) if cal.get("Ex-Dividend Date") else None,
        },
        "performance": perf,
        "financials": {
            "history": history, "revenueCagr": cagr_rev, "epsCagr": cagr_eps,
            "ttm": {
                "revenue": _safe_float(info.get("totalRevenue")), "ebitda": ebitda,
                "freeCashFlow": fcf, "operatingCashFlow": _safe_float(info.get("operatingCashflow")),
                "grossMargin": _safe_float(info.get("grossMargins")), "operatingMargin": metrics["operatingMargin"],
                "netMargin": metrics["netMargin"], "revenueGrowth": metrics["revenueGrowth"],
                "earningsGrowth": _safe_float(info.get("earningsGrowth")),
            },
        },
        "balanceSheet": {
            "cash": cash, "debt": debt, "netDebt": (debt - cash) if debt is not None and cash is not None else None,
            "netDebtToEbitda": net_debt_ebitda, "debtToEquity": _safe_float(info.get("debtToEquity")),
            "currentRatio": metrics["currentRatio"], "interestCoverage": interest_cov,
            "roe": metrics["roe"], "roa": _safe_float(info.get("returnOnAssets")),
            "payoutRatio": _safe_float(info.get("payoutRatio")),
        },
        "valuation": {
            "multiples": {
                "trailingPE": pe_now, "forwardPE": _safe_float(info.get("forwardPE")),
                "peg": _safe_float(info.get("trailingPegRatio")) or _safe_float(info.get("pegRatio")),
                "priceToSales": _safe_float(info.get("priceToSalesTrailing12Months")),
                "priceToBook": _safe_float(info.get("priceToBook")),
                "evToEbitda": _safe_float(info.get("enterpriseToEbitda")),
                "evToRevenue": _safe_float(info.get("enterpriseToRevenue")),
                "fcfYield": fcf_yield, "dividendYield": div_yield,
                "earningsYieldForward": earnings_yield_fwd,
            },
            "historicalPE": hist_pes, "historicalPEMedian": _round(pe_hist_median, 1),
            "tenYearYield": ten_y,
            "earningsYieldVsBond": (earnings_yield_fwd - ten_y) if earnings_yield_fwd is not None and ten_y is not None else None,
            "fairValues": fair_values, "verdict": verdict,
            "scenarios12m": scenarios, "fiveYearReturns": five_year,
        },
        "estimates": {
            "eps": earn_rows, "revenue": rev_rows, "revisions": _revisions(raw.get("eps_trend")),
            "growthUsed": growth,
        },
        "earningsTrack": track,
        "analysts": analysts,
        "ownership": {
            "insidersPct": _safe_float(info.get("heldPercentInsiders")),
            "institutionsPct": _safe_float(info.get("heldPercentInstitutions")),
            "shortPercentOfFloat": metrics["shortPercentOfFloat"], "shortRatio": _safe_float(info.get("shortRatio")),
            "insiderActivity": _insider_section(raw.get("insider")),
        },
        "scorecard": _scorecard(metrics),
        "flags": _flags(metrics),
        "methodologyNote": _METHODOLOGY_NOTE,
    }


def _compute_tear_sheet(sym: str) -> dict:
    try:
        return _build_tear_sheet(sym, _fetch_raw(sym))
    except Exception as e:
        logger.warning("tear sheet failed for %s: %s", sym, e)
        return {"symbol": sym, "error": str(e)}


@router.get("/api/tear-sheet/{symbol}")
async def get_tear_sheet(symbol: str):
    sym = symbol.upper().strip()
    cache_key = f"tearsheet:{sym}"
    cached = cache_get(cache_key, _TEAR_SHEET_TTL)
    if cached is not None:
        return cached
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: _compute_tear_sheet(sym))
    if not result.get("error"):
        cache_set(cache_key, result)
    return result
