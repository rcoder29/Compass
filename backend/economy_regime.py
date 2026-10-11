"""Economic regime model — where are we in the cycle, and how worried should we be about a recession?

Three transparent, rule-based readings built from the indicator catalog (nothing is fitted or learned, so
every number on the page can be traced to a rule):

1. **Growth and inflation composites → quadrant.** Each component is converted to a score between -1 and
   +1 from its percentile against *its own history up to that date* (an expanding window, so a 1998 reading
   is judged only against what had happened by 1998). Growth blends activity indicators (CFNAI, industrial
   production, retail sales, payrolls, regional factory surveys, jobless claims); inflation blends core CPI,
   core PCE and CPI. The quadrant comes from the *direction* of each composite over three months:

       growth up,   inflation down  -> Goldilocks          growth up,   inflation up   -> Overheating
       growth down, inflation down  -> Slowdown            growth down, inflation up   -> Stagflation

2. **Recession-risk score (0-100).** A weighted blend of ten warning signs — yield-curve inversion, the Sahm
   rule, jobless claims, CFNAI, credit spreads, financial conditions, payrolls, building permits, industrial
   production and bank lending standards. Each contributes a "stress" between 0 and 1 by a stated rule.

3. **Cycle phase.** Early recovery / Mid-cycle / Late-cycle / Slowdown / Recession from the growth level and
   momentum, with the recession-risk score able to override.

The same code runs over the full history to label every month back to ~1990, which is what lets the sector
Cycle Fit page ask "how did each sector behave in each phase". Caveats: FRED serves *revised* data, so the
historical labels are cleaner than a real-time observer would have seen; and a rule-based score is a summary
of conditions, not a forecast.
"""
import bisect
import math

import numpy as np
import pandas as pd

import economy
from economy_catalog import BY_ID

# Components of the growth composite: (indicator id, direction) where direction +1 means higher = stronger.
GROWTH_COMPONENTS = [("cfnai", 1), ("indpro", 1), ("retail", 1), ("payrolls", 1), ("philly", 1), ("empire", 1), ("claims", -1)]
INFLATION_COMPONENTS = [("corecpi", 1), ("corepce", 1), ("cpi", 1)]

QUADRANTS = {
    ("up", "down"): ("goldilocks", "Goldilocks", "Growth is picking up while inflation is easing: the combination that has usually been friendliest to stocks."),
    ("up", "up"): ("overheating", "Overheating", "Growth and inflation are both accelerating. Early on this favors cyclicals and commodities; the risk is a hawkish central bank."),
    ("down", "up"): ("stagflation", "Stagflation", "Growth is slowing while inflation is rising: the hardest backdrop for both stocks and bonds."),
    ("down", "down"): ("slowdown", "Slowdown", "Growth is slowing and inflation is easing. Defensive sectors and falling yields have tended to help; the question is whether it deepens."),
}

PHASES = {
    "early": ("Early recovery", "Growth is below trend but improving. Historically the strongest stretch for stocks, led by cyclicals and financials."),
    "mid": ("Mid-cycle expansion", "Growth is above trend and still improving. Typically the longest phase, with broad but more moderate gains."),
    "late": ("Late cycle", "Growth is still above trend but losing momentum. Inflation and rates tend to bite; leadership often rotates toward defensives and energy."),
    "slowdown": ("Slowdown", "Growth is below trend and still weakening. A recession is possible; markets are usually choppy and defensive."),
    "recession": ("Recession risk", "Several recession warning signs are flashing. Historically the weakest phase for stocks, though markets often bottom before the data does."),
}

# (id, weight) — weights sum to 100. Each has a stress rule in _STRESS.
RISK_WEIGHTS = [("curve10_3m", 20), ("sahm", 15), ("claims", 12), ("cfnai", 12), ("baa", 10), ("payrolls", 8),
                ("indpro", 6), ("nfci", 6), ("slos", 6), ("permit", 5)]
RISK_BANDS = [(20, "Low"), (40, "Moderate"), (60, "Elevated"), (101, "High")]
# Calibrated against the NBER dates since 1990: at 55 the score covers 63 of 74 recession months with no false alarms
# outside the 9 months after a recession. Letting Sahm or CFNAI declare a recession on their own produced false alarms
# (1992, 2002, 2010, 2021 and the 2024 Sahm trigger), so they count only through the composite.
RECESSION_PHASE_THRESHOLD = 55


# ── helpers ───────────────────────────────────────────────────────────────────

def _clamp01(x):
    return np.clip(x, 0.0, 1.0)


def expanding_percentile(s: pd.Series, min_periods: int = 60) -> pd.Series:
    """For each point, its percentile rank among the observations up to and including that date (0-100)."""
    vals, out, seen = s.values, [], []
    for v in vals:
        if math.isnan(v):
            out.append(float("nan"))
            continue
        pos_lo, pos_hi = bisect.bisect_left(seen, v), bisect.bisect_right(seen, v)
        n = len(seen) + 1
        bisect.insort(seen, v)
        out.append((pos_lo + 0.5 * (pos_hi - pos_lo + 1)) / n * 100.0 if n >= min_periods else float("nan"))
    return pd.Series(out, index=s.index)


def monthly(s: pd.Series) -> pd.Series:
    """Month-start frequency (mean within the month) so daily, weekly and monthly series line up."""
    return s.resample("MS").mean().dropna()


def _indicator_series(indicator_id: str, series_map: dict[str, pd.Series]) -> pd.Series | None:
    meta = BY_ID[indicator_id]
    raw = series_map.get(meta["fred"])
    if raw is None:
        return None
    t = economy.transform(raw, meta["transform"], meta.get("scale", 1.0), meta["freq"])
    return monthly(t) if len(t) else None


def composite(series_map: dict[str, pd.Series], components: list[tuple[str, int]], min_components: int = 3) -> tuple[pd.Series, dict]:
    """(score series in [-1, 1], {id: latest component score}). Components that don't exist yet for a date are
    skipped for that date; a date needs `min_components` of them."""
    scores = {}
    for cid, direction in components:
        s = _indicator_series(cid, series_map)
        if s is None:
            continue
        pct = expanding_percentile(s)
        scores[cid] = (pct - 50.0) / 50.0 * direction
    if not scores:
        return pd.Series(dtype=float), {}
    frame = pd.DataFrame(scores).sort_index()
    avg = frame.mean(axis=1)
    avg[frame.notna().sum(axis=1) < min(min_components, len(scores))] = float("nan")
    latest = {cid: round(float(col.dropna().iloc[-1]), 3) for cid, col in frame.items() if col.notna().any()}
    return avg.dropna(), latest


def growth_inflation(series_map: dict[str, pd.Series]) -> tuple[pd.DataFrame, dict, dict]:
    """Monthly frame of growth/inflation levels (3-month smoothed) and momentum, plus latest component scores."""
    g, g_parts = composite(series_map, GROWTH_COMPONENTS)
    i, i_parts = composite(series_map, INFLATION_COMPONENTS, min_components=2)
    frame = pd.DataFrame({"growth": g.rolling(3, min_periods=2).mean(), "inflation": i.rolling(3, min_periods=2).mean()}).dropna()
    frame["growthMom"] = frame["growth"] - frame["growth"].shift(3)
    frame["inflationMom"] = frame["inflation"] - frame["inflation"].shift(3)
    return frame, g_parts, i_parts


def quadrant(growth_mom: float, inflation_mom: float) -> dict:
    g = "up" if growth_mom >= 0 else "down"
    i = "up" if inflation_mom >= 0 else "down"
    qid, name, text = QUADRANTS[(g, i)]
    return {"id": qid, "name": name, "description": text, "growthDirection": g, "inflationDirection": i}


# ── recession risk ────────────────────────────────────────────────────────────

def _stress_curve(s: pd.Series) -> pd.Series:
    """1 while inverted; 0.7 for the 12 months after an inversion (the historically dangerous stretch); 0.3 if flat."""
    inverted = s < 0
    recent = s.rolling(12, min_periods=1).min() < 0
    return pd.Series(np.where(inverted, 1.0, np.where(recent, 0.7, np.where(s < 0.5, 0.3, 0.0))), index=s.index)


def _stress_claims(s: pd.Series) -> pd.Series:
    return pd.Series(_clamp01((s / s.rolling(12, min_periods=6).min() - 1.0) / 0.30), index=s.index)


_STRESS = {
    "curve10_3m": (_stress_curve, "Inverted = full stress; stays elevated for 12 months after inversion"),
    "sahm": (lambda s: pd.Series(_clamp01(s / 0.5), index=s.index), "Full stress at the 0.50 trigger"),
    "claims": (_stress_claims, "Full stress when claims are 30% above their 12-month low"),
    "cfnai": (lambda s: pd.Series(_clamp01(-s / 0.7), index=s.index), "Full stress at -0.7 or below"),
    "baa": (lambda s: pd.Series(_clamp01((s - 2.0) / 1.5), index=s.index), "No stress at 2.0, full stress at 3.5 points"),
    "payrolls": (lambda s: pd.Series(_clamp01((100.0 - s) / 150.0), index=s.index), "No stress above 100K a month, full at -50K"),
    "indpro": (lambda s: pd.Series(_clamp01(-s / 3.0), index=s.index), "Full stress at -3% year over year"),
    "nfci": (lambda s: pd.Series(_clamp01(s / 0.5), index=s.index), "Stress once conditions are tighter than average; full at +0.5"),
    "slos": (lambda s: pd.Series(_clamp01(s / 40.0), index=s.index), "Full stress at 40% of banks tightening"),
    "permit": (lambda s: pd.Series(_clamp01(-s / 20.0), index=s.index), "Full stress at -20% year over year"),
}


def risk_band(score: float) -> str:
    return next(name for limit, name in RISK_BANDS if score < limit)


def risk_history(series_map: dict[str, pd.Series]) -> pd.DataFrame:
    """Monthly frame: one stress column per component (0-1), plus 'score' (0-100). Components missing for a
    date are left out and the remaining weights renormalised, so early history is scored on fewer signs."""
    cols = {}
    for cid, _ in RISK_WEIGHTS:
        s = _indicator_series(cid, series_map)
        if s is None:
            continue
        cols[cid] = _STRESS[cid][0](s)
    if not cols:
        return pd.DataFrame()
    frame = pd.DataFrame(cols).sort_index()
    weights = pd.Series({cid: w for cid, w in RISK_WEIGHTS if cid in frame})
    avail = frame.notna().astype(float).mul(weights, axis=1)
    frame["score"] = (frame[weights.index].fillna(0.0).mul(weights, axis=1).sum(axis=1) / avail.sum(axis=1).replace(0, np.nan)) * 100.0
    return frame.dropna(subset=["score"])


def risk_components_now(series_map: dict[str, pd.Series]) -> list[dict]:
    """The recession-risk table for the dashboard, from each component's latest *observation* (not a monthly mean)."""
    out = []
    for cid, weight in RISK_WEIGHTS:
        meta = BY_ID[cid]
        raw = series_map.get(meta["fred"])
        if raw is None:
            continue
        t = economy.transform(raw, meta["transform"], meta.get("scale", 1.0), meta["freq"])
        if t.empty:
            continue
        fn, rule = _STRESS[cid]
        m = monthly(t)
        stress_series = fn(m)
        stress = float(stress_series.iloc[-1]) if len(stress_series) else 0.0
        out.append({"id": cid, "name": meta["name"], "unit": meta["unit"], "value": round(float(t.iloc[-1]), 3),
                    "date": t.index[-1].strftime("%Y-%m-%d"), "weight": weight, "stress": round(stress, 3), "rule": rule,
                    "status": "high" if stress >= 0.66 else "watch" if stress >= 0.25 else "calm"})
    return out


# ── phase ─────────────────────────────────────────────────────────────────────

def phase_id(growth: float, growth_mom: float, risk: float | None) -> str:
    if risk is not None and risk >= RECESSION_PHASE_THRESHOLD:
        return "recession"
    if growth < 0:
        return "early" if growth_mom >= 0 else "slowdown"
    return "mid" if growth_mom >= 0 else "late"


def regime_history(series_map: dict[str, pd.Series]) -> pd.DataFrame:
    """Every month from ~1990 with growth, inflation, momentum, risk score, quadrant and phase."""
    gi, _, _ = growth_inflation(series_map)
    risk = risk_history(series_map)
    if gi.empty:
        return pd.DataFrame()
    frame = gi.join(risk[["score"]].rename(columns={"score": "risk"}), how="left")
    frame = frame.dropna(subset=["growthMom", "inflationMom"])
    frame["phase"] = [phase_id(r.growth, r.growthMom, None if pd.isna(r.risk) else r.risk) for r in frame.itertuples()]
    frame["quadrant"] = [quadrant(r.growthMom, r.inflationMom)["id"] for r in frame.itertuples()]
    return frame


def track_record(frame: pd.DataFrame, recessions: list[dict], warn_at: float = 40.0, since: str = "1970-01-01") -> list[dict]:
    """How the score behaved around each NBER recession: its peak, and when it first crossed `warn_at` relative to the
    recession's start (negative months = before it began). Shown on the page so the score is judged by its record."""
    out = []
    risk = frame["risk"].dropna() if "risk" in frame else pd.Series(dtype=float)
    for r in recessions:
        start, end = pd.Timestamp(r["start"]), pd.Timestamp(r["end"])
        if start < pd.Timestamp(since) or risk.empty or start < risk.index[0] + pd.DateOffset(months=12):
            continue
        window = risk[(risk.index >= start - pd.DateOffset(months=18)) & (risk.index <= end + pd.DateOffset(months=3))]
        if window.empty:
            continue
        crossed = window[window >= warn_at]
        lead = None
        if len(crossed):
            first = crossed.index[0]
            lead = (first.year - start.year) * 12 + (first.month - start.month)
        out.append({"start": r["start"][:7], "end": r["end"][:7], "peak": round(float(window.max()), 1),
                    "firstWarning": None if not len(crossed) else crossed.index[0].strftime("%Y-%m"), "monthsFromStart": lead})
    return out


# ── dashboard payload ─────────────────────────────────────────────────────────

def _label(level: float, mom: float, noun: str) -> str:
    where = "well above" if level > 0.5 else "above" if level > 0.1 else "near" if level >= -0.1 else "below" if level >= -0.5 else "well below"
    way = "improving" if mom > 0.03 else "weakening" if mom < -0.03 else "steady"
    return f"{noun} {where} its historical norm and {way}"


def build_regime(series_map: dict[str, pd.Series], recessions: list[dict] | None = None, history_months: int = 120) -> dict | None:
    frame = regime_history(series_map)
    if frame.empty:
        return None
    gi, g_parts, i_parts = growth_inflation(series_map)
    cur = frame.iloc[-1]
    comps = risk_components_now(series_map)
    avail_w = sum(c["weight"] for c in comps) or 1
    score = sum(c["stress"] * c["weight"] for c in comps) / avail_w * 100.0 if comps else None
    pid = phase_id(float(cur.growth), float(cur.growthMom), score)
    q = quadrant(float(cur.growthMom), float(cur.inflationMom))
    curve = _indicator_series("curve10_3m", series_map)
    inversion = None
    if curve is not None and len(curve):
        inv = curve[curve < 0]
        inversion = {"invertedNow": bool(curve.iloc[-1] < 0), "value": round(float(curve.iloc[-1]), 2),
                     "lastInverted": inv.index[-1].strftime("%Y-%m") if len(inv) else None,
                     "monthsInvertedLast24": int((curve.iloc[-24:] < 0).sum())}
    hist = frame.iloc[-history_months:]

    def comp_rows(parts, comps_def):
        return [{"id": cid, "name": BY_ID[cid]["name"], "score": parts[cid]} for cid, _ in comps_def if cid in parts]
    return {
        "asOf": frame.index[-1].strftime("%Y-%m-%d"),
        "growth": {"level": round(float(cur.growth), 3), "momentum": round(float(cur.growthMom), 3),
                   "label": _label(float(cur.growth), float(cur.growthMom), "Growth"), "components": comp_rows(g_parts, GROWTH_COMPONENTS)},
        "inflation": {"level": round(float(cur.inflation), 3), "momentum": round(float(cur.inflationMom), 3),
                      "label": _label(float(cur.inflation), float(cur.inflationMom), "Inflation"), "components": comp_rows(i_parts, INFLATION_COMPONENTS)},
        "quadrant": q,
        "recession": None if score is None else {"score": round(score, 1), "band": risk_band(score), "components": comps, "curve": inversion},
        "phase": {"id": pid, "name": PHASES[pid][0], "description": PHASES[pid][1]},
        "trackRecord": track_record(frame, recessions or []),
        "history": [{"date": d.strftime("%Y-%m-%d"), "growth": round(float(r.growth), 3), "inflation": round(float(r.inflation), 3),
                     "risk": None if pd.isna(r.risk) else round(float(r.risk), 1), "phase": r.phase, "quadrant": r.quadrant}
                    for d, r in hist.iterrows()],
        "method": "Rule-based and transparent; uses FRED's revised data, so history is cleaner than it looked in real time. "
                  "A summary of current conditions, not a forecast.",
    }
