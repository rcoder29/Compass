"""Thematic investing maths — basket performance, analyst-implied outlook, and a transparent candidate score.

Pure functions over (catalog entry, Yahoo metrics, price-performance row); data fetching lives in
hundred_bagger_data.py (fundamentals, shared with the 100-Bagger Finder) and holdings_perf.py (price returns),
and the HTTP surface in routers/themes.py.

What the pages say about the future, and where it comes from:
  - *Analyst-implied upside*: each analyst's 12-month price target against today's price (names with 3+ analysts).
    Targets are opinions, are wrong a lot, and are cut after prices fall; they show sentiment, not a forecast.
  - *Growth*: the same blended revenue growth the 100-Bagger Finder uses (multi-year rate and latest year, capped).
  - *Scenarios*: what a basket would be worth if it compounded at stated rates. Arithmetic, not a prediction; the basket's
    own record and drawdown are shown beside it so the rates can be judged.
  - *Editorial view*: catalysts, risks and drivers written by hand in themes_catalog.py, dated.

The candidate ("setup") score ranks names within a theme from six fixed-weight parts, then applies a risk haircut
(x0.85 for very-high-risk names, x0.93 for high) and caps the label at "Mixed" for very-high-risk names and for any
name down 40%+ over a year, so cheap-looking speculation cannot top the list. It compares names, it does not
say any of them will do well:
  exposure 20   how much of the business is the theme
  momentum 20   average excess return over SPY across 3 and 6 months
  analysts 20   upside to the mean price target (3+ analysts)
  growth 20     blended revenue growth
  strength 10   balance sheet and profitability: can it fund the wait?
  valuation 10  price against growth
"""
import math
import statistics

import pandas as pd

import hundred_bagger as hb

WEIGHTS = {"exposure": 20, "momentum": 20, "analysts": 20, "growth": 20, "strength": 10, "valuation": 10}
FACTOR_NAMES = {"exposure": "Theme exposure", "momentum": "Momentum vs SPY", "analysts": "Analyst upside", "growth": "Growth",
                "strength": "Financial strength", "valuation": "Valuation vs growth"}
SETUP_LABELS = [(68, "Stronger setup"), (52, "Mixed"), (0, "Weaker setup")]
RISK_MULTIPLIER = {"Very high": 0.85, "High": 0.93, "Moderate": 1.0, "Lower": 1.0}
DEEP_DRAWDOWN = -0.40       # down this much over a year caps the label at "Mixed": the market is saying something
MIN_ANALYSTS = 3
PERIODS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"]
SCENARIO_RATES = [(0.08, "Market-like"), (0.15, "Strong"), (0.25, "Exceptional")]
SCENARIO_YEARS = [1, 3, 5, 10]


def _num(x):
    return hb._num(x)


def recommendation_label(mean: float | None) -> str | None:
    """Yahoo's recommendationMean runs 1 (strong buy) to 5 (sell)."""
    if mean is None:
        return None
    return "Strong buy" if mean <= 1.5 else "Buy" if mean <= 2.5 else "Hold" if mean <= 3.5 else "Underperform"


def upside(metrics: dict | None) -> dict | None:
    """Analyst price-target upside from the current price, or None with fewer than MIN_ANALYSTS analysts."""
    if not metrics:
        return None
    price, mean = metrics.get("price"), metrics.get("targetMean")
    if not price or price <= 0 or not mean or metrics.get("analystCount", 0) < MIN_ANALYSTS:
        return None
    hi, lo = metrics.get("targetHigh"), metrics.get("targetLow")
    return {"mean": mean / price - 1.0, "high": None if not hi else hi / price - 1.0, "low": None if not lo else lo / price - 1.0,
            "count": metrics["analystCount"], "rating": recommendation_label(metrics.get("recommendation"))}


def size_label(cap: float | None) -> str:
    return "Unknown" if cap is None else "Large cap" if cap >= 50e9 else "Mid cap" if cap >= 10e9 else "Small cap" if cap >= 2e9 else "Micro cap"


def risk_level(m: dict | None) -> str:
    """Rough risk of permanent loss from size and profitability. Not a volatility measure."""
    if not m or m.get("marketCap") is None:
        return "Very high"
    cap = m["marketCap"]
    profitable = (m.get("operatingMargin") or 0) > 0
    burning = m.get("freeCashFlow") is not None and m["freeCashFlow"] < 0
    if cap < 2e9 or (not profitable and burning and cap < 10e9):
        return "Very high"
    if cap < 10e9 or not profitable:
        return "High"
    return "Moderate" if cap < 50e9 else "Lower"


def setup_label(score: float) -> str:
    return next(name for floor, name in SETUP_LABELS if score >= floor)


# ── candidate score ───────────────────────────────────────────────────────────

def score_candidate(entry: dict, m: dict | None, returns: dict | None, bench_returns: dict | None) -> dict:
    parts, notes = {}, {}
    parts["exposure"] = {1: 35.0, 2: 70.0, 3: 100.0}.get(entry["exposure"], 35.0)
    notes["exposure"] = {1: "A minor part of the business", 2: "A major part of the business", 3: "Most of the business"}.get(entry["exposure"], "")

    excess = []
    for p in ("3M", "6M"):
        a, b = (returns or {}).get(p), (bench_returns or {}).get(p)
        if a is not None and b is not None:
            excess.append(a - b)
    if excess:
        e = sum(excess) / len(excess)
        parts["momentum"] = hb.interp(e, [(-0.30, 0), (0.0, 45), (0.15, 75), (0.40, 100)])
        notes["momentum"] = f"{e:+.0%} versus SPY over 3-6 months"
    up = upside(m)
    if up:
        parts["analysts"] = hb.interp(up["mean"], [(-0.15, 0), (0.0, 35), (0.15, 65), (0.40, 100)])
        notes["analysts"] = f"Mean target {up['mean']:+.0%} from here ({up['count']} analysts)"
    if m:
        g, gnote = hb.score_growth(m)
        if g is not None:
            parts["growth"], notes["growth"] = g, gnote
        b, bnote = hb.score_balance(m)
        om = m.get("operatingMargin")
        if b is not None:
            prof = 100.0 if (om or 0) > 0.05 else 50.0 if (om or 0) > 0 else 10.0
            parts["strength"] = 0.6 * b + 0.4 * prof if om is not None else b
            notes["strength"] = bnote + ("; profitable" if (om or 0) > 0 else "; not yet profitable" if om is not None else "")
        v, vnote = hb.score_valuation(m)
        if v is not None:
            parts["valuation"], notes["valuation"] = v, vnote
    factors, total = {}, 0.0
    for name, w in WEIGHTS.items():
        missing = name not in parts
        s = hb.MISSING_SCORE if missing else float(parts[name])
        pts = s * w / 100.0
        total += pts
        factors[name] = {"score": round(s, 1), "weight": w, "points": round(pts, 1), "missing": missing, "note": "No data" if missing else notes.get(name, "")}
    risk = risk_level(m)
    mult = RISK_MULTIPLIER[risk]
    raw = round(total, 1)
    total = round(total * mult, 1)
    label = setup_label(total)
    cap_reason = None
    if label == "Stronger setup":
        if risk == "Very high":
            label, cap_reason = "Mixed", "Capped at Mixed: very high risk (small, unprofitable or cash-burning)"
        elif (returns or {}).get("1Y") is not None and returns["1Y"] <= DEEP_DRAWDOWN:
            label, cap_reason = "Mixed", f"Capped at Mixed: down {abs(returns['1Y']):.0%} over the past year"
    return {"score": total, "rawScore": raw, "riskMultiplier": mult, "risk": risk, "label": label, "capReason": cap_reason, "factors": factors}


# ── per-name view ─────────────────────────────────────────────────────────────

FUND_SETUP = {"score": None, "rawScore": None, "riskMultiplier": 1.0, "risk": "Fund", "label": "Fund", "capReason": None, "factors": {}}


def member_view(entry: dict, m: dict | None, perf: dict | None, bench_returns: dict | None) -> dict:
    is_fund = entry.get("kind", "stock") == "fund"
    if is_fund:
        m = None                                    # a fund has no company fundamentals; it gets live returns only
    returns = (perf or {}).get("returns") or {}
    ann = (perf or {}).get("annualised") or {}
    cand = dict(FUND_SETUP) if is_fund else score_candidate(entry, m, returns, bench_returns)
    if entry["role"] == "atrisk" and not is_fund:                       # a "setup" is meaningless for a business the theme could undercut
        cand = {**cand, "label": "Disruption risk", "capReason": None}
    hbs = hb.score(m) if m else None
    g = hb.blended_growth(m) if m else None
    return {
        "symbol": entry["symbol"], "name": entry["name"], "kind": "fund" if is_fund else "stock", "layer": entry["layer"], "role": entry["role"], "exposure": entry["exposure"], "why": entry["why"],
        "available": bool(perf or m),
        "price": (perf or {}).get("price") or (m or {}).get("price"),
        "marketCap": (m or {}).get("marketCap"), "size": "Fund" if is_fund else size_label((m or {}).get("marketCap")), "risk": "Fund" if is_fund else risk_level(m),
        "returns": {p: returns.get(p) for p in PERIODS}, "annualised": {p: ann.get(p) for p in ("3Y", "5Y")},
        "excess": {p: (returns[p] - bench_returns[p]) if returns.get(p) is not None and (bench_returns or {}).get(p) is not None else None for p in ("3M", "6M", "1Y")},
        "upside": upside(m), "growth": g, "revenueGrowth": (m or {}).get("revenueGrowth"), "forwardPE": (m or {}).get("forwardPE"),
        "operatingMargin": (m or {}).get("operatingMargin"), "profitable": None if not m or m.get("operatingMargin") is None else m["operatingMargin"] > 0,
        "off52wHigh": (m["price"] / m["week52High"] - 1.0) if m and m.get("price") and m.get("week52High") else None,
        "setup": cand, "bagger": None if not hbs else {"score": hbs["score"], "tier": hbs["tier"]},
        "flags": [f for f in (hb.flags(m) if m else []) if not f.startswith("Already")],
    }


# ── basket ────────────────────────────────────────────────────────────────────

def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def basket_returns(views: list[dict]) -> dict:
    """Average return of the members with data, per period, and how many contributed."""
    out = {}
    for p in PERIODS:
        vals = [v["returns"][p] for v in views if v["returns"].get(p) is not None]
        out[p] = {"mean": _mean(vals), "median": _median(vals), "n": len(vals), "positive": (sum(1 for x in vals if x > 0) / len(vals)) if vals else None}
    return out


def basket_series(daily: dict[str, pd.Series], symbols: list[str], bench: str = "SPY", weekly: bool = True) -> dict | None:
    """Equal-weight basket (rebalanced daily) and the benchmark, both rebased to 100, plus volatility and max drawdown."""
    frames = {s: daily[s] for s in symbols if s in daily and len(daily[s]) > 20}
    if len(frames) < 3 or bench not in daily:
        return None
    px = pd.DataFrame(frames).sort_index()
    px = px[px.notna().sum(axis=1) >= math.ceil(len(px.columns) / 2)]                      # start once at least half the names trade
    rets = px.pct_change().iloc[1:]
    basket = (1.0 + rets.mean(axis=1, skipna=True)).cumprod() * 100.0
    b = daily[bench].reindex(basket.index).ffill().dropna()
    if b.empty:
        return None
    basket = basket.reindex(b.index)
    b = b / b.iloc[0] * 100.0
    basket = basket / basket.iloc[0] * 100.0
    dd = float((basket / basket.cummax() - 1.0).min())
    vol = float(basket.pct_change().std() * math.sqrt(252))
    bdd = float((b / b.cummax() - 1.0).min())
    if weekly:
        basket, b = basket.resample("W-FRI").last().dropna(), b.resample("W-FRI").last().dropna()
    pts = [[d.strftime("%Y-%m-%d"), round(float(basket.loc[d]), 2), round(float(b.loc[d]), 2)] for d in basket.index if d in b.index]
    return {"points": pts, "maxDrawdown": round(dd, 4), "volatility": round(vol, 4), "benchMaxDrawdown": round(bdd, 4), "members": len(frames), "start": pts[0][0] if pts else None}


def outlook(views: list[dict], basket: dict) -> dict:
    ups = [v["upside"]["mean"] for v in views if v["upside"]]
    ratings = [v["upside"]["rating"] for v in views if v["upside"] and v["upside"]["rating"]]
    growth = [v["growth"] for v in views if v["growth"] is not None]
    pes = [v["forwardPE"] for v in views if v["forwardPE"] and 0 < v["forwardPE"] < 500]
    prof = [v["profitable"] for v in views if v["profitable"] is not None]
    caps = [(v["marketCap"], v["upside"]["mean"]) for v in views if v["upside"] and v["marketCap"]]
    wsum = sum(c for c, _ in caps)
    return {
        "analystUpsideMedian": _median(ups), "analystUpsideCapWeighted": (sum(c * u for c, u in caps) / wsum) if wsum else None, "analystNames": len(ups),
        "buyShare": (sum(1 for r in ratings if r in ("Buy", "Strong buy")) / len(ratings)) if ratings else None,
        "growthMedian": _median(growth), "forwardPEMedian": _median(pes), "profitableShare": (sum(1 for p in prof if p) / len(prof)) if prof else None,
        "record": {"annualised3Y": (basket.get("3Y") or {}).get("annualised"), "annualised5Y": (basket.get("5Y") or {}).get("annualised")},
    }


def scenarios(start: float = 10000.0) -> dict:
    rows = [{"rate": r, "label": lab, "values": {str(y): round(start * (1 + r) ** y) for y in SCENARIO_YEARS}} for r, lab in SCENARIO_RATES]
    return {"start": start, "years": SCENARIO_YEARS, "rows": rows}


def annualised_mean(views: list[dict], key: str) -> float | None:
    return _mean([v["annualised"].get(key) for v in views])


# ── whole theme ───────────────────────────────────────────────────────────────

def build_theme(theme: dict, metrics: dict[str, dict], perf_rows: dict[str, dict], bench_returns: dict | None, series: dict | None, etf_perf: dict[str, dict]) -> dict:
    views = [member_view(e, metrics.get(e["symbol"]), perf_rows.get(e["symbol"]), bench_returns) for e in theme["stocks"]]
    avail = [v for v in views if v["available"] and v["role"] != "atrisk"]      # at-risk names are shown, never counted
    basket = basket_returns(avail)
    for key in ("3Y", "5Y"):
        basket[key]["annualised"] = annualised_mean(avail, key)
    out = outlook(avail, basket)
    by_role = {r: [v for v in views if v["role"] == r] for r in ("core", "enabler", "adjacent", "emerging", "atrisk")}
    ranked = sorted([v for v in avail if v["setup"]["score"] is not None], key=lambda v: -v["setup"]["score"])
    movers = sorted([v for v in avail if v["returns"].get("3M") is not None], key=lambda v: -v["returns"]["3M"])
    etfs = [{"symbol": s, "name": n, **(etf_perf.get(s) or {})} for s, n in theme["etfs"]]
    return {
        "id": theme["id"], "name": theme["name"], "short": theme["short"], "color": theme["color"], "tagline": theme["tagline"], "thesis": theme["thesis"],
        "whyNow": theme["whyNow"], "layers": theme["layers"], "shortTerm": theme["shortTerm"], "longTerm": theme["longTerm"], "watch": theme["watch"],
        "members": views, "roleCounts": {r: len(v) for r, v in by_role.items()}, "impact": theme.get("impact"), "roleLabels": theme.get("roleLabels"),
        "basket": basket, "benchmark": bench_returns, "series": series, "outlook": out, "scenarios": scenarios(),
        "top": [v["symbol"] for v in ranked[:5]], "leaders3M": [v["symbol"] for v in movers[:3]], "laggards3M": [v["symbol"] for v in movers[-3:]],
        "etfs": etfs, "unavailable": [v["symbol"] for v in views if not v["available"]],
        "factorNames": FACTOR_NAMES, "weights": WEIGHTS,
    }


def theme_summary(t: dict) -> dict:
    """The overview card for one built theme."""
    b = t["basket"]
    return {"id": t["id"], "name": t["name"], "short": t["short"], "color": t["color"], "tagline": t["tagline"], "members": len([m for m in t["members"] if m["available"]]),
            "roleLabels": t.get("roleLabels"),
            "returns": {p: b[p]["mean"] for p in PERIODS}, "benchmark": t["benchmark"], "outlook": t["outlook"], "series": t["series"],
            "top": [{"symbol": s, "name": next(m["name"] for m in t["members"] if m["symbol"] == s), "score": next(m["setup"]["score"] for m in t["members"] if m["symbol"] == s)} for s in t["top"][:3]],
            "leaders3M": t["leaders3M"], "laggards3M": t["laggards3M"], "roleCounts": t["roleCounts"]}
