"""Manager Holdings — Find Ideas → Manager Holdings.

  GET    /api/managers                              the investors that can be followed, with their latest filing
  GET    /api/managers/{id}                         a 13F manager's latest holdings, changes vs the prior quarter, history and returns;
                                                    or a disclosed investor's sourced log
  POST   /api/managers/{id}/disclosures             add a publicly stated position or rule to a disclosed investor's log
  DELETE /api/managers/{id}/disclosures/{row_id}    remove one

13F data comes from SEC EDGAR (thirteenf_data.py), maths from thirteenf.py, the list of investors from managers_catalog.py.
A 13F is a long-only snapshot up to 45 days stale; the report says so and gives the next expected date.
"""
import asyncio
import logging
import re
from datetime import date, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import managers_catalog as catalog
import thirteenf as tf
import thirteenf_data as tfd
from database import ManagerDisclosure, cache_get, cache_set, db_session

logger = logging.getLogger(__name__)
router = APIRouter()

_REPORT_TTL = timedelta(minutes=20)
HISTORY_QUARTERS = 6
EXITED_LIMIT = 25
POSITION_LIMIT = 200


def _manager(manager_id: str) -> dict:
    m = catalog.BY_ID.get(manager_id)
    if not m:
        raise HTTPException(404, f"Unknown manager '{manager_id}'")
    return m


def _filing_url(cik: int, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"


def build_report(m: dict) -> dict:
    cik = m["cik"]
    periods = tfd.group_periods(tfd.filings_for(cik))
    if not periods:
        raise RuntimeError(f"{m['name']} has no 13F-HR filings on record")
    use = periods[:HISTORY_QUARTERS]
    aggs = tfd.parallel(lambda e: tfd.load_period(cik, e), use)
    current, previous = aggs[0], (aggs[1] if len(aggs) > 1 else None)
    latest = use[0]
    cmp_ = tf.compare(current, previous, history=list(reversed(aggs)))
    rows, exited = cmp_["positions"][:POSITION_LIMIT], cmp_["exited"][:EXITED_LIMIT]

    lookup = [r["cusip"] for r in rows[:tfd.MAX_LOOKUP]] + [e["cusip"] for e in exited[:15]]
    names = {r["cusip"]: r["name"] for r in rows} | {e["cusip"]: e["name"] for e in exited}
    tickers = tfd.tickers_for(list(dict.fromkeys(lookup)), names)
    for r in rows:
        r["ticker"] = tickers.get(r["cusip"])
    for e in exited:
        e["ticker"] = tickers.get(e["cusip"])

    period_end, filed = latest["period"], latest["original"]["filed"]
    syms = [r["ticker"] for r in rows if r["ticker"]]
    series = tfd.load_prices(syms) if syms else {}
    tfd.attach_prices(rows, period_end, filed, series)
    bench = tfd.benchmark_returns(series, period_end, filed)
    perf = {"sinceQE": tf.weighted_return(rows, "priceQE"), "sinceFiled": tf.weighted_return(rows, "priceFiled"), "benchmark": bench}

    movers = lambda status, key, rev=True: sorted((r for r in rows if r["status"] == status), key=key, reverse=rev)[:8]
    return {
        "manager": {k: m[k] for k in ("id", "name", "person", "kind", "blurb")},
        "filing": {"period": period_end, "filed": filed, "form": latest["original"]["form"], "url": _filing_url(cik, latest["original"]["accession"]),
                   "amendments": [{"filed": a["filed"], "url": _filing_url(cik, a["accession"])} for a in latest["amendments"]],
                   "previousPeriod": use[1]["period"] if len(use) > 1 else None, "nextExpected": tf.next_deadline(period_end),
                   "daysSinceFiled": (date.today() - date.fromisoformat(filed)).days},
        "summary": tf.summarize(rows, cmp_["exited"], current, previous), "positions": rows, "exited": exited,
        "otherPositions": max(0, len(cmp_["positions"]) - len(rows)),
        "history": {"periods": [e["period"] for e in reversed(use)], "series": tf.concentration_series([{"period": e["period"], "data": a} for e, a in zip(reversed(use), reversed(aggs))])},
        "performance": perf,
        "highlights": {"new": movers("new", lambda r: r["value"]), "added": movers("added", lambda r: r["sharesChangePct"] or 0),
                       "reduced": movers("reduced", lambda r: r["sharesChangePct"] or 0, rev=False)},
        "periodsAvailable": len(periods),
    }


def build_list() -> list[dict]:
    def one(m):
        base = {k: m[k] for k in ("id", "name", "person", "kind", "blurb")}
        if m["kind"] != "13f":
            return {**base, "latestPeriod": None, "latestFiled": None}
        try:
            periods = tfd.group_periods(tfd.filings_for(m["cik"]))
            return {**base, "latestPeriod": periods[0]["period"] if periods else None, "latestFiled": periods[0]["original"]["filed"] if periods else None}
        except Exception as exc:
            logger.warning("manager list %s: %s", m["id"], exc)
            return {**base, "latestPeriod": None, "latestFiled": None, "error": True}
    return tfd.parallel(one, catalog.MANAGERS)


# ── Disclosed investors ───────────────────────────────────────────────────────

def _seed(manager_id: str) -> None:
    """Insert the sourced starter entries once per manager (never again, so deleting one stays deleted)."""
    seeds = catalog.DISCLOSURE_SEEDS.get(manager_id)
    if not seeds or cache_get(f"mgr:seeded:{manager_id}", timedelta(days=3650)) is not None:
        return
    sources = {s["match"]: s for s in catalog.DISCLOSURE_SOURCES.get(manager_id, [])}
    with db_session() as db:
        for s in seeds:
            src = sources.get(s["confidence"], {})
            db.add(ManagerDisclosure(manager_id=manager_id, symbol=s["symbol"], name=s["name"], action=s["action"], as_of=s["as_of"], note=s["note"],
                                     source_title=src.get("title"), source_url=src.get("url"), confidence=s["confidence"]))
    cache_set(f"mgr:seeded:{manager_id}", {"done": True})


def _row(r: ManagerDisclosure) -> dict:
    return {"id": r.id, "symbol": r.symbol, "name": r.name, "action": r.action, "asOf": r.as_of, "note": r.note,
            "sourceTitle": r.source_title, "sourceUrl": r.source_url, "confidence": r.confidence}


def build_disclosed(m: dict) -> dict:
    _seed(m["id"])
    with db_session() as db:
        rows = [_row(r) for r in db.query(ManagerDisclosure).filter(ManagerDisclosure.manager_id == m["id"]).order_by(ManagerDisclosure.id).all()]
    positions = [r for r in rows if r["symbol"]]
    syms = sorted({r["symbol"] for r in positions})
    prices = {}
    if syms:
        try:
            series = tfd.load_prices(syms)
            for s in syms:
                ser = series.get(s)
                if ser is not None and len(ser) > 1:
                    last = float(ser.iloc[-1])
                    year = tfd.price_on_or_before(ser, (date.today() - timedelta(days=365)).isoformat(), 10)
                    prices[s] = {"price": last, "ret1y": (last / year - 1.0) if year else None}
        except Exception as exc:
            logger.warning("disclosed prices failed: %s", exc)
    for r in positions:
        r.update(prices.get(r["symbol"], {"price": None, "ret1y": None}))
    return {"manager": {k: m[k] for k in ("id", "name", "person", "kind", "blurb")}, "positions": positions, "approach": [r for r in rows if not r["symbol"]],
            "sources": list({(r["sourceUrl"], r["sourceTitle"]): {"url": r["sourceUrl"], "title": r["sourceTitle"]} for r in rows if r["sourceUrl"]}.values())}


class DisclosureIn(BaseModel):
    symbol: str | None = Field(None, max_length=20)
    name: str | None = Field(None, max_length=120)
    action: str
    asOf: str | None = Field(None, max_length=10)
    note: str | None = Field(None, max_length=600)
    sourceTitle: str | None = Field(None, max_length=200)
    sourceUrl: str | None = Field(None, max_length=500)


_AS_OF = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


@router.get("/api/managers")
async def managers():
    return {"managers": await asyncio.get_event_loop().run_in_executor(None, build_list)}


@router.get("/api/managers/{manager_id}")
async def manager(manager_id: str):
    m = _manager(manager_id)
    try:
        if m["kind"] == "disclosed":
            return await asyncio.get_event_loop().run_in_executor(None, build_disclosed, m)
        key = f"mgr:report:{m['id']}"
        cached = cache_get(key, _REPORT_TTL)
        if cached is not None:
            return cached
        out = await asyncio.get_event_loop().run_in_executor(None, build_report, m)
        cache_set(key, out)
        return out
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("manager %s failed: %s", manager_id, exc)
        raise HTTPException(502, f"Couldn't load {m['name']}'s holdings: {exc}")


@router.post("/api/managers/{manager_id}/disclosures")
def add_disclosure(manager_id: str, body: DisclosureIn):
    m = _manager(manager_id)
    if m["kind"] != "disclosed":
        raise HTTPException(400, "Only investors without a 13F keep a disclosure log")
    if body.action not in catalog.ACTIONS:
        raise HTTPException(400, f"action must be one of {', '.join(catalog.ACTIONS)}")
    if body.asOf and not _AS_OF.match(body.asOf):
        raise HTTPException(400, "asOf must be YYYY-MM or YYYY-MM-DD")
    if body.sourceUrl and urlparse(body.sourceUrl).scheme not in ("http", "https"):
        raise HTTPException(400, "sourceUrl must start with http:// or https://")
    symbol = (body.symbol or "").strip().upper() or None
    if not symbol and body.action != "approach" and not (body.note or "").strip():
        raise HTTPException(400, "Add a ticker, or a note describing the statement")
    _seed(manager_id)
    with db_session() as db:
        row = ManagerDisclosure(manager_id=manager_id, symbol=symbol, name=body.name, action=body.action, as_of=body.asOf, note=body.note,
                                source_title=body.sourceTitle, source_url=body.sourceUrl, confidence="user")
        db.add(row)
        db.flush()
        return _row(row)


@router.delete("/api/managers/{manager_id}/disclosures/{row_id}")
def delete_disclosure(manager_id: str, row_id: int):
    _manager(manager_id)
    with db_session() as db:
        row = db.query(ManagerDisclosure).filter(ManagerDisclosure.id == row_id, ManagerDisclosure.manager_id == manager_id).first()
        if not row:
            raise HTTPException(404, "No such entry")
        db.delete(row)
    return {"ok": True}
