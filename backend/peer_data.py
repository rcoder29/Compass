"""Data side of the peer comparison: Yahoo's industry and sector company lists, and a flat fundamentals record per company.

Peers are the largest companies in the stock's Yahoo industry (its sector if the industry is too thin), narrowed to the closest in
size by peer_valuation.choose_peers. Per-company records and the company lists are cached for 24 hours and shared between every stock
in the same industry, and fetched through the shared background scanner with Yahoo rate-limit back-off.
"""
import logging
from datetime import timedelta

import yfinance as yf

import yahoo_limits
from database import cache_get, cache_set

logger = logging.getLogger(__name__)

_TTL = timedelta(hours=24)
MAX_CANDIDATES = 40


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v or v in (float("inf"), float("-inf")) else v


def record_from_info(symbol: str, i: dict) -> dict | None:
    """Flat comparison record from a Yahoo info dict, or None for something with no market cap (not a listed company)."""
    cap = _num(i.get("marketCap"))
    if not cap:
        return None
    fcf = _num(i.get("freeCashflow"))
    debt, cash = _num(i.get("totalDebt")), _num(i.get("totalCash"))
    return {"symbol": symbol, "name": i.get("shortName") or i.get("longName") or symbol, "sector": i.get("sector"), "industry": i.get("industry"),
            "industryKey": i.get("industryKey"), "sectorKey": i.get("sectorKey"), "quoteType": i.get("quoteType"),
            "price": _num(i.get("currentPrice") or i.get("regularMarketPrice")), "marketCap": cap,
            "trailingPE": _num(i.get("trailingPE")), "forwardPE": _num(i.get("forwardPE")), "evToEbitda": _num(i.get("enterpriseToEbitda")),
            "priceToSales": _num(i.get("priceToSalesTrailing12Months")), "priceToBook": _num(i.get("priceToBook")),
            "fcfYield": (fcf / cap) if fcf is not None else None,
            "revenueGrowth": _num(i.get("revenueGrowth")), "operatingMargin": _num(i.get("operatingMargins")), "roe": _num(i.get("returnOnEquity")),
            "ebitda": _num(i.get("ebitda")), "netDebt": (debt - cash) if debt is not None and cash is not None else None}


def fetch_peer(symbol: str) -> dict | None:
    """Comparison record for one company (cached 24 h). Clean 'nothing there' results are remembered; failures are not."""
    key = f"peer:{symbol}"
    cached = cache_get(key, _TTL)
    if cached is not None:
        return cached if cached.get("symbol") else None
    yahoo_limits.wait_if_paused()
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        if yahoo_limits.is_rate_limit(exc):
            yahoo_limits.rate_limited()
        else:
            logger.warning("peer fetch %s failed: %s", symbol, exc)
        return None
    yahoo_limits.success()
    rec = record_from_info(symbol, info)
    cache_set(key, rec if rec else {"symbol": None})
    return rec


def cached_records(symbols: list[str]) -> tuple[dict[str, dict], list[str]]:
    have, missing = {}, []
    for s in symbols:
        c = cache_get(f"peer:{s}", _TTL)
        if c is None:
            missing.append(s)
        elif c.get("symbol"):
            have[s] = c
    return have, missing


def company_list(kind: str, key: str) -> list[str]:
    """Largest companies in a Yahoo industry or sector (kind 'industry' | 'sector'), cached 24 h. Empty on any failure."""
    ck = f"peers:list:{kind}:{key}"
    cached = cache_get(ck, _TTL)
    if cached is not None:
        return cached
    try:
        obj = yf.Industry(key) if kind == "industry" else yf.Sector(key)
        tc = obj.top_companies
        syms = [str(s) for s in tc.index] if tc is not None else []
    except Exception as exc:
        if yahoo_limits.is_rate_limit(exc):
            yahoo_limits.rate_limited()
        logger.warning("peer list %s/%s failed: %s", kind, key, exc)
        return []
    cache_set(ck, syms)
    return syms


def candidate_symbols(subject: dict) -> tuple[list[str], str, str]:
    """(candidate tickers excluding the subject, scope kind, scope label). Industry first; the sector when the industry has under five."""
    sym = subject["symbol"]
    if subject.get("industryKey"):
        lst = [s for s in company_list("industry", subject["industryKey"]) if s != sym]
        if len(lst) >= 5:
            return lst[:MAX_CANDIDATES], "industry", subject.get("industry") or subject["industryKey"]
    if subject.get("sectorKey"):
        lst = [s for s in company_list("sector", subject["sectorKey"]) if s != sym]
        if lst:
            return lst[:MAX_CANDIDATES], "sector", subject.get("sector") or subject["sectorKey"]
    return [], "none", ""
