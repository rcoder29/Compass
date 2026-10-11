"""Sector strategy — Sectors group.

  GET /api/sectors/scoreboard          11 SPDR sector ETFs vs SPY: returns 1D..LTD, excess, risk, calendar years
  GET /api/sectors/rotation            relative-rotation graph points (RS-Ratio / RS-Momentum with trails)
  GET /api/sectors/screener            horizon screener (?horizon=tactical|intermediate|strategic&weights=json)
  GET /api/sectors/cycle-fit           sector excess return by cycle phase or growth/inflation quadrant
  GET /api/sectors/backtest            rules-based rotation vs SPY and equal weight (?top_n&cost_bps&defensive)

Computation is in sectors.py; daily prices come from market_history.py and the cycle labels from
economy_regime.py (FRED).
"""
import asyncio
import json
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

import economy_regime
import fred_data
import market_history
import sectors
from database import cache_get, cache_set
from economy_catalog import INDICATORS

logger = logging.getLogger(__name__)
router = APIRouter()

_TTL = timedelta(minutes=30)
_SLOW_TTL = timedelta(hours=6)
_SYMBOLS = sectors.SYMBOLS + [sectors.BENCH, sectors.EQUAL_WEIGHT]


def _prices() -> dict:
    prices = market_history.get_many_daily(_SYMBOLS)
    if sectors.BENCH not in prices or len([s for s in sectors.SYMBOLS if s in prices]) < 8:
        return {}
    return prices


def _regime_months():
    """Monthly regime labels (FRED), or None if FRED can't be reached."""
    series = fred_data.get_many([i["fred"] for i in INDICATORS])
    frame = economy_regime.regime_history(series) if series else None
    return None if frame is None or frame.empty else frame


async def _run(fn, *args):
    return await asyncio.get_event_loop().run_in_executor(None, fn, *args)


def _cached(key: str, ttl, compute):
    hit = cache_get(key, ttl)
    if hit is not None:
        return hit
    out = compute()
    if out is not None:
        cache_set(key, out)
    return out


def _need(result, what: str):
    if result is None:
        raise HTTPException(502, f"Couldn't load enough price history to build the {what}. Try again in a minute.")
    return result


@router.get("/api/sectors/scoreboard")
async def scoreboard():
    def go():
        def compute():
            p = _prices()
            return sectors.build_scoreboard(p) if p else None
        return _cached("sectors:scoreboard", _TTL, compute)
    return _need(await _run(go), "scoreboard")


@router.get("/api/sectors/rotation")
async def rotation():
    def go():
        def compute():
            p = _prices()
            return sectors.build_rotation(p) if p else None
        return _cached("sectors:rotation", _TTL, compute)
    return _need(await _run(go), "rotation map")


def _cycle_fit(group: str):
    def compute():
        p = _prices()
        reg = _regime_months()
        if not p or reg is None:
            return None
        return sectors.cycle_fit(p, reg, group)
    return _cached(f"sectors:cyclefit:{group}", _SLOW_TTL, compute)


@router.get("/api/sectors/cycle-fit")
async def cycle_fit(group: str = Query("phase", pattern="^(phase|quadrant)$")):
    result = _need(await _run(_cycle_fit, group), "cycle-fit table")
    reg = await _run(_regime_months)
    if reg is not None:
        last = reg.iloc[-1]
        result = {**result, "current": {"phase": last["phase"], "quadrant": last["quadrant"], "asOf": reg.index[-1].strftime("%Y-%m-%d")}}
    return result


def _parse_weights(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        w = json.loads(raw)
        if not isinstance(w, dict):
            raise ValueError
        return {k: float(v) for k, v in w.items() if k in sectors.FACTORS and 0 <= float(v) <= 100}
    except (ValueError, TypeError):
        raise HTTPException(400, "weights must be a JSON object like {\"momentum\": 40, \"trend\": 30}")


@router.get("/api/sectors/screener")
async def screener(horizon: str = Query("intermediate"), weights: str | None = None):
    if horizon not in sectors.HORIZONS:
        raise HTTPException(404, f"Unknown horizon '{horizon}'")
    w = _parse_weights(weights)

    def go():
        p = _prices()
        if not p:
            return None
        phase_name, fit_for_phase = None, None
        reg = _regime_months()
        if reg is not None:
            phase = reg.iloc[-1]["phase"]
            phase_name = economy_regime.PHASES[phase][0]
            fit_for_phase = sectors.cycle_fit_for_phase(_cycle_fit("phase"), phase)
        return sectors.build_screener(p, horizon, w, fit_for_phase, phase_name)
    return _need(await _run(go), "screener")


@router.get("/api/sectors/backtest")
async def backtest(top_n: int = Query(3, ge=1, le=6), cost_bps: float = Query(10.0, ge=0, le=100), defensive: bool = True):
    def go():
        def compute():
            p = _prices()
            return sectors.run_backtest(p, top_n, cost_bps, defensive) if p else None
        return _cached(f"sectors:backtest:{top_n}:{cost_bps:g}:{int(defensive)}", _SLOW_TTL, compute)
    return _need(await _run(go), "backtest")
