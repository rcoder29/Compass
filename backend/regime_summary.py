"""One compact "where are we?" summary, shared by the Home dashboard card and the daily/weekly digest.

It stitches together the newest Economy, Sectors, Themes and Short Interest work, but never triggers a slow job:
  - the economic regime (cycle phase, quadrant, recession risk) is computed from FRED, which is cached and takes a few seconds cold;
  - the sector scoreboard comes from daily ETF prices, also cached and fast;
  - themes and short interest are heavy background scans, so they are read from the cache *only* (any age up to a day) and are left out
    when nobody has opened those pages recently. A missing part is simply absent from the summary.

Each part is built independently, so one failing source drops that part and is named in `errors` instead of sinking the summary.
It also keeps a small per-day history (phase and recession score) so the summary can say what changed since an earlier day.

Pure summarisers take the raw payloads of the existing endpoints; `load_summary()` does the fetching and caching.
"""
import logging
from datetime import date, timedelta

from database import cache_get, cache_set

logger = logging.getLogger(__name__)

HISTORY_KEY = "regime:history"
HISTORY_DAYS = 21
RISK_CHANGE = 5.0          # a move in the recession-risk score smaller than this isn't reported as a change
STALE = timedelta(hours=24)


def summarize_regime(raw: dict | None) -> dict | None:
    """Phase, quadrant and recession risk from the /api/economy/regime payload."""
    if not raw:
        return None
    rec = raw.get("recession") or {}
    comps = rec.get("components") or []
    curve = rec.get("curve") or {}
    return {
        "asOf": raw.get("asOf"),
        "phase": {"id": raw["phase"]["id"], "name": raw["phase"]["name"]},
        "quadrant": {"id": raw["quadrant"]["id"], "name": raw["quadrant"]["name"]},
        "growth": raw.get("growth", {}).get("label"), "inflation": raw.get("inflation", {}).get("label"),
        "riskScore": rec.get("score"), "riskBand": rec.get("band"),
        "flashing": [c["name"] for c in comps if c.get("status") == "high"],
        "watching": [c["name"] for c in comps if c.get("status") == "watch"],
        "curveInverted": curve.get("invertedNow"),
    }


def summarize_sectors(sb: dict | None, count: int = 3) -> dict | None:
    """Leaders and laggards over three months, measured against SPY, from the /api/sectors/scoreboard payload."""
    if not sb or not sb.get("sectors"):
        return None
    rows = []
    for s in sb["sectors"]:
        total = (s["returns"].get("3M") or {}).get("total")
        excess = (s.get("excess") or {}).get("3M")
        if total is not None and excess is not None:
            rows.append({"symbol": s["symbol"], "name": s["name"], "ret3m": total, "excess3m": excess})
    if len(rows) < 2 * count:
        return None
    rows.sort(key=lambda r: -r["excess3m"])
    spy = (sb.get("benchmark", {}).get("returns", {}).get("3M") or {}).get("total")
    return {"asOf": sb.get("asOf"), "spy3m": spy, "top": rows[:count], "bottom": list(reversed(rows[-count:]))}


def summarize_themes(built: dict | None, count: int = 3) -> dict | None:
    """The strongest and weakest themes over three months against SPY, from the assembled themes payload."""
    if not built or not built.get("themes"):
        return None
    spy = (built.get("benchmark") or {}).get("3M")
    rows = []
    for t in built["themes"]:
        ret = (t.get("basket", {}).get("3M") or {}).get("mean")
        if ret is not None and spy is not None:
            rows.append({"id": t["id"], "name": t["name"], "short": t.get("short") or t["name"], "ret3m": ret, "vsSpy": ret - spy})
    if len(rows) < 2 * min(count, 2):
        return None
    rows.sort(key=lambda r: -r["vsSpy"])
    return {"asOf": built.get("asOf"), "spy3m": spy, "top": rows[:count], "bottom": list(reversed(rows[-min(count, 2):]))}


def summarize_shorts(built: dict | None, count: int = 5) -> dict | None:
    """The most shorted names with their borrow fee and equity-vs-credit read, from the short-interest payload."""
    if not built or not built.get("rows"):
        return None
    rows = [{"symbol": r["symbol"], "name": r["name"], "siPctFloat": r["siPctFloat"], "changePct": r.get("changePct"),
             "fee": (r.get("borrow") or {}).get("fee"), "displacement": r["displacement"]["key"], "displacementLabel": r["displacement"]["label"]}
            for r in built["rows"][:count]]
    s = built.get("summary") or {}
    return {"settlement": built.get("settlement"), "top": rows, "count": s.get("count", len(built["rows"])), "above30": s.get("above30"),
            "hardToBorrow": s.get("hardToBorrow"), "creditConfirms": (s.get("displacement") or {}).get("confirmed"),
            "biggestIncreases": s.get("biggestIncreases") or []}


# ── What changed ──────────────────────────────────────────────────────────────

def changes_since(current: dict | None, history: dict[str, dict], today: str) -> dict | None:
    """Compare today's regime with the most recent earlier day in `history` ({'YYYY-MM-DD': {phase, riskScore}}), or None."""
    if not current:
        return None
    earlier = sorted(d for d in history if d < today)
    if not earlier:
        return None
    prev_day = earlier[-1]
    prev = history[prev_day]
    out = {"since": prev_day, "phaseFrom": None, "phaseTo": None, "riskFrom": None, "riskTo": None}
    if prev.get("phase") and prev["phase"] != current["phase"]["name"]:
        out["phaseFrom"], out["phaseTo"] = prev["phase"], current["phase"]["name"]
    if prev.get("riskScore") is not None and current.get("riskScore") is not None and abs(current["riskScore"] - prev["riskScore"]) >= RISK_CHANGE:
        out["riskFrom"], out["riskTo"] = prev["riskScore"], current["riskScore"]
    return out if (out["phaseTo"] or out["riskTo"]) else None


def record_history(history: dict[str, dict], today: str, regime: dict | None) -> dict[str, dict]:
    """History with today's entry set and anything older than HISTORY_DAYS dropped."""
    out = dict(history)
    if regime:
        out[today] = {"phase": regime["phase"]["name"], "riskScore": regime.get("riskScore")}
    cutoff = (date.fromisoformat(today) - timedelta(days=HISTORY_DAYS)).isoformat()
    return {d: v for d, v in out.items() if d >= cutoff}


def assemble(regime_raw, sectors_raw, themes_raw, shorts_raw, history: dict[str, dict], today: str, errors: dict | None = None) -> dict:
    regime = summarize_regime(regime_raw)
    return {"date": today, "regime": regime, "changes": changes_since(regime, history, today), "sectors": summarize_sectors(sectors_raw),
            "themes": summarize_themes(themes_raw), "shorts": summarize_shorts(shorts_raw), "errors": errors or {}}


# ── Loading (cached; never starts a slow scan) ────────────────────────────────

def _regime_raw():
    from routers import economy
    return economy._regime()


def _sectors_raw():
    cached = cache_get("sectors:scoreboard", STALE)
    if cached is not None:
        return cached
    import sectors
    from routers import sectors as sectors_router
    prices = sectors_router._prices()
    out = sectors.build_scoreboard(prices) if prices else None
    if out is not None:
        cache_set("sectors:scoreboard", out)
    return out


def _themes_raw():
    return cache_get("themes:built", STALE)             # cache only: a theme scan reads ~200 companies


def _shorts_raw():
    return cache_get("short:built:100:300", STALE)       # cache only: the first short-interest build takes minutes


LOADERS = {"regime": _regime_raw, "sectors": _sectors_raw, "themes": _themes_raw, "shorts": _shorts_raw}


def load_summary(today: date | None = None, loaders: dict | None = None) -> dict:
    """The live summary. Each source is loaded independently; failures are listed in `errors`. Records today's regime in the history."""
    today_s = (today or date.today()).isoformat()
    loaders = {**LOADERS, **(loaders or {})}
    raw, errors = {}, {}
    for name, fn in loaders.items():
        try:
            raw[name] = fn()
        except Exception as exc:
            logger.warning("regime summary: %s failed: %s", name, exc)
            raw[name], errors[name] = None, f"{type(exc).__name__}: {exc}"[:160]
    history = cache_get(HISTORY_KEY, timedelta(days=HISTORY_DAYS + 1)) or {}
    out = assemble(raw.get("regime"), raw.get("sectors"), raw.get("themes"), raw.get("shorts"), history, today_s, errors)
    if out["regime"]:
        cache_set(HISTORY_KEY, record_history(history, today_s, out["regime"]))
    return out
