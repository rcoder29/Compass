"""Quarterly income flow — where a quarter's revenue goes, from income streams to dividends.

For each of the last few quarters this builds a Sankey graph:

    income streams -> revenue -> (cost of revenue | gross profit) -> (R&D | SG&A | other | operating
    income) -> (other income/expense) -> pretax income -> (tax | minority & other | net income)
    -> (dividends | buybacks | retained earnings)

Inputs are yfinance's quarterly income statement and cash-flow statement, the dividend history
(for per-share amounts), and optionally the revenue-by-stream breakdown from SEC filings
(sec_revenue_streams.py). `layout_sankey` turns the graph into drawable geometry (rectangles and
Bezier link paths in a fixed coordinate space) so the web page and the PDF render *identical*
diagrams from one source of truth.

Every node's value is conserved: what flows in equals what flows out. Real statements rarely
tie out perfectly (minority interests, discontinued operations, rounding), so each step derives
its remainder from the reported subtotals and surfaces any residual as an explicit node instead
of letting the diagram silently disagree with the reported numbers. Loss-making quarters can't
be drawn as a flow of positive money, so a shortfall becomes a red "funded from reserves" source
feeding the costs, and the diagram stops where profit runs out.
"""
import math

import pandas as pd

_MIN_SHARE = 0.004          # items under 0.4% of revenue are folded into "Other" / omitted
_PRETAX_SPLIT = 0.015       # interest & other income/expense above 1.5% of revenue gets its own pretax column
_EPS = 1e-9

KIND_COLORS = {
    "revenue": "#3b82f6", "cost": "#f87171", "expense": "#fbbf24", "profit": "#34d399", "tax": "#fb923c",
    "net": "#10b981", "dividend": "#a78bfa", "buyback": "#8b5cf6", "retained": "#14b8a6",
    "income": "#6ee7b7", "loss": "#ef4444", "funding": "#94a3b8",
}
STREAM_COLORS = ["#38bdf8", "#818cf8", "#22d3ee", "#c084fc", "#60a5fa", "#2dd4bf", "#e879f9", "#7dd3fc"]


# ── Reading the statements ────────────────────────────────────────────────────

def _num(df, labels, col):
    """First available, non-NaN value among `labels` for column `col`."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            v = df.loc[label, col]
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if not math.isnan(f):
                return f
    return None


def _match_col(df, ts, tol_days=12):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    best = min(df.columns, key=lambda c: abs((pd.Timestamp(c) - ts).days))
    return best if abs((pd.Timestamp(best) - ts).days) <= tol_days else None


def quarter_pnl(income, cashflow, dividends, col) -> dict:
    """One quarter's figures as a flat dict (None where the statements don't have it)."""
    cf_col = _match_col(cashflow, pd.Timestamp(col))
    sga = _num(income, ["Selling General And Administration"], col)
    if sga is None:
        parts = [_num(income, [k], col) for k in ("Selling And Marketing Expense", "General And Administrative Expense")]
        sga = sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None
    div_paid = _num(cashflow, ["Cash Dividends Paid", "Common Stock Dividend Paid"], cf_col) if cf_col is not None else None
    buyback = _num(cashflow, ["Repurchase Of Capital Stock"], cf_col) if cf_col is not None else None
    end = pd.Timestamp(col)
    dps = None
    if dividends is not None and len(dividends):
        idx = dividends.index.tz_localize(None) if getattr(dividends.index, "tz", None) is not None else dividends.index
        in_q = dividends[(idx > end - pd.Timedelta(days=92)) & (idx <= end + pd.Timedelta(days=5))]
        dps = float(in_q.sum()) if len(in_q) else None
    return {
        "quarter": str(end.date()),
        "revenue": _num(income, ["Total Revenue", "Operating Revenue"], col),
        "costOfRevenue": _num(income, ["Cost Of Revenue", "Reconciled Cost Of Revenue"], col),
        "grossProfit": _num(income, ["Gross Profit"], col),
        "researchAndDevelopment": _num(income, ["Research And Development"], col),
        "sellingGeneralAdmin": sga,
        "operatingExpense": _num(income, ["Operating Expense"], col),
        "operatingIncome": _num(income, ["Operating Income", "Total Operating Income As Reported"], col),
        "pretaxIncome": _num(income, ["Pretax Income"], col),
        "incomeTax": _num(income, ["Tax Provision"], col),
        "netIncome": _num(income, ["Net Income", "Net Income Common Stockholders"], col),
        "dividendsPaid": abs(div_paid) if div_paid else None,
        "buybacks": abs(buyback) if buyback else None,
        "dividendPerShare": dps,
    }


# ── Graph building ────────────────────────────────────────────────────────────

class _Graph:
    def __init__(self, revenue: float):
        self.revenue = revenue
        self.nodes: dict[str, dict] = {}
        self.links: list[dict] = []
        self.notes: list[str] = []

    def node(self, nid, label, stage, kind, color=None, detail=None):
        self.nodes.setdefault(nid, {"id": nid, "label": label, "stage": stage, "kind": kind,
                                    "color": color or KIND_COLORS[kind], "detail": detail})

    def link(self, src, dst, value):
        if value is not None and value > self.revenue * 1e-4:
            self.links.append({"source": src, "target": dst, "value": float(value)})

    def step(self, prev_id, prev_val, outflows, inflows, node_id, label, stage, kind, loss_label=None):
        """One stage of the waterfall. `prev_val` (node `prev_id`) pays `outflows`
        [(id, label, amount, kind)]; `inflows` [(id, label, amount, kind)] are new sources that add
        straight into the resulting node `node_id`.

        Normal case: the node holds prev_val - outflows + inflows. Shortfall case (prev can't fund
        its outflows): no node is created; the outflows are instead funded by prev, any inflows, and
        a red loss source covering the gap, and the diagram stops here.
        Returns (node_id | None, resulting value)."""
        out_total = sum(a for _, _, a, _ in outflows)
        in_total = sum(a for _, _, a, _ in inflows)
        node_val = prev_val - out_total + in_total
        eps = self.revenue * 1e-4
        source_stage = stage - 1                       # new sources sit in the previous node's column
        if prev_val >= out_total - eps and node_val > eps:
            self.node(node_id, label, stage, kind)
            self.link(prev_id, node_id, prev_val - out_total)
            for nid, lab, amt, k in outflows:
                self.node(nid, lab, stage, k)
                self.link(prev_id, nid, amt)
            for nid, lab, amt, k in inflows:
                self.node(nid, lab, source_stage, k)
                self.link(nid, node_id, amt)
            return node_id, node_val
        if out_total <= 0:
            return None, node_val
        funders = [(prev_id, prev_val)]
        for nid, lab, amt, k in inflows:
            self.node(nid, lab, source_stage, k)
            funders.append((nid, amt))
        shortfall = out_total - prev_val - in_total
        if shortfall > eps:
            loss_id = f"loss:{node_id}"
            self.node(loss_id, loss_label or "Shortfall", source_stage, "loss")
            funders.append((loss_id, shortfall))
        for nid, lab, amt, k in outflows:
            self.node(nid, lab, stage, k)
            for funder, f_val in funders:
                self.link(funder, nid, f_val * amt / out_total)
        return None, node_val


def build_graph(pnl: dict, streams: dict | None = None) -> dict | None:
    """Sankey graph (nodes, links, notes) for one quarter, or None without usable revenue."""
    R = pnl.get("revenue")
    if not R or R <= 0:
        return None
    g = _Graph(R)
    small = R * _MIN_SHARE

    # stage 0-1: income streams -> revenue
    g.node("revenue", "Revenue", 1, "revenue")
    used_streams = False
    if streams and streams.get("streams"):
        total = sum(s["value"] for s in streams["streams"])
        if abs(total - R) / R <= 0.03:
            for i, s in enumerate(streams["streams"]):
                nid = f"stream:{i}"
                g.node(nid, s["name"], 0, "stream", STREAM_COLORS[i % len(STREAM_COLORS)])
                g.link(nid, "revenue", s["value"])
            gap = R - total
            if gap > small:
                g.node("stream:other", "Other / unallocated", 0, "stream", "#94a3b8")
                g.link("stream:other", "revenue", gap)
            used_streams = True
        else:
            g.notes.append("Revenue by income stream is reported on a different basis than the income statement, so it isn't shown.")

    # stage 2: gross profit
    gp = pnl.get("grossProfit")
    if gp is None and pnl.get("costOfRevenue") is not None:
        gp = R - pnl["costOfRevenue"]
    cur_id, cur_val, stage = "revenue", R, 2
    if gp is not None and gp < R - small:
        cost = R - gp
        cur_id, cur_val = g.step("revenue", R, [("cost", "Cost of revenue", cost, "cost")], [], "gross", "Gross profit",
                                 2, "profit", "Gross loss")
        stage = 3
        if cur_id is None:
            g.notes.append("Cost of revenue exceeded revenue this quarter, so there is no profit to distribute.")
            return _finish(g, pnl, used_streams)

    # stage 3: operating expenses -> operating income (or pretax income for banks / no operating line)
    oi, pretax = pnl.get("operatingIncome"), pnl.get("pretaxIncome")
    target = oi if oi is not None else pretax
    target_label = "Operating income" if oi is not None else "Pretax income"
    if target is not None and cur_id:
        opex_total = cur_val - target
        outflows = _opex_items(pnl, opex_total, small, bank_like=(oi is None))
        if opex_total > small and outflows:
            cur_id, cur_val = g.step(cur_id, cur_val, outflows, [], "operating", target_label, stage, "profit",
                                     "Operating loss")
            stage += 1
            if cur_id is None:
                g.notes.append("Costs exceeded revenue this quarter - an operating loss, so nothing flows through to net income.")
                return _finish(g, pnl, used_streams)
        else:
            g.nodes.setdefault("operating", {"id": "operating", "label": target_label, "stage": stage, "kind": "profit",
                                             "color": KIND_COLORS["profit"], "detail": None})
            g.link(cur_id, "operating", cur_val)
            cur_id = "operating"
            stage += 1

    # stage 4: other (mostly interest) income / expense -> pretax income. Only a material adjustment earns its
    # own column; a small one is folded into the net-income step so the diagram stays compact.
    other = None
    if oi is not None and pretax is not None and cur_id == "operating":
        other = pretax - oi
        if abs(other) > R * _PRETAX_SPLIT:
            if other > 0:
                cur_id, cur_val = g.step("operating", cur_val, [], [("other_income", "Other income", other, "income")],
                                         "pretax", "Pretax income", stage, "profit")
            else:
                cur_id, cur_val = g.step("operating", cur_val, [("other_expense", "Other expense", -other, "cost")], [],
                                         "pretax", "Pretax income", stage, "profit", "Pretax loss")
            other = None
            if cur_id is None:
                g.notes.append("Interest and other expenses pushed the quarter into a pretax loss.")
                return _finish(g, pnl, used_streams)
            stage += 1

    # stage 5: tax and other deductions -> net income
    ni, tax = pnl.get("netIncome"), pnl.get("incomeTax")
    if ni is not None and cur_id:
        outflows, inflows = [], []
        if tax is not None:
            if tax > small:
                outflows.append(("tax", "Income tax", tax, "tax"))
            elif tax < -small:
                inflows.append(("tax_benefit", "Tax benefit", -tax, "income"))
        if other is not None:
            if other > small:
                inflows.append(("other_income", "Other income", other, "income"))
            elif other < -small:
                outflows.append(("other_expense", "Other expense", -other, "cost"))
        residual = cur_val - sum(a for _, _, a, _ in outflows) + sum(a for _, _, a, _ in inflows) - ni
        if residual > small:
            outflows.append(("minority", "Minority interest & other", residual, "tax"))
        elif residual < -small:
            inflows.append(("other_items", "Other items (net)", -residual, "income"))
        if ni > small:
            cur_id, cur_val = g.step(cur_id, cur_val, outflows, inflows, "net", "Net income", stage, "net")
            stage += 1
        if ni <= small or cur_id is None:
            g.notes.append("Net income was zero or negative this quarter, so there is no profit to distribute.")
            return _finish(g, pnl, used_streams)

    # stage 6: shareholder returns
    if cur_id == "net":
        _shareholder_returns(g, pnl, cur_val, stage, small)
    return _finish(g, pnl, used_streams)


def _opex_items(pnl, opex_total, small, bank_like):
    """Named operating-cost outflows that add up to `opex_total` (with an 'Other' remainder)."""
    if opex_total <= small:
        return []
    rnd, sga = pnl.get("researchAndDevelopment"), pnl.get("sellingGeneralAdmin")
    items = []
    if not bank_like or sga:
        for nid, label, v in (("rnd", "Research & development", rnd), ("sga", "Selling, general & admin", sga)):
            if v is not None and v > small:
                items.append([nid, label, v])
    named = sum(v for _, _, v in items)
    if named > opex_total * 1.02:        # breakdown inconsistent with the subtotal: show one lump instead
        items, named = [], 0.0
    other = opex_total - named
    other_label = "Other costs & expenses" if bank_like else "Other operating expenses"
    if other > small or not items:
        items.append(["opex_other", other_label if items else ("Operating costs & expenses"), max(other, 0.0)])
    elif other > 0 and items:            # sub-threshold remainder: fold into the largest named item
        items[0][2] += other
    return [(nid, label, v, "expense") for nid, label, v in items if v > 0]


def _shareholder_returns(g, pnl, ni, stage, small):
    div, buy = pnl.get("dividendsPaid") or 0.0, pnl.get("buybacks") or 0.0
    if div <= small:
        div = 0.0
    if buy <= small:
        buy = 0.0
    if not div and not buy:
        g.notes.append("No dividends or buybacks were paid this quarter, so all of net income is retained.")
        g.node("retained", "Retained earnings", stage, "retained")
        g.link("net", "retained", ni)
        return
    outflows = []
    if div:
        dps = pnl.get("dividendPerShare")
        g.node("dividends", "Dividends", stage, "dividend", detail=f"${dps:.2f}/share" if dps else None)
        outflows.append(("dividends", div))
    if buy:
        g.node("buybacks", "Share buybacks", stage, "buyback")
        outflows.append(("buybacks", buy))
    total = div + buy
    if total <= ni:
        for nid, amt in outflows:
            g.link("net", nid, amt)
        if ni - total > small:
            g.node("retained", "Retained earnings", stage, "retained")
            g.link("net", "retained", ni - total)
    else:
        # payouts exceed earnings: net income funds its share, cash reserves cover the rest
        g.node("funding", "Cash reserves", stage - 1, "funding")
        for nid, amt in outflows:
            g.link("net", nid, amt * ni / total)
            g.link("funding", nid, amt * (total - ni) / total)
        g.notes.append("Dividends and buybacks together exceeded net income this quarter; the difference came from cash reserves.")


def _finish(g, pnl, used_streams):
    nodes = list(g.nodes.values())
    linked = {l["source"] for l in g.links} | {l["target"] for l in g.links}
    nodes = [n for n in nodes if n["id"] in linked]
    return {"nodes": nodes, "links": g.links, "notes": g.notes, "hasStreams": used_streams}


# ── Layout ────────────────────────────────────────────────────────────────────

# Vertical order inside a column: what you keep on top, extra money sources next, costs and payouts below.
_KIND_RANK = {"revenue": 0, "stream": 0, "profit": 0, "net": 0, "income": 1, "loss": 1, "funding": 1}
LABEL_SLOT = 26        # min vertical room a node's two-line label needs, in layout units


def layout_sankey(graph: dict, revenue: float, width: int = 1000, height: int = 420, node_w: int = 12, pad: int = 8,
                  margin_top: int = 8, margin_bottom: int = 8, margin_left: int = 150, margin_right: int = 165) -> dict:
    """Pixel geometry for a graph: node rectangles plus link centre-line paths and thicknesses.

    Columns are the distinct node stages, left to right. Within a column nodes stack from the top
    in graph order (profit path first, costs below), so the money you keep stays on top and each
    cost peels off downward."""
    nodes = {n["id"]: dict(n) for n in graph["nodes"]}
    links = [dict(l) for l in graph["links"]]
    if not nodes:
        return {"width": width, "height": height, "nodes": [], "links": []}
    for n in nodes.values():
        n["in"] = sum(l["value"] for l in links if l["target"] == n["id"])
        n["out"] = sum(l["value"] for l in links if l["source"] == n["id"])
        n["value"] = max(n["in"], n["out"])

    stages = sorted({n["stage"] for n in nodes.values()})
    col_of = {s: i for i, s in enumerate(stages)}
    plot_w = width - margin_left - margin_right
    step_x = (plot_w - node_w) / max(len(stages) - 1, 1)
    plot_h = height - margin_top - margin_bottom

    columns: dict[int, list] = {i: [] for i in range(len(stages))}
    for n in nodes.values():                      # dict order == insertion order
        columns[col_of[n["stage"]]].append(n)
    for col in columns.values():                  # profit path on top, then money sources, then costs (stable within a rank)
        col.sort(key=lambda n: _KIND_RANK.get(n["kind"], 3))
    # Scale so every column fits, counting the extra room tiny nodes need for their labels. The
    # reserved room depends on the scale, so refine a few times (converges almost immediately).
    k = min((plot_h - (len(col) - 1) * pad) / sum(n["value"] for n in col) for col in columns.values() if col)
    for _ in range(4):
        k = min((plot_h - (len(col) - 1) * pad - sum(max(0.0, LABEL_SLOT - n["value"] * k) for n in col))
                / sum(n["value"] for n in col) for col in columns.values() if col)
    for ci, col in columns.items():
        y = margin_top
        for n in col:
            h = max(n["value"] * k, 1.5)
            slot = max(h, LABEL_SLOT)
            n["x"] = margin_left + ci * step_x
            n["y"] = y + (slot - h) / 2           # a tiny node sits mid-slot, level with its label
            n["h"] = h
            n["w"] = node_w
            n["col"] = ci
            y += slot + pad

    for l in links:
        l["thickness"] = l["value"] * k            # needed on both ends before any offsets are assigned
    for n in nodes.values():
        outs = sorted((l for l in links if l["source"] == n["id"]), key=lambda l: nodes[l["target"]]["y"])
        off = 0.0
        for l in outs:
            l["sy"] = n["y"] + off + l["thickness"] / 2
            off += l["thickness"]
        ins = sorted((l for l in links if l["target"] == n["id"]), key=lambda l: nodes[l["source"]]["y"])
        off = 0.0
        for l in ins:
            l["ty"] = n["y"] + off + l["thickness"] / 2
            off += l["thickness"]

    out_links = []
    for l in links:
        s, t = nodes[l["source"]], nodes[l["target"]]
        x0, x1 = s["x"] + s["w"], t["x"]
        xm = (x0 + x1) / 2
        color = s["color"] if s["kind"] == "stream" else t["color"]
        out_links.append({"source": l["source"], "target": l["target"], "value": l["value"], "thickness": round(l["thickness"], 2),
                          "color": color, "x0": round(x0, 2), "y0": round(l["sy"], 2), "x1": round(x1, 2), "y1": round(l["ty"], 2),
                          "d": f"M{x0:.1f},{l['sy']:.1f} C{xm:.1f},{l['sy']:.1f} {xm:.1f},{l['ty']:.1f} {x1:.1f},{l['ty']:.1f}"})
    out_nodes = []
    for n in nodes.values():
        first = n["col"] == 0 and n["in"] == 0
        out_nodes.append({"id": n["id"], "label": n["label"], "kind": n["kind"], "color": n["color"], "detail": n.get("detail"),
                          "x": round(n["x"], 2), "y": round(n["y"], 2), "w": n["w"], "h": round(n["h"], 2),
                          "value": n["value"], "pct": n["value"] / revenue if revenue else None,
                          "labelSide": "left" if first else "right", "column": n["col"]})
    return {"width": width, "height": height, "nodes": out_nodes, "links": out_links}


# ── Assembly for the tear sheet ───────────────────────────────────────────────

def _growth(current, prior, cap=5.0):
    """Year-over-year growth, or None when it isn't meaningful: no/negative prior, or beyond +/-500%
    (a sliver of revenue on a near-zero base would otherwise print as +1,500%)."""
    if current is None or not prior or prior <= 0:
        return None
    g = current / prior - 1
    return g if abs(g) <= cap else None


def build_income_flows(income, cashflow, dividends, streams_by_quarter: dict | None = None, max_quarters: int = 4) -> dict | None:
    """{'quarters': [...newest first...]} for the last `max_quarters` quarters with revenue, or None.

    Each quarter: its P&L figures, the revenue-stream breakdown (if SEC data resolved), YoY
    revenue growth, and the laid-out Sankey (`flow`, or None when the statements can't support it)."""
    if income is None or not isinstance(income, pd.DataFrame) or income.empty:
        return None
    cols = sorted(income.columns, reverse=True)
    quarters = []
    for i, col in enumerate(cols):
        if len(quarters) >= max_quarters:
            break
        pnl = quarter_pnl(income, cashflow, dividends, col)
        if not pnl["revenue"]:
            continue
        streams = (streams_by_quarter or {}).get(pnl["quarter"])
        year_ago_rev = _num(income, ["Total Revenue", "Operating Revenue"], cols[i + 4]) if i + 4 < len(cols) else None
        yoy = None
        if streams and streams.get("priorTotal"):
            yoy = pnl["revenue"] / streams["priorTotal"] - 1
        elif year_ago_rev:
            yoy = pnl["revenue"] / year_ago_rev - 1
        graph = build_graph(pnl, streams)
        if graph is not None and not graph["links"]:
            graph = None                       # revenue alone: nothing to flow
        flow = layout_sankey(graph, pnl["revenue"]) if graph else None
        if flow:
            flow["notes"] = graph["notes"]
            flow["hasStreams"] = graph["hasStreams"]
        stream_rows = None
        if streams and graph and graph["hasStreams"]:
            stream_rows = {
                "axisLabel": streams["axisLabel"], "derived": streams.get("derived", False), "form": streams.get("form"),
                "streams": [{"name": s["name"], "value": s["value"], "share": s["value"] / pnl["revenue"],
                             "yoy": _growth(s["value"], s.get("prior"))} for s in streams["streams"]],
            }
        quarters.append({"quarter": pnl["quarter"], "pnl": pnl, "revenueYoY": yoy, "streams": stream_rows, "flow": flow})
    return {"quarters": quarters} if quarters else None
