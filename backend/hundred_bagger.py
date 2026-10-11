"""100-Bagger screen — which stocks share the traits of past multi-decade compounders?

A "100-bagger" is a stock that returns 100x. It takes a long time (see `required_cagr`): 26% a year for 20 years,
20% for 25, 16.6% for 30. Studies of past 100-baggers (Christopher Mayer's *100 Baggers*, Thomas Phelps's
original work) find they tend to share a handful of traits at the start of the run, and this module scores
those traits. It does not predict anything: most stocks that look like this never get there, and many
100-baggers looked unremarkable at the start.

The traits and their weights (they sum to 100):
  size 20        small enough that 100x is arithmetically possible (100x the market cap must be a plausible company)
  growth 25      revenue growth, both the multi-year compound rate and the latest year
  returns 15     high return on equity: can it reinvest profits at high rates for years?
  margins 10     gross margin (pricing power) and operating margin, plus whether margins are widening
  balance 10     little debt, positive free cash flow: survives the bad years
  owners 10      insider ownership: founders and managers with their own money in the stock
  valuation 10   the price isn't already assuming perfection (growth-adjusted)

Each factor is scored 0-100 on fixed thresholds (not ranked against peers), so a score means the same thing
in a small-cap universe as in a mid-cap one. Missing data scores neutral-low rather than being dropped, and
is listed so you can see what the score rests on.
"""
import math

MAX_GROWTH = 0.50         # growth beyond this is almost always a small base or one lumpy year; don't extrapolate it
UNPROFITABLE_CAP = 60.0   # a company that has never made money in the available years can't be a "strong fit"
# 100x market caps above this are bigger than the whole US stock market's top companies: the math stops working.
CEILING_USD = 12e12
HARD_MAX_CAP = CEILING_USD / 100          # $120B: above this, 100x is not plausible at all
WEIGHTS = {"size": 20, "growth": 25, "returns": 15, "margins": 10, "balance": 10, "owners": 10, "valuation": 10}
FACTOR_NAMES = {"size": "Room to grow (size)", "growth": "Growth", "returns": "Return on equity", "margins": "Margins & pricing power",
                "balance": "Balance sheet", "owners": "Owner-operators", "valuation": "Valuation vs growth"}
TIERS = [(70, "Strong fit"), (55, "Promising"), (40, "Partial fit"), (0, "Weak fit")]


# ── helpers ───────────────────────────────────────────────────────────────────

def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def interp(x: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear score through (x, score) points sorted by x; clamped at both ends."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y1
    return points[-1][1]


def required_cagr(years: float, multiple: float = 100.0) -> float:
    return multiple ** (1.0 / years) - 1.0


def years_to_multiple(cagr: float | None, multiple: float = 100.0) -> float | None:
    if cagr is None or cagr <= 0:
        return None
    return math.log(multiple) / math.log(1.0 + cagr)


def tier(score: float) -> str:
    return next(name for floor, name in TIERS if score >= floor)


# ── metrics from raw Yahoo data ───────────────────────────────────────────────

def cagr_from_series(values: list[float | None]) -> tuple[float | None, int]:
    """Compound annual growth from a newest-first list of annual values; (cagr, years spanned). Needs positive end points."""
    clean = [(i, v) for i, v in enumerate(values) if v is not None and v > 0]
    if len(clean) < 3:
        return None, 0
    (i_new, v_new), (i_old, v_old) = clean[0], clean[-1]
    years = i_old - i_new
    if years < 2:
        return None, 0
    return (v_new / v_old) ** (1.0 / years) - 1.0, years


def metrics_from_yahoo(symbol: str, info: dict, revenue: list, op_income: list, net_income: list) -> dict:
    """Normalised metrics. Statement lists are annual values, newest first, None where missing."""
    rev_cagr, rev_years = cagr_from_series([_num(v) for v in revenue])
    op_margins = [(_num(o) / _num(r)) if _num(o) is not None and _num(r) else None for o, r in zip(op_income, revenue)]
    om_new = next((m for m in op_margins if m is not None), None)
    om_old = next((m for m in reversed(op_margins) if m is not None), None)
    profitable_years = sum(1 for v in net_income if _num(v) is not None and _num(v) > 0)
    de = _num(info.get("debtToEquity"))
    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector"), "industry": info.get("industry"),
        "summary": (info.get("longBusinessSummary") or "")[:320] or None,
        "price": _num(info.get("currentPrice") or info.get("regularMarketPrice")),
        "marketCap": _num(info.get("marketCap")),
        "revenue": _num(info.get("totalRevenue")),
        "revenueGrowth": _num(info.get("revenueGrowth")),
        "revenueCagr": rev_cagr, "revenueCagrYears": rev_years,
        "earningsGrowth": _num(info.get("earningsGrowth")),
        "roe": _num(info.get("returnOnEquity")),
        "grossMargin": _num(info.get("grossMargins")),
        "operatingMargin": _num(info.get("operatingMargins")) if _num(info.get("operatingMargins")) is not None else om_new,
        "marginChange": (om_new - om_old) if om_new is not None and om_old is not None and len(op_margins) >= 3 else None,
        "debtToEquity": None if de is None else de / 100.0,
        "freeCashFlow": _num(info.get("freeCashflow")),
        "totalCash": _num(info.get("totalCash")), "totalDebt": _num(info.get("totalDebt")),
        "insiders": _num(info.get("heldPercentInsiders")),
        "trailingPE": _num(info.get("trailingPE")), "forwardPE": _num(info.get("forwardPE")),
        "priceToSales": _num(info.get("priceToSalesTrailing12Months")),
        "targetMean": _num(info.get("targetMeanPrice")), "targetHigh": _num(info.get("targetHighPrice")), "targetLow": _num(info.get("targetLowPrice")),
        "analystCount": int(_num(info.get("numberOfAnalystOpinions")) or 0), "recommendation": _num(info.get("recommendationMean")),
        "week52High": _num(info.get("fiftyTwoWeekHigh")), "week52Low": _num(info.get("fiftyTwoWeekLow")), "beta": _num(info.get("beta")),
        "profitableYears": profitable_years, "statementYears": len([v for v in net_income if _num(v) is not None]),
    }


# ── scoring ───────────────────────────────────────────────────────────────────

def blended_growth(m: dict) -> float | None:
    """The growth rate used for scoring and for "years to 100x": the multi-year revenue CAGR weighted 60/40 with the
    latest year's growth, falling back to whichever exists."""
    c, g = m.get("revenueCagr"), m.get("revenueGrowth")
    blended = 0.6 * c + 0.4 * g if c is not None and g is not None else c if c is not None else g
    return None if blended is None else min(blended, MAX_GROWTH)


def money(x: float) -> str:
    return f"${x/1e12:.1f}T" if x >= 1e12 else f"${x/1e9:.0f}B" if x >= 1e10 else f"${x/1e9:.1f}B"


def score_size(m):
    cap = m.get("marketCap")
    if cap is None:
        return None, "Market cap unknown"
    s = interp(math.log10(cap), [(8.0, 100), (9.0, 100), (9.5, 85), (10.0, 62), (10.5, 35), (11.0, 12), (11.08, 0)])
    return s, f"{money(cap)} market cap; 100x would be {money(cap * 100)}"


def score_growth(m):
    g = blended_growth(m)
    if g is None:
        return None, "No revenue growth data"
    s = interp(g, [(-0.05, 0), (0.0, 8), (0.08, 35), (0.15, 62), (0.25, 85), (0.35, 100)])
    parts = []
    if m.get("revenueCagr") is not None:
        parts.append(f"{m['revenueCagr']:.0%} a year over {m['revenueCagrYears']} years")
    if m.get("revenueGrowth") is not None:
        parts.append(f"{m['revenueGrowth']:.0%} latest")
    return s, "Revenue " + ", ".join(parts)


def score_returns(m):
    roe = m.get("roe")
    if roe is None:
        return None, "Return on equity unknown"
    s = interp(roe, [(0.0, 0), (0.08, 30), (0.15, 65), (0.25, 90), (0.35, 100)])
    de = m.get("debtToEquity")
    note = ""
    if de is not None and de > 2.0 and roe > 0.15:
        s *= 0.7
        note = " (discounted: boosted by heavy debt)"
    return s, f"Return on equity {roe:.0%}{note}"


def score_margins(m):
    gm, om = m.get("grossMargin"), m.get("operatingMargin")
    if gm is None and om is None:
        return None, "Margins unknown"
    parts, notes = [], []
    if gm is not None:
        parts.append(interp(gm, [(0.1, 10), (0.25, 40), (0.45, 75), (0.65, 100)]))
        notes.append(f"gross {gm:.0%}")
    if om is not None:
        parts.append(interp(om, [(0.0, 5), (0.08, 35), (0.18, 75), (0.30, 100)]))
        notes.append(f"operating {om:.0%}")
    s = sum(parts) / len(parts)
    chg = m.get("marginChange")
    if chg is not None:
        s = min(100.0, max(0.0, s + (8 if chg > 0.03 else -8 if chg < -0.03 else 0)))
        if abs(chg) > 0.03:
            notes.append("widening" if chg > 0 else "narrowing")
    return s, "Margins " + ", ".join(notes)


def score_balance(m):
    de, fcf, cash, debt = m.get("debtToEquity"), m.get("freeCashFlow"), m.get("totalCash"), m.get("totalDebt")
    if de is None and fcf is None and debt is None:
        return None, "Balance sheet unknown"
    net_cash = cash is not None and debt is not None and cash >= debt
    s = 100.0 if (net_cash or (de is not None and de < 0.1)) else interp(de, [(0.1, 100), (0.5, 80), (1.0, 55), (2.0, 20), (3.0, 0)]) if de is not None else 50.0
    note = "net cash" if net_cash else (f"debt/equity {de:.1f}" if de is not None else "debt unknown")
    if fcf is not None:
        if fcf < 0:
            s *= 0.75
            note += ", negative free cash flow"
        else:
            note += ", positive free cash flow"
    return s, "Balance sheet: " + note


def score_owners(m):
    ins = m.get("insiders")
    if ins is None:
        return None, "Insider ownership unknown"
    return interp(ins, [(0.0, 10), (0.02, 25), (0.05, 50), (0.10, 75), (0.20, 100)]), f"Insiders own {ins:.1%}"


def score_valuation(m):
    g = blended_growth(m)
    fpe, tpe, ps = m.get("forwardPE"), m.get("trailingPE"), m.get("priceToSales")
    pe = fpe if fpe and fpe > 0 else tpe if tpe and tpe > 0 else None
    if pe is not None and g is not None and g > 0.02:
        peg = pe / (g * 100.0)
        return interp(peg, [(0.5, 100), (1.0, 85), (1.5, 62), (2.5, 30), (4.0, 5)]), f"P/E {pe:.0f} against {g:.0%} growth (PEG {peg:.1f})"
    if pe is not None:
        return interp(pe, [(10, 70), (20, 55), (35, 30), (60, 10)]), f"P/E {pe:.0f}; growth too low to adjust"
    if ps is not None and g is not None and g > 0.02:
        ratio = ps / (g * 100.0)
        return interp(ratio, [(0.1, 90), (0.25, 70), (0.5, 40), (1.0, 10)]), f"No earnings; price/sales {ps:.1f} against {g:.0%} growth"
    return None, "Valuation not measurable (no earnings or growth)"


SCORERS = {"size": score_size, "growth": score_growth, "returns": score_returns, "margins": score_margins,
           "balance": score_balance, "owners": score_owners, "valuation": score_valuation}
MISSING_SCORE = 30.0


def score(m: dict) -> dict:
    """{score, tier, factors: {name: {score, weight, points, note, missing}}}."""
    factors, total = {}, 0.0
    for name, fn in SCORERS.items():
        s, note = fn(m)
        missing = s is None
        s_used = MISSING_SCORE if missing else float(s)
        pts = s_used * WEIGHTS[name] / 100.0
        total += pts
        factors[name] = {"score": round(s_used, 1), "weight": WEIGHTS[name], "points": round(pts, 1), "note": note, "missing": missing}
    capped = m.get("statementYears", 0) >= 3 and m.get("profitableYears", 0) == 0 and total > UNPROFITABLE_CAP
    total = round(UNPROFITABLE_CAP if capped else total, 1)
    return {"score": total, "tier": tier(total), "factors": factors, "capped": capped}


TRAITS = [
    ("small", "Under $10B", lambda m: m.get("marketCap") is not None and m["marketCap"] < 10e9),
    ("growth", "Growing 20%+ a year", lambda m: (blended_growth(m) or 0) >= 0.20),
    ("returns", "ROE 15%+", lambda m: (m.get("roe") or 0) >= 0.15),
    ("margins", "Gross margin 40%+", lambda m: (m.get("grossMargin") or 0) >= 0.40),
    ("balance", "Low debt", lambda m: (m.get("debtToEquity") is not None and m["debtToEquity"] < 0.5) or (m.get("totalCash") or 0) >= (m.get("totalDebt") or 0) > 0 or (m.get("totalDebt") == 0)),
    ("owners", "Insiders own 10%+", lambda m: (m.get("insiders") or 0) >= 0.10),
    ("valuation", "Not priced for perfection", lambda m: score_valuation(m)[0] is not None and score_valuation(m)[0] >= 60),
]


def traits(m: dict) -> list[dict]:
    return [{"id": i, "label": label, "met": bool(fn(m))} for i, label, fn in TRAITS]


def flags(m: dict) -> list[str]:
    """Reasons for caution, shown beside the score."""
    out = []
    cap = m.get("marketCap")
    if cap is not None and cap > 30e9:
        out.append(f"Already {money(cap)}: 100x would need {money(cap * 100)}")
    if m.get("revenueGrowth") is not None and m["revenueGrowth"] < 0:
        out.append("Revenue shrinking")
    if m.get("operatingMargin") is not None and m["operatingMargin"] < 0:
        out.append("Operating at a loss")
    if m.get("debtToEquity") is not None and m["debtToEquity"] > 2:
        out.append("Heavily indebted")
    if m.get("freeCashFlow") is not None and m["freeCashFlow"] < 0:
        out.append("Burning cash")
    if m.get("marginChange") is not None and m["marginChange"] < -0.05:
        out.append("Margins narrowing")
    if m.get("statementYears", 0) >= 3 and m.get("profitableYears", 0) == 0:
        out.append("Never profitable in the available years")
    if m.get("revenueCagrYears", 0) == 0:
        out.append("Short track record")
    return out


def build_row(m: dict) -> dict:
    sc = score(m)
    g = blended_growth(m)
    yrs = years_to_multiple(g)
    cap = m.get("marketCap")
    return {**{k: m.get(k) for k in ("symbol", "name", "sector", "industry", "price", "marketCap", "revenue", "revenueGrowth", "revenueCagr", "revenueCagrYears",
                                     "earningsGrowth", "roe", "grossMargin", "operatingMargin", "marginChange", "debtToEquity", "insiders",
                                     "forwardPE", "trailingPE", "priceToSales", "freeCashFlow", "summary")},
            **sc, "growthUsed": None if g is None else round(g, 4), "yearsTo100x": None if yrs is None else round(yrs, 1),
            "capAt100x": None if cap is None else cap * 100, "traits": traits(m), "traitsMet": sum(1 for t in traits(m) if t["met"]), "flags": flags(m)}


def build_results(metrics: list[dict], max_cap: float | None = None) -> dict:
    """Scored rows, best first. Stocks above `max_cap` (default: the $120B ceiling) are counted but left out."""
    ceiling = HARD_MAX_CAP if max_cap is None else max_cap
    rows, skipped_big, skipped_data = [], 0, 0
    for m in metrics:
        if m.get("marketCap") is None or (m.get("revenue") is None and m.get("revenueCagr") is None):
            skipped_data += 1
            continue
        if m["marketCap"] > ceiling:
            skipped_big += 1
            continue
        rows.append(build_row(m))
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    dist = {name: sum(1 for r in rows if r["tier"] == name) for _, name in TIERS}
    return {"rows": rows, "counts": {"scored": len(rows), "tooBig": skipped_big, "noData": skipped_data}, "tierCounts": dist,
            "weights": WEIGHTS, "factorNames": FACTOR_NAMES,
            "timeline": [{"years": y, "cagr": round(required_cagr(y), 4)} for y in (10, 15, 20, 25, 30)]}
