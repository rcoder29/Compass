"""Data side of the Manager Holdings page: SEC filing discovery, information tables, ticker lookup and prices.

  - Filing lists come from data.sec.gov submissions JSON (cached 6 h). A quarter can have an original 13F-HR plus 13F-HR/A
    amendments; "new holdings" amendments (usually positions that had confidential treatment) are merged into the original.
  - Each quarter's information table is parsed once and cached as aggregated JSON keyed by manager, quarter and the number of
    amendments, so a newly filed amendment invalidates it by itself. Filings never change otherwise, so parsed quarters live 90 days.
  - CUSIPs are turned into tickers with OpenFIGI (free, batched 10 per request), cached 90 days. Only the largest positions are looked up.
  - Prices for those tickers come from the shared daily-price loader (one locked yfinance download).
"""
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import requests

import holdings_perf
import thirteenf as tf
from database import cache_get, cache_set

logger = logging.getLogger(__name__)

SEC_UA = {"User-Agent": "Compass/1.0 raghuravuri@gmail.com"}
FIGI_URL = "https://api.openfigi.com/v3/mapping"
MAX_LOOKUP = 200            # tickers/prices are resolved for this many of the largest positions (every row the page shows)
HOURS_6, DAYS_30, DAYS_90 = 6 * 3600, 30 * 86400, 90 * 86400


def _ttl(seconds: int):
    return timedelta(seconds=seconds)


def _get(url: str, **kw) -> requests.Response:
    for attempt in range(3):
        r = requests.get(url, headers=SEC_UA, timeout=30, **kw)
        if r.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


# ── Filings ───────────────────────────────────────────────────────────────────

def parse_submissions(js: dict) -> list[dict]:
    """[{form, accession, filed, period}] for 13F-HR and 13F-HR/A filings, newest first."""
    f = js["filings"]["recent"]
    out = [{"form": fm, "accession": a, "filed": fd, "period": rd}
           for fm, a, fd, rd in zip(f["form"], f["accessionNumber"], f["filingDate"], f["reportDate"]) if fm in ("13F-HR", "13F-HR/A") and rd]
    return sorted(out, key=lambda x: (x["period"], x["filed"]), reverse=True)


def group_periods(filings: list[dict]) -> list[dict]:
    """One entry per quarter, newest first: the original 13F-HR (the earliest one filed) and any amendments, oldest first."""
    by: dict[str, dict] = {}
    for f in sorted(filings, key=lambda x: x["filed"]):
        e = by.setdefault(f["period"], {"period": f["period"], "original": None, "amendments": []})
        if f["form"] == "13F-HR" and e["original"] is None:
            e["original"] = f
        elif f["form"] == "13F-HR/A":
            e["amendments"].append(f)
    # an amendment with no original on record cannot be used
    return sorted((e for e in by.values() if e["original"]), key=lambda e: e["period"], reverse=True)


def filings_for(cik: int) -> list[dict]:
    key = f"13f:subs:{cik}"
    cached = cache_get(key, _ttl(HOURS_6))
    if cached is not None:
        return cached
    js = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    out = parse_submissions(js)
    cache_set(key, out)
    return out


def _index_files(cik: int, accession: str) -> list[str]:
    acc = accession.replace("-", "")
    js = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json").json()
    return [i["name"] for i in js.get("directory", {}).get("item", []) if i["name"].lower().endswith(".xml")]


def fetch_aggregate(cik: int, filing: dict) -> dict:
    """Aggregated positions of one filing (cached; a filing never changes)."""
    key = f"13f:agg:v2:{filing['accession']}"
    cached = cache_get(key, _ttl(DAYS_90))
    if cached is not None:
        return cached
    acc = filing["accession"].replace("-", "")
    names = [n for n in _index_files(cik, filing["accession"]) if n.lower() != "primary_doc.xml"]
    if not names:
        raise RuntimeError(f"no information table in filing {filing['accession']}")
    rows = []
    for n in names:                                         # normally one file; some managers split the table across several
        rows += tf.parse_infotable(_get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{n}").text, filing["filed"])
    out = tf.aggregate(rows)
    cache_set(key, out)
    return out


def amendment_type(cik: int, accession: str) -> str | None:
    key = f"13f:amd:{accession}"
    cached = cache_get(key, _ttl(DAYS_90))
    if cached is not None:
        return cached.get("type")
    acc = accession.replace("-", "")
    try:
        text = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml").text
        m = re.search(r"<amendmentType>([^<]+)</amendmentType>", text)
        t = m.group(1).strip() if m else None
    except requests.RequestException:
        t = None
    cache_set(key, {"type": t})
    return t


def load_period(cik: int, entry: dict) -> dict:
    """The quarter's holdings: the original filing with any amendments merged in."""
    data = fetch_aggregate(cik, entry["original"])
    for a in entry["amendments"]:
        try:
            data = tf.merge_amendment(data, fetch_aggregate(cik, a), amendment_type(cik, a["accession"]))
        except Exception as exc:
            logger.warning("13F amendment %s skipped: %s", a["accession"], exc)
    return data


# ── CUSIP → ticker ────────────────────────────────────────────────────────────

def pick_ticker(results: list[dict]) -> str | None:
    """The US common-stock/ETF ticker from an OpenFIGI result list, preferring the primary US listing."""
    cands = [r for r in results if r.get("ticker")]
    for want in ("US", None):
        for r in cands:
            if (want is None or r.get("exchCode") == want) and r.get("securityType") in ("Common Stock", "ETP", "REIT", "Depositary Receipt", "ADR"):
                return r["ticker"]
    return cands[0]["ticker"] if cands else None


# Foreign-domiciled issuers whose CUSIPs OpenFIGI does not map (they carry a CINS-style code starting with a letter).
CUSIP_OVERRIDES = {"H1467J104": "CB"}      # Chubb Limited


_figi_lock = threading.Lock()
_figi_last = [0.0]
FIGI_GAP = 2.6              # seconds between requests: the keyless limit is 25 a minute


def _figi_post(batch: list[str]):
    """One OpenFIGI mapping request, paced to stay under the keyless rate limit and retried when it still answers 429."""
    for attempt in range(3):
        with _figi_lock:
            wait = FIGI_GAP - (time.time() - _figi_last[0])
            if wait > 0:
                time.sleep(wait)
            _figi_last[0] = time.time()
            r = requests.post(FIGI_URL, json=[{"idType": "ID_CUSIP", "idValue": c} for c in batch], headers={"Content-Type": "application/json"}, timeout=30)
        if r.status_code == 429:
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("OpenFIGI rate limit")


_US_EXCHANGES = {"NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BTS"}
_NOISE = {"INC", "CORP", "CO", "LTD", "PLC", "NV", "N", "V", "SA", "AG", "HLDG", "HLDGS", "HOLDINGS", "HOLDING", "GROUP", "CORPORATION", "COMPANY", "LIMITED", "THE", "CL", "CLASS", "COM", "NEW", "SYS", "SYSTEMS"}


def _core(name: str) -> list[str]:
    return [w for w in re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper()).split() if w not in _NOISE]


_NUMERALS = {"II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "1", "2", "3", "4", "5"}


def name_matches(filing_name: str, listed_name: str) -> bool:
    """True when the two names are the same company name once legal suffixes are dropped, or one is the other plus extra words that
    are not a series number: 'AON PLC' matches 'Aon plc', but not 'Aonic Corp', and 'ARES ACQUISITION CORP III' does not match
    'Ares Acquisition Corporation' (a different, earlier vehicle). Cautious on purpose: a name search must never attach the wrong ticker."""
    a, b = _core(filing_name), _core(listed_name)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    extra = long_[len(short):]
    if long_[:len(short)] != short:
        return False
    return not any(w in _NUMERALS for w in extra) and short[-1] not in _NUMERALS      # a series number on either side means a different vehicle


def ticker_by_name(name: str) -> str | None:
    """Fallback for foreign-domiciled issuers that OpenFIGI cannot map by CUSIP: the first US-listed equity that Yahoo's search returns
    for the issuer name, accepted only if its name agrees with the filing's."""
    try:
        import yfinance as yf
        for q in yf.Search(name, max_results=6, news_count=0).quotes:
            if q.get("quoteType") == "EQUITY" and q.get("exchange") in _US_EXCHANGES and name_matches(name, q.get("longname") or q.get("shortname") or ""):
                return q.get("symbol")
    except Exception as exc:
        logger.info("name search for %s failed: %s", name, exc)
    return None


def tickers_for(cusips: list[str], names: dict[str, str] | None = None) -> dict[str, str | None]:
    """{cusip: ticker or None}. Overrides first, then the cache, then OpenFIGI by CUSIP, then (for foreign-domiciled issuers, whose
    CUSIPs start with a letter) a cautious name search. Lookup failures are not cached, so a later visit fills the gaps in."""
    out, need = {}, []
    for c in cusips:
        if c in CUSIP_OVERRIDES:
            out[c] = CUSIP_OVERRIDES[c]
            continue
        cached = cache_get(f"figi:{c}", _ttl(DAYS_90))
        if cached is None:
            need.append(c)
        else:
            out[c] = cached.get("ticker")
    for i in range(0, len(need), 10):
        batch = need[i:i + 10]
        try:
            for c, res in zip(batch, _figi_post(batch)):
                t = pick_ticker(res.get("data", []))
                if t is None and names and c[:1].isalpha() and names.get(c):
                    t = ticker_by_name(names[c])
                out[c] = t
                cache_set(f"figi:{c}", {"ticker": t})
        except Exception as exc:
            logger.warning("OpenFIGI lookup failed for %s: %s", batch, exc)
            for c in batch:
                out.setdefault(c, None)
    return out


# ── Prices ────────────────────────────────────────────────────────────────────

def price_on_or_before(series, day: str, tol_days: int = 6):
    import pandas as pd
    if series is None or len(series) == 0:
        return None
    hit = holdings_perf._price_on_or_before(series, pd.Timestamp(day), tol_days)
    return hit[1] if hit else None


def load_prices(symbols: list[str]) -> dict:
    """{symbol: daily close Series} (about 400 days) for Yahoo symbols plus SPY."""
    syms = list(dict.fromkeys([holdings_perf.yahoo_symbol(s) for s in symbols] + ["SPY"]))
    return holdings_perf.download_daily(syms)


def attach_prices(rows: list[dict], period_end: str, filed: str, series: dict) -> None:
    """Add price at the quarter end, at the filing date and now, and the returns since each, to each row that has a ticker."""
    for r in rows:
        t = r.get("ticker")
        s = series.get(holdings_perf.yahoo_symbol(t)) if t else None
        r["priceQE"] = price_on_or_before(s, period_end)
        r["priceFiled"] = price_on_or_before(s, filed)
        r["priceNow"] = float(s.iloc[-1]) if s is not None and len(s) else None
        r["retSinceQE"] = (r["priceNow"] / r["priceQE"] - 1.0) if r["priceNow"] and r["priceQE"] else None
        r["retSinceFiled"] = (r["priceNow"] / r["priceFiled"] - 1.0) if r["priceNow"] and r["priceFiled"] else None


def benchmark_returns(series: dict, period_end: str, filed: str) -> dict:
    s = series.get("SPY")
    now = float(s.iloc[-1]) if s is not None and len(s) else None
    qe, fd = price_on_or_before(s, period_end), price_on_or_before(s, filed)
    return {"sinceQE": (now / qe - 1.0) if now and qe else None, "sinceFiled": (now / fd - 1.0) if now and fd else None}


def parallel(fn, items, workers: int = 4):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
