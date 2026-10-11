"""100-Bagger Finder — Research → 100-Bagger Finder.

  GET /api/hundred-baggers/universes             the preset universes
  GET /api/hundred-baggers?universe=SP600        scored stocks, or scan progress while data is still loading
  GET /api/hundred-baggers?symbols=ABC,XYZ       the same for your own tickers (e.g. the watchlist)

The first request for a universe starts a background scan (about a minute for ~600 stocks); the page polls until
`status` is "ready". The scoring is in hundred_bagger.py, the data in hundred_bagger_data.py.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

import hundred_bagger as hb
import hundred_bagger_data as data

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/hundred-baggers/universes")
def universes():
    return {"universes": data.universe_list(), "weights": hb.WEIGHTS, "factorNames": hb.FACTOR_NAMES,
            "timeline": [{"years": y, "cagr": round(hb.required_cagr(y), 4)} for y in (10, 15, 20, 25, 30)]}


def _resolve(universe: str | None, symbols: str | None) -> tuple[str, str, list[str], list[dict] | None]:
    if symbols:
        syms = data.clean_symbols(symbols.split(","))
        if not syms:
            raise HTTPException(400, "No valid tickers in 'symbols'")
        return "custom:" + ",".join(sorted(syms)), "Your tickers", syms, None
    uid = (universe or "SP600").upper()
    if uid not in data.UNIVERSES:
        raise HTTPException(404, f"Unknown universe '{universe}'")
    members = data.universe_members(uid)
    return uid, data.UNIVERSES[uid]["name"], [m["symbol"] for m in members], members


def _build(universe, symbols):
    key, name, syms, members = _resolve(universe, symbols)
    have, missing = data.cached_metrics(syms)
    partial = None
    if missing and data.cooling_down(key):
        # A scan just finished but Yahoo refused some symbols (usually rate limiting): show what loaded, retry after the cooldown.
        partial = {"missing": len(missing), "retryInSeconds": data.retry_in(key),
                   "note": f"{len(missing)} of {len(syms)} stocks couldn't be loaded (Yahoo is limiting requests). Showing the rest; the app retries automatically in a few minutes."}
    elif missing:
        job = data.start_scan(key, missing)
        return {"status": "running", "universe": {"id": key, "name": name, "size": len(syms)},
                "progress": {"done": len(syms) - len(missing) + min(job["done"], len(missing)), "total": len(syms)}, "error": job["error"]}
    sector_of = {m["symbol"]: m.get("sector") for m in members} if members else {}
    for m in have:                                    # Wikipedia's GICS sector is steadier than Yahoo's label
        m["sector"] = sector_of.get(m["symbol"]) or m.get("sector")
    result = hb.build_results(have)
    return {"status": "ready", "universe": {"id": key, "name": name, "size": len(syms)}, "partial": partial, **result}


@router.get("/api/hundred-baggers")
async def hundred_baggers(universe: str | None = None, symbols: str | None = None):
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _build, universe, symbols)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("hundred baggers failed: %s", exc)
        raise HTTPException(502, f"Couldn't build the screen: {exc}")
