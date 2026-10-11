"""FRED (Federal Reserve Economic Data) series loader — no API key required.

FRED publishes every series as a plain CSV at `fredgraph.csv?id=<SERIES>` with its full history
(unemployment from 1948, the 10Y-2Y spread from 1976, NBER recession dates from 1854, ...). The
older Economic Indicators view needed a FRED_API_KEY and only kept ~2 years; this module needs
neither, which is what makes long-run percentiles, recession shading and market-response studies
possible.

Notes on the data:
  - These are the *current, revised* values, not what was known at the time of each release. A
    study built on them looks cleaner than real-time reality would have; callers that present
    historical studies say so.
  - A few series carry licence-restricted history (ICE credit spreads start in 2023). That is
    reported as-is rather than papered over.

Series are cached in SQLite (`fred:{id}`, 6 hours) as {dates, values}; loading ~50 series in
parallel takes ~3 seconds cold.
"""
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pandas as pd
import requests

from database import cache_get, cache_set

logger = logging.getLogger(__name__)

_FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Compass/1.0)"}
_TTL = timedelta(hours=6)
_MAX_WORKERS = 8


def _parse_csv(text: str) -> pd.Series | None:
    """FRED CSV -> float Series on a DatetimeIndex ('.' marks a missing observation)."""
    try:
        df = pd.read_csv(io.StringIO(text), na_values=".")
    except Exception:
        return None
    if df.shape[1] < 2 or df.empty:
        return None
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(df.iloc[:, 0], errors="coerce")).dropna()
    s = s[s.index.notna()]
    return s.sort_index() if not s.empty else None


def get_series(series_id: str) -> pd.Series | None:
    """One FRED series, or None if it can't be loaded. Never raises."""
    key = f"fred:{series_id}"
    cached = cache_get(key, _TTL)
    if cached is not None:
        return pd.Series(cached["values"], index=pd.to_datetime(cached["dates"]), dtype=float)
    for attempt in range(2):
        try:
            r = requests.get(_FRED_URL, params={"id": series_id}, headers=_HEADERS, timeout=25)
            if r.status_code != 200:
                logger.warning("FRED %s: HTTP %s", series_id, r.status_code)
                return None
            s = _parse_csv(r.text)
            if s is None:
                return None
            cache_set(key, {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [float(v) for v in s.values]})
            return s
        except Exception as exc:
            logger.warning("FRED %s attempt %d failed: %s", series_id, attempt + 1, exc)
    return None


def get_many(series_ids: list[str]) -> dict[str, pd.Series]:
    """{id: Series} for those that loaded; ones that failed are simply absent."""
    ids = list(dict.fromkeys(series_ids))
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        results = list(pool.map(get_series, ids))
    return {sid: s for sid, s in zip(ids, results) if s is not None}


def recession_periods(usrec: pd.Series | None) -> list[dict]:
    """NBER recession spans from the monthly USREC (1 = recession) series: [{start, end}] as ISO dates.
    A recession still in progress has `end` = the last observation."""
    if usrec is None or usrec.empty:
        return []
    flags = usrec.fillna(0).astype(int)
    out, start, prev = [], None, None
    for d, v in flags.items():
        if v == 1 and start is None:
            start = d
        if v == 0 and start is not None:
            out.append({"start": start.strftime("%Y-%m-%d"), "end": prev.strftime("%Y-%m-%d")})
            start = None
        prev = d
    if start is not None:
        out.append({"start": start.strftime("%Y-%m-%d"), "end": prev.strftime("%Y-%m-%d")})
    return out
