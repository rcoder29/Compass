"""Holdings performance — returns for every holding of an index or ETF over many periods.

Universes (what "holdings" means):
  - Indexes: S&P 500 (Wikipedia's constituents table, with GICS sector), Nasdaq-100 (Nasdaq's
    official list, with market-cap weights), Dow 30 (the in-app list).
  - Index-tracking ETFs resolve to their index (SPY/IVV/VOO -> S&P 500, QQQ -> Nasdaq-100,
    DIA -> Dow 30) and the Select Sector SPDRs (XLK, XLF, ...) to their GICS-sector slice of the
    S&P 500, which is exactly how those funds are built.
  - Any other ETF/fund falls back to the top 10 holdings Yahoo publishes, flagged as partial —
    there is no free source of complete holdings for arbitrary funds.

Returns are total returns (dividend-adjusted closes) over 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y,
10Y and LTD (life to date: since the first trade). Short periods use one daily download; the long
ones need decades of history for ~500 stocks, so those come from weekly bars downloaded in small
chunks (memory stays low) of which only a few anchor prices per symbol are kept and cached for a
day. Multi-year and LTD periods also get an annualised figure.
"""
import logging
import re
import threading
from datetime import date, timedelta
from statistics import mean, median

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

from database import cache_get, cache_set

logger = logging.getLogger(__name__)

PERIODS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y", "LTD"]
ANNUALISED = ["3Y", "5Y", "10Y", "LTD"]

_UNIVERSE_TTL = timedelta(hours=24)
_PAYLOAD_TTL = timedelta(minutes=15)
_ANCHOR_TTL = timedelta(hours=26)
_DAILY_LOOKBACK_DAYS = 400
_WEEKLY_CHUNK = 100
_MIN_ANCHOR_COVERAGE = 0.8

_WIKI_UA = {"User-Agent": "Compass/1.0 raghuravuri@gmail.com"}
_NASDAQ_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                   "Accept": "application/json, text/plain, */*"}
_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"

# Select Sector SPDR -> GICS sector in the S&P 500 table
SECTOR_ETFS = {
    "XLK": "Information Technology", "XLF": "Financials", "XLV": "Health Care", "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples", "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
    "XLRE": "Real Estate", "XLC": "Communication Services",
}
INDEX_ALIASES = {
    "SPY": "SP500", "IVV": "SP500", "VOO": "SP500", "SPLG": "SP500", "RSP": "SP500",
    "QQQ": "NASDAQ100", "QQQM": "NASDAQ100", "DIA": "DOW30",
}
INDEXES = {
    "SP500": {"name": "S&P 500", "benchmark": "SPY"},
    "NASDAQ100": {"name": "Nasdaq-100", "benchmark": "QQQ"},
    "DOW30": {"name": "Dow Jones Industrial Average (30)", "benchmark": "DIA"},
}


def yahoo_symbol(s: str) -> str:
    """Wikipedia / Nasdaq write BRK.B; Yahoo wants BRK-B."""
    return str(s).strip().upper().replace(".", "-").replace("/", "-")


# ── Universe sources ──────────────────────────────────────────────────────────

def fetch_sp500() -> list[dict]:
    r = requests.get(_SP500_URL, headers=_WIKI_UA, timeout=20)
    r.raise_for_status()
    table = BeautifulSoup(r.text, "html.parser").find("table", id="constituents")
    if table is None:
        raise ValueError("S&P 500 table not found")
    members = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        members.append({"symbol": yahoo_symbol(cells[0].get_text(strip=True)), "name": cells[1].get_text(" ", strip=True),
                        "sector": cells[2].get_text(" ", strip=True) or None, "weight": None})
    if len(members) < 400:
        raise ValueError(f"S&P 500 list looks incomplete ({len(members)} rows)")
    return members


_SHARE_SUFFIX = re.compile(r"\s+(Class [A-C]\s+)?(Common Stock|Ordinary Shares?|American Depositary Shares?|Capital Stock|Common Shares?)\b.*$", re.I)


def clean_name(raw: str) -> str:
    return _SHARE_SUFFIX.sub("", raw or "").strip() or (raw or "")


def fetch_nasdaq100() -> list[dict]:
    r = requests.get(_NASDAQ100_URL, headers=_NASDAQ_HEADERS, timeout=20)
    r.raise_for_status()
    rows = r.json()["data"]["data"]["rows"]
    caps = {}
    for row in rows:
        try:
            caps[row["symbol"]] = float(str(row.get("marketCap", "")).replace(",", "")) or None
        except ValueError:
            caps[row["symbol"]] = None
    total = sum(v for v in caps.values() if v)
    members = [{"symbol": yahoo_symbol(row["symbol"]), "name": clean_name(row.get("companyName", "")), "sector": row.get("sector") or None,
                "weight": round(caps[row["symbol"]] / total * 100, 3) if caps.get(row["symbol"]) and total else None} for row in rows]
    if len(members) < 90:
        raise ValueError(f"Nasdaq-100 list looks incomplete ({len(members)} rows)")
    return members


def _static_list(key: str) -> list[dict]:
    from routers.index_constituents import _INDEX_CONSTITUENTS
    return [{"symbol": c["symbol"], "name": c["name"], "sector": c.get("sector"), "weight": None} for c in _INDEX_CONSTITUENTS[key]]


def index_members(index_id: str) -> tuple[list[dict], str | None, bool]:
    """(members, note, degraded). The live list when its source answers; otherwise the in-app list,
    with `degraded` set and a note saying so."""
    key = f"holdperf_u:{index_id}"
    cached = cache_get(key, _UNIVERSE_TTL)
    if cached is not None:
        return cached["members"], cached.get("note"), bool(cached.get("degraded"))
    note, degraded = None, False
    try:
        if index_id == "SP500":
            members = fetch_sp500()
        elif index_id == "NASDAQ100":
            members = fetch_nasdaq100()
        else:
            members = _static_list("DOW30")
            note = "Dow 30 membership is the list maintained in this app; it can lag index changes."
    except Exception as exc:
        logger.warning("holdings perf: live %s list failed: %s", index_id, exc)
        degraded = True
        if index_id == "SP500":
            members, note = _static_list("SP100"), "Couldn't load the full S&P 500 list right now, so this shows the 100 largest members."
        else:
            members, note = _static_list("NASDAQ100"), "Couldn't load the live Nasdaq-100 list, so this uses the in-app list (it may be missing a few members)."
    cache_set(key, {"members": members, "note": note, "degraded": degraded})
    return members, note, degraded


def etf_top_holdings(symbol: str) -> list[dict]:
    """The (up to 10) top holdings Yahoo publishes for an ETF/fund; raises ValueError if it has none."""
    try:
        th = yf.Ticker(symbol).funds_data.top_holdings
    except Exception as exc:
        raise ValueError(f"{symbol} isn't an ETF or fund Yahoo has holdings for") from exc
    if th is None or getattr(th, "empty", True):
        raise ValueError(f"No holdings are published for {symbol}")
    members = []
    for sym, row in th.iterrows():
        if not isinstance(sym, str) or not sym:
            continue
        pct = row.get("Holding Percent") if hasattr(row, "get") else None
        members.append({"symbol": yahoo_symbol(sym), "name": str(row.get("Name") or sym), "sector": None,
                        "weight": round(float(pct) * 100, 3) if pct is not None and pct == pct else None})
    if not members:
        raise ValueError(f"No holdings are published for {symbol}")
    return members


def preset_universes() -> list[dict]:
    out = [{"id": k, "name": v["name"], "kind": "index", "benchmark": v["benchmark"]} for k, v in INDEXES.items()]
    out += [{"id": etf, "name": f"{etf} — {sector} (S&P 500 sector)", "kind": "sector-etf", "benchmark": etf}
            for etf, sector in SECTOR_ETFS.items()]
    return out


def resolve_universe(key: str) -> dict:
    """{id, name, kind, benchmark, members, partial, note}. Raises ValueError for unknown/empty funds."""
    k = re.sub(r"[\s&_-]", "", (key or "").upper())
    k = {"SPX": "SP500", "SANDP500": "SP500", "NASDAQ": "NASDAQ100", "NDX": "NASDAQ100", "DOW": "DOW30", "DJIA": "DOW30"}.get(k, k)
    if not k:
        raise ValueError("Enter an index or ETF")
    alias_of = INDEX_ALIASES.get(k)
    index_id = alias_of or (k if k in INDEXES else None)
    if index_id:
        members, note, degraded = index_members(index_id)
        meta = INDEXES[index_id]
        bench = k if alias_of else meta["benchmark"]
        name = meta["name"] + (f" (holdings of {k})" if alias_of else "")
        if alias_of == "SP500" and k == "RSP":
            note = ((note + " ") if note else "") + "RSP holds the same stocks as the S&P 500 but equal-weighted, so its own return differs from the index."
        return {"id": k, "name": name, "kind": "index", "benchmark": bench, "members": members, "partial": degraded, "note": note}
    if k in SECTOR_ETFS:
        sp, note, degraded = index_members("SP500")
        sector = SECTOR_ETFS[k]
        members = [m for m in sp if m["sector"] == sector]
        if not members:
            raise ValueError(f"No S&P 500 members found for {sector}")
        return {"id": k, "name": f"{k} — {sector} (S&P 500 sector)", "kind": "sector-etf", "benchmark": k, "members": members,
                "partial": degraded,
                "note": (note + " " if note else "") + f"{k} holds the S&P 500's {sector} stocks; shown equal-weighted here, so the weights differ from the fund's."}
    members = etf_top_holdings(k)
    return {"id": k, "name": f"{k} — top holdings", "kind": "etf", "benchmark": k, "members": members, "partial": True,
            "note": f"Showing only the top {len(members)} holdings: Yahoo doesn't publish a fund's full list. "
                    "S&P 500, Nasdaq-100, Dow 30, their index ETFs (SPY, QQQ, DIA…) and the sector SPDRs (XLK, XLF…) show every holding."}


# ── Return math ───────────────────────────────────────────────────────────────

def _clean(series: pd.Series | None) -> pd.Series | None:
    if series is None:
        return None
    s = series.dropna()
    if s.empty:
        return None
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    return s.sort_index()


def _price_on_or_before(series: pd.Series, target: pd.Timestamp, tol_days: int = 5):
    """(date, price) of the last bar at/before `target`, or None if the history doesn't reach back that far."""
    if series.index[0] > target + pd.Timedelta(days=tol_days):
        return None
    sub = series[:target]
    if sub.empty:
        return None
    price = float(sub.iloc[-1])
    return (sub.index[-1], price) if price > 0 else None


def _weekly_price_near(close: pd.Series, target: pd.Timestamp, tol_days: int = 8):
    """Weekly bars are labelled with the week's Monday but close on Friday: pick the bar whose close
    date is nearest `target`, and refuse if the history starts after it."""
    ends = close.index + pd.Timedelta(days=4)
    if ends[0] > target + pd.Timedelta(days=tol_days):
        return None
    pos = int(abs(ends - target).argmin())
    if abs((ends[pos] - target).days) > tol_days:
        return None
    price = float(close.iloc[pos])
    return {"price": price, "date": str(ends[pos].date())} if price > 0 else None


def weekly_anchors(w_close: pd.Series | None, w_open: pd.Series | None, as_of: pd.Timestamp) -> dict | None:
    """The handful of long-ago prices a symbol's multi-year returns need, from its weekly history."""
    close = _clean(w_close)
    if close is None:
        return None
    out = {}
    for key, years in (("3Y", 3), ("5Y", 5), ("10Y", 10)):
        out[key] = _weekly_price_near(close, as_of - pd.DateOffset(years=years))
    first_open = None
    opens = _clean(w_open)
    if opens is not None and float(opens.iloc[0]) > 0:
        first_open = float(opens.iloc[0])
    start = float(close.iloc[0]) if first_open is None else first_open
    out["LTD"] = {"price": start, "date": str(close.index[0].date())} if start > 0 else None
    return out


def compute_returns(daily: pd.Series | None, anchors: dict | None) -> dict | None:
    """{'returns': {period: fraction|None}, 'annualised': {...}, 'ltdSince', 'price', 'asOf'} or None without prices."""
    d = _clean(daily)
    if d is None or len(d) < 2:
        return None
    last_date, last = d.index[-1], float(d.iloc[-1])
    if last <= 0:
        return None
    ret: dict = {"1D": last / float(d.iloc[-2]) - 1 if float(d.iloc[-2]) > 0 else None}
    for key, offset in (("1W", pd.Timedelta(days=7)), ("1M", pd.DateOffset(months=1)), ("3M", pd.DateOffset(months=3)),
                        ("6M", pd.DateOffset(months=6)), ("1Y", pd.DateOffset(years=1))):
        base = _price_on_or_before(d, last_date - offset)
        ret[key] = last / base[1] - 1 if base else None
    year_end = pd.Timestamp(year=last_date.year - 1, month=12, day=31)
    base = _price_on_or_before(d, year_end, tol_days=3)
    if base:
        ret["YTD"] = last / base[1] - 1
    else:                                           # listed this year: measure from its first close
        this_year = d[d.index.year == last_date.year]
        ret["YTD"] = last / float(this_year.iloc[0]) - 1 if len(this_year) > 1 and float(this_year.iloc[0]) > 0 else None
    ann: dict = {}
    ltd_since = None
    for key in ("3Y", "5Y", "10Y", "LTD"):
        a = (anchors or {}).get(key)
        if not a:
            ret[key] = None
            continue
        ret[key] = last / a["price"] - 1
        years = (last_date - pd.Timestamp(a["date"])).days / 365.25
        # annualising a few months of history is misleading, so LTD needs a year behind it
        if years >= (1.0 if key == "LTD" else 2.5) and ret[key] > -1:
            ann[key] = (1 + ret[key]) ** (1 / years) - 1
        if key == "LTD":
            ltd_since = a["date"]
    return {"returns": {k: (round(v, 5) if v is not None else None) for k, v in ret.items()},
            "annualised": {k: round(v, 5) for k, v in ann.items()},
            "ltdSince": ltd_since, "price": round(last, 4), "asOf": str(last_date.date())}


def summarize(rows: list[dict], benchmark: dict | None) -> dict:
    """Per-period headline stats over the holdings: count, mean, median, share up, share beating the benchmark, best/worst."""
    out = {}
    bench = (benchmark or {}).get("returns", {})
    for p in PERIODS:
        vals = [(r["symbol"], r["returns"][p]) for r in rows if r["returns"].get(p) is not None]
        if not vals:
            out[p] = {"n": 0, "mean": None, "median": None, "positive": None, "beating": None, "best": None, "worst": None}
            continue
        nums = [v for _, v in vals]
        b = bench.get(p)
        best, worst = max(vals, key=lambda x: x[1]), min(vals, key=lambda x: x[1])
        out[p] = {"n": len(vals), "mean": round(mean(nums), 5), "median": round(median(nums), 5),
                  "positive": sum(1 for v in nums if v > 0) / len(nums),
                  "beating": (sum(1 for v in nums if v > b) / len(nums)) if b is not None else None,
                  "best": {"symbol": best[0], "return": best[1]}, "worst": {"symbol": worst[0], "return": worst[1]}}
    return out


# ── Downloading ───────────────────────────────────────────────────────────────

def _field(df: pd.DataFrame | None, symbol: str, field: str, multi: bool = True):
    """One price column for one symbol. Decided by the frame's actual shape, not by how many tickers were
    requested: current yfinance returns multi-level (ticker, field) columns even for a single ticker,
    older versions returned flat columns. (`multi` is accepted for call-site compatibility only.)"""
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            return df[symbol][field]
        return df[field]
    except KeyError:
        return None


# yfinance.download keeps its working state in module-level dicts, so two downloads running at once
# (even from different threads) corrupt each other and hang. All downloads here go through this lock.
_YF_DOWNLOAD_LOCK = threading.Lock()


def _download(symbols: list[str], **kw):
    with _YF_DOWNLOAD_LOCK:
        df = yf.download(symbols if len(symbols) > 1 else symbols[0], group_by="ticker", auto_adjust=True, threads=True,
                         progress=False, **kw)
    return df, len(symbols) > 1


def download_daily(symbols: list[str]) -> dict[str, pd.Series]:
    start = (date.today() - timedelta(days=_DAILY_LOOKBACK_DAYS)).isoformat()
    df, multi = _download(symbols, start=start, interval="1d")
    return {s: c for s in symbols if (c := _clean(_field(df, s, "Close", multi))) is not None}


def download_anchors(symbols: list[str], as_of: pd.Timestamp) -> dict[str, dict]:
    """Weekly full history in chunks (a 500-stock download at once holds ~150 MB); keeps only anchors."""
    chunks = [symbols[i:i + _WEEKLY_CHUNK] for i in range(0, len(symbols), _WEEKLY_CHUNK)]

    def one(chunk):
        try:
            df, multi = _download(chunk, period="max", interval="1wk")
        except Exception as exc:
            logger.warning("holdings perf: weekly chunk failed: %s", exc)
            return {}
        out = {s: weekly_anchors(_field(df, s, "Close", multi), _field(df, s, "Open", multi), as_of) for s in chunk}
        return {s: a for s, a in out.items() if a}
    anchors: dict[str, dict] = {}
    for chunk in chunks:                            # sequential: downloads can't overlap anyway (see _YF_DOWNLOAD_LOCK)
        anchors.update(one(chunk))
    return anchors


_anchor_lock = threading.Lock()


def load_anchors(symbols: list[str]) -> dict[str, dict]:
    """Long-history anchors for `symbols`, from one per-day cache shared by every universe: the S&P 500, SPY,
    and a sector ETF overlap almost entirely, so each only downloads the symbols no earlier lookup has seen."""
    key = f"holdperf_anchors:{date.today().isoformat()}"
    with _anchor_lock:
        shared = cache_get(key, _ANCHOR_TTL) or {}
        need = [s for s in symbols if s not in shared]
        if need:
            fresh = download_anchors(need, pd.Timestamp(date.today()))
            # A partial result (rate limiting, a failed chunk) must not be pinned for a day: only keep it when most
            # of what was asked for came back. The 80% bar leaves room for symbols with no weekly history at all.
            if len(fresh) >= _MIN_ANCHOR_COVERAGE * len(need):
                shared = {**shared, **fresh}
                cache_set(key, shared)
            else:
                shared = {**shared, **fresh}            # still usable for this request, just not saved
    return {s: shared[s] for s in symbols if s in shared}


# ── Assembly ──────────────────────────────────────────────────────────────────

def build_payload(universe: dict, daily: dict[str, pd.Series], anchors: dict[str, dict]) -> dict:
    """Pure assembly (no I/O): holdings with returns, the benchmark's returns, summary stats, sorted by YTD."""
    rows, missing = [], []
    for m in universe["members"]:
        calc = compute_returns(daily.get(m["symbol"]), anchors.get(m["symbol"]))
        if calc is None:
            missing.append(m["symbol"])
            continue
        rows.append({"symbol": m["symbol"], "name": m["name"], "sector": m.get("sector"), "weight": m.get("weight"), **calc})
    bench_sym = universe["benchmark"]
    bench = compute_returns(daily.get(bench_sym), anchors.get(bench_sym))
    rows.sort(key=lambda r: (r["returns"].get("YTD") is None, -(r["returns"].get("YTD") or 0)))
    return {
        "universe": {"id": universe["id"], "name": universe["name"], "kind": universe["kind"], "partial": universe["partial"],
                     "note": universe["note"], "holdingCount": len(universe["members"]), "withData": len(rows)},
        "periods": PERIODS, "annualisedPeriods": ANNUALISED,
        "asOf": max((r["asOf"] for r in rows), default=None),
        "benchmark": {"symbol": bench_sym, **bench} if bench else {"symbol": bench_sym, "returns": {}, "annualised": {}},
        "summary": summarize(rows, bench),
        "holdings": rows, "missing": missing,
    }


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def holdings_performance(key: str) -> dict:
    """Cached payload for an index/ETF. A second request for the same universe during a cold build waits
    for the first instead of repeating ~500 downloads."""
    universe = resolve_universe(key)
    cache_key = f"holdperf:{universe['id']}"
    cached = cache_get(cache_key, _PAYLOAD_TTL)
    if cached is not None:
        return cached
    with _locks_guard:
        lock = _locks.setdefault(cache_key, threading.Lock())
    with lock:
        cached = cache_get(cache_key, _PAYLOAD_TTL)
        if cached is not None:
            return cached
        symbols = list(dict.fromkeys([m["symbol"] for m in universe["members"]] + [universe["benchmark"]]))
        daily = download_daily(symbols)
        anchors = load_anchors(symbols)
        payload = build_payload(universe, daily, anchors)
        if payload["holdings"]:
            cache_set(cache_key, payload)
        return payload
