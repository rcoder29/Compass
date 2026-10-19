"""13F holdings maths — parsing SEC information tables, merging amendments, and comparing quarters.

Pure functions (text and dicts in, dicts out); downloads live in thirteenf_data.py and the HTTP surface in
routers/manager_holdings.py.

What a 13F is, and is not (these limits are shown on the page too):
  - Every US institutional manager above $100M files one within 45 days of each quarter end, listing its long positions in
    US-listed equities, ETFs, options and some convertible bonds. It is a snapshot at the quarter end, published up to 45 days
    later, so it is always out of date by the time it is seen.
  - It excludes short positions, most foreign-listed shares, cash and bonds; a manager can also ask the SEC to keep a position
    confidential, in which case it is omitted and may appear months later in an amendment.
  - A fund family or holding company files one report for everything it manages: Berkshire's covers its insurance portfolios, not
    Warren Buffett personally.

Values: filings submitted before 2023-01-03 report value in thousands of dollars; later ones in dollars. A manager reports one row
per sub-account and class, so rows are aggregated by CUSIP (the security identifier) before anything is compared.
"""
import xml.etree.ElementTree as ET

DOLLARS_FROM = "2023-01-03"          # filings on/after this date report dollars, earlier ones thousands
EPS = 1e-9


def _text(el, path):
    node = el.find(path)
    return None if node is None or node.text is None else node.text.strip()


def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def parse_infotable(xml_text: str, filing_date: str | None = None) -> list[dict]:
    """Rows of an SEC 13F information table, with values in dollars.

    Filers differ in how they write the XML (default namespace, an `ns1:` prefix, or none), so namespaces are stripped first. The unit
    comes from the filing date (thousands before 2023-01-03), and is then checked against the data: some filers still report thousands
    after the change, which shows up as a median implied share price under $1, so those values are scaled up."""
    root = ET.fromstring(xml_text)
    for el in root.iter():
        el.tag = el.tag.rsplit("}", 1)[-1]
    scale = 1 if (filing_date or DOLLARS_FROM) >= DOLLARS_FROM else 1000
    out = []
    for it in root.iter("infoTable"):
        out.append({
            "name": _text(it, "nameOfIssuer") or "", "class": _text(it, "titleOfClass") or "",
            "cusip": (_text(it, "cusip") or "").upper(), "value": _int(_text(it, "value")) * scale,
            "shares": _int(_text(it, "shrsOrPrnAmt/sshPrnamt")), "unit": _text(it, "shrsOrPrnAmt/sshPrnamtType") or "SH",
            "putCall": _text(it, "putCall"),
        })
    prices = [r["value"] / r["shares"] for r in out if r["unit"] == "SH" and not r["putCall"] and r["shares"] > 0 and r["value"] > 0]
    med = _median(prices)
    if med is not None and med < 1.0 and len(prices) >= 3:
        for r in out:
            r["value"] *= 1000
    return out


def aggregate(rows: list[dict]) -> dict:
    """{'positions': {cusip: {...}}, 'optionsValue', 'bondsValue', 'totalValue'} with share classes summed per CUSIP. Options (puts and
    calls) and principal-amount rows (bonds) are kept out of the share counts so a call position is not read as owning the stock."""
    pos, options, bonds = {}, 0, 0
    for r in rows:
        if r["putCall"]:
            options += r["value"]
            continue
        if r["unit"] == "PRN":
            bonds += r["value"]
            continue
        p = pos.setdefault(r["cusip"], {"cusip": r["cusip"], "name": r["name"], "class": r["class"], "value": 0, "shares": 0})
        p["value"] += r["value"]
        p["shares"] += r["shares"]
    return {"positions": pos, "optionsValue": options, "bondsValue": bonds, "totalValue": sum(p["value"] for p in pos.values())}


def merge_amendment(base: dict, amendment: dict, amendment_type: str | None) -> dict:
    """Apply a 13F-HR/A to its original. 'NEW HOLDINGS' amendments add positions the original left out (usually ones that had
    confidential treatment); a 'RESTATEMENT' replaces the original entirely."""
    if (amendment_type or "").upper().startswith("RESTATE"):
        return amendment
    pos = {k: dict(v) for k, v in base["positions"].items()}
    for cusip, p in amendment["positions"].items():
        if cusip in pos:
            pos[cusip]["value"] += p["value"]
            pos[cusip]["shares"] += p["shares"]
        else:
            pos[cusip] = dict(p)
    return {"positions": pos, "optionsValue": base["optionsValue"] + amendment["optionsValue"], "bondsValue": base["bondsValue"] + amendment["bondsValue"],
            "totalValue": sum(p["value"] for p in pos.values())}


# ── Comparing quarters ────────────────────────────────────────────────────────

def status_of(shares: int, prev_shares: int | None) -> tuple[str, float | None]:
    """('new' | 'added' | 'reduced' | 'unchanged', percent change in shares). Share changes, not value changes, are the manager's decisions."""
    if not prev_shares:
        return "new", None
    chg = shares / prev_shares - 1.0
    if abs(chg) < 0.005:
        return "unchanged", 0.0
    return ("added" if chg > 0 else "reduced"), chg


def compare(current: dict, previous: dict | None, history: list[dict] | None = None) -> dict:
    """Positions ranked by value with weight, change vs the previous quarter and share counts over `history` (oldest to newest, the
    current quarter last), plus the positions that were sold out. `history` entries are aggregate() results."""
    total = current["totalValue"] or 1
    prev_pos = (previous or {}).get("positions", {})
    rows = []
    for cusip, p in current["positions"].items():
        prev = prev_pos.get(cusip)
        status, chg = status_of(p["shares"], prev["shares"] if prev else None) if previous else ("unknown", None)
        rows.append({
            "cusip": cusip, "name": p["name"], "class": p["class"], "shares": p["shares"], "value": p["value"], "weight": p["value"] / total,
            "status": status, "sharesChangePct": chg, "prevShares": prev["shares"] if prev else None,
            "shareChange": (p["shares"] - prev["shares"]) if prev else p["shares"] if previous else None,
            "prevWeight": (prev["value"] / (previous["totalValue"] or 1)) if prev else None,
            "history": [h["positions"].get(cusip, {}).get("shares", 0) for h in (history or [])],
        })
    rows.sort(key=lambda r: -r["value"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    exited = []
    if previous:
        ptotal = previous["totalValue"] or 1
        exited = sorted(({"cusip": c, "name": p["name"], "class": p["class"], "prevShares": p["shares"], "prevValue": p["value"], "prevWeight": p["value"] / ptotal}
                         for c, p in prev_pos.items() if c not in current["positions"]), key=lambda e: -e["prevValue"])
    return {"positions": rows, "exited": exited}


def summarize(rows: list[dict], exited: list[dict], current: dict, previous: dict | None) -> dict:
    ws = sorted((r["weight"] for r in rows), reverse=True)
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("new", "added", "reduced", "unchanged")}
    counts["exited"] = len(exited)
    return {
        "totalValue": current["totalValue"], "positions": len(rows), "top5": sum(ws[:5]), "top10": sum(ws[:10]), "largestWeight": ws[0] if ws else None,
        "optionsValue": current["optionsValue"], "bondsValue": current["bondsValue"], "counts": counts,
        "previousValue": previous["totalValue"] if previous else None,
        "valueChangePct": (current["totalValue"] / previous["totalValue"] - 1.0) if previous and previous["totalValue"] else None,
    }


def concentration_series(reports: list[dict]) -> list[dict]:
    """Total value, number of positions and top-5 weight for each period (oldest first): `reports` = [{'period', 'data'}, ...]."""
    out = []
    for r in reports:
        pos = sorted(r["data"]["positions"].values(), key=lambda p: -p["value"])
        total = r["data"]["totalValue"] or 1
        out.append({"period": r["period"], "totalValue": r["data"]["totalValue"], "positions": len(pos), "top5": sum(p["value"] for p in pos[:5]) / total})
    return out


# ── Returns from prices ───────────────────────────────────────────────────────

def weighted_return(rows: list[dict], start_key: str, end_key: str = "priceNow") -> dict | None:
    """Value-weighted return of the positions that have both prices, using the reported values as weights: what the reported portfolio
    would have returned from the start price to the end price. Returns {'return', 'coverage'} (coverage = share of value included)."""
    num = den = covered = 0.0
    for r in rows:
        a, b = r.get(start_key), r.get(end_key)
        if a and b and a > 0:
            num += r["value"] * (b / a - 1.0)
            den += r["value"]
            covered += r["value"]
    total = sum(r["value"] for r in rows) or 1
    return {"return": num / den, "coverage": covered / total} if den > 0 else None


def next_deadline(period_end: str) -> str:
    """The date the next report is due: 45 days after the following quarter end."""
    from datetime import date, timedelta
    y, m, d = (int(x) for x in period_end.split("-"))
    m += 3
    if m > 12:
        m -= 12
        y += 1
    last = {3: 31, 6: 30, 9: 30, 12: 31}.get(m, 30)
    return (date(y, m, last) + timedelta(days=45)).isoformat()
