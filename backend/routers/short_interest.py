"""Short Interest Monitor — Markets → Short Interest.

  GET /api/short-interest?limit=100&min_cap=300     the most heavily shorted stocks (share of float), each with its borrow
                                                    fee, bond yields/spreads and an equity-vs-credit displacement read

The first request does the slow work in stages, each in a background scan the page polls (status "running" with the
stage and progress): float and market caps for ~600 candidate stocks, interest-expense statements for the top names,
and the corporate-bond ETFs' holdings. After that everything is cached (hours to a day). Maths in short_interest.py,
downloads in short_interest_data.py.
"""
import asyncio
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

import hundred_bagger_data as scanner
import short_interest as si
import short_interest_data as data
from database import cache_get, cache_set

logger = logging.getLogger(__name__)
router = APIRouter()

_TTL = timedelta(minutes=15)


def _running(job: dict, stage: int, label: str, done_before: int, total: int) -> dict:
    return {"status": "running", "stage": stage, "stages": 3, "stageLabel": label,
            "progress": {"done": done_before + min(job["done"], total - done_before), "total": total}, "error": job["error"]}


def _build(limit: int, min_cap_m: float) -> dict:
    key = f"short:built:{limit}:{int(min_cap_m)}"
    cached = cache_get(key, _TTL)
    if cached is not None:
        return {"status": "ready", **cached}
    notes: list[str] = []
    partial = False

    # Stage 1: float and market cap for the candidates FINRA says are heavily shorted
    fin = data.finra_candidates()
    finra = {r["symbol"]: r for r in fin["rows"]}
    infos, missing = data.cached_many("si:info:", list(finra))
    if missing:
        if scanner.cooling_down(data.CANDIDATE_JOB):
            partial = True
            notes.append(f"Float data for {len(missing)} of {len(finra)} candidates couldn't be loaded (Yahoo is limiting requests); those are left out for now.")
        else:
            job = scanner.start_scan(data.CANDIDATE_JOB, missing, fetch=data.fetch_info)
            return _running(job, 1, "Reading float and market caps", len(finra) - len(missing), len(finra))
    ranked = si.rank_rows(finra, infos, min_cap_m * 1e6, limit)
    top = [r["symbol"] for r in ranked]

    # Stage 2: interest expense from the income statements of the top names
    credit_raw, missing = data.cached_many("si:credit:", top)
    if missing:
        if scanner.cooling_down(data.CREDIT_JOB):
            partial = True
            notes.append(f"Interest-paid figures for {len(missing)} companies couldn't be loaded yet.")
        else:
            job = scanner.start_scan(data.CREDIT_JOB, missing, fetch=data.fetch_credit)
            return _running(job, 2, "Reading interest expense and debt", len(top) - len(missing), len(top))

    # Stage 3: the corporate-bond ETFs' holdings (a few large SEC filings)
    ready, missing_funds = data.bond_funds_ready()
    index = {}
    if missing_funds:
        if scanner.cooling_down(data.BOND_JOB):
            partial = True
            notes.append("Bond holdings couldn't be loaded; showing the interest-paid proxy instead of bond spreads.")
        else:
            job = scanner.start_scan(data.BOND_JOB, missing_funds, fetch=data.fetch_bond_fund)
            return _running(job, 3, "Reading corporate-bond fund holdings", len(data.BOND_FUNDS) - len(missing_funds), len(data.BOND_FUNDS))
    else:
        index = data.bond_index()

    try:
        borrow = data.ibkr_borrow()
    except Exception as exc:
        logger.warning("IBKR borrow file failed: %s", exc)
        borrow = {"stamp": None, "data": {}}
        notes.append("Borrow rates are unavailable right now (Interactive Brokers' stock-loan file couldn't be read).")
    try:
        ust = data.ust10(data.treasury_curve())
    except Exception as exc:
        logger.warning("treasury curve failed: %s", exc)
        ust = None

    credit = {s: {**c, "totalDebt": infos[s].get("totalDebt"), "totalCash": infos[s].get("totalCash")} for s, c in credit_raw.items() if s in infos}
    for s in top:                                            # a name with no statement still gets its debt from the info record
        credit.setdefault(s, {"totalDebt": infos[s].get("totalDebt"), "totalCash": infos[s].get("totalCash")})
    rows = si.build_rows(ranked, borrow["data"], index, credit, ust)
    out = {"settlement": fin["settlement"], "borrowAsOf": borrow["stamp"], "limit": limit, "minCapM": min_cap_m, "treasury10y": ust,
           "rows": rows, "summary": si.summarize(rows), "partial": {"note": " ".join(notes)} if partial else None, "notes": notes,
           "bondFunds": data.BOND_FUNDS}
    if not partial:
        cache_set(key, out)
    return {"status": "ready", **out}


@router.get("/api/short-interest")
async def short_interest(limit: int = Query(100, ge=10, le=200), min_cap: float = Query(300, ge=0, le=100000)):
    try:
        return await asyncio.get_event_loop().run_in_executor(None, _build, limit, min_cap)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("short interest failed: %s", exc)
        raise HTTPException(502, f"Couldn't build the short-interest list: {exc}")
