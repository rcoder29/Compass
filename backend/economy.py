"""Economic indicator maths — transforms, long-run percentiles, trend and signal.

Everything here is pure (Series in, dicts out) so it can be tested against hand-computed numbers; the
FRED download lives in fred_data.py and the HTTP surface in routers/economy.py.

For each catalog indicator we compute, on the *displayed* (transformed) series:
  - the latest reading, the previous one and the change over ~3 and ~12 months;
  - its percentile against the series' whole history (e.g. "unemployment is in its 31st percentile
    since 1948") and a z-score against the last ten years;
  - a trend (rising / falling / flat over ~3 months, judged against how much the series normally moves);
  - a signal — supportive, neutral or cautionary for equities — and the reason in words.

The signal is deliberately simple and explainable: a warning level or comfort band if the catalog defines
one, otherwise whether the trend is moving in the direction that has historically been better for stocks.
It is a reading of conditions, not a forecast.
"""
import math

import pandas as pd

from economy_catalog import BY_ID, CATEGORIES, INDICATORS

# Observations further than this from the target date don't count as "the value a year ago". Tight on purpose:
# monthly data is dated the 1st, so anything further than ~3 weeks off means a month is missing, and quietly
# matching the previous month would turn "year over year" into a 13-month change.
_LAG_TOLERANCE_DAYS = {"D": 5, "W": 7, "M": 20, "Q": 45}
_TREND_FLAT_SIGMA = 0.5
_MAD_TO_SIGMA = 1.4826             # scales a median absolute deviation to a standard-deviation equivalent
_STALE_FACTOR = 2.5
_EXPECTED_GAP_DAYS = {"D": 5, "W": 10, "M": 45, "Q": 110}


# ── Transforms ────────────────────────────────────────────────────────────────

def lagged(s: pd.Series, offset: pd.DateOffset, tolerance_days: int) -> pd.Series:
    """For each observation, the value `offset` earlier (last observation at or before that date),
    NaN where there isn't one within `tolerance_days`."""
    targets = s.index - offset
    pos = s.index.searchsorted(targets, side="right") - 1
    ok = pos >= 0
    out = pd.Series(float("nan"), index=s.index)
    if ok.any():
        found = s.index[pos[ok]]
        close = (targets[ok] - found).days <= tolerance_days
        vals = s.values[pos[ok]]
        idx = s.index[ok]
        out.loc[idx[close]] = vals[close]
    return out


def transform(s: pd.Series, spec: str, scale: float = 1.0, freq: str = "M") -> pd.Series:
    """'level' | 'yoy' (percent change vs a year earlier) | 'avg3_chg' (3-month mean of the monthly change)."""
    s = s.dropna().sort_index().astype(float)
    if spec == "level":
        return s * scale
    if spec == "yoy":
        prior = lagged(s, pd.DateOffset(years=1), _LAG_TOLERANCE_DAYS.get(freq, 20))
        out = (s / prior - 1.0) * 100.0
        return out[prior.notna() & (prior != 0)].dropna()
    if spec == "avg3_chg":
        return (s.diff().rolling(3).mean() * scale).dropna()
    raise ValueError(f"unknown transform {spec!r}")


# ── Statistics ────────────────────────────────────────────────────────────────

def percentile_rank(s: pd.Series, value: float) -> float:
    """Percent of the history at or below `value` (ties count half)."""
    v = s.dropna().values
    if len(v) == 0:
        return float("nan")
    return float(((v < value).sum() + 0.5 * (v == value).sum()) / len(v) * 100.0)


def zscore(s: pd.Series, years: int = 10) -> float | None:
    """How many standard deviations the latest value is from its mean over the last `years` years."""
    recent = s[s.index >= s.index[-1] - pd.DateOffset(years=years)]
    if len(recent) < 8:
        return None
    sd = float(recent.std())
    return float((s.iloc[-1] - recent.mean()) / sd) if sd > 0 else None


def trend(s: pd.Series, freq: str = "M") -> dict:
    """Direction over about three months, judged against how much the series usually moves in three months
    (so a 0.2-point move is 'flat' for CPI-style series and 'rising' for a very calm one)."""
    last_date, last = s.index[-1], float(s.iloc[-1])
    prior = lagged(s, pd.DateOffset(months=3), _LAG_TOLERANCE_DAYS.get(freq, 20))
    base = prior.iloc[-1]
    if pd.isna(base):
        return {"direction": "flat", "change3m": None}
    delta = last - float(base)
    recent_changes = (s - prior)[s.index >= last_date - pd.DateOffset(years=10)].dropna()
    # Robust spread (median absolute deviation): a single crisis spike like 2020 would otherwise inflate a plain
    # standard deviation so much that ordinary moves all look like noise.
    sd = float((recent_changes - recent_changes.median()).abs().median() * _MAD_TO_SIGMA) if len(recent_changes) > 8 else 0.0
    if sd <= 0:
        direction = "rising" if delta > 0 else "falling" if delta < 0 else "flat"
    elif abs(delta) < _TREND_FLAT_SIGMA * sd:
        direction = "flat"
    else:
        direction = "rising" if delta > 0 else "falling"
    return {"direction": direction, "change3m": delta}


# ── Signal ────────────────────────────────────────────────────────────────────

_TAIL = 15.0          # percentile counted as the extreme tail of history


def signal(meta: dict, value: float, direction: str, pct: float | None = None) -> dict:
    """{'status': 'supportive'|'neutral'|'cautionary', 'reason': str} for equities.

    Order of precedence: a warning level, then a comfort band, then the trend (with `pct`, the long-run
    percentile, tempering it: improving from the worst tail of history is neutral, not supportive)."""
    wa, wb, band, hib = meta.get("warn_above"), meta.get("warn_below"), meta.get("band"), meta.get("hib")
    unit = meta.get("unit", "")
    if wa is not None and value >= wa:
        return {"status": "cautionary", "reason": f"At or above the {wa:g}{unit if unit in ('%', 'K') else ''} warning level"}
    if wb is not None and value <= wb:
        return {"status": "cautionary", "reason": f"At or below the {wb:g}{unit if unit in ('%', 'K') else ''} warning level"}
    if band is not None:
        lo, hi = band
        if value > hi:
            return {"status": "cautionary", "reason": f"Above the {lo:g}-{hi:g}% comfort range"}
        if value < lo:
            return {"status": "cautionary", "reason": f"Below the {lo:g}-{hi:g}% comfort range"}
        return {"status": "supportive", "reason": f"Inside the {lo:g}-{hi:g}% comfort range"}
    if hib is None:
        return {"status": "neutral", "reason": "Direction matters more than level; read it alongside other indicators"}
    if direction == "flat":
        return {"status": "neutral", "reason": "Little changed over the last three months"}
    good = (direction == "rising") == bool(hib)
    word = "Rising" if direction == "rising" else "Falling"
    better = "higher" if hib else "lower"
    if pct is not None:
        unfavourable_tail = pct <= _TAIL if hib else pct >= 100 - _TAIL
        favourable_tail = pct >= 100 - _TAIL if hib else pct <= _TAIL
        if good and unfavourable_tail:
            return {"status": "neutral", "reason": f"{word}, but still in the weakest {_TAIL:.0f}% of its history"}
        if not good and favourable_tail:
            return {"status": "neutral", "reason": f"{word}, but from one of the strongest {_TAIL:.0f}% of readings"}
    if good:
        return {"status": "supportive", "reason": f"{word}, and {better} has been better for stocks"}
    return {"status": "cautionary", "reason": f"{word}, and {better} has been better for stocks"}


# ── Per-indicator summaries ───────────────────────────────────────────────────

def _num(x) -> float | None:
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else float(x)


def summarize(meta: dict, raw: pd.Series | None) -> dict | None:
    """The row shown in the indicator table, or None if the series is unusable."""
    if raw is None:
        return None
    s = transform(raw, meta["transform"], meta.get("scale", 1.0), meta["freq"])
    if len(s) < 3:
        return None
    last_date, last = s.index[-1], float(s.iloc[-1])
    tr = trend(s, meta["freq"])
    pct = percentile_rank(s, last)
    sig = signal(meta, last, tr["direction"], pct)
    tol = _LAG_TOLERANCE_DAYS.get(meta["freq"], 20)
    prior12 = lagged(s, pd.DateOffset(years=1), tol).iloc[-1]
    days_old = (pd.Timestamp.now().normalize() - last_date).days
    return {
        "id": meta["id"], "name": meta["name"], "category": meta["category"], "unit": meta["unit"], "freq": meta["freq"],
        "lead": meta["lead"], "horizon": meta["horizon"], "hib": meta["hib"],
        "date": last_date.strftime("%Y-%m-%d"), "value": round(last, 4),
        "previous": _num(round(float(s.iloc[-2]), 4)),
        "change3m": _num(round(tr["change3m"], 4)) if tr["change3m"] is not None else None,
        "change1y": _num(round(last - float(prior12), 4)) if not pd.isna(prior12) else None,
        "percentile": round(pct, 1),
        "zscore10y": _num(round(zscore(s), 2)) if zscore(s) is not None else None,
        "historyStart": s.index[0].strftime("%Y-%m-%d"),
        "trend": tr["direction"], "signal": sig["status"], "reason": sig["reason"],
        "stale": days_old > _STALE_FACTOR * _EXPECTED_GAP_DAYS.get(meta["freq"], 45) + 30,
        "spark": [round(float(v), 4) for v in s.iloc[-24:].values],
    }


def build_catalog(series_map: dict[str, pd.Series]) -> dict:
    """All indicators with their summaries grouped by category, plus per-category signal counts."""
    rows = []
    for meta in INDICATORS:
        row = summarize(meta, series_map.get(meta["fred"]))
        if row:
            rows.append(row)
    by_cat = []
    for cat in CATEGORIES:
        items = [r for r in rows if r["category"] == cat["id"]]
        counts = {k: sum(1 for r in items if r["signal"] == k) for k in ("supportive", "neutral", "cautionary")}
        by_cat.append({"id": cat["id"], "name": cat["name"], "counts": counts, "indicators": items})
    overall = {k: sum(c["counts"][k] for c in by_cat) for k in ("supportive", "neutral", "cautionary")}
    return {"asOf": max((r["date"] for r in rows), default=None), "overall": overall,
            "categories": [c for c in by_cat if c["indicators"]],
            "missing": [m["id"] for m in INDICATORS if m["id"] not in {r["id"] for r in rows}]}


# ── Detail (one indicator, full history) ──────────────────────────────────────

def downsample(s: pd.Series, freq: str, max_points: int = 2600) -> pd.Series:
    """Weekly last-observation for dense (daily) series so a half-century chart stays light."""
    if freq == "D" and len(s) > max_points:
        return s.resample("W").last().dropna()
    return s


def detail(meta: dict, raw: pd.Series | None, recessions: list[dict]) -> dict | None:
    if raw is None:
        return None
    s = transform(raw, meta["transform"], meta.get("scale", 1.0), meta["freq"])
    if len(s) < 3:
        return None
    summary = summarize(meta, raw)
    ten = s[s.index >= s.index[-1] - pd.DateOffset(years=10)]

    def rng(x):
        return {"min": round(float(x.min()), 4), "median": round(float(x.median()), 4), "max": round(float(x.max()), 4),
                "minDate": x.idxmin().strftime("%Y-%m-%d"), "maxDate": x.idxmax().strftime("%Y-%m-%d")}
    pts = downsample(s, meta["freq"])
    return {
        "meta": {k: meta[k] for k in ("id", "fred", "name", "category", "unit", "transform", "freq", "hib", "lead", "horizon",
                                      "what", "why", "read")} | {"band": meta.get("band"), "warnAbove": meta.get("warn_above"),
                                                                  "warnBelow": meta.get("warn_below")},
        "summary": summary,
        "points": [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in pts.items()],
        "recessions": recessions,
        "stats": {"allTime": rng(s), "tenYear": rng(ten) if len(ten) > 2 else None, "observations": int(len(s))},
        "related": [i["id"] for i in INDICATORS if i["category"] == meta["category"] and i["id"] != meta["id"]][:6],
    }


def get_meta(indicator_id: str) -> dict | None:
    return BY_ID.get(indicator_id)
