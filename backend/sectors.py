"""Sector strategy maths — scoreboard, rotation map, horizon screener, cycle fit and backtest.

Pure functions over daily adjusted-close Series (total return for ETFs); the downloads live in
market_history.py and the HTTP surface in routers/sectors.py.

Universe: the 11 SPDR sector ETFs against SPY. XLRE starts in late 2015 and XLC in mid-2018, so any
window longer than a sector's life shows "n/a" for it rather than a misleading shorter figure.

Screener design (rule-based and explainable; nothing is fitted):
  Every factor is turned into a 0-100 score by ranking the sectors against each other, and the score is
  a weighted average. Each horizon preset picks the factors and weights that tend to matter at that horizon:
    tactical (1-3 months)      momentum 1-6M, trend, rotation momentum, seasonality
    intermediate (3-12 months) momentum 3-12M, trend, rotation, risk, cycle fit
    strategic (1-5 years)      long-run return, risk-adjusted return, drawdown, cycle fit
  Valuation is deliberately absent: point-in-time sector valuation history isn't freely available, and a
  screen built on today's multiples against revised history would be misleading.

Backtest design: month-end rebalance into the top-N sectors by the same momentum/trend/risk score, using only
data available at that month-end; costs charged on turnover; returns credited for the *following* month.
"""
import math
from datetime import datetime

import numpy as np
import pandas as pd

SECTORS = [
    {"symbol": "XLK", "name": "Technology"}, {"symbol": "XLF", "name": "Financials"}, {"symbol": "XLV", "name": "Health Care"},
    {"symbol": "XLY", "name": "Consumer Discretionary"}, {"symbol": "XLP", "name": "Consumer Staples"}, {"symbol": "XLE", "name": "Energy"},
    {"symbol": "XLI", "name": "Industrials"}, {"symbol": "XLB", "name": "Materials"}, {"symbol": "XLU", "name": "Utilities"},
    {"symbol": "XLRE", "name": "Real Estate"}, {"symbol": "XLC", "name": "Communication Services"},
]
NAMES = {s["symbol"]: s["name"] for s in SECTORS}
SYMBOLS = [s["symbol"] for s in SECTORS]
BENCH = "SPY"
EQUAL_WEIGHT = "RSP"
DEFENSIVE = ["XLP", "XLU", "XLV"]

PERIODS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y", "LTD"]
_OFFSETS = {"1W": pd.DateOffset(weeks=1), "1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3), "6M": pd.DateOffset(months=6),
            "1Y": pd.DateOffset(years=1), "3Y": pd.DateOffset(years=3), "5Y": pd.DateOffset(years=5), "10Y": pd.DateOffset(years=10)}
_ANNUAL_YEARS = {"3Y": 3, "5Y": 5, "10Y": 10}
_TOL_DAYS = 6


# ── prices and returns ────────────────────────────────────────────────────────

def price_on_or_before(s: pd.Series, target: pd.Timestamp, tol_days: int = _TOL_DAYS) -> float | None:
    pos = s.index.searchsorted(target, side="right") - 1
    if pos < 0:
        return None
    if (target - s.index[pos]).days > tol_days:
        return None
    return float(s.iloc[pos])


def period_return(s: pd.Series, period: str) -> float | None:
    """Total return over the period ending at the last observation, or None if the history is too short."""
    if s is None or len(s) < 2:
        return None
    last_date, last = s.index[-1], float(s.iloc[-1])
    if period == "1D":
        return last / float(s.iloc[-2]) - 1.0
    if period == "LTD":
        return last / float(s.iloc[0]) - 1.0
    if period == "YTD":
        base = price_on_or_before(s, pd.Timestamp(year=last_date.year - 1, month=12, day=31), tol_days=10)
        return None if base is None else last / base - 1.0
    target = last_date - _OFFSETS[period]
    if s.index[0] > target + pd.Timedelta(days=_TOL_DAYS):
        return None
    base = price_on_or_before(s, target)
    return None if base is None else last / base - 1.0


def annualise(total: float | None, years: float) -> float | None:
    if total is None or years <= 0 or total <= -1:
        return None
    return (1.0 + total) ** (1.0 / years) - 1.0


def returns_row(s: pd.Series) -> dict:
    """{period: {total, annualised}} for every period."""
    out = {}
    for p in PERIODS:
        total = period_return(s, p)
        if p == "LTD":
            yrs = (s.index[-1] - s.index[0]).days / 365.25
            ann = annualise(total, yrs) if yrs >= 1 else None
        else:
            ann = annualise(total, _ANNUAL_YEARS[p]) if p in _ANNUAL_YEARS else None
        out[p] = {"total": None if total is None else round(total, 5), "annualised": None if ann is None else round(ann, 5)}
    return out


def monthly_returns(s: pd.Series) -> pd.Series:
    return s.resample("ME").last().dropna().pct_change().dropna()


def max_drawdown(s: pd.Series) -> float | None:
    if s is None or len(s) < 5:
        return None
    return float((s / s.cummax() - 1.0).min())


def window(s: pd.Series, years: int) -> pd.Series:
    return s[s.index >= s.index[-1] - pd.DateOffset(years=years)]


def risk_metrics(s: pd.Series, bench: pd.Series, years: int = 3) -> dict:
    """Volatility, drawdown, return/risk, beta and up/down capture over the trailing `years` (monthly, except drawdown)."""
    w = window(s, years)
    covered = (w.index[0] - (s.index[-1] - pd.DateOffset(years=years))).days <= 31 + _TOL_DAYS
    out = {"windowYears": years, "volatility": None, "maxDrawdown": None, "returnPerRisk": None, "beta": None, "upCapture": None,
           "downCapture": None, "short": not covered}
    if len(w) < 40:
        return out
    dd = max_drawdown(w)
    m = monthly_returns(w)
    mb = monthly_returns(window(bench, years))
    j = pd.concat([m, mb], axis=1, join="inner").dropna()
    j.columns = ["a", "b"]
    out["maxDrawdown"] = None if dd is None else round(dd, 4)
    if len(j) >= 12:
        vol = float(j["a"].std() * math.sqrt(12))
        out["volatility"] = round(vol, 4)
        yrs = (w.index[-1] - w.index[0]).days / 365.25
        cagr = annualise(float(w.iloc[-1] / w.iloc[0] - 1.0), yrs)
        out["returnPerRisk"] = None if (cagr is None or vol <= 0) else round(cagr / vol, 2)
        var_b = float(j["b"].var())
        out["beta"] = round(float(j["a"].cov(j["b"]) / var_b), 2) if var_b > 0 else None
        up, down = j[j["b"] > 0], j[j["b"] < 0]
        if len(up) >= 3:
            out["upCapture"] = round(float(up["a"].mean() / up["b"].mean()), 2)
        if len(down) >= 3:
            out["downCapture"] = round(float(down["a"].mean() / down["b"].mean()), 2)
    return out


def calendar_years(s: pd.Series, count: int = 10) -> dict[str, float | None]:
    """{year: return} for the last `count` calendar years (the current year is year-to-date)."""
    last_year = s.index[-1].year
    out = {}
    for y in range(last_year - count + 1, last_year + 1):
        end = s[s.index <= pd.Timestamp(year=y, month=12, day=31)]
        start = s[s.index <= pd.Timestamp(year=y - 1, month=12, day=31)]
        if len(start) == 0 or len(end) == 0 or end.index[-1].year != y:
            out[str(y)] = None
            continue
        out[str(y)] = round(float(end.iloc[-1] / start.iloc[-1] - 1.0), 5)
    return out


# ── scoreboard ────────────────────────────────────────────────────────────────

def rs_series(s: pd.Series, bench: pd.Series) -> pd.Series:
    """Relative-strength line: the sector's price divided by the benchmark's, on shared dates."""
    j = pd.concat([s, bench], axis=1, join="inner").dropna()
    return j.iloc[:, 0] / j.iloc[:, 1] if len(j) else pd.Series(dtype=float)


def trend_flags(s: pd.Series) -> dict:
    """Position against the 50- and 200-day averages."""
    if len(s) < 200:
        return {"above50": None, "above200": None, "ma50Above200": None, "pctFrom200": None}
    ma50, ma200 = float(s.iloc[-50:].mean()), float(s.iloc[-200:].mean())
    last = float(s.iloc[-1])
    return {"above50": last > ma50, "above200": last > ma200, "ma50Above200": ma50 > ma200, "pctFrom200": round(last / ma200 - 1.0, 4)}


def build_scoreboard(prices: dict[str, pd.Series]) -> dict | None:
    bench = prices.get(BENCH)
    if bench is None or len(bench) < 250:
        return None
    rows = []
    for sec in SECTORS:
        s = prices.get(sec["symbol"])
        if s is None or len(s) < 30:
            continue
        rets = returns_row(s)
        excess = {}
        for p in PERIODS:
            a, b = rets[p]["total"], period_return(bench, p)
            excess[p] = None if a is None or b is None else round(a - b, 5)
        rs = rs_series(s, bench)
        rs_chg = {}
        for p in ("1M", "3M", "6M", "1Y"):
            if len(rs) > 2:
                v = period_return(rs, p)
                rs_chg[p] = None if v is None else round(v, 4)
        rows.append({"symbol": sec["symbol"], "name": sec["name"], "inception": s.index[0].strftime("%Y-%m-%d"),
                     "price": round(float(s.iloc[-1]), 2), "returns": rets, "excess": excess, "risk": risk_metrics(s, bench),
                     "trend": trend_flags(s), "rsChange": rs_chg, "calendar": calendar_years(s)})
    if not rows:
        return None
    bench_row = {"symbol": BENCH, "name": "S&P 500 (SPY)", "inception": bench.index[0].strftime("%Y-%m-%d"), "price": round(float(bench.iloc[-1]), 2),
                 "returns": returns_row(bench), "risk": risk_metrics(bench, bench), "trend": trend_flags(bench), "calendar": calendar_years(bench)}
    ew = prices.get(EQUAL_WEIGHT)
    ew_row = None if ew is None else {"symbol": EQUAL_WEIGHT, "name": "S&P 500 Equal Weight (RSP)", "inception": ew.index[0].strftime("%Y-%m-%d"),
                                      "price": round(float(ew.iloc[-1]), 2), "returns": returns_row(ew), "calendar": calendar_years(ew)}
    return {"asOf": bench.index[-1].strftime("%Y-%m-%d"), "periods": PERIODS, "sectors": rows, "benchmark": bench_row, "equalWeight": ew_row,
            "notes": ["Returns are total returns (dividends reinvested). Periods of 3 years or more also show annualised figures.",
                      "Risk figures use the trailing 3 years of monthly data (max drawdown uses daily); a sector with a shorter life is flagged.",
                      "XLRE (Real Estate) launched in late 2015 and XLC (Communication Services) in mid-2018; longer periods show n/a."]}


# ── rotation map (relative-rotation graph) ────────────────────────────────────

RRG_QUADRANTS = {
    (True, True): ("leading", "Leading", "Outperforming and still gaining strength"),
    (True, False): ("weakening", "Weakening", "Outperforming, but momentum is fading"),
    (False, False): ("lagging", "Lagging", "Underperforming and still losing ground"),
    (False, True): ("improving", "Improving", "Underperforming, but momentum is turning up"),
}


def rrg_points(s: pd.Series, bench: pd.Series, trail: int = 8, long: int = 40, smooth: int = 5, mom: int = 5) -> list[dict] | None:
    """Weekly RS-Ratio (relative strength vs its own ~40-week average) and RS-Momentum (its rate of change), oldest to newest.
    A transparent approximation of the usual relative-rotation graph: 100 = in line with the benchmark's trend."""
    ratio = rs_series(s.resample("W-FRI").last().dropna(), bench.resample("W-FRI").last().dropna())
    if len(ratio) < long + smooth + mom + trail:
        return None
    rs_ratio = (100.0 * ratio / ratio.rolling(long).mean()).rolling(smooth).mean()
    rs_mom = 100.0 + (rs_ratio / rs_ratio.shift(mom) - 1.0) * 100.0
    df = pd.concat([rs_ratio, rs_mom], axis=1).dropna().iloc[-trail:]
    if len(df) < trail:
        return None
    return [{"date": d.strftime("%Y-%m-%d"), "ratio": round(float(r), 2), "momentum": round(float(m), 2)} for d, (r, m) in df.iterrows()]


def build_rotation(prices: dict[str, pd.Series], trail: int = 8) -> dict | None:
    bench = prices.get(BENCH)
    if bench is None:
        return None
    out = []
    for sec in SECTORS:
        s = prices.get(sec["symbol"])
        if s is None:
            continue
        pts = rrg_points(s, bench, trail=trail)
        if not pts:
            continue
        cur = pts[-1]
        qid, qname, qtext = RRG_QUADRANTS[(cur["ratio"] >= 100, cur["momentum"] >= 100)]
        out.append({"symbol": sec["symbol"], "name": sec["name"], "trail": pts, "ratio": cur["ratio"], "momentum": cur["momentum"],
                    "quadrant": qid, "quadrantName": qname, "quadrantText": qtext})
    if not out:
        return None
    return {"asOf": bench.index[-1].strftime("%Y-%m-%d"), "sectors": out,
            "note": "Weekly. RS-Ratio compares a sector's strength against SPY with its own 40-week trend; RS-Momentum is how fast that ratio is changing. "
                    "Sectors tend to rotate clockwise: Improving, Leading, Weakening, Lagging."}


# ── screener ──────────────────────────────────────────────────────────────────

FACTORS = {
    "momentum": "Price momentum", "trend": "Trend", "rotation": "Rotation (relative strength)", "risk": "Risk-adjusted return",
    "drawdown": "Resilience (drawdown)", "seasonality": "Seasonality", "cycle": "Cycle fit",
}

HORIZONS = {
    "tactical": {"name": "Tactical", "span": "1-3 months", "blurb": "Short-term leadership: what is trending now.",
                 "weights": {"momentum": 40, "trend": 25, "rotation": 25, "seasonality": 10}, "momentum_periods": {"1M": 1, "3M": 2, "6M": 1}},
    "intermediate": {"name": "Intermediate", "span": "3-12 months", "blurb": "Trend persistence plus where we are in the cycle.",
                     "weights": {"momentum": 30, "trend": 15, "rotation": 15, "risk": 15, "cycle": 25}, "momentum_periods": {"3M": 1, "6M": 2, "1Y": 2}},
    "strategic": {"name": "Strategic", "span": "1-5+ years", "blurb": "Durable, risk-adjusted leadership across full cycles.",
                  "weights": {"momentum": 25, "risk": 35, "drawdown": 20, "cycle": 20}, "momentum_periods": {"1Y": 1, "3Y": 2, "5Y": 2}},
}


def pct_rank(values: dict[str, float | None]) -> dict[str, float | None]:
    """0-100 rank of each value against the others (100 = best); None stays None."""
    items = {k: v for k, v in values.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}
    if len(items) < 2:
        return {k: (50.0 if k in items else None) for k in values}
    ordered = sorted(items.values())
    n = len(ordered)
    out = {}
    for k, v in values.items():
        if k not in items:
            out[k] = None
            continue
        lo, hi = ordered.index(v), n - 1 - ordered[::-1].index(v)
        out[k] = round(((lo + hi) / 2.0) / (n - 1) * 100.0, 1)
    return out


def seasonal_excess(s: pd.Series, bench: pd.Series, month: int, span: int = 3) -> float | None:
    """Average excess return vs SPY over the `span` months starting at calendar `month` (history for this sector)."""
    ms, mb = s.resample("MS").last().dropna(), bench.resample("MS").last().dropna()
    j = pd.concat([ms, mb], axis=1, join="inner").dropna()
    if len(j) < 60:
        return None
    r = j.pct_change(span).shift(-span).dropna()
    r = r.iloc[:, 0] - r.iloc[:, 1]
    sel = r[r.index.month == month]
    return float(sel.mean()) if len(sel) >= 4 else None


def factor_raw(prices: dict[str, pd.Series], horizon: str, as_of_month: int, cycle_fit: dict[str, float] | None = None) -> dict[str, dict[str, float | None]]:
    """Raw (unranked) factor values per sector."""
    bench = prices[BENCH]
    cfg = HORIZONS[horizon]
    raw = {f: {} for f in FACTORS}
    for sym in SYMBOLS:
        s = prices.get(sym)
        if s is None or len(s) < 60:
            for f in FACTORS:
                raw[f][sym] = None
            continue
        mom_parts, wsum = [], 0
        for p, w in cfg["momentum_periods"].items():
            a, b = period_return(s, p), period_return(bench, p)
            if a is not None and b is not None:
                yrs = _ANNUAL_YEARS.get(p)
                mom_parts.append(w * ((annualise(a, yrs) - annualise(b, yrs)) if yrs else (a - b)))
                wsum += w
        raw["momentum"][sym] = sum(mom_parts) / wsum if wsum else None
        t = trend_flags(s)
        raw["trend"][sym] = None if t["above200"] is None else (1.0 * t["above200"] + 0.6 * t["above50"] + 0.4 * t["ma50Above200"]) + (t["pctFrom200"] or 0.0)
        pts = rrg_points(s, bench, trail=1)
        raw["rotation"][sym] = None if not pts else (pts[-1]["ratio"] - 100.0) + (pts[-1]["momentum"] - 100.0)
        rm = risk_metrics(s, bench, 3 if horizon != "tactical" else 1)
        raw["risk"][sym] = rm["returnPerRisk"]
        raw["drawdown"][sym] = rm["maxDrawdown"]
        raw["seasonality"][sym] = seasonal_excess(s, bench, as_of_month)
        raw["cycle"][sym] = None if not cycle_fit else cycle_fit.get(sym)
    return raw


def tier(score: float) -> str:
    return "Overweight" if score >= 62 else "Underweight" if score <= 38 else "Neutral"


def _fmt_raw(factor: str, v: float | None) -> str:
    if v is None:
        return "n/a"
    return {"momentum": f"{v:+.1%} vs SPY", "trend": f"{v:+.2f}", "rotation": f"{v:+.1f}", "risk": f"{v:.2f}",
            "drawdown": f"{v:.0%}", "seasonality": f"{v:+.1%} avg 3-mo vs SPY", "cycle": f"{v:+.2%}/mo vs SPY"}[factor]


def build_screener(prices: dict[str, pd.Series], horizon: str = "intermediate", weights: dict[str, float] | None = None,
                   cycle_fit: dict[str, float] | None = None, cycle_phase_name: str | None = None, today: datetime | None = None) -> dict | None:
    if horizon not in HORIZONS or BENCH not in prices:
        return None
    cfg = HORIZONS[horizon]
    month = (today or datetime.now()).month
    raw = factor_raw(prices, horizon, month, cycle_fit)
    ranks = {f: pct_rank(raw[f]) for f in FACTORS}
    # drawdown is negative; a smaller drawdown (closer to 0) is better, which the ascending rank already gives
    w = {f: float(x) for f, x in (weights or cfg["weights"]).items() if f in FACTORS and float(x) > 0}
    w = {f: x for f, x in w.items() if f != "cycle" or cycle_fit}
    if not w:
        return None
    rows = []
    for sym in SYMBOLS:
        if sym not in prices or len(prices[sym]) < 60:
            continue
        have = {f: ranks[f][sym] for f in w if ranks[f][sym] is not None}
        if not have:
            continue
        tot = sum(w[f] for f in have)
        contrib = {f: round(ranks[f][sym] * w[f] / tot, 1) for f in have}
        score = round(sum(contrib.values()), 1)
        ordered = sorted(have, key=lambda f: ranks[f][sym])
        best, worst = ordered[-1], ordered[0]
        if ranks[best][sym] >= 60:
            why = f"Strongest on {FACTORS[best].lower()} ({_fmt_raw(best, raw[best][sym])})"
        else:
            why = f"Nothing stands out; best factor is {FACTORS[best].lower()} ({_fmt_raw(best, raw[best][sym])})"
        if ranks[worst][sym] < 40 and worst != best:
            why += f"; weakest on {FACTORS[worst].lower()} ({_fmt_raw(worst, raw[worst][sym])})"
        rows.append({"symbol": sym, "name": NAMES[sym], "score": score, "tier": tier(score),
                     "factors": {f: {"rank": ranks[f][sym], "raw": raw[f][sym] if raw[f][sym] is None else round(float(raw[f][sym]), 4),
                                     "weight": round(w[f] / tot * 100, 1), "contribution": contrib[f]} for f in have},
                     "missing": [f for f in w if f not in have], "why": why})
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {"asOf": prices[BENCH].index[-1].strftime("%Y-%m-%d"), "horizon": horizon,
            "horizonInfo": {"name": cfg["name"], "span": cfg["span"], "blurb": cfg["blurb"]},
            "weights": {f: x for f, x in w.items()}, "defaultWeights": cfg["weights"], "factorNames": FACTORS,
            "cyclePhase": cycle_phase_name, "sectors": rows,
            "notes": ["Scores rank the sectors against each other (0-100, 100 best); they describe relative attractiveness, not expected returns.",
                      "Valuation is not included: point-in-time sector valuation history isn't freely available.",
                      "Past relative performance does not guarantee future results. Not investment advice."]}


# ── cycle fit ─────────────────────────────────────────────────────────────────

def cycle_fit(prices: dict[str, pd.Series], regime_months: pd.DataFrame, group: str = "phase") -> dict | None:
    """Average monthly excess return vs SPY for each sector in each cycle phase (or growth/inflation quadrant),
    with the number of months and distinct episodes behind each cell."""
    bench = prices.get(BENCH)
    if bench is None or regime_months is None or regime_months.empty or group not in regime_months:
        return None
    mb = bench.resample("MS").last().dropna().pct_change()
    labels = regime_months[group]
    cells, any_ok = {}, False
    for sym in SYMBOLS:
        s = prices.get(sym)
        if s is None:
            continue
        ex = (s.resample("MS").last().dropna().pct_change() - mb).dropna()
        # a month's regime is known at its start; the return credited is that month's
        j = pd.concat([ex.rename("ex"), labels.rename("g")], axis=1, join="inner").dropna()
        if j.empty:
            continue
        row = {}
        for g, sub in j.groupby("g"):
            runs = int(((sub.index.to_series().diff().dt.days.fillna(999) > 40)).sum())
            row[g] = {"avgMonthlyExcess": round(float(sub["ex"].mean()), 5), "months": int(len(sub)), "episodes": runs,
                      "hitRate": round(float((sub["ex"] > 0).mean()), 3)}
            any_ok = True
        cells[sym] = row
    if not any_ok:
        return None
    groups = sorted({g for r in cells.values() for g in r})
    return {"group": group, "groups": groups, "sectors": [{"symbol": s, "name": NAMES[s], "cells": cells[s]} for s in SYMBOLS if s in cells],
            "samples": {g: int((labels == g).sum()) for g in groups},
            "note": "Sector history starts in 1999 (Real Estate 2015, Communication Services 2018), so each cell rests on few distinct episodes. "
                    "Regime labels use revised data and are cleaner than they looked in real time."}


def cycle_fit_for_phase(fit: dict | None, phase: str) -> dict[str, float] | None:
    """{symbol: avg monthly excess} for one phase, only for cells with at least 6 months of evidence."""
    if not fit:
        return None
    out = {s["symbol"]: s["cells"][phase]["avgMonthlyExcess"] for s in fit["sectors"] if phase in s["cells"] and s["cells"][phase]["months"] >= 6}
    return out or None


# ── backtest ──────────────────────────────────────────────────────────────────

def _month_end_scores(prices: dict[str, pd.Series], date: pd.Timestamp) -> dict[str, float]:
    """Momentum / trend / risk score at `date` using only data up to `date`."""
    cut = {k: v[v.index <= date] for k, v in prices.items()}
    out = {}
    cand = {}
    for sym in SYMBOLS:
        s = cut.get(sym)
        if s is None or len(s) < 260 or s.index[0] > date - pd.DateOffset(years=1, days=10):
            continue
        r = {p: period_return(s, p) for p in ("3M", "6M", "1Y")}
        if any(v is None for v in r.values()):
            continue
        cand[sym] = (0.3 * r["3M"] + 0.4 * r["6M"] + 0.3 * r["1Y"],
                     1.0 * (s.iloc[-1] > s.iloc[-200:].mean()) + 0.5 * (s.iloc[-50:].mean() > s.iloc[-200:].mean()),
                     -float(s.iloc[-63:].pct_change().std()))
    if len(cand) < 4:
        return out
    ranks = [pct_rank({k: v[i] for k, v in cand.items()}) for i in range(3)]
    for sym in cand:
        out[sym] = 0.6 * ranks[0][sym] + 0.25 * ranks[1][sym] + 0.15 * ranks[2][sym]
    return out


def completed_month_ends(s: pd.Series) -> list[pd.Timestamp]:
    """The last trading day of each month in the series, leaving out a final month that isn't over yet."""
    last_days = s.groupby(s.index.to_period("M")).tail(1).index
    out = list(last_days)
    if out and out[-1] < out[-1] + pd.offsets.MonthEnd(0) - pd.Timedelta(days=4):
        out = out[:-1]
    return out


def run_backtest(prices: dict[str, pd.Series], top_n: int = 3, cost_bps: float = 10.0, defensive_switch: bool = True,
                 start: str = "2000-01-01") -> dict | None:
    bench = prices.get(BENCH)
    if bench is None:
        return None
    month_ends = completed_month_ends(bench)
    month_ends = [d for d in month_ends if d >= pd.Timestamp(start)]
    daily_idx = {k: v for k, v in prices.items()}

    def px_at(sym, d):
        s = daily_idx.get(sym)
        return None if s is None else price_on_or_before(s, d, tol_days=7)

    equity, bench_eq, ew_eq, curve = 1.0, 1.0, 1.0, []
    holdings: dict[str, float] = {}
    turnover_total, months_run, switches = 0.0, 0, 0
    port_rets, bench_rets = [], []
    for i in range(len(month_ends) - 1):
        d0, d1 = month_ends[i], month_ends[i + 1]
        scores = _month_end_scores(prices, d0)
        if not scores:
            continue
        picks = sorted(scores, key=lambda k: -scores[k])[:top_n]
        risk_off = False
        if defensive_switch and len(bench[bench.index <= d0]) >= 210:
            b = bench[bench.index <= d0]
            risk_off = float(b.iloc[-1]) < float(b.iloc[-210:].mean())
        if risk_off:
            picks = [d for d in DEFENSIVE if d in prices and px_at(d, d0) is not None][:top_n]
            switches += 1
        new = {p: 1.0 / len(picks) for p in picks}
        turn = sum(abs(new.get(k, 0.0) - holdings.get(k, 0.0)) for k in set(new) | set(holdings)) / 2.0
        cost = turn * 2.0 * cost_bps / 10000.0
        r = 0.0
        for sym, wgt in new.items():
            a, b_ = px_at(sym, d0), px_at(sym, d1)
            if a and b_:
                r += wgt * (b_ / a - 1.0)
        r -= cost
        rb = (px_at(BENCH, d1) or 0) / (px_at(BENCH, d0) or 1) - 1.0
        legs = [(px_at(s, d1) or 0) / px_at(s, d0) - 1.0 for s in SYMBOLS if px_at(s, d0) and px_at(s, d1)]
        rew = float(np.mean(legs)) if legs else rb
        equity *= 1 + r
        bench_eq *= 1 + rb
        ew_eq *= 1 + rew
        holdings = new
        turnover_total += turn
        months_run += 1
        port_rets.append(r)
        bench_rets.append(rb)
        curve.append({"date": d1.strftime("%Y-%m-%d"), "strategy": round(equity, 4), "spy": round(bench_eq, 4), "equalWeight": round(ew_eq, 4),
                      "holdings": picks})
    if months_run < 24:
        return None

    def stats(rets, eq):
        arr = np.array(rets)
        yrs = len(arr) / 12.0
        cagr = eq ** (1 / yrs) - 1
        vol = float(arr.std() * math.sqrt(12))
        curve_v = np.cumprod(1 + arr)
        dd = float((curve_v / np.maximum.accumulate(curve_v) - 1).min())
        return {"cagr": round(float(cagr), 4), "volatility": round(vol, 4), "sharpe": round(cagr / vol, 2) if vol > 0 else None,
                "maxDrawdown": round(dd, 4), "totalReturn": round(float(eq - 1), 4), "bestMonth": round(float(arr.max()), 4), "worstMonth": round(float(arr.min()), 4),
                "positiveMonths": round(float((arr > 0).mean()), 3)}
    ew_rets = []
    prev = 1.0
    for c in curve:
        ew_rets.append(c["equalWeight"] / prev - 1.0)
        prev = c["equalWeight"]
    outperf = [p - b for p, b in zip(port_rets, bench_rets)]
    return {"params": {"topN": top_n, "costBps": cost_bps, "defensiveSwitch": defensive_switch, "start": start},
            "start": curve[0]["date"], "end": curve[-1]["date"], "months": months_run,
            "strategy": stats(port_rets, equity), "spy": stats(bench_rets, bench_eq), "equalWeight": stats(ew_rets, ew_eq),
            "annualTurnover": round(turnover_total / (months_run / 12.0), 2), "riskOffMonths": switches,
            "monthsBeatingSpy": round(float(np.mean([o > 0 for o in outperf])), 3),
            "curve": curve[::1] if len(curve) <= 400 else curve[::2],
            "latestHoldings": curve[-1]["holdings"],
            "notes": ["Hypothetical, rule-based, month-end rebalancing using only data available at each month-end; returns are credited for the following month.",
                      f"Costs: {cost_bps:g} bps per side on turnover. Taxes, slippage and fund-level tracking differences are ignored.",
                      "Sector ETF history starts in 1999 and the whole sample contains only a few market cycles; backtests flatter rules that were chosen after seeing the data.",
                      "Not a forecast and not investment advice."]}
