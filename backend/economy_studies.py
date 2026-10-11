"""Indicator studies — what has each macro condition historically meant for the stock market?

A study asks: *after this condition appeared, what did the S&P 500 (and each sector) do over the next 1, 3, 6,
12 and 36 months, compared with a normal month?*  Examples: the yield curve inverting, the Sahm rule
triggering, jobless claims surging, inflation above 5%, credit spreads blowing out.

How the numbers are built (and why they are fairer than a naive version):
  - A condition is a True/False state per month. An *episode* is a run of True months (runs closer than six
    months apart are merged); forward returns are measured from the start of each episode. Counting every
    month in the state is also reported, but those windows overlap heavily, so episodes are the honest sample size.
  - **Publication lag.** Monthly data isn't known when the month ends (unemployment arrives the following month),
    so the entry is the close of the month *after* the observation for monthly series, and two months after
    for quarterly ones. Without this the studies would trade on information nobody had yet.
  - The baseline is the same horizon's return from *every* month over the same period, so "above average" means
    above what you'd have got by simply being invested.
  - S&P 500 returns are price-only (the long index history excludes dividends); the baseline is built the same
    way, so the comparison holds. Sector figures use dividend-adjusted ETFs and cover 1999 onward, so they rest on
    only a few episodes and are marked when thin.

Limits stated on every page: FRED serves revised data (so conditions look cleaner than they did in real time),
the number of independent episodes is small, and past relationships are not guarantees.
"""
import math

import numpy as np
import pandas as pd

import economy_regime as er
from market_history import forward_returns

HORIZONS = [1, 3, 6, 12, 36]
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC"]
MIN_GAP_MONTHS = 6
THIN_EPISODES = 4          # fewer independent episodes than this is flagged as thin
HISTOGRAM_EDGES = [-60, -40, -30, -20, -10, 0, 10, 20, 30, 40, 60, 100]


# ── state builders (each returns a boolean monthly Series) ────────────────────

def _ind(m, cid):
    return er._indicator_series(cid, m)


def _fred_monthly(m, fred_id):
    raw = m.get(fred_id)
    return None if raw is None else er.monthly(raw)


def _yoy_of(m, fred_id):
    s = _fred_monthly(m, fred_id)
    return None if s is None else (s / s.shift(12) - 1.0) * 100.0


def _need(*series):
    return all(s is not None and len(s) > 24 for s in series)


def st_curve_inverted(m):
    c = _ind(m, "curve10_3m")
    return None if not _need(c) else c < 0


def st_curve_reverted(m):
    """The first months after an inversion of at least three months ends: the stretch that has often preceded recessions."""
    c = _ind(m, "curve10_3m")
    if not _need(c):
        return None
    inv = (c < 0).astype(float)
    return (c >= 0) & (inv.rolling(6, min_periods=1).max() == 1) & (inv.rolling(18, min_periods=1).sum() >= 3)


def st_sahm(m):
    s = _ind(m, "sahm")
    return None if not _need(s) else s >= 0.5


def st_claims(m):
    s = _ind(m, "claims")
    return None if not _need(s) else s >= 1.2 * s.rolling(12, min_periods=6).min()


def st_cfnai(m):
    s = _ind(m, "cfnai")
    return None if not _need(s) else s <= -0.7


def st_cpi_high(m):
    s = _ind(m, "cpi")
    return None if not _need(s) else s >= 5.0


def st_disinflation(m):
    s = _ind(m, "corecpi")
    return None if not _need(s) else (s.rolling(12, min_periods=6).max() - s) >= 1.0


def st_fed_cutting(m):
    s = er.monthly(m["FEDFUNDS"]) if "FEDFUNDS" in m else None
    return None if not _need(s) else s <= s.shift(6) - 0.5


def st_fed_hiking(m):
    s = er.monthly(m["FEDFUNDS"]) if "FEDFUNDS" in m else None
    return None if not _need(s) else s >= s.shift(6) + 1.0


def st_credit(m):
    s = _ind(m, "baa")
    return None if not _need(s) else s >= 3.0


def st_nfci(m):
    s = _ind(m, "nfci")
    return None if not _need(s) else s > 0


def st_real_yield(m):
    s = _fred_monthly(m, "DFII10")
    return None if not _need(s) else s >= 2.0


def st_sentiment(m):
    s = _ind(m, "umcsent")
    if not _need(s):
        return None
    return er.expanding_percentile(s, min_periods=60) <= 10.0


def st_philly(m):
    s = _ind(m, "philly")
    return None if not _need(s) else s <= -10


def st_dollar(m):
    y = _yoy_of(m, "DTWEXBGS")
    return None if not _need(y) else y >= 10.0


def st_oil(m):
    y = _yoy_of(m, "DCOILWTICO")
    return None if not _need(y) else y >= 50.0


def st_permits(m):
    s = _ind(m, "permit")
    return None if not _need(s) else s <= -20.0


def st_unemployment(m):
    s = _ind(m, "unrate")
    return None if not _need(s) else (s - s.shift(6)) >= 0.5


def st_risk(m):
    """Scored only over the period the regime model covers (before that, only one or two components exist)."""
    h = er.regime_history(m)
    return None if h.empty or h["risk"].dropna().empty else h["risk"].dropna() >= 40.0


STUDIES = [
    {"id": "curve-inverted", "name": "Yield curve inverted", "state": st_curve_inverted, "lag": 0, "indicators": ["curve10_3m"],
     "condition": "The 10-year Treasury yield is below the 3-month bill yield.",
     "question": "How has the stock market done after the yield curve inverted?"},
    {"id": "curve-reverted", "name": "Yield curve un-inverts", "state": st_curve_reverted, "lag": 0, "indicators": ["curve10_3m"],
     "condition": "The curve returns to positive after at least three months inverted.",
     "question": "What happens once an inversion ends — when recessions have often begun?"},
    {"id": "sahm", "name": "Sahm Rule triggered", "state": st_sahm, "lag": 1, "indicators": ["sahm", "unrate"],
     "condition": "The 3-month average unemployment rate is 0.5 points above its 12-month low.",
     "question": "How has the market done after the labor market's recession trigger fired?"},
    {"id": "claims-surge", "name": "Jobless claims surge", "state": st_claims, "lag": 0, "indicators": ["claims"],
     "condition": "The 4-week average of initial claims is 20%+ above its 12-month low.",
     "question": "What follows a sharp rise in layoffs?"},
    {"id": "activity-weak", "name": "Economic activity contracting", "state": st_cfnai, "lag": 1, "indicators": ["cfnai"],
     "condition": "The Chicago Fed National Activity Index (3-mo avg) is at or below -0.7.",
     "question": "How does the market behave once broad activity is contracting?"},
    {"id": "inflation-high", "name": "Inflation above 5%", "state": st_cpi_high, "lag": 1, "indicators": ["cpi"],
     "condition": "Headline CPI is 5% or more above a year ago.",
     "question": "What has high inflation meant for stocks?"},
    {"id": "disinflation", "name": "Inflation falling from a peak", "state": st_disinflation, "lag": 1, "indicators": ["corecpi"],
     "condition": "Core CPI inflation is at least one point below its 12-month high.",
     "question": "Does disinflation help the market?"},
    {"id": "fed-cutting", "name": "Fed cutting rates", "state": st_fed_cutting, "lag": 1, "indicators": ["fedfunds"],
     "condition": "The Fed funds rate is at least half a point below six months earlier.",
     "question": "Are rate-cutting cycles good for stocks?"},
    {"id": "fed-hiking", "name": "Fed hiking rates", "state": st_fed_hiking, "lag": 1, "indicators": ["fedfunds"],
     "condition": "The Fed funds rate is at least one point above six months earlier.",
     "question": "How have markets fared during rapid tightening?"},
    {"id": "credit-stress", "name": "Credit spreads wide", "state": st_credit, "lag": 0, "indicators": ["baa"],
     "condition": "The Baa corporate bond spread over Treasuries is 3 points or more.",
     "question": "What do wide credit spreads say about the next year?"},
    {"id": "tight-conditions", "name": "Financial conditions tight", "state": st_nfci, "lag": 0, "indicators": ["nfci"],
     "condition": "The Chicago Fed financial conditions index is above zero (tighter than average).",
     "question": "How has the market done when financial conditions tighten?"},
    {"id": "real-yield-high", "name": "Real yields above 2%", "state": st_real_yield, "lag": 0, "indicators": ["realyield"],
     "condition": "The 10-year TIPS (real) yield is 2% or higher. Available from 2003.",
     "question": "How have markets handled restrictive real interest rates?"},
    {"id": "sentiment-low", "name": "Consumer sentiment at a low", "state": st_sentiment, "lag": 0, "indicators": ["umcsent"],
     "condition": "University of Michigan sentiment is in its bottom decile of history to date.",
     "question": "Is pessimism a buying signal?"},
    {"id": "factory-weak", "name": "Regional factory surveys negative", "state": st_philly, "lag": 0, "indicators": ["philly"],
     "condition": "The Philadelphia Fed manufacturing index is -10 or lower.",
     "question": "What has factory weakness meant for stocks?"},
    {"id": "dollar-surge", "name": "Dollar surges", "state": st_dollar, "lag": 0, "indicators": ["dollar"],
     "condition": "The broad dollar index is 10%+ above a year ago. Available from 2006.",
     "question": "How have stocks done when the dollar spikes?"},
    {"id": "oil-spike", "name": "Oil price spike", "state": st_oil, "lag": 0, "indicators": ["oil"],
     "condition": "WTI crude is 50%+ above a year ago.",
     "question": "What do big oil shocks mean for the market?"},
    {"id": "housing-slump", "name": "Building permits collapse", "state": st_permits, "lag": 1, "indicators": ["permit"],
     "condition": "Building permits are 20%+ below a year ago.",
     "question": "Does a housing downturn warn of weak markets?"},
    {"id": "unemployment-rising", "name": "Unemployment rising", "state": st_unemployment, "lag": 1, "indicators": ["unrate"],
     "condition": "The unemployment rate is at least half a point above six months earlier.",
     "question": "What follows a clear rise in unemployment?"},
    {"id": "recession-risk", "name": "Recession-risk score elevated", "state": st_risk, "lag": 1, "indicators": ["curve10_3m", "sahm", "claims", "cfnai"],
     "condition": "This app's composite recession-risk score is 40 or higher.",
     "question": "How has the market done when the recession-risk score was elevated?"},
]
BY_ID_STUDY = {s["id"]: s for s in STUDIES}


# ── episodes ──────────────────────────────────────────────────────────────────

def episodes(state: pd.Series, min_gap: int = MIN_GAP_MONTHS) -> list[dict]:
    """Runs of True months as [{start, end, months}], merging runs separated by fewer than `min_gap` months."""
    st = state.fillna(False).astype(bool)
    runs, start, prev = [], None, None
    for d, v in st.items():
        if v and start is None:
            start = d
        if not v and start is not None:
            runs.append([start, prev])
            start = None
        prev = d
    if start is not None:
        runs.append([start, prev])
    merged = []
    for s, e in runs:
        if merged and (s.year - merged[-1][1].year) * 12 + (s.month - merged[-1][1].month) <= min_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [{"start": s, "end": e, "months": (e.year - s.year) * 12 + (e.month - s.month) + 1} for s, e in merged]


def _entry(start: pd.Timestamp, lag: int) -> pd.Timestamp:
    return start + pd.DateOffset(months=lag)


# ── statistics ────────────────────────────────────────────────────────────────

def _stats(values: list[float]) -> dict | None:
    v = np.array([x for x in values if x is not None and not math.isnan(x)], dtype=float)
    if len(v) == 0:
        return None
    return {"n": int(len(v)), "mean": float(v.mean()), "median": float(np.median(v)), "pctPositive": float((v > 0).mean()),
            "best": float(v.max()), "worst": float(v.min())}


def _round_stats(s: dict | None) -> dict | None:
    return None if s is None else {k: (round(x, 4) if isinstance(x, float) else x) for k, x in s.items()}


def baseline(prices: pd.Series, months: int, start: pd.Timestamp) -> dict | None:
    fr = forward_returns(prices, months)
    return _round_stats(_stats(list(fr[fr.index >= start].dropna().values)))


def histogram(values: list[float], edges: list[float] = HISTOGRAM_EDGES) -> list[float]:
    """Share (%) of values falling in each bin of `edges` (percent returns); first/last bins are open-ended."""
    if not values:
        return [0.0] * (len(edges) - 1)
    pct = np.clip(np.array(values) * 100.0, edges[0] + 1e-9, edges[-1] - 1e-9)
    counts, _ = np.histogram(pct, bins=edges)
    return [round(float(c) / len(values) * 100.0, 1) for c in counts]


def sector_response(eps_entries: list[pd.Timestamp], etfs: dict[str, pd.Series], spy: pd.Series | None, months: int = 12) -> list[dict]:
    """Average excess return vs SPY over the next `months` for each sector across the study's episodes (1999+)."""
    if spy is None:
        return []
    out = []
    for sym in SECTOR_ETFS:
        px = etfs.get(sym)
        if px is None:
            continue
        rows = []
        for e in eps_entries:
            if e not in px.index or e not in spy.index:
                continue
            exit_ = e + pd.DateOffset(months=months)
            if exit_ not in px.index or exit_ not in spy.index:
                continue
            rows.append(float(px.loc[exit_] / px.loc[e] - 1.0) - float(spy.loc[exit_] / spy.loc[e] - 1.0))
        if rows:
            out.append({"symbol": sym, "n": len(rows), "avgExcess": round(float(np.mean(rows)), 4),
                        "pctBeating": round(float((np.array(rows) > 0).mean()), 3), "thin": len(rows) < THIN_EPISODES})
    return sorted(out, key=lambda r: -r["avgExcess"])


def run_study(study: dict, series_map: dict, sp: pd.Series, etfs: dict[str, pd.Series], spy: pd.Series | None) -> dict | None:
    state = study["state"](series_map)
    if state is None or state.dropna().empty or not state.any():
        return None
    lag = study["lag"]
    eps = episodes(state)
    sample_start = state.dropna().index[0] + pd.DateOffset(months=lag)
    entries = [_entry(e["start"], lag) for e in eps]
    frs = {h: forward_returns(sp, h) for h in HORIZONS}

    horizons = []
    for h in HORIZONS:
        ep_vals = [frs[h].get(en) for en in entries]
        ep_vals = [float(x) for x in ep_vals if x is not None and not math.isnan(x)]
        month_entries = [d + pd.DateOffset(months=lag) for d in state[state].index]
        all_vals = [float(frs[h].get(en)) for en in month_entries if en in frs[h].index and not math.isnan(frs[h].get(en))]
        horizons.append({"months": h, "episodes": _round_stats(_stats(ep_vals)), "allMonths": _round_stats(_stats(all_vals)),
                         "baseline": baseline(sp, h, sample_start)})

    ep_rows = []
    for e, en in zip(eps, entries):
        ep_rows.append({"start": e["start"].strftime("%Y-%m"), "end": e["end"].strftime("%Y-%m"), "months": e["months"],
                        "entry": en.strftime("%Y-%m"),
                        "forward": {str(h): (None if (r := frs[h].get(en)) is None or math.isnan(r) else round(float(r), 4)) for h in HORIZONS}})
    twelve = [r["forward"]["12"] for r in ep_rows if r["forward"]["12"] is not None]
    base12 = forward_returns(sp, 12)
    base12_vals = list(base12[base12.index >= sample_start].dropna().values)
    n_ep = (horizons[3]["episodes"] or {}).get("n", 0)
    return {
        "study": {k: study[k] for k in ("id", "name", "condition", "question", "indicators")} | {"lagMonths": lag},
        "episodeCount": len(eps), "monthsInState": int(state.sum()), "sampleStart": sample_start.strftime("%Y-%m"),
        "sampleEnd": sp.index[-1].strftime("%Y-%m"),
        "currentlyActive": bool(state.iloc[-1]) if len(state) else False,
        "horizons": horizons, "episodes": ep_rows[-15:],
        "distribution12m": {"edges": HISTOGRAM_EDGES, "study": histogram(twelve), "baseline": histogram(base12_vals)},
        "sectors12m": sector_response([en for en in entries if en >= pd.Timestamp("1999-01-01")], etfs, spy, 12),
        "thin": n_ep < THIN_EPISODES,
        "notes": notes(n_ep, lag),
    }


def notes(n_episodes: int, lag: int) -> list[str]:
    out = [f"{n_episodes} independent episode{'s' if n_episodes != 1 else ''} with a full 12-month window. "
           + ("That is too few to draw firm conclusions; treat the figures as anecdotes." if n_episodes < THIN_EPISODES
              else "Still a small sample: macro regimes are rare events.")]
    out.append("Entry is " + ("the close of the observation month." if lag == 0 else
                              f"the close {lag} month{'s' if lag > 1 else ''} after the observation month, because that is when the data would have been published."))
    out.append("Uses FRED's revised figures, so conditions look cleaner than they did in real time. S&P 500 returns exclude dividends (the baseline does too).")
    return out


def headline(result: dict) -> str | None:
    """One sentence of plain English from the 12-month figures."""
    h12 = next((h for h in result["horizons"] if h["months"] == 12), None)
    if not h12 or not h12["episodes"] or not h12["baseline"]:
        return None
    e, b = h12["episodes"], h12["baseline"]
    return (f"In the 12 months after \u201c{result['study']['name']}\u201d began, the S&P 500 averaged {e['mean']:+.1%} "
            f"versus {b['mean']:+.1%} for any 12-month period, and was higher {e['pctPositive']:.0%} of the time "
            f"({e['n']} episodes).")


def study_list() -> list[dict]:
    return [{"id": s["id"], "name": s["name"], "question": s["question"], "condition": s["condition"], "indicators": s["indicators"]}
            for s in STUDIES]
