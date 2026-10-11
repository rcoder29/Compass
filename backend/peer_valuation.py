"""Peer-relative valuation — is this stock cheap or expensive compared with similar companies, and is that earned?

Pure functions over plain dicts (no network): peer_data.py fetches, routers/tear_sheet_peers.py serves.

What it computes, for a stock and a set of peers:
  - Six valuation multiples (forward and trailing P/E, EV/EBITDA, price/sales, price/book, FCF yield) and three quality measures
    (revenue growth, operating margin, return on equity). For each: the stock's value, the peer median and quartiles, the premium or
    discount to the median, and the share of peers it is cheaper than (valuation) or better than (quality).
  - An *expensiveness rank* (average share of peers the stock is pricier than, 0-100) and a *quality rank* (average share of peers it
    beats). Together they give the read: a premium with stronger fundamentals "looks earned"; a premium without them does not; a
    discount with stronger fundamentals is the interesting case; a discount with weaker fundamentals may be deserved.
  - A peer-implied price: what the stock would cost at the peers' median (and 25th-75th percentile) multiples. It ignores differences in
    growth and risk, so it is a reference point, not a target.

Judgement calls, stated plainly: multiples that are negative or absurd are ignored; financial companies skip EV/EBITDA, FCF yield and
price/sales, and REITs skip P/E, because those measures don't mean the same thing there; a metric needs at least four peers with a
value to count; and the rank thresholds (35/65 for price, 40/60 for quality) are rules of thumb.
"""
import math
import statistics

MIN_PEERS = 4              # a comparison needs at least this many peers in total
MIN_METRIC_PEERS = 4       # ...and a metric needs this many peers with a usable value
MAX_PEERS = 12
WIDE_RATIO = 3.0           # an implied price more than 3x above or below the market price is flagged as probably not a like-for-like comparison
EXPENSIVE_AT, CHEAP_AT = 65.0, 35.0
STRONG_AT, WEAK_AT = 60.0, 40.0

# (key, label, kind, lower_is_cheaper, valid range)
VALUATION = [
    ("forwardPE", "P/E (forward)", "x", True, (0, 150)),
    ("trailingPE", "P/E (trailing)", "x", True, (0, 150)),
    ("evToEbitda", "EV / EBITDA", "x", True, (0, 100)),
    ("priceToSales", "Price / sales", "x", True, (0, 100)),
    ("priceToBook", "Price / book", "x", True, (0, 100)),
    ("fcfYield", "FCF yield", "%", False, (-0.5, 0.5)),
]
QUALITY = [
    ("revenueGrowth", "Revenue growth", "%", (-1.0, 5.0)),
    ("operatingMargin", "Operating margin", "%", (-2.0, 1.0)),
    ("roe", "Return on equity", "%", (-2.0, 3.0)),
]
SECTOR_SKIPS = {"Financial Services": {"evToEbitda", "fcfYield", "priceToSales"}, "Real Estate": {"trailingPE", "forwardPE", "fcfYield"}}
PRICE_SCALED = ("forwardPE", "trailingPE", "priceToSales", "priceToBook")      # price moves in proportion to the multiple
BOOK_VALUE_SECTORS = {"Financial Services", "Real Estate"}                      # price/book only means something for the implied price here


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def metric_value(rec: dict, key: str, lo_hi, inclusive: bool = False) -> float | None:
    """A usable number for `key`, or None. Multiples must be positive (exclusive lower bound) and below a sanity cap; yields, growth,
    margins and returns may legitimately be zero or negative (inclusive bounds)."""
    v = _num(rec.get(key))
    if v is None:
        return None
    lo, hi = lo_hi
    return v if ((lo <= v <= hi) if inclusive else (lo < v <= hi)) else None


def percentile_of(values: list[float], q: float) -> float:
    return float(statistics.quantiles(values, n=100, method="inclusive")[max(0, min(98, int(round(q)) - 1))]) if len(values) >= 2 else values[0]


SIZE_BANDS = [(0.1, 20), (0.02, 50), (0.005, 200)]      # market cap as a multiple of the subject's, from tight to loose
MIN_PEER_CAP = 300e6                                      # below this a "peer" is a micro-cap whose multiples are noise (unless the subject is tiny too)


def choose_peers(subject_cap: float | None, candidates: list[dict], limit: int = MAX_PEERS, bands: list[tuple] | None = None) -> list[dict]:
    """The `limit` candidates closest to the subject in market cap. The size band widens step by step (a tenth to 20x, then a fiftieth
    to 50x, then a two-hundredth to 200x) until at least six peers fit, and companies under $300M are never used for a larger subject,
    so a mega-cap is not compared with micro-caps just because its industry is thin. Pass a shorter `bands` list (the router uses only
    the tightest band for a broad sector, where the biggest companies tell you nothing about a small one)."""
    bands = bands or SIZE_BANDS
    floor = min(MIN_PEER_CAP, 0.1 * subject_cap) if subject_cap else MIN_PEER_CAP
    pool = [c for c in candidates if c.get("marketCap") and c["marketCap"] >= floor]
    if subject_cap:
        chosen = None
        for lo, hi in bands:
            near = [c for c in pool if lo <= c["marketCap"] / subject_cap <= hi]
            if len(near) >= 6:
                chosen = near
                break
        if chosen is None:                                            # thin industry: the widest band, even if short of six
            chosen = [c for c in pool if bands[-1][0] <= c["marketCap"] / subject_cap <= bands[-1][1]]
        pool = sorted(chosen, key=lambda c: abs(math.log(c["marketCap"] / subject_cap)))
    else:
        pool.sort(key=lambda c: -c["marketCap"])
    return pool[:limit]


def applicable(sector: str | None) -> list[tuple]:
    skips = SECTOR_SKIPS.get(sector or "", set())
    return [m for m in VALUATION if m[0] not in skips]


def _implied_prices(subject: dict, key: str, peer_levels: dict) -> dict | None:
    """Price at the peer 25th / median / 75th percentile multiple. EV/EBITDA goes through enterprise value and net debt."""
    price, cap = _num(subject.get("price")), _num(subject.get("marketCap"))
    if not price or price <= 0:
        return None
    out = {}
    for tag, mult in peer_levels.items():
        if key in PRICE_SCALED:
            s = _num(subject.get(key))
            if not s or s <= 0:
                return None
            out[tag] = price * mult / s
        elif key == "evToEbitda":
            ebitda, net_debt = _num(subject.get("ebitda")), _num(subject.get("netDebt"))
            if not ebitda or ebitda <= 0 or not cap or cap <= 0 or net_debt is None:
                return None
            out[tag] = price * (mult * ebitda - net_debt) / cap
        else:
            return None
    return out if all(v is not None and v > 0 for v in out.values()) else None


def read_verdict(expensive: float | None, quality: float | None) -> dict:
    """The combined read from the two ranks. Returns {key, label, tone, text}."""
    if expensive is None:
        return {"key": "unknown", "label": "Not enough peer data", "tone": "neutral", "text": "Too few usable multiples to rank this stock against its peers."}
    price = "pricey" if expensive >= EXPENSIVE_AT else "cheap" if expensive <= CHEAP_AT else "inline"
    qual = None if quality is None else "strong" if quality >= STRONG_AT else "weak" if quality <= WEAK_AT else "similar"
    table = {
        ("pricey", "strong"): ("premium_earned", "Premium looks earned", "neutral", "It trades above most peers, but its growth, margins and returns are also better than most, which can justify paying more."),
        ("pricey", "similar"): ("premium_unexplained", "Pricier than peers, no clear edge", "bad", "It trades above most peers without clearly better growth, margins or returns."),
        ("pricey", "weak"): ("premium_unearned", "Expensive and weaker than peers", "bad", "It trades above most peers while its growth, margins and returns are weaker than most: the premium is hard to explain."),
        ("pricey", None): ("premium_unexplained", "Pricier than peers", "bad", "It trades above most peers; there is not enough data to judge whether its fundamentals explain that."),
        ("inline", "strong"): ("inline_strong", "In line with peers, stronger business", "good", "It is priced like its peers while its fundamentals rank better than most."),
        ("inline", "similar"): ("inline", "In line with peers", "neutral", "Valuation and fundamentals both sit close to the middle of the peer group."),
        ("inline", "weak"): ("inline_weak", "In line with peers, weaker business", "neutral", "It is priced like its peers although its fundamentals rank below most."),
        ("inline", None): ("inline", "In line with peers", "neutral", "Valuation sits close to the middle of the peer group."),
        ("cheap", "strong"): ("discount_strong", "Cheaper than peers despite stronger fundamentals", "good", "It trades below most peers while its growth, margins and returns are better than most: the case worth investigating."),
        ("cheap", "similar"): ("discount", "Cheaper than peers", "good", "It trades below most peers with similar fundamentals."),
        ("cheap", "weak"): ("discount_deserved", "Cheap, but the discount may be deserved", "neutral", "It trades below most peers, though its fundamentals are also weaker than most: a classic value-trap check."),
        ("cheap", None): ("discount", "Cheaper than peers", "good", "It trades below most peers; there is not enough data to judge its fundamentals against theirs."),
    }
    key, label, tone, text = table[(price, qual)]
    return {"key": key, "label": label, "tone": tone, "text": text}


def compare(subject: dict, peers: list[dict]) -> dict | None:
    """The full comparison, or None when there are too few peers. `subject` and each peer are flat dicts of raw fields."""
    if len(peers) < MIN_PEERS:
        return None
    metrics, e_scores, q_scores, premiums, implied_mid, implied_lo, implied_hi = [], [], [], [], [], [], []
    for key, label, unit, lower_cheaper, rng in applicable(subject.get("sector")):
        inc = key == "fcfYield"
        s = metric_value(subject, key, rng, inc)
        vals = [v for v in (metric_value(p, key, rng, inc) for p in peers) if v is not None]
        row = {"key": key, "label": label, "unit": unit, "group": "valuation", "value": s, "peers": len(vals), "median": None, "p25": None, "p75": None,
               "premium": None, "cheaperThan": None, "expensiveness": None, "impliedPrice": None}
        if s is not None and len(vals) >= MIN_METRIC_PEERS:
            med = statistics.median(vals)
            row.update(median=med, p25=percentile_of(vals, 25), p75=percentile_of(vals, 75))
            cheaper = sum(1 for v in vals if (v < s if lower_cheaper else v > s))      # peers that are cheaper than the subject
            row["cheaperThan"] = len(vals) - cheaper - sum(1 for v in vals if v == s)  # peers the subject is cheaper than
            row["expensiveness"] = round(100.0 * cheaper / len(vals), 1)
            e_scores.append(100.0 * cheaper / len(vals))
            if lower_cheaper and med:
                row["premium"] = s / med - 1.0
                premiums.append(row["premium"])
            book_ok = key != "priceToBook" or subject.get("sector") in BOOK_VALUE_SECTORS
            imp = _implied_prices(subject, key, {"low": row["p25"], "mid": med, "high": row["p75"]}) if lower_cheaper and book_ok else None
            if imp:
                row["impliedPrice"] = {k: round(v, 2) for k, v in imp.items()}
                implied_lo.append(imp["low"]); implied_mid.append(imp["mid"]); implied_hi.append(imp["high"])
        metrics.append(row)
    for key, label, unit, rng in QUALITY:
        s = metric_value(subject, key, rng, True)
        vals = [v for v in (metric_value(p, key, rng, True) for p in peers) if v is not None]
        row = {"key": key, "label": label, "unit": unit, "group": "quality", "value": s, "peers": len(vals), "median": None, "p25": None, "p75": None,
               "premium": None, "cheaperThan": None, "expensiveness": None, "impliedPrice": None, "betterThan": None, "quality": None}
        if s is not None and len(vals) >= MIN_METRIC_PEERS:
            worse = sum(1 for v in vals if v < s)
            row.update(median=statistics.median(vals), p25=percentile_of(vals, 25), p75=percentile_of(vals, 75), betterThan=worse, quality=round(100.0 * worse / len(vals), 1))
            q_scores.append(100.0 * worse / len(vals))
        metrics.append(row)
    expensive = round(sum(e_scores) / len(e_scores), 1) if len(e_scores) >= 2 else None
    quality = round(sum(q_scores) / len(q_scores), 1) if len(q_scores) >= 2 else None
    price = _num(subject.get("price"))
    peer_implied = None
    if implied_mid and price:
        mid = statistics.median(implied_mid)
        peer_implied = {"low": round(statistics.median(implied_lo), 2), "mid": round(mid, 2), "high": round(statistics.median(implied_hi), 2), "vsPrice": mid / price - 1.0, "price": price,
                        "metrics": [m["key"] for m in metrics if m["impliedPrice"]],
                        "farFromPrice": not (1 / WIDE_RATIO <= mid / price <= WIDE_RATIO)}
    return {
        "verdict": read_verdict(expensive, quality), "expensiveRank": expensive, "qualityRank": quality,
        "medianPremium": statistics.median(premiums) if premiums else None, "premiumCount": len(premiums),
        "metrics": metrics, "peerImplied": peer_implied, "scatter": scatter(subject, peers),
    }


def scatter(subject: dict, peers: list[dict]) -> dict | None:
    """Growth against the first valuation multiple that at least five companies (peers plus the subject) have: shows whether a premium
    sits where faster growth would predict."""
    for key, label, _unit, _lc, rng in applicable(subject.get("sector")):
        pts = []
        for rec, is_subject in [(subject, True)] + [(p, False) for p in peers]:
            x, y = metric_value(rec, "revenueGrowth", (-1.0, 5.0), True), metric_value(rec, key, rng, key == "fcfYield")
            if x is not None and y is not None:
                pts.append({"symbol": rec.get("symbol"), "x": x, "y": y, "isSubject": is_subject})
        if len(pts) >= 5 and any(p["isSubject"] for p in pts):
            return {"xLabel": "Revenue growth", "yLabel": label, "yKey": key, "points": pts}
    return None


def headline(subject_symbol: str, result: dict) -> str:
    """One sentence for the top of the section."""
    prem, n = result.get("medianPremium"), result.get("premiumCount", 0)
    imp = result.get("peerImplied")
    if prem is None:
        return f"{subject_symbol}: not enough comparable multiples to measure a premium or discount to its peers."
    word = "premium" if prem >= 0 else "discount"
    basis = f"median across {n} multiples" if n >= 3 else f"based on only {n} multiple{'s' if n != 1 else ''}, so treat it loosely"
    text = f"{subject_symbol} trades at a {abs(prem):.0%} {word} to the peer median ({basis})."
    if imp:
        text += f" At peer-median multiples it would be about ${imp['mid']:,.2f} ({imp['vsPrice']:+.0%} from ${imp['price']:,.2f})."
    return text


def peer_row(rec: dict) -> dict:
    """The compact record shown in the peers table."""
    out = {"symbol": rec.get("symbol"), "name": rec.get("name"), "marketCap": rec.get("marketCap")}
    for key, *_ in VALUATION:
        out[key] = rec.get(key)
    for key, *_ in QUALITY:
        out[key] = rec.get(key)
    return out
