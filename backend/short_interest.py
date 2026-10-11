"""Short-interest monitor maths — ranking, borrow cost, bond matching and the equity-vs-credit displacement signal.

Pure functions (text and dicts in, dicts out) so every rule can be tested against hand-built data; the downloads live in
short_interest_data.py and the HTTP surface in routers/short_interest.py.

Sources and what each does and doesn't tell you:
  - FINRA bi-monthly short interest (public CSV, every exchange-listed stock): shares sold short at settlement, the prior
    figure, average daily volume and days to cover. It is published twice a month and is roughly a week old when released.
  - Float and market cap come from Yahoo Finance. "Short interest % of float" = FINRA shares short / float.
  - Borrow cost comes from Interactive Brokers' public stock-loan table: the annualised fee to borrow, the rebate and
    the shares IBKR has available. It is one broker's indicative rate, not a market-wide quote, and the hardest-to-borrow
    names are often missing or marked unavailable.
  - Bond data comes from the corporate-bond ETFs' latest SEC N-PORT filings (price is market value / par, a quarterly
    snapshot). Only issuers held by those funds can be matched, and matching is by company name, so every match shows the
    issuer name it used. For the rest, an implied interest rate from the income statement (interest expense / debt) is
    shown as a weaker, lagging proxy.

Displacement: heavily shorted stocks say the equity market expects trouble; bond spreads say how much the credit market
agrees. When shorts are piling in but the bonds trade tight, the equity market is more pessimistic than lenders (a
valuation or growth call, or a squeeze setup); when spreads are wide too, both agree. This is a way to organise questions,
not a trading signal.
"""
import csv
import io
import math
import re
from datetime import date, datetime

EXCHANGES = {"NNM", "NYSE", "SC", "AMEX"}      # FINRA market classes that are common-stock venues (ARCA/BZX are mostly ETFs)
_NOT_COMMON = re.compile(r"\bwarrants?\b|\betf\b|\btrust\b|\bfund\b|\bnotes?\b|\bunits?\b|\bdepositary\b|\bpreferred\b|\brights?\b", re.I)
MIN_ADV = 150_000
MIN_SHORT = 1_000_000

BORROW_BANDS = [(1.0, "General collateral", "easy"), (5.0, "Elevated", "warm"), (25.0, "Hard to borrow", "hard"), (math.inf, "Very hard to borrow", "extreme")]
SPREAD_BANDS = [(200.0, "Tight", "tight"), (400.0, "Moderate", "moderate"), (700.0, "Wide", "wide"), (math.inf, "Distressed", "distressed")]


def _num(x):
    try:
        v = float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


# ── FINRA ─────────────────────────────────────────────────────────────────────

def parse_finra(text: str) -> list[dict]:
    """Rows of the FINRA short-interest CSV (pipe-delimited), skipping any with no usable share count."""
    out = []
    for r in csv.DictReader(io.StringIO(text), delimiter="|"):
        short, prev = _num(r.get("currentShortPositionQuantity")), _num(r.get("previousShortPositionQuantity"))
        sym = (r.get("symbolCode") or "").strip()
        if not sym or short is None:
            continue
        out.append({"symbol": sym, "name": (r.get("issueName") or "").strip(), "exchange": (r.get("marketClassCode") or "").strip(),
                    "short": short, "prevShort": prev, "adv": _num(r.get("averageDailyVolumeQuantity")),
                    "daysToCover": _num(r.get("daysToCoverQuantity")), "changePct": _num(r.get("changePercent")),
                    "settlement": (r.get("settlementDate") or "").strip()})
    return out


def select_candidates(rows: list[dict], by_short: int = 400, by_dtc: int = 200) -> list[dict]:
    """Liquid exchange-listed common stocks worth looking up: the largest short positions plus the highest days-to-cover
    (a small float can be heavily shorted with few shares, so shares-short alone would miss it)."""
    pool = [r for r in rows if r["exchange"] in EXCHANGES and not _NOT_COMMON.search(r["name"])
            and (r["adv"] or 0) >= MIN_ADV and r["short"] >= MIN_SHORT]
    top_short = sorted(pool, key=lambda r: -r["short"])[:by_short]
    top_dtc = sorted(pool, key=lambda r: -(r["daysToCover"] or 0))[:by_dtc]
    seen, out = set(), []
    for r in top_short + top_dtc:
        if r["symbol"] not in seen:
            seen.add(r["symbol"])
            out.append(r)
    return out


# ── Borrow (Interactive Brokers stock-loan table) ─────────────────────────────

def parse_ibkr(text: str) -> tuple[dict[str, dict], str | None]:
    """({symbol: {fee, rebate, available, availableCapped}}, 'YYYY-MM-DD HH:MM:SS' file timestamp). Fee and rebate are
    annualised percentages; 'NA' becomes None; '>10000000' means at least that many shares."""
    out, stamp = {}, None
    for line in text.splitlines():
        if line.startswith("#BOF"):
            stamp = line.split("|", 1)[1].replace("|", " ").replace(".", "-", 2) if "|" in line else None      # 2026.10.11|17:43:33 -> 2026-10-11 17:43:33
            continue
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("|")
        if len(f) < 8:
            continue
        avail_raw = f[7].strip()
        capped = avail_raw.startswith(">")
        out[f[0].strip()] = {"fee": _num(f[6]), "rebate": _num(f[5]), "available": _num(avail_raw.lstrip(">")), "availableCapped": capped}
    return out, stamp


def band(value: float | None, bands: list[tuple[float, str, str]]):
    if value is None:
        return None
    for limit, label, key in bands:
        if value < limit:
            return {"label": label, "key": key}
    return None


# ── Ranking ───────────────────────────────────────────────────────────────────

def rank_rows(finra: dict[str, dict], infos: dict[str, dict], min_cap: float = 300e6, limit: int = 100) -> list[dict]:
    """Stocks ranked by short interest as a share of float, highest first. Needs a Yahoo record that says it's an equity
    with a float and market cap; fund-like and tiny names drop out."""
    rows = []
    for sym, f in finra.items():
        info = infos.get(sym)
        if not info or info.get("quoteType") not in (None, "EQUITY"):
            continue
        cap = info.get("marketCap")
        flt = info.get("floatShares") or info.get("sharesOutstanding")
        if not cap or cap < min_cap or not flt or flt <= 0:
            continue
        pct = f["short"] / flt
        rows.append({
            "symbol": sym, "name": info.get("name") or f["name"], "sector": info.get("sector"), "exchange": f["exchange"],
            "price": info.get("price"), "marketCap": cap, "floatShares": flt,
            "sharesShort": f["short"], "prevShort": f["prevShort"], "changePct": f["changePct"], "adv": f["adv"], "daysToCover": f["daysToCover"],
            "siPctFloat": pct, "change52w": info.get("change52w"), "settlement": f["settlement"],
        })
    rows.sort(key=lambda r: -r["siPctFloat"])
    rows = rows[:limit]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ── Bonds ─────────────────────────────────────────────────────────────────────

_SUFFIXES = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HOLDINGS", "HOLDING", "HLDGS", "HLDG", "GROUP", "GRP", "LLC", "LP",
             "NV", "SA", "AG", "SE", "THE", "CLASS", "A", "B", "C", "COMMON", "STOCK", "ORDINARY", "SHARES", "ADR", "NEW", "DE", "INTL", "INTERNATIONAL"}


def normalize_name(name: str | None) -> str:
    """Upper-case company name without punctuation or generic corporate words, for matching issuers to companies."""
    if not name:
        return ""
    s = re.sub(r"[^A-Z0-9 ]", " ", name.upper().replace("&", " AND "))
    toks = [t for t in s.split() if t not in _SUFFIXES]
    return " ".join(toks)


def match_issuer(company: str, issuer: str) -> str | None:
    """'exact' if the normalised names are equal; 'prefix' if one is a whole-word prefix of the other and distinctive enough
    (two or more words, or a single word of 8+ letters); otherwise None."""
    if not company or not issuer:
        return None
    if company == issuer:
        return "exact"
    short, long_ = (company, issuer) if len(company) <= len(issuer) else (issuer, company)
    if long_.startswith(short + " ") and (len(short.split()) >= 2 or len(short) >= 8):
        return "prefix"
    return None


def build_bond_index(funds: dict[str, tuple[str, list[dict]]], treasury: list[dict], today: date, price_fn, ytm_fn, interp_fn) -> dict[str, dict]:
    """{normalised issuer: {issuer, bonds: [...]}} from bond-ETF holdings. A bond held by several funds is merged by CUSIP
    (market values add; the price comes from the largest holder). Bonds under three months or with no usable price are dropped."""
    merged: dict[str, dict] = {}
    for fund, (grade, holdings) in funds.items():
        for h in holdings:
            issuer, mat = h.get("issuerName"), h.get("maturityDate")
            if not issuer or not mat:
                continue
            key = h.get("cusip") or f"{issuer}:{mat}:{h.get('couponRate')}"
            mv = h.get("marketValue") or 0
            b = merged.setdefault(key, {"cusip": h.get("cusip"), "issuer": issuer, "coupon": h.get("couponRate"), "maturity": mat, "mv": 0.0,
                                        "grades": set(), "price": None, "_pmv": -1, "default": bool(h.get("isDefault"))})
            b["mv"] += mv
            b["grades"].add(grade)
            p = price_fn(h)
            if p and mv > b["_pmv"]:
                b["price"], b["_pmv"] = p, mv
    index: dict[str, dict] = {}
    for b in merged.values():
        try:
            years = (datetime.strptime(b["maturity"], "%Y-%m-%d").date() - today).days / 365.25
        except ValueError:
            continue
        if years < 0.25 or b["price"] is None or b["coupon"] is None:
            continue
        ytm = ytm_fn(b["price"], b["coupon"], years)
        if ytm is None:
            continue
        ust = interp_fn(years, treasury)
        entry = {"cusip": b["cusip"], "coupon": b["coupon"], "maturity": b["maturity"], "years": round(years, 2), "price": b["price"], "ytm": ytm,
                 "spreadBps": None if ust is None else round((ytm - ust) * 100), "mv": b["mv"], "grades": sorted(b["grades"]), "default": b["default"]}
        index.setdefault(normalize_name(b["issuer"]), {"issuer": b["issuer"], "bonds": []})["bonds"].append(entry)
    return index


def company_bonds(index: dict[str, dict], names: list[str | None]) -> dict | None:
    """Summary of the bonds issued by a company, matched by name, or None when no fund holds any. Averages are weighted by
    the funds' holdings (market value), so widely held benchmark bonds count most."""
    targets = [n for n in (normalize_name(x) for x in names) if n]
    matches = []
    for norm, entry in index.items():
        kinds = [match_issuer(t, norm) for t in targets]
        kind = "exact" if "exact" in kinds else "prefix" if "prefix" in kinds else None
        if kind:
            matches.append((kind, entry))
    if any(k == "exact" for k, _ in matches):
        matches = [m for m in matches if m[0] == "exact"]          # an exact match beats looser ones
    bonds = [b for _, e in matches for b in e["bonds"]]
    if not bonds:
        return None
    def weights(items):
        total = sum(b["mv"] for b in items)
        return [(b["mv"] / total) if total > 0 else 1.0 / len(items) for b in items]
    with_spread = [b for b in bonds if b["spreadBps"] is not None]
    wavg = lambda key: sum(b[key] * w for b, w in zip(with_spread, weights(with_spread))) if with_spread else None
    grades = {g for b in bonds for g in b["grades"]}
    top = sorted(bonds, key=lambda b: -b["mv"])
    return {
        "issuer": matches[0][1]["issuer"], "matchType": matches[0][0], "count": len(bonds),
        "avgCoupon": round(sum(b["coupon"] * w for b, w in zip(bonds, weights(bonds))), 3),
        "avgYtm": None if not with_spread else round(wavg("ytm"), 3), "avgSpreadBps": None if not with_spread else round(wavg("spreadBps")),
        "grade": "HY" if "HY" in grades and "IG" not in grades else "IG" if "IG" in grades and "HY" not in grades else "Mixed",
        "inDefault": any(b["default"] for b in bonds),
        "nextMaturity": min(b["maturity"] for b in bonds), "lastMaturity": max(b["maturity"] for b in bonds),
        "top": [{k: b[k] for k in ("coupon", "maturity", "price", "ytm", "spreadBps", "grades")} for b in top[:5]],
    }


def credit_proxy(stmt: dict | None, ust10: float | None) -> dict | None:
    """Interest actually paid, from the income statement: interest expense / total debt, interest cover (EBIT / interest),
    and the implied rate's gap to the 10-year Treasury in basis points (a lagging, blunt proxy for the credit spread)."""
    if not stmt:
        return None
    exp, debt, ebit = stmt.get("interestExpense"), stmt.get("totalDebt"), stmt.get("ebit")
    exp = abs(exp) if exp is not None else None
    out = {"interestExpense": exp, "totalDebt": debt, "impliedRate": None, "coverage": None, "proxySpreadBps": None,
           "netDebt": None if debt is None or stmt.get("totalCash") is None else debt - stmt["totalCash"]}
    if exp and debt and debt > 0:
        rate = exp / debt * 100.0
        if 0 < rate < 60:
            out["impliedRate"] = round(rate, 2)
            if ust10 is not None:
                out["proxySpreadBps"] = round((rate - ust10) * 100)
    if exp and ebit is not None:
        out["coverage"] = round(ebit / exp, 1)
    return out if any(out[k] is not None for k in ("impliedRate", "coverage", "netDebt")) else None


MIN_PROXY_RATE = 3.0         # an implied rate below this is mostly near-zero-coupon convertibles, which says nothing about credit stress
MIN_PROXY_DEBT_TO_CAP = 0.02


def proxy_usable(cp: dict | None, market_cap: float | None) -> bool:
    """The interest-paid proxy only stands in for a bond spread when the rate is meaningful (3%+) and the debt is not
    trivial next to the company's size; otherwise the company has no usable credit read."""
    if not cp or cp.get("impliedRate") is None or cp.get("proxySpreadBps") is None:
        return False
    if cp["impliedRate"] < MIN_PROXY_RATE:
        return False
    debt = cp.get("totalDebt")
    return not (market_cap and debt is not None and debt < MIN_PROXY_DEBT_TO_CAP * market_cap)


# ── Displacement ──────────────────────────────────────────────────────────────

def classify_displacement(si_pct: float, spread_bps: float | None, is_proxy: bool = False, in_default: bool = False) -> dict:
    """How the credit market's view compares with the short sellers'. Thresholds on the spread: under 400 bps lenders see
    little default risk, 400-700 is wide, 700+ is distressed."""
    eq = f"{si_pct:.0%} of the float is sold short"
    if in_default:
        return {"key": "confirmed", "label": "Credit confirms", "tone": "bad", "text": f"{eq}, and a bond is flagged in default: lenders and short sellers agree."}
    if spread_bps is None:
        return {"key": "none", "label": "No bond read", "tone": "none", "text": f"{eq}, but no bond data was found to compare. Equity view only."}
    src = "an implied-rate proxy for the spread" if is_proxy else "bond spreads"
    if spread_bps >= SPREAD_BANDS[2][0]:
        return {"key": "confirmed", "label": "Credit confirms", "tone": "bad", "text": f"{eq}, and {src} are around {spread_bps:.0f} bps over Treasuries: both markets are pricing real distress."}
    if spread_bps >= SPREAD_BANDS[1][0]:
        return {"key": "partial", "label": "Partly confirmed", "tone": "warn", "text": f"{eq}; {src} are wide at about {spread_bps:.0f} bps, so credit is uneasy but not pricing distress."}
    return {"key": "equity_leads", "label": "Equity ahead of credit", "tone": "info",
            "text": f"{eq}, yet {src} are only about {spread_bps:.0f} bps: lenders see little default risk. Shorts are betting on valuation or growth, not solvency, which also leaves squeeze risk if the story turns."}


def percentile(values: list[float], v: float) -> float:
    return 100.0 * sum(1 for x in values if x <= v) / len(values) if values else 0.0


def build_rows(ranked: list[dict], borrow: dict[str, dict], bond_index: dict[str, dict], credit: dict[str, dict], ust10: float | None) -> list[dict]:
    """Attach borrow cost, bond summary, interest-paid proxy and the displacement read to each ranked stock."""
    out = []
    for r in ranked:
        b = borrow.get(r["symbol"])
        bonds = company_bonds(bond_index, [r["name"]]) if bond_index else None
        cp = credit_proxy(credit.get(r["symbol"]), ust10)
        if bonds and bonds["avgSpreadBps"] is not None:
            spread, proxy = bonds["avgSpreadBps"], False
        elif proxy_usable(cp, r.get("marketCap")):
            spread, proxy = cp["proxySpreadBps"], True
        else:
            spread, proxy = None, True
        disp = classify_displacement(r["siPctFloat"], spread, proxy, bool(bonds and bonds["inDefault"]))
        out.append({**r, "borrow": None if not b else {**b, "band": band(b["fee"], BORROW_BANDS)},
                    "bonds": bonds, "interestPaid": cp, "spreadBps": spread, "spreadIsProxy": proxy if spread is not None else None, "displacement": disp})
    eq_vals = [r["siPctFloat"] for r in out]
    sp_vals = [r["spreadBps"] for r in out if r["spreadBps"] is not None]
    for r in out:
        r["equityPercentile"] = round(percentile(eq_vals, r["siPctFloat"]))
        r["creditPercentile"] = None if r["spreadBps"] is None else round(percentile(sp_vals, r["spreadBps"]))
        r["displacementScore"] = None if r["creditPercentile"] is None else r["equityPercentile"] - r["creditPercentile"]
    return out


def summarize(rows: list[dict]) -> dict:
    sis = sorted(r["siPctFloat"] for r in rows)
    fees = [(r["borrow"]["fee"], r) for r in rows if r.get("borrow") and r["borrow"]["fee"] is not None]
    keys = [r["displacement"]["key"] for r in rows]
    by_change = sorted([r for r in rows if r.get("changePct") is not None and (r.get("prevShort") or 0) > 0], key=lambda r: -r["changePct"])
    return {
        "count": len(rows), "medianSi": sis[len(sis) // 2] if sis else None, "above30": sum(1 for s in sis if s >= 0.30),
        "withBorrow": len(fees), "hardToBorrow": sum(1 for f, _ in fees if f >= BORROW_BANDS[1][0]),
        "mostExpensive": [{"symbol": r["symbol"], "fee": f} for f, r in sorted(fees, key=lambda x: -x[0])[:3]],
        "biggestIncreases": [{"symbol": r["symbol"], "changePct": r["changePct"]} for r in by_change[:3]],
        "withBonds": sum(1 for r in rows if r.get("bonds")), "withProxy": sum(1 for r in rows if r.get("spreadIsProxy")),
        "displacement": {k: keys.count(k) for k in ("equity_leads", "partial", "confirmed", "none")},
    }
