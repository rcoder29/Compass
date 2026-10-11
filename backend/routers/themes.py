"""Thematic investing — Themes group (Overview, AI, Robotics, Quantum Computing, Space Exploration).

  GET /api/themes            summary of every theme (basket performance, analyst outlook, top setups)
  GET /api/themes/{id}       one theme in full: members with returns/analyst/growth/score, basket chart, outlook, scenarios

Curated framing is in themes_catalog.py; the maths in themes.py. Fundamentals and analyst data come from the same
cached Yahoo fetch as the 100-Bagger Finder (hundred_bagger_data.py), so one background scan serves every theme page;
prices come from the Holdings Performance engine. Results are cached for 15 minutes.
"""
import asyncio
import logging
from datetime import timedelta

import holdings_perf
import hundred_bagger_data as data
import themes
import themes_catalog as catalog
from database import cache_get, cache_set
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

_TTL = timedelta(minutes=15)
_PARTIAL_TTL = timedelta(minutes=2)      # a partial result (fundamentals still loading) is reused briefly so polling can't re-download every price
_SCAN_KEY = "themes:all"
_PRICE_CHUNK = 60


def _universe() -> dict:
    names = {}
    for t in catalog.THEMES:
        for s in t["stocks"]:
            names.setdefault(s["symbol"], s["name"])
        for sym, nm in t["etfs"]:
            names.setdefault(sym, nm)
    names.setdefault("SPY", "SPDR S&P 500 ETF")
    return {"id": "THEMES", "name": "Themes", "kind": "custom", "partial": False, "note": None, "benchmark": "SPY",
            "members": [{"symbol": s, "name": n, "sector": None, "weight": None} for s, n in names.items()]}


def _assemble(metrics: dict[str, dict], partial: dict | None) -> dict:
    uni = _universe()
    symbols = [m["symbol"] for m in uni["members"]]
    daily: dict = {}
    for i in range(0, len(symbols), _PRICE_CHUNK):          # chunked: one bulk request for 200+ symbols invites rate limiting
        daily.update(holdings_perf.download_daily(symbols[i:i + _PRICE_CHUNK]))
    if "SPY" not in daily or len(daily) < 10:
        raise RuntimeError("couldn't download price history (Yahoo may be rate-limiting)")
    anchors = holdings_perf.load_anchors(symbols)
    payload = holdings_perf.build_payload(uni, daily, anchors)
    rows = {r["symbol"]: r for r in payload["holdings"]}
    bench = (payload.get("benchmark") or {}).get("returns")
    built = []
    for t in catalog.THEMES:
        series = themes.basket_series(daily, [s["symbol"] for s in t["stocks"] if s["role"] != "atrisk"])
        etf_perf = {sym: {"returns": rows[sym]["returns"], "price": rows[sym].get("price")} for sym, _ in t["etfs"] if sym in rows}
        built.append(themes.build_theme(t, metrics, rows, bench, series, etf_perf))
    return {"asOf": payload.get("asOf"), "benchmark": bench, "themes": built, "partial": partial,
            "editorialDate": catalog.EDITORIAL_DATE, "periods": themes.PERIODS}


def _build() -> dict:
    cached = cache_get("themes:built", _TTL)
    if cached is not None:
        return {"status": "ready", **cached}
    syms = catalog.stock_symbols()
    have, missing = data.cached_metrics(syms)
    if missing and data.cooling_down(_SCAN_KEY):
        recent = cache_get("themes:partial", _PARTIAL_TTL)
        if recent is not None:
            return {"status": "ready", **recent}
    partial = None
    if missing and data.cooling_down(_SCAN_KEY):
        partial = {"missing": len(missing), "retryInSeconds": data.retry_in(_SCAN_KEY),
                   "note": f"Fundamentals and analyst data for {len(missing)} of {len(syms)} companies couldn't be loaded (Yahoo is limiting requests). Prices and performance are complete; the app retries in a few minutes."}
    elif missing:
        job = data.start_scan(_SCAN_KEY, missing)
        return {"status": "running", "progress": {"done": len(syms) - len(missing) + min(job["done"], len(missing)), "total": len(syms)}, "error": job["error"]}
    out = _assemble({m["symbol"]: m for m in have}, partial)
    if partial:                                      # shown now, kept only briefly, so the retry after the cooldown picks up fresh data
        cache_set("themes:partial", out)
    else:
        cache_set("themes:built", out)
    return {"status": "ready", **out}


async def _run():
    try:
        return await asyncio.get_event_loop().run_in_executor(None, _build)
    except Exception as exc:
        logger.warning("themes failed: %s", exc)
        raise HTTPException(502, f"Couldn't build the themes: {exc}")


@router.get("/api/themes")
async def themes_overview():
    res = await _run()
    if res["status"] != "ready":
        return res
    return {"status": "ready", "asOf": res["asOf"], "benchmark": res["benchmark"], "partial": res["partial"], "periods": res["periods"],
            "editorialDate": res["editorialDate"], "themes": [themes.theme_summary(t) for t in res["themes"]]}


@router.get("/api/themes/{theme_id}")
async def theme_detail(theme_id: str):
    if theme_id not in catalog.BY_ID:
        raise HTTPException(404, f"Unknown theme '{theme_id}'")
    res = await _run()
    if res["status"] != "ready":
        return res
    theme = next(t for t in res["themes"] if t["id"] == theme_id)
    return {"status": "ready", "asOf": res["asOf"], "partial": res["partial"], "editorialDate": res["editorialDate"], "periods": res["periods"],
            "others": [{"id": t["id"], "name": t["name"]} for t in res["themes"] if t["id"] != theme_id], "theme": theme}
