"""Holdings Performance — Markets → Holdings Performance.

Returns over 1D … 10Y and life-to-date for every holding of an index or ETF, ranked by YTD.
The work is in holdings_perf.py; this is the HTTP surface.

  GET /api/holdings-performance/universes      preset indexes and sector ETFs for the picker
  GET /api/holdings-performance?universe=SPY   returns table for an index, index ETF, sector SPDR,
                                               or any ETF's top holdings
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

import holdings_perf

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/holdings-performance/universes")
def universes():
    return {"presets": holdings_perf.preset_universes(), "periods": holdings_perf.PERIODS}


@router.get("/api/holdings-performance")
async def get_holdings_performance(universe: str = "SP500"):
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: holdings_perf.holdings_performance(universe))
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.warning("holdings performance %s failed: %s", universe, exc)
        raise HTTPException(502, f"Couldn't build the performance table: {exc}")
