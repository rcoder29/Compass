"""Tear Sheet → Versus peers.

  GET /api/tear-sheet/{symbol}/peers     the stock's multiples, growth, margins and returns against similar companies

Loaded separately from the main sheet so the sheet appears at once. The first request for an industry fetches ~40 company records
in a background scan (status "running" with progress); everything is then cached and shared by every stock in that industry. The
maths is in peer_valuation.py, the downloads in peer_data.py.
"""
import asyncio
import logging
import re
from datetime import timedelta

from fastapi import APIRouter, HTTPException

import hundred_bagger_data as scanner
import peer_data as data
import peer_valuation as pv
from database import cache_get, cache_set

logger = logging.getLogger(__name__)
router = APIRouter()

_TTL = timedelta(hours=6)
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")


def build_peers(sym: str) -> dict:
    cached = cache_get(f"peers:built:{sym}", _TTL)
    if cached is not None:
        return {"status": "ready", **cached}
    subject = data.fetch_peer(sym)
    if subject is None:
        _, unresolved = data.cached_records([sym])
        if unresolved:                       # not even a "nothing there" marker is cached: the lookup failed, usually Yahoo rate limiting
            return {"status": "unavailable", "transient": True,
                    "reason": "Yahoo Finance is limiting requests right now, so the peer comparison couldn't load. Try again in a few minutes."}
        return {"status": "unavailable", "reason": "No market data was found for this symbol, so it can't be compared with peers."}
    if subject.get("quoteType") not in (None, "EQUITY"):
        return {"status": "unavailable", "reason": "Peer comparison applies to individual companies, not funds."}
    candidates, scope, label = data.candidate_symbols(subject)
    if not candidates:
        return {"status": "unavailable", "reason": "Yahoo Finance doesn't list comparable companies for this stock's industry."}
    have, missing = data.cached_records(candidates)
    job_key = f"peers:{scope}:{label}"
    partial = None
    if missing:
        if scanner.cooling_down(job_key):
            partial = {"missing": len(missing), "note": f"{len(missing)} of {len(candidates)} candidate peers couldn't be loaded yet (Yahoo is limiting requests); the comparison uses the rest."}
        else:
            job = scanner.start_scan(job_key, missing, fetch=data.fetch_peer)
            return {"status": "running", "progress": {"done": len(candidates) - len(missing) + min(job["done"], len(missing)), "total": len(candidates)}, "error": job["error"]}
    bands = pv.SIZE_BANDS if scope == "industry" else pv.SIZE_BANDS[:1]       # a whole sector is too broad for loose size matching
    chosen = pv.choose_peers(subject.get("marketCap"), [r for r in have.values() if r.get("quoteType") in (None, "EQUITY")], bands=bands)
    result = pv.compare(subject, chosen)
    if result is None:
        reason = (f"No similarly sized companies were found in Yahoo's {scope} '{label}', so there is nothing fair to compare this stock with."
                  if not chosen else f"Only {len(chosen)} comparable compan{'y' if len(chosen) == 1 else 'ies'} could be found (at least {pv.MIN_PEERS} are needed).")
        return {"status": "unavailable", "reason": reason}
    out = {"symbol": sym, "name": subject.get("name"), "scope": scope, "scopeLabel": label, "partial": partial, "peerCount": len(chosen),
           "headline": pv.headline(sym, result), **result,
           "subject": pv.peer_row(subject), "peers": sorted((pv.peer_row(p) for p in chosen), key=lambda r: -(r["marketCap"] or 0)),
           "note": ("Peers are the companies closest in size within Yahoo's " + ("industry" if scope == "industry" else "sector (the industry was too thin)") + f" '{label}'.")}
    if not partial:
        cache_set(f"peers:built:{sym}", out)
    return {"status": "ready", **out}


async def peers_for(sym: str) -> dict:
    return await asyncio.get_event_loop().run_in_executor(None, build_peers, sym)


def cached_peers(sym: str) -> dict | None:
    """The finished comparison if it is already cached, else None. Never triggers a download (used by the PDF)."""
    return cache_get(f"peers:built:{sym}", _TTL)


@router.get("/api/tear-sheet/{symbol}/peers")
async def tear_sheet_peers(symbol: str):
    sym = symbol.upper().strip()
    if not _SYMBOL_RE.match(sym):
        raise HTTPException(400, "Invalid ticker symbol")
    try:
        return await peers_for(sym)
    except Exception as exc:
        logger.warning("peers failed for %s: %s", sym, exc)
        raise HTTPException(502, f"Couldn't build the peer comparison: {exc}")
