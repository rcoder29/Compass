"""Economy — Economy → Indicators / Regime Dashboard / Indicator Studies.

  GET /api/economy/indicators        every catalog indicator with latest reading, long-run percentile,
                                     trend and an equity-conditions signal, grouped by category
  GET /api/economy/indicator/{id}    one indicator's full history (with NBER recession spans) and its
                                     "what it means" text
  GET /api/economy/regime            growth/inflation quadrant, recession-risk score and its components,
                                     cycle phase, track record vs NBER recessions, and 10 years of history
  GET /api/economy/studies           the list of indicator studies
  GET /api/economy/studies/{id}      forward S&P 500 / sector returns after that condition began

Data is FRED's keyless CSV feed (fred_data.py); the maths is in economy.py. Values are the current,
revised figures, not what was known at each release date.
"""
import asyncio
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException

import economy
import economy_regime
import economy_studies
import fred_data
import market_history
from database import cache_get, cache_set
from economy_catalog import INDICATORS

logger = logging.getLogger(__name__)
router = APIRouter()

_CATALOG_TTL = timedelta(minutes=30)
_DETAIL_TTL = timedelta(minutes=30)


def _catalog() -> dict:
    cached = cache_get("economy:catalog", _CATALOG_TTL)
    if cached is not None:
        return cached
    series = fred_data.get_many([i["fred"] for i in INDICATORS])
    result = economy.build_catalog(series)
    if result["categories"]:
        cache_set("economy:catalog", result)
    return result


def _detail(indicator_id: str) -> dict | None:
    meta = economy.get_meta(indicator_id)
    if meta is None:
        return None
    key = f"economy:detail:{indicator_id}"
    cached = cache_get(key, _DETAIL_TTL)
    if cached is not None:
        return cached
    recessions = fred_data.recession_periods(fred_data.get_series("USREC"))
    result = economy.detail(meta, fred_data.get_series(meta["fred"]), recessions)
    if result:
        cache_set(key, result)
    return result


_REGIME_TTL = timedelta(minutes=30)
_KEY_INDICATORS = ["curve10_3m", "unrate", "claims", "corepce", "fedfunds", "dgs10", "hy", "vix"]


def _regime() -> dict | None:
    cached = cache_get("economy:regime", _REGIME_TTL)
    if cached is not None:
        return cached
    series = fred_data.get_many([i["fred"] for i in INDICATORS] + ["USREC"])
    result = economy_regime.build_regime(series, fred_data.recession_periods(series.get("USREC")))
    if result is None:
        return None
    by_id = {r["id"]: r for c in economy.build_catalog(series)["categories"] for r in c["indicators"]}
    result["keyIndicators"] = [by_id[i] for i in _KEY_INDICATORS if i in by_id]
    cache_set("economy:regime", result)
    return result


@router.get("/api/economy/regime")
async def economy_regime_endpoint():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _regime)
    if result is None:
        raise HTTPException(502, "Couldn't load enough economic data from FRED to assess the regime. Try again in a minute.")
    return result


_STUDY_TTL = timedelta(hours=6)
_STUDY_FRED = ["USREC", "FEDFUNDS", "DFII10", "DTWEXBGS", "DCOILWTICO"]


@router.get("/api/economy/studies")
async def economy_studies_list():
    return {"studies": economy_studies.study_list()}


def _study(study_id: str) -> dict | None:
    key = f"economy:study:{study_id}"
    cached = cache_get(key, _STUDY_TTL)
    if cached is not None:
        return cached
    study = economy_studies.BY_ID_STUDY[study_id]
    series = fred_data.get_many([i["fred"] for i in INDICATORS] + _STUDY_FRED)
    prices = market_history.get_many_monthly(["^GSPC", "SPY"] + economy_studies.SECTOR_ETFS)
    sp = prices.get("^GSPC")
    if sp is None or not series:
        return None
    etfs = {k: v for k, v in prices.items() if k in economy_studies.SECTOR_ETFS}
    result = economy_studies.run_study(study, series, sp, etfs, prices.get("SPY"))
    if result is None:
        return {"unavailable": True, "study": {k: study[k] for k in ("id", "name", "condition", "question", "indicators")}}
    result["headline"] = economy_studies.headline(result)
    cache_set(key, result)
    return result


@router.get("/api/economy/studies/{study_id}")
async def economy_study(study_id: str):
    if study_id not in economy_studies.BY_ID_STUDY:
        raise HTTPException(404, f"Unknown study '{study_id}'")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _study, study_id)
    if result is None:
        raise HTTPException(502, "Couldn't load the economic or market history for this study. Try again in a minute.")
    return result


@router.get("/api/economy/indicators")
async def economy_indicators():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _catalog)
    if not result["categories"]:
        raise HTTPException(502, "Couldn't load economic data from FRED right now. Try again in a minute.")
    return result


@router.get("/api/economy/indicator/{indicator_id}")
async def economy_indicator(indicator_id: str):
    if economy.get_meta(indicator_id) is None:
        raise HTTPException(404, f"Unknown indicator '{indicator_id}'")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: _detail(indicator_id))
    if result is None:
        raise HTTPException(502, "Couldn't load that series from FRED right now.")
    return result
