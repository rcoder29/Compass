"""Data side of the 100-bagger screen: universes, per-symbol Yahoo fundamentals, and a background scanner.

Fundamentals for ~1,000 stocks take about a minute cold (0.7 s each, 8 at a time), longer than a request should
hang, so a scan runs in a background thread and the page polls its progress. Per-symbol metrics are cached for
24 hours (`hb:{symbol}`); scoring is recomputed from them on every request, so changing a threshold needs no refetch.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import requests
import yfinance as yf
from bs4 import BeautifulSoup

import hundred_bagger as hb
import yahoo_limits
from database import cache_get, cache_set
from holdings_perf import yahoo_symbol

logger = logging.getLogger(__name__)

_METRICS_TTL = timedelta(hours=24)
_UNIVERSE_TTL = timedelta(hours=24)
_WIKI_UA = {"User-Agent": "StockMonitor/1.0 raghuravuri@gmail.com"}
_WORKERS = 4
_RETRY_COOLDOWN = 300            # seconds before a scan retries the symbols that failed (e.g. Yahoo rate limiting)
MAX_CUSTOM = 400

UNIVERSES = {
    "SP600": {"name": "S&P SmallCap 600", "url": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
              "blurb": "~600 profitable small caps: the most natural hunting ground"},
    "SP400": {"name": "S&P MidCap 400", "url": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
              "blurb": "~400 mid caps: bigger, safer, less runway"},
}


def universe_list() -> list[dict]:
    return [{"id": k, "name": v["name"], "blurb": v["blurb"]} for k, v in UNIVERSES.items()]


def parse_constituents(html: str) -> list[dict]:
    table = BeautifulSoup(html, "html.parser").find("table", id="constituents")
    if table is None:
        raise ValueError("constituents table not found")
    out = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        out.append({"symbol": yahoo_symbol(cells[0].get_text(strip=True)), "name": cells[1].get_text(" ", strip=True),
                    "sector": cells[2].get_text(" ", strip=True) or None})
    return out


def universe_members(universe_id: str) -> list[dict]:
    spec = UNIVERSES[universe_id]
    key = f"hb_u:{universe_id}"
    cached = cache_get(key, _UNIVERSE_TTL)
    if cached is not None:
        return cached
    r = requests.get(spec["url"], headers=_WIKI_UA, timeout=20)
    r.raise_for_status()
    members = parse_constituents(r.text)
    if len(members) < 300:
        raise ValueError(f"{spec['name']} list looks incomplete ({len(members)} rows)")
    cache_set(key, members)
    return members


def clean_symbols(raw: list[str]) -> list[str]:
    seen, out = set(), []
    for s in raw:
        s = yahoo_symbol(str(s).strip().upper())
        if s and len(s) <= 12 and s not in seen and all(c.isalnum() or c in "-.^=" for c in s):
            seen.add(s)
            out.append(s)
    return out[:MAX_CUSTOM]


# ── fetching ──────────────────────────────────────────────────────────────────

def _series(df, row_names: list[str]) -> list:
    if df is None or getattr(df, "empty", True):
        return []
    for name in row_names:
        if name in df.index:
            return [None if v != v else float(v) for v in df.loc[name].values]
    return []


def fetch_metrics(symbol: str) -> dict | None:
    """Metrics for one symbol (cached 24 h), or None if Yahoo has nothing usable or the fetch failed (not cached)."""
    key = f"hb:{symbol}"
    cached = cache_get(key, _METRICS_TTL)
    if cached is not None:
        return cached if cached.get("symbol") else None
    yahoo_limits.wait_if_paused()
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        if not info.get("marketCap"):
            cache_set(key, {"symbol": None})
            return None
        try:
            inc = t.income_stmt
        except Exception:
            inc = None
        m = hb.metrics_from_yahoo(symbol, info, _series(inc, ["Total Revenue", "Operating Revenue"]),
                                  _series(inc, ["Operating Income", "Total Operating Income As Reported"]),
                                  _series(inc, ["Net Income", "Net Income Common Stockholders"]))
    except Exception as exc:
        if yahoo_limits.is_rate_limit(exc):
            yahoo_limits.rate_limited()
        else:
            logger.warning("100-bagger metrics %s failed: %s", symbol, exc)
        return None
    yahoo_limits.success()
    cache_set(key, m)
    return m


def cached_metrics(symbols: list[str]) -> tuple[list[dict], list[str]]:
    """(metrics available in cache, symbols still missing). A cached 'no data' marker counts as done."""
    have, missing = [], []
    for s in symbols:
        c = cache_get(f"hb:{s}", _METRICS_TTL)
        if c is None:
            missing.append(s)
        elif c.get("symbol"):
            have.append(c)
    return have, missing


# ── background scans ──────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run(job_key: str, symbols: list[str]):
    job = _jobs[job_key]
    try:
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            for _ in pool.map(fetch_metrics, symbols):
                job["done"] += 1
    except Exception as exc:
        job["error"] = str(exc)
        logger.warning("100-bagger scan %s failed: %s", job_key, exc)
    finally:
        job["finished"] = time.time()
        job["running"] = False


def start_scan(job_key: str, symbols: list[str]) -> dict:
    """Start (or join) a background scan of `symbols`; returns its progress dict."""
    with _jobs_lock:
        job = _jobs.get(job_key)
        if job and job["running"]:
            return job
        job = {"running": True, "done": 0, "total": len(symbols), "started": time.time(), "finished": None, "error": None, "attempt": 1}
        _jobs[job_key] = job
        threading.Thread(target=_run, args=(job_key, symbols), daemon=True).start()
        return job


def progress(job_key: str) -> dict | None:
    return _jobs.get(job_key)


def cooling_down(job_key: str) -> bool:
    """True if a scan of this key finished recently with symbols still missing: don't hammer Yahoo again yet."""
    job = _jobs.get(job_key)
    return bool(job and not job["running"] and job["finished"] and time.time() - job["finished"] < _RETRY_COOLDOWN)


def retry_in(job_key: str) -> int:
    job = _jobs.get(job_key)
    return 0 if not job or not job["finished"] else max(0, int(_RETRY_COOLDOWN - (time.time() - job["finished"])))
