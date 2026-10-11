"""Data side of the short-interest monitor: FINRA, Interactive Brokers, Yahoo fundamentals, bond-ETF holdings.

Everything is cached (FINRA 6 h, IBKR 1 h, Yahoo per symbol 24 h, bond index 12 h) and every slow step runs through the
shared background scanner (hundred_bagger_data.start_scan) with Yahoo rate-limit back-off, so the page shows progress
instead of hanging.
"""
import ftplib
import io
import logging
from datetime import date, datetime, timedelta

import requests
import yfinance as yf

import short_interest as si
import yahoo_limits
from database import cache_get, cache_set

logger = logging.getLogger(__name__)

_FINRA_TTL = timedelta(hours=6)
_IBKR_TTL = timedelta(hours=1)
_INFO_TTL = timedelta(hours=24)
_BOND_TTL = timedelta(hours=12)
_UA = {"User-Agent": "Mozilla/5.0 (compatible; Compass/1.0)"}
FINRA_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d}.csv"
IBKR_HOST, IBKR_FILE = "ftp2.interactivebrokers.com", "usa.txt"
BOND_FUNDS = ["LQD", "VCIT", "VCSH", "USIG", "HYG", "JNK", "USHY"]      # same universe as Research → Corporate Bonds
CANDIDATE_JOB, CREDIT_JOB, BOND_JOB = "short:candidates", "short:credit", "short:bonds"


# ── FINRA ─────────────────────────────────────────────────────────────────────

def latest_finra_text(today: date | None = None, lookback_days: int = 50) -> tuple[str, str]:
    """(csv text, settlement date) of the newest published file; the file is named by settlement date (twice a month)."""
    today = today or date.today()
    for back in range(lookback_days):
        d = (today - timedelta(days=back)).strftime("%Y%m%d")
        url = FINRA_URL.format(d=d)
        try:
            if requests.head(url, headers=_UA, timeout=10).status_code != 200:
                continue
            r = requests.get(url, headers=_UA, timeout=60)
            r.raise_for_status()
            return r.text, f"{d[:4]}-{d[4:6]}-{d[6:]}"
        except requests.RequestException:
            continue
    raise RuntimeError("couldn't find a recent FINRA short-interest file")


def finra_candidates() -> dict:
    """{'settlement': date, 'rows': [candidate rows]} (cached). Only the candidates are kept: the full file is 22,000 rows."""
    cached = cache_get("si:finra", _FINRA_TTL)
    if cached is not None:
        return cached
    text, settlement = latest_finra_text()
    out = {"settlement": settlement, "rows": si.select_candidates(si.parse_finra(text))}
    cache_set("si:finra", out)
    return out


# ── Borrow ────────────────────────────────────────────────────────────────────

def ibkr_borrow() -> dict:
    """{'stamp': file time, 'data': {symbol: {...}}} from Interactive Brokers' public stock-loan table (cached 1 h)."""
    cached = cache_get("si:ibkr", _IBKR_TTL)
    if cached is not None:
        return cached
    buf = io.BytesIO()
    ftp = ftplib.FTP(IBKR_HOST, timeout=30)
    try:
        ftp.login("shortstock", "")
        ftp.retrbinary(f"RETR {IBKR_FILE}", buf.write)
    finally:
        try:
            ftp.quit()
        except Exception:
            pass
    data, stamp = si.parse_ibkr(buf.getvalue().decode("latin-1"))
    out = {"stamp": stamp, "data": {k: v for k, v in data.items() if v["fee"] is not None or v["available"] is not None}}
    cache_set("si:ibkr", out)
    return out


# ── Yahoo per symbol ──────────────────────────────────────────────────────────

def _num(x):
    return si._num(x)


def fetch_info(symbol: str) -> dict | None:
    """Float, market cap and the fields the ranking and the debt proxy need (cached 24 h). Failures aren't cached."""
    key = f"si:info:{symbol}"
    cached = cache_get(key, _INFO_TTL)
    if cached is not None:
        return cached if cached.get("symbol") else None
    yahoo_limits.wait_if_paused()
    try:
        i = yf.Ticker(symbol).info or {}
    except Exception as exc:
        if yahoo_limits.is_rate_limit(exc):
            yahoo_limits.rate_limited()
        else:
            logger.warning("short-interest info %s failed: %s", symbol, exc)
        return None
    yahoo_limits.success()
    if not i.get("marketCap"):
        cache_set(key, {"symbol": None})
        return None
    out = {"symbol": symbol, "name": i.get("shortName") or i.get("longName"), "sector": i.get("sector"), "quoteType": i.get("quoteType"),
           "price": _num(i.get("currentPrice") or i.get("regularMarketPrice")), "marketCap": _num(i.get("marketCap")),
           "floatShares": _num(i.get("floatShares")), "sharesOutstanding": _num(i.get("sharesOutstanding")),
           "change52w": _num(i.get("52WeekChange")), "totalDebt": _num(i.get("totalDebt")), "totalCash": _num(i.get("totalCash"))}
    cache_set(key, out)
    return out


def fetch_credit(symbol: str) -> dict | None:
    """Interest expense and EBIT from the latest annual income statement (cached 24 h)."""
    key = f"si:credit:{symbol}"
    cached = cache_get(key, _INFO_TTL)
    if cached is not None:
        return cached if cached.get("ok") else None
    yahoo_limits.wait_if_paused()
    try:
        inc = yf.Ticker(symbol).income_stmt
    except Exception as exc:
        if yahoo_limits.is_rate_limit(exc):
            yahoo_limits.rate_limited()
        return None

    def first(names):
        if inc is None or getattr(inc, "empty", True):
            return None
        for n in names:
            if n in inc.index:
                for v in inc.loc[n].values:                 # newest column first; skip empty years
                    v = _num(v)
                    if v is not None:
                        return v
        return None
    out = {"ok": True, "interestExpense": first(["Interest Expense", "Interest Expense Non Operating"]), "ebit": first(["EBIT", "Operating Income"])}
    cache_set(key, out)
    return out


def cached_many(prefix: str, symbols: list[str], ttl=_INFO_TTL) -> tuple[dict, list[str]]:
    have, missing = {}, []
    for s in symbols:
        c = cache_get(f"{prefix}{s}", ttl)
        if c is None:
            missing.append(s)
        elif c.get("symbol", c.get("ok")):
            have[s] = c
    return have, missing


# ── Bond index ────────────────────────────────────────────────────────────────

def treasury_curve() -> list[dict]:
    from routers.treasury import treasury_current
    return treasury_current().get("rates", [])


def ust10(rates: list[dict]) -> float | None:
    pts = [r for r in rates if r.get("yield") is not None and abs(r["years"] - 10) < 0.01]
    return pts[0]["yield"] if pts else None


def bond_funds_ready() -> tuple[list[str], list[str]]:
    from routers import corporate_bonds as cb
    missing = [f for f in BOND_FUNDS if cache_get(f"bond_fund:{f}", cb._BOND_FUND_TTL) is None]
    return [f for f in BOND_FUNDS if f not in missing], missing


def fetch_bond_fund(fund: str):
    from routers import corporate_bonds as cb
    return cb._fetch_bond_fund_holdings(fund)


def bond_index() -> dict:
    """Index of every bond held by the corporate-bond ETFs, priced and spread against Treasuries (cached 12 h)."""
    cached = cache_get("si:bondindex", _BOND_TTL)
    if cached is not None:
        return cached
    from routers import corporate_bonds as cb
    grades = {sym: grade for sym, _label, grade in cb._BOND_ETF_UNIVERSE}
    funds = {f: (grades.get(f, "IG"), cb._fetch_bond_fund_holdings(f)) for f in BOND_FUNDS}
    index = si.build_bond_index(funds, treasury_curve(), datetime.utcnow().date(), cb._bond_price_per_100, cb._bond_ytm, cb._interpolate_treasury_yield)
    cache_set("si:bondindex", index)
    return index
