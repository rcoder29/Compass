"""Shared back-off for Yahoo Finance rate limiting (HTTP 429 "Too Many Requests").

Yahoo blocks an IP that makes too many requests, and the block lasts minutes to hours. Every worker that fetches
per-symbol data calls `wait_if_paused()` before a request and `rate_limited()` when one is refused; a refusal pauses
*all* workers, and the pause grows with consecutive refusals (20 s, 45 s, 90 s) so a long block is not hammered.
A success resets it. Failures are never cached by callers, so a block never poisons the cache.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

BACKOFF = (20, 45, 90)
_pause_until = 0.0
_strikes = 0
_lock = threading.Lock()


def is_rate_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "429" in text


def wait_if_paused() -> None:
    while True:
        delay = _pause_until - time.time()
        if delay <= 0:
            return
        time.sleep(min(delay, 1.0))


def rate_limited() -> None:
    global _pause_until, _strikes
    with _lock:
        wait = BACKOFF[min(_strikes, len(BACKOFF) - 1)]
        _strikes += 1
        _pause_until = max(_pause_until, time.time() + wait)
    logger.warning("Yahoo rate limit hit; pausing per-symbol fetches for %ds", wait)


def success() -> None:
    global _strikes
    _strikes = 0


def paused_for() -> float:
    return max(0.0, _pause_until - time.time())
