"""Home dashboard → market regime card.

  GET /api/home/regime     compact regime summary: cycle phase, quadrant, recession risk, sector leaders/laggards, strongest themes,
                           most-shorted stocks, and what changed since an earlier day

Built by regime_summary.py (shared with the digest). It only reads fast or already-cached data and never starts a slow scan:
themes and short interest appear once their pages have been opened and are otherwise left out. Cached for ten minutes.
"""
import asyncio
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException

import regime_summary
from database import cache_get, cache_set

logger = logging.getLogger(__name__)
router = APIRouter()

_TTL = timedelta(minutes=10)


def _build() -> dict:
    cached = cache_get("home:regime", _TTL)
    if cached is not None:
        return cached
    out = regime_summary.load_summary()
    if out.get("regime") or out.get("sectors"):           # don't cache a result where every source failed
        cache_set("home:regime", out)
    return out


@router.get("/api/home/regime")
async def home_regime():
    try:
        return await asyncio.get_event_loop().run_in_executor(None, _build)
    except Exception as exc:
        logger.warning("home regime failed: %s", exc)
        raise HTTPException(502, f"Couldn't build the market regime summary: {exc}")
