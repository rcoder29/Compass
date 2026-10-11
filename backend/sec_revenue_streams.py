"""Revenue by income stream (product / segment / region) from SEC XBRL filings.

yfinance has no revenue breakdown, but every 10-Q/10-K carries one in its XBRL instance
document, tagged on a dimension (ProductOrServiceAxis, StatementBusinessSegmentsAxis,
StatementGeographicalAxis). This module pulls those facts for a quarter:

  - 10-Q: the 3-month fact ending at the report date, plus the year-ago quarter that every
    10-Q repeats as a comparative (for year-over-year growth).
  - Q4: companies file no Q4 10-Q, so Q4 = fiscal year (10-K) minus the nine-month year-to-date
    figure from that year's Q3 10-Q, member by member.

Dimension members overlap (AAPL tags "Products" and also iPhone/Mac/iPad/Wearables, which sum
to it), so summing them all would double count. For each axis `choose_partition` finds the
largest set of members that adds up to total revenue and ignores the aggregates. Axes are
tried products/services first (the closest thing to "income streams"), then business
segments, then regions. If nothing reconciles to the reported total the result is None —
a wrong breakdown is worse than none, and callers fall back to a single revenue node.

Parsed facts are cached per filing (filings never change), so only a ticker's first
tear sheet pays for downloading the instance documents.
"""
import json
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from itertools import combinations

from database import cache_get, cache_set

logger = logging.getLogger(__name__)

_FILING_TTL = timedelta(days=30)
_MAX_INSTANCE_BYTES = 30_000_000      # skip enormous filers (big banks) rather than stall the tear sheet

_XBRLI = "{http://www.xbrl.org/2003/instance}"
_XBRLDI = "{http://xbrl.org/2006/xbrldi}"
_XLINK = "{http://www.w3.org/1999/xlink}"
_LINK = "{http://www.xbrl.org/2003/linkbase}"

_REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
]
AXES = [
    ("ProductOrServiceAxis", "Products & services"),
    ("StatementBusinessSegmentsAxis", "Business segments"),
    ("StatementGeographicalAxis", "Regions"),
]
_RECONCILE_TOL = 0.003      # a real partition adds up to total revenue to within rounding (<0.01%); 0.3% leaves room for
                            # small unallocated items (hedging gains, eliminations) while rejecting accidental subset sums
_MAX_STREAMS = 8
_MAX_CANDIDATES = 16        # subset search is 2^n; keep the 16 largest members


# ── Member naming ─────────────────────────────────────────────────────────────

def prettify_member(qname: str, labels: dict[str, str] | None = None) -> str:
    """'aapl:IPhoneMember' -> 'iPhone' via the filing's label linkbase, else a camelCase split."""
    key = qname.replace(":", "_")
    if labels and key in labels:
        return labels[key]
    name = qname.split(":")[-1]
    name = re.sub(r"(Segment)?Member$", "", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    name = name.replace("Three Six Five", "365")
    name = re.sub(r"(?<=\w) (And|Of|The|For|In|On|To) ", lambda m: f" {m.group(1).lower()} ", name)
    return name.strip() or qname


def parse_labels(xml_bytes: bytes) -> dict[str, str]:
    """{'aapl_IPhoneMember': 'iPhone'} from a label linkbase (_lab.xml); standard labels only."""
    out: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    loc_to_elem, arcs, texts = {}, {}, {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "loc":
            href = el.get(f"{_XLINK}href", "")
            loc_to_elem[el.get(f"{_XLINK}label")] = href.split("#")[-1]
        elif tag == "labelArc":
            arcs.setdefault(el.get(f"{_XLINK}from"), []).append(el.get(f"{_XLINK}to"))
        elif tag == "label" and el.get(f"{_XLINK}role", "").endswith("/role/label"):
            texts[el.get(f"{_XLINK}label")] = (el.text or "").strip()
    for loc, elem in loc_to_elem.items():
        if not elem.endswith("Member"):
            continue
        for target in arcs.get(loc, []):
            text = texts.get(target)
            if text:
                text = re.sub(r"\s*\[Member\]\s*$", "", text)
                text = re.sub(r"\s+Segments?$", "", text)
                out.setdefault(elem, text)
    return out


def parse_metalinks(raw: bytes) -> dict[str, str]:
    """{'msft_LinkedInCorporationMember': 'LinkedIn'} from a MetaLinks.json (shipped instead of the
    label linkbase by some filing agents). The short 'terseLabel' is preferred over the full label."""
    out: dict[str, str] = {}
    try:
        instances = json.loads(raw).get("instance", {})
    except (ValueError, AttributeError):
        return out
    for inst in instances.values():
        for key, tag in (inst.get("tag") or {}).items():
            if not key.endswith("Member"):
                continue
            roles = ((tag.get("lang") or {}).get("en-us") or {}).get("role") or {}
            text = roles.get("terseLabel") or roles.get("label")
            if text:
                out.setdefault(key, re.sub(r"\s*\[Member\]\s*$", "", text).strip())
    return out


# ── Instance document parsing ─────────────────────────────────────────────────

def parse_instance(xml_bytes: bytes) -> list[dict]:
    """Revenue facts from an XBRL instance as compact rows:
    {start, end, axis (None = consolidated total), member, value}.
    Keeps only consolidated totals and contexts split on exactly one of the AXES (optionally also
    on ConsolidationItemsAxis=OperatingSegmentsMember, which merely marks reportable segments)."""
    root = ET.fromstring(xml_bytes)
    contexts = {}
    for c in root.findall(f"{_XBRLI}context"):
        period = c.find(f"{_XBRLI}period")
        start, end = period.find(f"{_XBRLI}startDate"), period.find(f"{_XBRLI}endDate")
        if start is None or end is None:
            continue                                          # instants (balance sheet) don't carry revenue
        if any(True for _ in c.iter(f"{_XBRLDI}typedMember")):
            continue
        dims = {m.get("dimension", "").split(":")[-1]: (m.text or "").strip() for m in c.iter(f"{_XBRLDI}explicitMember")}
        if dims.get("ConsolidationItemsAxis", "").endswith("OperatingSegmentsMember"):
            dims.pop("ConsolidationItemsAxis")           # just marks "reportable segment"; not a real split
        if len(dims) > 1 or "ConsolidationItemsAxis" in dims:
            continue                                     # cross-tabs (product x region) and eliminations
        axis, member = next(iter(dims.items())) if dims else (None, None)
        if axis is not None and axis not in dict(AXES):
            continue
        contexts[c.get("id")] = (start.text, end.text, axis, member)

    rank = {name: i for i, name in enumerate(_REVENUE_CONCEPTS)}
    best: dict[tuple, tuple[int, float]] = {}
    for el in root:
        concept = el.tag.split("}")[-1]
        ctx = contexts.get(el.get("contextRef"))
        if concept not in rank or ctx is None or not (el.text or "").strip():
            continue
        try:
            value = float(el.text)
        except ValueError:
            continue
        if el.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            continue
        key = ctx
        if key not in best or rank[concept] < best[key][0]:
            best[key] = (rank[concept], value)
    return [{"start": s, "end": e, "axis": a, "member": m, "value": v} for (s, e, a, m), (_, v) in best.items()]


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def period_values(rows: list[dict], end_near: date, lo: int, hi: int, tol_days: int = 10):
    """(total, {axis: {member: value}}) for facts whose period is lo..hi days long and ends within
    `tol_days` of `end_near`. The period end actually used is the one closest to `end_near`."""
    cands = [r for r in rows if lo <= _days(r["start"], r["end"]) <= hi
             and abs((date.fromisoformat(r["end"]) - end_near).days) <= tol_days]
    if not cands:
        return None, {}
    use_end = min({r["end"] for r in cands}, key=lambda e: abs((date.fromisoformat(e) - end_near).days))
    total, axes = None, {}
    for r in cands:
        if r["end"] != use_end:
            continue
        if r["axis"] is None:
            total = r["value"] if total is None else max(total, r["value"])
        else:
            axes.setdefault(r["axis"], {})[r["member"]] = r["value"]
    return total, axes


# ── Picking the members that add up to total revenue ──────────────────────────

def choose_partition(members: dict[str, float], total: float, tol: float = _RECONCILE_TOL) -> list[str] | None:
    """Largest subset of `members` whose values sum to `total` within `tol` (ties: closest sum).
    Returns None when no subset of 2+ members reconciles."""
    if not total or total <= 0:
        return None
    pool = sorted(((m, v) for m, v in members.items() if v and v > 0), key=lambda kv: -kv[1])[:_MAX_CANDIDATES]
    best, best_key = None, None
    for size in range(len(pool), 1, -1):
        for combo in combinations(pool, size):
            s = sum(v for _, v in combo)
            err = abs(s - total) / total
            if err <= tol and (best is None or err < best_key):
                best, best_key = [m for m, _ in combo], err
        if best is not None:
            return best              # largest size that reconciles; combinations at this size already compared
    return None


def streams_from_values(total: float | None, axes: dict[str, dict[str, float]], prior_total: float | None = None,
                        prior_axes: dict[str, dict[str, float]] | None = None, labels: dict[str, str] | None = None) -> dict | None:
    """Best income-stream breakdown for one period, or None if no axis reconciles to `total`."""
    if not total:
        return None
    for axis, axis_label in AXES:
        members = axes.get(axis)
        if not members:
            continue
        chosen = choose_partition(members, total)
        if not chosen:
            continue
        prior_members = (prior_axes or {}).get(axis, {})
        streams = [{"name": prettify_member(m, labels), "member": m, "value": members[m],
                    "prior": prior_members.get(m)} for m in chosen]
        streams.sort(key=lambda s: -s["value"])
        if len(streams) > _MAX_STREAMS:                       # fold the long tail into one node
            head, tail = streams[:_MAX_STREAMS - 1], streams[_MAX_STREAMS - 1:]
            priors = [s["prior"] for s in tail]
            head.append({"name": "Other", "member": None, "value": sum(s["value"] for s in tail),
                         "prior": sum(priors) if all(p is not None for p in priors) else None})
            streams = head
        return {"axis": axis, "axisLabel": axis_label, "streams": streams, "total": total, "priorTotal": prior_total}
    return None


# ── Filing discovery and download ─────────────────────────────────────────────

def _req(url: str):
    from edgar_utils import _edgar_req
    return _edgar_req(url)


def list_filings(cik: str) -> list[dict]:
    """10-Q / 10-K filings, newest first: {form, reportDate, accession}."""
    r = _req(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()["filings"]["recent"]
    rows = [{"form": r["form"][i], "reportDate": r["reportDate"][i], "accession": r["accessionNumber"][i]}
            for i in range(len(r["form"])) if r["form"][i] in ("10-Q", "10-K") and r["reportDate"][i]]
    return sorted(rows, key=lambda f: f["reportDate"], reverse=True)


def _filing_base(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"


def _filing_files(cik: str, accession: str) -> list[dict]:
    return _req(_filing_base(cik, accession) + "index.json").json()["directory"]["item"]


def filing_rows(cik: str, accession: str) -> list[dict]:
    """Cached revenue rows for one filing ([] if it has no usable XBRL instance)."""
    key = f"sec_rev_rows:{cik}:{accession}"
    cached = cache_get(key, _FILING_TTL)
    if cached is not None:
        return cached
    files = _filing_files(cik, accession)
    inst = next((f for f in files if f["name"].endswith("_htm.xml")), None)
    if inst is None:
        inst = next((f for f in files if f["name"].endswith(".xml")
                     and not re.search(r"_(cal|def|lab|pre|ref)\.xml$|FilingSummary|^R\d+\.xml$", f["name"])), None)
    rows: list[dict] = []
    if inst is not None and int(inst.get("size") or 0) <= _MAX_INSTANCE_BYTES:
        rows = parse_instance(_req(_filing_base(cik, accession) + inst["name"]).content)
    cache_set(key, rows)
    return rows


def filing_labels(cik: str, accession: str) -> dict[str, str]:
    key = f"sec_rev_labels:{cik}:{accession}"
    cached = cache_get(key, _FILING_TTL)
    if cached is not None:
        return cached
    files = _filing_files(cik, accession)
    lab = next((f for f in files if f["name"].endswith("_lab.xml")), None)
    meta = next((f for f in files if f["name"] == "MetaLinks.json"), None)
    if lab:
        labels = parse_labels(_req(_filing_base(cik, accession) + lab["name"]).content)
    elif meta:
        labels = parse_metalinks(_req(_filing_base(cik, accession) + meta["name"]).content)
    else:
        labels = {}
    cache_set(key, labels)
    return labels


# ── Per-quarter streams ───────────────────────────────────────────────────────

def _near(filings: list[dict], target: date, form: str | None = None, tol: int = 12):
    best = None
    for f in filings:
        if form and f["form"] != form:
            continue
        d = abs((date.fromisoformat(f["reportDate"]) - target).days)
        if d <= tol and (best is None or d < best[0]):
            best = (d, f)
    return best[1] if best else None


def quarter_streams(quarter_end: date, filings: list[dict], rows_for, labels: dict[str, str] | None = None) -> dict | None:
    """Income streams for the fiscal quarter ending near `quarter_end`.

    `rows_for(filing)` returns that filing's parsed rows (injected so tests need no network)."""
    f = _near(filings, quarter_end)
    if f is None:
        return None
    ends = date.fromisoformat(f["reportDate"])
    year_ago = ends - timedelta(days=365)

    if f["form"] == "10-Q":
        rows = rows_for(f)
        total, axes = period_values(rows, ends, 80, 100)
        p_total, p_axes = period_values(rows, year_ago, 80, 100)
    else:
        # Q4 = fiscal year (this 10-K) - nine-month YTD (the same year's Q3 10-Q), member by member
        q3 = _near(filings, ends - timedelta(days=91), form="10-Q", tol=20)
        if q3 is None:
            return None
        fy_rows, q3_rows = rows_for(f), rows_for(q3)
        q3_end = date.fromisoformat(q3["reportDate"])
        total, axes = _subtract(period_values(fy_rows, ends, 350, 380), period_values(q3_rows, q3_end, 240, 285))
        p_total, p_axes = _subtract(period_values(fy_rows, year_ago, 350, 380),
                                    period_values(q3_rows, q3_end - timedelta(days=365), 240, 285))
    result = streams_from_values(total, axes, p_total, p_axes, labels)
    if result:
        result["filing"] = f["accession"]
        result["form"] = f["form"]
        result["derived"] = f["form"] == "10-K"
    return result


def _subtract(full, ytd):
    """(total, axes) of full-year minus year-to-date; members missing from either side are dropped."""
    (t_full, a_full), (t_ytd, a_ytd) = full, ytd
    total = t_full - t_ytd if t_full is not None and t_ytd is not None else None
    axes = {}
    for axis, members in a_full.items():
        common = {m: v - a_ytd[axis][m] for m, v in members.items() if m in a_ytd.get(axis, {})}
        if common:
            axes[axis] = common
    return total, axes


def streams_for_quarters(sym: str, quarter_ends: list[date]) -> dict[str, dict]:
    """{quarter_end_iso: streams-dict} for the quarters that could be resolved. Best effort: any
    failure for a quarter (or the whole lookup) just means no breakdown for it."""
    from edgar_utils import _get_cik
    cik = _get_cik(sym)
    if not cik or not quarter_ends:
        return {}
    filings = list_filings(cik)
    if not filings:
        return {}
    # prefetch every filing any requested quarter might need, in parallel
    needed: dict[str, dict] = {}
    for qe in quarter_ends:
        f = _near(filings, qe)
        if f is None:
            continue
        needed[f["accession"]] = f
        if f["form"] == "10-K":
            q3 = _near(filings, date.fromisoformat(f["reportDate"]) - timedelta(days=91), form="10-Q", tol=20)
            if q3:
                needed[q3["accession"]] = q3
    if not needed:
        return {}
    cache: dict[str, list[dict]] = {}

    def load(f):
        try:
            cache[f["accession"]] = filing_rows(cik, f["accession"])
        except Exception as exc:
            logger.warning("revenue streams: %s %s failed: %s", sym, f["accession"], exc)
            cache[f["accession"]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(load, needed.values()))

    # member names differ between filings (a Q3 member may not exist in the 10-K's label file), so
    # merge the label maps of every filing used, newest first
    def load_labels(f):
        try:
            return filing_labels(cik, f["accession"])
        except Exception as exc:
            logger.warning("revenue streams: labels for %s %s failed: %s", sym, f["accession"], exc)
            return {}
    by_newest = sorted(needed.values(), key=lambda f: f["reportDate"], reverse=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        label_maps = list(pool.map(load_labels, by_newest))
    labels: dict[str, str] = {}
    for m in label_maps:
        for k, v in m.items():
            labels.setdefault(k, v)
    out = {}
    for qe in quarter_ends:
        try:
            res = quarter_streams(qe, filings, lambda f: cache.get(f["accession"], []), labels)
        except Exception as exc:
            logger.warning("revenue streams: %s quarter %s failed: %s", sym, qe, exc)
            res = None
        if res:
            out[qe.isoformat()] = res
    return out
