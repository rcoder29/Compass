"""Long monthly price history for indexes and ETFs, shared by Indicator Studies and the Sectors pages.

`Ticker.history(period="max", interval="1d")` goes back much further than Yahoo's own monthly bars (the
S&P 500 index to 1927 vs 1985), so monthly series are built by taking each month's last daily close. ETF
series are dividend-adjusted (total return); the S&P 500 index series is price-only, so absolute levels
exclude dividends — comparisons within one series are unaffected.

Each symbol is cached for 24 hours as {dates, values}. Per-symbol `Ticker.history` calls are independent
(unlike the batched `yf.download`, which is not thread-safe), so they run in a small thread pool.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pandas as pd
import yfinance as yf

from database import cache_get, cache_set

logger = logging.getLogger(__name__)

_TTL = timedelta(hours=24)


def _fetch_monthly(symbol: str) -> pd.Series | None:
    try:
        h = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=True)
    except Exception as exc:
        logger.warning("monthly history %s failed: %s", symbol, exc)
        return None
    if h is None or h.empty or "Close" not in h:
        return None
    close = h["Close"].dropna()
    if getattr(close.index, "tz", None) is not None:
        close.index = close.index.tz_localize(None)
    m = close.resample("MS").last().dropna()
    return m[m > 0] if len(m) else None


def get_monthly(symbol: str) -> pd.Series | None:
    """Month-start-indexed last close of each month, or None."""
    key = f"mhist:{symbol}"
    cached = cache_get(key, _TTL)
    if cached is not None:
        return pd.Series(cached["values"], index=pd.to_datetime(cached["dates"]), dtype=float)
    s = _fetch_monthly(symbol)
    if s is not None:
        cache_set(key, {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [float(v) for v in s.values]})
    return s


def get_many_monthly(symbols: list[str]) -> dict[str, pd.Series]:
    syms = list(dict.fromkeys(symbols))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(get_monthly, syms))
    return {s: r for s, r in zip(syms, results) if r is not None}


def forward_return(prices: pd.Series, entry: pd.Timestamp, months: int) -> float | None:
    """Return from the close of the `entry` month to the close `months` later; None if either is unavailable."""
    if entry not in prices.index:
        return None
    exit_ = entry + pd.DateOffset(months=months)
    if exit_ not in prices.index:
        return None
    return float(prices.loc[exit_] / prices.loc[entry] - 1.0)


def forward_returns(prices: pd.Series, months: int) -> pd.Series:
    """Forward `months`-month return from every month (NaN where the window runs past the data)."""
    shifted = prices.reindex(prices.index + pd.DateOffset(months=months)).values
    return pd.Series(shifted / prices.values - 1.0, index=prices.index)


# ── daily history (sector scoreboard, rotation map, screener, backtest) ──────

_DAILY_TTL = timedelta(hours=6)


def get_daily(symbol: str) -> pd.Series | None:
    """Full daily adjusted-close history (total return for ETFs), tz-naive, or None."""
    key = f"dhist:{symbol}"
    cached = cache_get(key, _DAILY_TTL)
    if cached is not None:
        return pd.Series(cached["values"], index=pd.to_datetime(cached["dates"]), dtype=float)
    try:
        h = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=True)
    except Exception as exc:
        logger.warning("daily history %s failed: %s", symbol, exc)
        return None
    if h is None or h.empty or "Close" not in h:
        return None
    close = h["Close"].dropna()
    close = close[close > 0]
    if getattr(close.index, "tz", None) is not None:
        close.index = close.index.tz_localize(None)
    close.index = close.index.normalize()
    close = close[~close.index.duplicated(keep="last")]
    if close.empty:
        return None
    cache_set(key, {"dates": [d.strftime("%Y-%m-%d") for d in close.index], "values": [round(float(v), 4) for v in close.values]})
    return close


def get_many_daily(symbols: list[str]) -> dict[str, pd.Series]:
    syms = list(dict.fromkeys(symbols))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(get_daily, syms))
    return {s: r for s, r in zip(syms, results) if r is not None}
