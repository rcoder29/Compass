"""Tear Sheet → PDF.

Renders the dict returned by GET /api/tear-sheet/{symbol} as a multi-page, light-theme
PDF (letter, portrait) using reportlab: the same sections as the on-screen page, with
charts redrawn as vector graphics. The same bytes are served by the Download button and
attached to shared emails, so what a recipient sees is exactly what the user saw.

Helvetica (a built-in PDF font) only covers Windows-1252, so every string passes through
`_txt`, which maps the few symbols the page uses outside that set and replaces anything
else (e.g. CJK company names) with '?' instead of failing the whole render.
"""
import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, HRFlowable, KeepTogether, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
W = PAGE_W - 2 * MARGIN          # usable width in points

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d1d5db")
PANEL = colors.HexColor("#f3f4f6")
GREEN = colors.HexColor("#059669")
RED = colors.HexColor("#dc2626")
AMBER = colors.HexColor("#d97706")
BLUE = colors.HexColor("#2563eb")
PURPLE = colors.HexColor("#7c3aed")
GRAY = colors.HexColor("#9ca3af")
TONES = {"good": GREEN, "bad": RED, "neutral": AMBER}
REC_COLORS = {"strongBuy": "#059669", "buy": "#34d399", "hold": "#fbbf24", "sell": "#f87171", "strongSell": "#b91c1c"}
REC_LABELS = {"strongBuy": "Strong Buy", "buy": "Buy", "hold": "Hold", "sell": "Sell", "strongSell": "Strong Sell"}
DASH = "—"

_REPLACEMENTS = {"→": "->", "−": "-", "＋": "+", "≥": ">=", "≤": "<=", "…": "...", " ": " ", "​": ""}


def _txt(value) -> str:
    """Text safe for Helvetica/WinAnsi: known symbols mapped, anything else -> '?'."""
    s = "" if value is None else str(value)
    for k, v in _REPLACEMENTS.items():
        s = s.replace(k, v)
    return s.encode("cp1252", "replace").decode("cp1252")


# ── Number formatting (mirrors TearSheet.jsx) ─────────────────────────────────

def money(n, d=2, sym="$"):
    return DASH if n is None else f"{'-' if n < 0 else ''}{sym}{abs(n):,.{d}f}"


def big(n, sym="$"):
    if n is None:
        return DASH
    a, sign = abs(n), "-" if n < 0 else ""
    if a >= 1e12:
        return f"{sign}{sym}{a / 1e12:.2f}T"
    if a >= 1e9:
        return f"{sign}{sym}{a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}{sym}{a / 1e6:.1f}M"
    return f"{sign}{sym}{a:,.0f}"


def pct(n, d=1, signed=False):
    if n is None:
        return DASH
    return f"{'+' if signed and n > 0 else ''}{n * 100:.{d}f}%"


def mult(n, d=1):
    return DASH if n is None else f"{n:.{d}f}x"


def num(n, d=2):
    return DASH if n is None else f"{n:.{d}f}"


def integer(n):
    return DASH if n is None else f"{round(n):,}"


def _posneg(n):
    return None if n is None else (GREEN if n >= 0 else RED)


def _score_color(s):
    return GRAY if s is None else GREEN if s >= 67 else AMBER if s >= 40 else RED


# ── Styles / small flowables ──────────────────────────────────────────────────

def _style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=8, leading=10.5, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_BODY = _style("body")
S_SMALL = _style("small", fontSize=7, leading=9, textColor=MUTED)
S_CELL = _style("cell", fontSize=7.5, leading=9.5)
S_CELL_R = _style("cellr", fontSize=7.5, leading=9.5, alignment=TA_RIGHT)
S_HEAD = _style("head", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=MUTED)
S_HEAD_R = _style("headr", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=MUTED, alignment=TA_RIGHT)
S_H2 = _style("h2", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK, spaceBefore=10)
S_SUB = _style("sub", fontSize=7, leading=9, textColor=MUTED, spaceAfter=3)
S_LABEL = _style("label", fontSize=6.5, leading=8, textColor=MUTED)
S_VALUE = _style("value", fontName="Helvetica-Bold", fontSize=9, leading=11)


def _p(text, style=S_BODY, color=None, bold=False):
    t = escape(_txt(text))
    if bold:
        t = f"<b>{t}</b>"
    if color is not None:
        t = f'<font color="{color.hexval().replace("0x", "#")}">{t}</font>'
    return Paragraph(t, style)


def _section(title, subtitle=None, need=1.6 * inch):
    """Heading block; starts a new page first if less than `need` points remain, so a heading
    is never stranded at the bottom and a chart + table that belong together stay together."""
    out = [CondPageBreak(need), Paragraph(escape(_txt(title)), S_H2),
           HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=1, spaceAfter=3)]
    if subtitle:
        out.append(Paragraph(escape(_txt(subtitle)), S_SUB))
    return out


def _table(head, rows, widths=None, right_from=1, zebra=True):
    """head: list[str]; rows: list[list[str | (str, color)]]. Columns >= right_from are right-aligned."""
    def cell(v, col, header=False):
        color = None
        if isinstance(v, tuple):
            v, color = v
        right = col >= right_from
        style = (S_HEAD_R if right else S_HEAD) if header else (S_CELL_R if right else S_CELL)
        return _p(v, style, color=color)
    data = [[cell(h, i, True) for i, h in enumerate(head)]]
    data += [[cell(c, i) for i, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        style += [("BACKGROUND", (0, i), (-1, i), PANEL) for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def _caption_with(caption, flowable):
    """A small caption kept on the same page as the chart or table it describes."""
    return KeepTogether([_p(caption, S_SMALL), flowable]) if flowable is not None else _p(caption, S_SMALL)


def _stat_row(stats, per_row=4):
    """Grid of label/value tiles: stats = [(label, value, sub?, color?)]."""
    cells = []
    for s in stats:
        label, value = s[0], s[1]
        sub = s[2] if len(s) > 2 else None
        color = s[3] if len(s) > 3 else None
        parts = [_p(label.upper(), S_LABEL), _p(value, S_VALUE, color=color)]
        if sub:
            parts.append(_p(sub, S_LABEL))
        cells.append(parts)
    while len(cells) % per_row:
        cells.append("")
    rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
    t = Table(rows, colWidths=[W / per_row] * per_row)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("BOX", (0, 0), (-1, -1), 0.4, colors.white),
                           ("INNERGRID", (0, 0), (-1, -1), 2, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
    return t


def _note(text, color=AMBER):
    t = Table([[_p(text, _style("note", fontSize=7.5, leading=10))]], colWidths=[W])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, color), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# ── Charts (vector) ───────────────────────────────────────────────────────────

def _label(d, x, y, text, size=6, color=MUTED, anchor="start"):
    d.add(String(x, y, _txt(text), fontName="Helvetica", fontSize=size, fillColor=color, textAnchor=anchor))


def _line_chart(dates, series, width=W, height=120, baseline=None, yfmt=lambda v: f"{v:.0f}"):
    vals = [v for s in series for v in s["values"] if v is not None]
    if not dates or len(dates) < 2 or not vals:
        return None
    d = Drawing(width, height)
    left, right, top, bottom = 34, 4, 6, 14
    pw, ph = width - left - right, height - top - bottom
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad
    n = len(dates)

    def x(i):
        return left + i / (n - 1) * pw

    def y(v):
        return bottom + (v - lo) / (hi - lo) * ph

    for f in (0, 0.25, 0.5, 0.75, 1):
        v = lo + (hi - lo) * f
        d.add(Line(left, y(v), width - right, y(v), strokeColor=colors.HexColor("#e5e7eb"), strokeWidth=0.4))
        _label(d, left - 3, y(v) - 2, yfmt(v), anchor="end")
    if baseline is not None and lo < baseline < hi:
        d.add(Line(left, y(baseline), width - right, y(baseline), strokeColor=GRAY, strokeWidth=0.6, strokeDashArray=[2, 2]))
    for i in range(1, n):
        if dates[i][:4] != dates[i - 1][:4]:
            _label(d, x(i), 3, dates[i][:4], anchor="middle")
    for s in series:
        seg = []
        for i, v in enumerate(s["values"]):
            if v is None:
                if len(seg) >= 4:
                    d.add(PolyLine(seg, strokeColor=s["color"], strokeWidth=s.get("width", 1.0)))
                seg = []
            else:
                seg += [x(i), y(v)]
        if len(seg) >= 4:
            d.add(PolyLine(seg, strokeColor=s["color"], strokeWidth=s.get("width", 1.0)))
    return d


def _legend(items, width=W):
    d = Drawing(width, 10)
    x = 0
    for label, color in items:
        d.add(Rect(x, 3, 9, 2, fillColor=color, strokeColor=None))
        _label(d, x + 12, 1.5, label, size=6.5)
        x += 12 + 5 * len(label) + 10
    return d


def _grouped_bars(groups, series, sym="$", width=W, height=110):
    vals = [g[s["key"]] for g in groups for s in series if g.get(s["key"]) is not None]
    if not vals:
        return None
    d = Drawing(width, height)
    bottom, top = 12, 10
    hi, lo = max(max(vals), 0), min(min(vals), 0)
    span = (hi - lo) or 1

    def y(v):
        return bottom + (v - lo) / span * (height - bottom - top)
    zero = y(0)
    gw = width / len(groups)
    bw = min(26, (gw - 6) / len(series))
    d.add(Line(0, zero, width, zero, strokeColor=GRAY, strokeWidth=0.5))
    for gi, g in enumerate(groups):
        left = gi * gw + (gw - bw * len(series)) / 2
        for si, s in enumerate(series):
            v = g.get(s["key"])
            if v is None:
                continue
            y0, y1 = sorted((zero, y(v)))
            d.add(Rect(left + si * bw, y0, bw - 1.5, max(y1 - y0, 0.6), fillColor=s["color"], strokeColor=None))
            if bw >= 17:
                _label(d, left + si * bw + (bw - 1.5) / 2, (y1 + 1.5) if v >= 0 else (y0 - 6), big(v, sym).replace("$", ""),
                       size=5, anchor="middle")
        _label(d, gi * gw + gw / 2, 2, g["label"], size=6.5, anchor="middle")
    return d


def _range_strip(rows, price, vmin, vmax, width=W, label_w=150, row_h=15):
    """Valuation 'football field': one row per model with a dot (and optional low-high bar), price line on top."""
    if vmax <= vmin:
        return None
    h = row_h * len(rows) + 18
    d = Drawing(width, h)
    pw = width - label_w - 50

    def x(v):
        return label_w + (v - vmin) / (vmax - vmin) * pw
    for i, r in enumerate(rows):
        cy = h - 8 - i * row_h
        _label(d, 0, cy - 2, r["label"], size=6.8, color=INK)
        d.add(Line(label_w, cy, label_w + pw, cy, strokeColor=colors.HexColor("#e5e7eb"), strokeWidth=0.4))
        if r.get("low") is not None and r.get("high") is not None:
            d.add(Rect(x(r["low"]), cy - 3, max(x(r["high"]) - x(r["low"]), 1.5), 6,
                       fillColor=colors.HexColor("#bfdbfe"), strokeColor=None))
        if r.get("value") is not None:
            d.add(Circle(x(r["value"]), cy, 3.2, fillColor=r.get("color", BLUE), strokeColor=None))
            # keep the value label clear of the price line: flip it to the dot's left when the line is just to its right
            near_price = price is not None and 0 <= x(price) - x(r["value"]) < 48
            _label(d, x(r["value"]) + (-6 if near_price else 6), cy - 2, money(r["value"]), size=6.5, color=INK,
                   anchor="end" if near_price else "start")
    if price is not None and vmin <= price <= vmax:
        d.add(Line(x(price), 10, x(price), h, strokeColor=AMBER, strokeWidth=1.1, strokeDashArray=[3, 2]))
        _label(d, x(price), 1.5, f"Price {money(price)}", size=6.5, color=AMBER, anchor="middle")
    return d


def _bars_hbar(items, width=W * 0.55, row_h=11):
    """Horizontal bars: items = [(label, value, color)]."""
    if not items:
        return None
    mx = max(v for _, v, _ in items) or 1
    d = Drawing(width, row_h * len(items) + 2)
    lw, vw = 34, 34
    for i, (label, v, color) in enumerate(items):
        cy = row_h * (len(items) - i - 1) + 2
        _label(d, 0, cy + 1.5, label, size=6.5)
        d.add(Rect(lw, cy, max((width - lw - vw) * v / mx, 0.5), row_h - 3.5, fillColor=color, strokeColor=None))
        _label(d, width, cy + 1.5, mult(v), size=6.5, color=INK, anchor="end")
    return d


def _rec_bar(dist, label, width=W * 0.5):
    total = sum(dist.values()) if dist else 0
    if not total:
        return None
    d = Drawing(width, 24)
    _label(d, 0, 16, f"{label} - {total} analysts", size=6.5)
    x = 0
    for k in REC_COLORS:
        n = dist.get(k, 0)
        if n <= 0:
            continue
        w = width * n / total
        d.add(Rect(x, 0, w, 12, fillColor=colors.HexColor(REC_COLORS[k]), strokeColor=colors.white, strokeWidth=0.5))
        if w >= 9:
            _label(d, x + w / 2, 3, str(n), size=6.5, color=INK, anchor="middle")
        x += w
    return d


def _score_bars(pillars, width=W * 0.42):
    row_h = 13
    d = Drawing(width, row_h * len(pillars))
    lw, vw = 78, 22
    for i, p in enumerate(pillars):
        cy = row_h * (len(pillars) - i - 1) + 2
        s = p.get("score")
        _label(d, 0, cy + 1, p["name"], size=7, color=INK)
        d.add(Rect(lw, cy, width - lw - vw, 6, fillColor=colors.HexColor("#e5e7eb"), strokeColor=None))
        if s is not None:
            d.add(Rect(lw, cy, (width - lw - vw) * s / 100, 6, fillColor=_score_color(s), strokeColor=None))
        _label(d, width, cy, DASH if s is None else f"{s:.0f}", size=7, color=_score_color(s), anchor="end")
    return d


# ── Sections ──────────────────────────────────────────────────────────────────

def _header(d):
    prof, snap, verdict = d["profile"], d["snapshot"], d["valuation"]["verdict"]
    tone = TONES.get(verdict.get("tone"), AMBER)
    left = [_p(f"{d['symbol']}  {prof.get('name', '')}", _style("t", fontName="Helvetica-Bold", fontSize=16, leading=19)),
            _p(" · ".join(x for x in (prof.get("sector"), prof.get("industry"), prof.get("exchange")) if x)
               + f"  ·  as of {d.get('asOf', '')}", S_SMALL)]
    chg = snap.get("changePct")
    right = [_p(money(snap.get("price")), _style("pr", fontName="Helvetica-Bold", fontSize=16, leading=19, alignment=TA_RIGHT)),
             _p(DASH if chg is None else f"{chg:+.2f}% today", _style("chg", fontSize=8, alignment=TA_RIGHT,
                                                                       textColor=_posneg(chg) or MUTED))]
    pill = Table([[_p(verdict.get("label", ""), _style("pill", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white,
                                                        alignment=1))]], colWidths=[130])
    pill.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tone), ("TOPPADDING", (0, 0), (-1, -1), 3),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    right_cell = Table([[right[0]], [right[1]], [pill]], colWidths=[130], hAlign="RIGHT")
    right_cell.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    head = Table([[left, right_cell]], colWidths=[W - 140, 140])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    m = d["valuation"]["multiples"]
    stats = _stat_row([("Market cap", big(snap.get("marketCap"))), ("Enterprise value", big(snap.get("enterpriseValue"))),
                       ("P/E (trailing)", mult(m.get("trailingPE"))), ("P/E (forward)", mult(m.get("forwardPE"))),
                       ("Beta", num(snap.get("beta"))), ("Dividend yield", pct(m.get("dividendYield"))),
                       ("52w range", f"{money(snap.get('week52Low'), 0)} - {money(snap.get('week52High'), 0)}"),
                       ("Next earnings", snap.get("nextEarnings") or DASH)], per_row=4)
    out = [head, HRFlowable(width="100%", thickness=1.2, color=INK, spaceBefore=3, spaceAfter=5), stats]
    if prof.get("quoteType") and prof["quoteType"] != "EQUITY":
        out += [Spacer(1, 4), _note(f"{d['symbol']} is not an operating company (classified as {prof['quoteType']}) - financial statements, "
                                    "earnings estimates and the valuation verdict don't apply.")]
    return out


def _verdict_section(d):
    v = d["valuation"]["verdict"]
    fvs = d["valuation"]["fairValues"]
    price = d["snapshot"]["price"]
    a = d["analysts"]
    out = _section("Is it cheap or expensive?", "Rules-based verdict from four independent fair-value models")
    tone = TONES.get(v.get("tone"), AMBER)
    if v.get("fairValue") is not None:
        summary = [_p(v["label"], _style("vl", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=tone)),
                   _p(f"Fair value (median of {v['methodsUsed']} models): {money(v['fairValue'])}", S_BODY),
                   _p(f"{'Premium' if v['premium'] >= 0 else 'Discount'} to fair value: {abs(v['premium']) * 100:.0f}%  "
                      f"(model range {money(v['low'], 0)} - {money(v['high'], 0)})", S_BODY, color=tone)]
    else:
        summary = [_p(v["label"], _style("vl", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=tone)),
                   _p(f"Only {v['methodsUsed']} of 4 valuation models could run (usually negative earnings or free cash flow, "
                      "or a fund), which isn't enough for a verdict.", S_BODY)]
    sc = d["scorecard"]
    score_block = [_score_bars(sc["pillars"]),
                   _p(f"Overall score: {DASH if sc['overall'] is None else format(sc['overall'], '.0f')} / 100",
                      _style("os", fontName="Helvetica-Bold", fontSize=8), color=_score_color(sc["overall"]))]
    two = Table([[summary, score_block]], colWidths=[W * 0.52, W * 0.48])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    out.append(two)
    out.append(Spacer(1, 4))

    have = [f for f in fvs if f.get("value") is not None]
    rows = [{"label": f["method"], "value": f["value"]} for f in have]
    if v.get("fairValue") is not None:
        rows.append({"label": "Median fair value", "value": v["fairValue"], "color": GREEN})
    if a.get("targetMean") is not None:
        rows.append({"label": "12-mo analyst target (low-high)", "value": a["targetMean"],
                     "low": a.get("targetLow"), "high": a.get("targetHigh")})
    pts = [price] + [r["value"] for r in rows] + [x for x in (a.get("targetLow"), a.get("targetHigh")) if x is not None]
    chart = _range_strip(rows, price, min(pts) * 0.9, max(pts) * 1.05) if rows else None
    if chart:
        out.append(chart)
    out.append(_table(["Model", "Fair value", "Basis"],
                      [[f["method"], money(f.get("value")), f.get("basis", "")] for f in fvs],
                      widths=[W * 0.17, W * 0.12, W * 0.71], right_from=99))
    out += [Spacer(1, 3), _p(f"{d.get('methodologyNote', '')} Data: Yahoo Finance and SEC EDGAR; may be delayed or incomplete.", S_SMALL)]
    return out


def _takeaways(d):
    f = d["flags"]
    if not f["strengths"] and not f["risks"]:
        return []

    def col(title, items, color, mark):
        cells = [_p(title, _style("ft", fontName="Helvetica-Bold", fontSize=8.5), color=color)]
        cells += [_p(f"{mark} {t}", S_BODY) for t in items] or [_p("None flagged", S_SMALL)]
        return cells
    t = Table([[col("Strengths", f["strengths"], GREEN, "+"), col("Risks to weigh", f["risks"], RED, "-")]],
              colWidths=[W / 2, W / 2])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return _section("Key takeaways", "Auto-generated from the numbers in this report") + [t]


def _business(d):
    p = d["profile"]
    out = _section("Business overview")
    desc = p.get("description")
    out.append(_p(desc if desc else "No business description available.", S_BODY))
    out += [Spacer(1, 4), _stat_row([("Sector", p.get("sector") or DASH), ("Industry", p.get("industry") or DASH),
                                     ("Employees", integer(p.get("employees"))),
                                     ("Exchange", p.get("exchange") or DASH, p.get("country"))])]
    return out


def _performance(d):
    perf, sym = d["performance"], d["symbol"]
    out = _section("Past performance", "Total return (dividends included) vs. the S&P 500 (SPY)")
    out.append(_table(["Period", sym, "S&P 500", f"{sym} vs. S&P"],
                      [[r["period"], (pct(r["stock"], 1, True), _posneg(r["stock"])), (pct(r["spy"], 1, True), _posneg(r["spy"])),
                        (pct(r["relative"], 1, True), _posneg(r["relative"]))] for r in perf["returns"]],
                      widths=[W * 0.16, W * 0.28, W * 0.28, W * 0.28]))
    out += [Spacer(1, 3), _stat_row([("Max drawdown (5y)", pct(perf.get("maxDrawdown5y"), 0), None, RED),
                                     ("Volatility (1y, ann.)", pct(perf.get("volatility1y"), 0)),
                                     ("52-week low", money(d["snapshot"].get("week52Low"))),
                                     ("52-week high", money(d["snapshot"].get("week52High")))])]
    s = perf.get("series")
    if s:
        rel_series = [{"values": s["stockRebased"], "color": GREEN, "width": 1.2}]
        if s.get("spyRebased"):
            rel_series.insert(0, {"values": s["spyRebased"], "color": GRAY, "width": 0.9})
        rel = _line_chart(s["dates"], rel_series, height=105, baseline=100)
        if rel:
            out += [Spacer(1, 4), _caption_with(f"5-year growth of 100 - {sym} (green) vs. S&P 500 (gray)", rel)]
        px = _line_chart(s["dates"], [{"values": s["ma200"], "color": PURPLE, "width": 0.8},
                                      {"values": s["ma50"], "color": AMBER, "width": 0.8},
                                      {"values": s["close"], "color": BLUE, "width": 1.1}], height=105,
                         yfmt=lambda v: f"${v:.0f}")
        if px:
            out += [Spacer(1, 4), _caption_with("5-year price (blue) with 50-day (amber) and 200-day (purple) moving averages", px)]
    return out


def _financials(d):
    f, h = d["financials"], d["financials"]["history"]
    sym = d["currencyNote"]["financial"] + " " if d.get("currencyNote") else "$"
    n = len(h)
    sub = (f"Last {n} fiscal years, oldest to newest" + (" (all the annual history available for this ticker)" if n < 10 else "")
           if n else "Last fiscal years, oldest to newest")
    out = _section("Financial track record", sub, need=4.6 * inch)
    if d.get("currencyNote"):
        out.append(_note(f"{d['symbol']} reports in {d['currencyNote']['financial']} but trades in {d['currencyNote']['trading']}; "
                         "statement figures are in the reporting currency and per-share valuation models are skipped."))
        out.append(Spacer(1, 3))
    if d.get("bankNote"):
        out.append(_p("Free cash flow and gross profit aren't meaningful for banks, so they're left blank.", S_SMALL))
    if not h:
        out.append(_p("No annual financial statements available (common for ETFs and funds).", S_SMALL))
        return out

    def yr(r):
        return "FY" + r["fiscalYear"][2:4]
    chart = _grouped_bars([{"label": yr(r), "revenue": r["revenue"], "netIncome": r["netIncome"], "fcf": r["freeCashFlow"]} for r in h],
                          [{"key": "revenue", "color": BLUE}, {"key": "netIncome", "color": GREEN}, {"key": "fcf", "color": AMBER}], sym)
    if chart:
        out += [chart, _legend([("Revenue", BLUE), ("Net income", GREEN), ("Free cash flow", AMBER)])]

    def row(label, key, fmt, color=False):
        return [label] + [((fmt(r[key]), _posneg(r[key])) if color else fmt(r[key])) for r in h]
    label_w = 78
    cw = [label_w] + [(W - label_w) / n] * n
    out.append(_table([""] + [yr(r) for r in h], [
        row("Revenue", "revenue", lambda v: big(v, sym)), row("  growth YoY", "revenueGrowth", lambda v: pct(v, 1, True), True),
        row("Gross margin", "grossMargin", pct), row("Operating margin", "operatingMargin", pct),
        row("Net income", "netIncome", lambda v: big(v, sym)), row("Net margin", "netMargin", pct),
        row("Diluted EPS", "eps", lambda v: money(v, 2, sym)), row("  growth YoY", "epsGrowth", lambda v: pct(v, 1, True), True),
        row("Free cash flow", "freeCashFlow", lambda v: big(v, sym)), row("FCF margin", "fcfMargin", pct)], widths=cw))
    out += [Spacer(1, 3), _stat_row([(f"Revenue CAGR ({n - 1}y)", pct(f.get("revenueCagr"), 1, True), None, _posneg(f.get("revenueCagr"))),
                                     (f"EPS CAGR ({n - 1}y)", pct(f.get("epsCagr"), 1, True), None, _posneg(f.get("epsCagr"))),
                                     ("Revenue growth (TTM)", pct(f["ttm"].get("revenueGrowth"), 1, True), None, _posneg(f["ttm"].get("revenueGrowth"))),
                                     ("Earnings growth (TTM)", pct(f["ttm"].get("earningsGrowth"), 1, True), None, _posneg(f["ttm"].get("earningsGrowth")))])]
    return out


def _balance(d):
    b = d["balanceSheet"]
    sym = d["currencyNote"]["financial"] + " " if d.get("currencyNote") else "$"
    nd = b.get("netDebt")
    return _section("Balance sheet & returns on capital") + [_stat_row([
        ("Cash", big(b.get("cash"), sym)), ("Total debt", big(b.get("debt"), sym)),
        ("Net cash" if nd is not None and nd < 0 else "Net debt", big(abs(nd) if nd is not None else None, sym), None,
         GREEN if nd is not None and nd < 0 else None),
        ("Net debt / EBITDA", mult(b.get("netDebtToEbitda"))),
        ("Debt / equity", DASH if b.get("debtToEquity") is None else f"{b['debtToEquity']:.0f}%"),
        ("Current ratio", num(b.get("currentRatio"))), ("Interest coverage", mult(b.get("interestCoverage"))),
        ("Payout ratio", pct(b.get("payoutRatio"), 0)), ("Return on equity", pct(b.get("roe"))),
        ("Return on assets", pct(b.get("roa")))], per_row=5)]


def _valuation(d):
    v = d["valuation"]
    m = v["multiples"]
    out = _section("Valuation multiples", "How much you pay per dollar of earnings, sales and cash flow")
    out.append(_stat_row([
        ("P/E (trailing)", mult(m.get("trailingPE"))), ("P/E (forward)", mult(m.get("forwardPE"))), ("PEG", num(m.get("peg"))),
        ("Price / sales", mult(m.get("priceToSales"))), ("Price / book", mult(m.get("priceToBook"))),
        ("EV / EBITDA", mult(m.get("evToEbitda"))), ("EV / revenue", mult(m.get("evToRevenue"))), ("FCF yield", pct(m.get("fcfYield"))),
        ("Dividend yield", pct(m.get("dividendYield"))),
        ("Earnings yield (fwd)", pct(m.get("earningsYieldForward")),
         f"10-yr Treasury {pct(v.get('tenYearYield'), 2)}" if v.get("tenYearYield") is not None else None,
         _posneg(v.get("earningsYieldVsBond")))], per_row=5))
    eyb = v.get("earningsYieldVsBond")
    if eyb is not None:
        out += [Spacer(1, 3), _p(f"Forward earnings yield is {abs(eyb) * 100:.1f}% {'above' if eyb >= 0 else 'below'} the risk-free 10-year "
                                 "Treasury - " + ("stocks are paying you a premium for taking equity risk." if eyb >= 0 else
                                                  "you are accepting less earnings yield than a government bond pays, betting on "
                                                  "growth to close the gap."), S_BODY)]
    pes = v.get("historicalPE") or []
    if pes:
        items = [("FY" + p["fiscalYear"][2:4], p["pe"], BLUE) for p in pes]
        if m.get("trailingPE"):
            items.append(("Today", m["trailingPE"], AMBER))
        med = v.get("historicalPEMedian")
        out += [Spacer(1, 4), _caption_with("P/E at each fiscal year-end vs. today" + (f" - median {mult(med)}" if med is not None else ""),
                                            _bars_hbar(items))]
    return out


def _returns(d):
    v = d["valuation"]
    out = _section("Projected earnings & returns",
                   "What the stock could return if consensus earnings are delivered - and what happens if the multiple moves")
    if v["scenarios12m"]:
        out += [_caption_with("12-month scenarios (next fiscal-year consensus EPS, low / average / high)",
                              _table(["Case", "EPS", "P/E", "Price", "Total return"],
                       [[s["scenario"], money(s["eps"]), mult(s["peMultiple"]), money(s["price"]),
                         (pct(s["totalReturn"], 1, True), _posneg(s["totalReturn"]))] for s in v["scenarios12m"]],
                       widths=[W * 0.2, W * 0.2, W * 0.2, W * 0.2, W * 0.2]))]
    else:
        out.append(_p("12-month scenarios need current-year and next-year consensus EPS estimates.", S_SMALL))
    out.append(Spacer(1, 4))
    if v["fiveYearReturns"]:
        out += [_caption_with(f"5-year annualised return (EPS compounding at {pct(d['estimates'].get('growthUsed'))})",
                              _table(["If the P/E...", "Exit P/E", "Price in 5y", "Annual return"],
                       [[s["scenario"], mult(s["exitPe"]), money(s["endPrice"]), (pct(s["annualisedReturn"], 1, True),
                                                                                 _posneg(s["annualisedReturn"]))]
                        for s in v["fiveYearReturns"]], widths=[W * 0.34, W * 0.22, W * 0.22, W * 0.22]))]
        if v.get("tenYearYield") is not None:
            out.append(_p(f"Compare with the ~{pct(v['tenYearYield'])} a 10-year Treasury pays with no equity risk.", S_SMALL))
    else:
        out.append(_p("5-year returns need positive trailing EPS and a growth estimate.", S_SMALL))
    return out


def _estimates(d):
    e, t = d["estimates"], d["earningsTrack"]
    out = _section("Consensus estimates & earnings record")
    if e["eps"]:
        out += [_caption_with("EPS estimates",
                              _table(["Period", "Avg", "Low - High", "Year ago", "Growth", "# analysts"],
                       [[r["label"], money(r["avg"]), f"{num(r['low'])} - {num(r['high'])}", money(r["yearAgo"]),
                         (pct(r["growth"], 1, True), _posneg(r["growth"])), DASH if r["analysts"] is None else str(r["analysts"])]
                        for r in e["eps"]]))]
    if e["revenue"]:
        out += [Spacer(1, 3), _caption_with("Revenue estimates",
                                            _table(["Period", "Avg", "Year ago", "Growth"],
                                                   [[r["label"], big(r["avg"]), big(r["yearAgo"]), (pct(r["growth"], 1, True), _posneg(r["growth"]))]
                                                    for r in e["revenue"]]))]
    if e["revisions"]:
        out += [Spacer(1, 3), _caption_with("EPS estimate revisions (are analysts raising or cutting?)",
                                            _table(["Period", "Current", "30 days", "90 days"],
                                                   [[r["label"], money(r["current"]), (pct(r["change30d"], 1, True), _posneg(r["change30d"])),
                                                     (pct(r["change90d"], 1, True), _posneg(r["change90d"]))] for r in e["revisions"]]))]
    if not (e["eps"] or e["revenue"]):
        out.append(_p("No consensus estimates available.", S_SMALL))
    if t["quarters"]:
        extra = f" - beat {t['beats']}/{t['total']}" + (f", avg surprise {pct(t['avgSurprisePct'], 1, True)}" if t.get("avgSurprisePct") is not None else "") \
            if t["total"] else ""
        out += [Spacer(1, 3), _caption_with(f"Last {t['total'] or 'few'} quarters: actual vs. estimated EPS{extra}",
                                            _table(["Quarter", "Actual", "Estimate", "Surprise"],
                                                   [[q["quarter"], money(q["epsActual"]), money(q["epsEstimate"]), (pct(q["surprisePct"], 1, True), _posneg(q["surprisePct"]))]
                                                    for q in t["quarters"]]))]
    if d["snapshot"].get("nextEarnings"):
        out.append(_p(f"Next earnings report: {d['snapshot']['nextEarnings']}", S_SMALL))
    return out


def _analysts(d):
    a = d["analysts"]
    names = {"strong_buy": "Strong Buy", "buy": "Buy", "hold": "Hold", "underperform": "Underperform", "sell": "Sell", "strong_sell": "Strong Sell"}
    out = _section("Analyst ratings & price targets")
    out.append(_stat_row([("Consensus", names.get(a.get("recommendation"), a.get("recommendation") or DASH),
                           f"{a['recommendationMean']:.2f} / 5 (1 = strong buy)" if a.get("recommendationMean") is not None else None),
                          ("Mean target", money(a.get("targetMean"))), ("Target range", f"{money(a.get('targetLow'), 0)} - {money(a.get('targetHigh'), 0)}"),
                          ("Implied upside", pct(a.get("upsideToMean"), 1, True), None, _posneg(a.get("upsideToMean")))]))
    for dist, label in ((a.get("distribution"), "Ratings now"), (a.get("distribution3mAgo"), "Ratings 3 months ago")):
        bar = _rec_bar(dist, label) if dist else None
        if bar:
            out += [Spacer(1, 3), bar]
    if a.get("recentChanges"):
        out += [Spacer(1, 4), _p("Recent rating & target changes", S_SMALL),
                _table(["Date", "Firm", "Rating", "Target"],
                       [[c["date"], c["firm"], f"{c['from']} -> {c['to']}" if c.get("from") and c["from"] != c.get("to") else c.get("to", ""),
                         (money(c["target"], 0) + (f" (was {money(c['priorTarget'], 0)})" if c.get("priorTarget") else "")) if c.get("target") else DASH]
                        for c in a["recentChanges"]], widths=[W * 0.14, W * 0.3, W * 0.32, W * 0.24], right_from=99)]
    return out


def _ownership(d):
    o = d["ownership"]
    stats = [("Held by institutions", pct(o.get("institutionsPct"))), ("Held by insiders", pct(o.get("insidersPct"))),
             ("Short % of float", pct(o.get("shortPercentOfFloat")), None, RED if (o.get("shortPercentOfFloat") or 0) > 0.1 else None),
             ("Days to cover", num(o.get("shortRatio"), 1))]
    ins = o.get("insiderActivity")
    if ins:
        stats += [("Insider buys (6m)", integer(ins.get("boughtShares6m")), f"{integer(ins.get('buyTransactions6m'))} transactions", GREEN),
                  ("Insider sells (6m)", integer(ins.get("soldShares6m")), f"{integer(ins.get('sellTransactions6m'))} transactions", RED),
                  ("Net shares (6m)", integer(ins.get("netShares6m")), None, _posneg(ins.get("netShares6m")))]
    return _section("Ownership, insiders & short interest") + [_stat_row(stats)]


def _footer(canvas, doc, symbol, as_of):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 0.5 * inch, PAGE_W - MARGIN, 0.5 * inch)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 0.36 * inch, _txt(f"StockMonitor Tear Sheet - {symbol} - data as of {as_of} - not investment advice - Yahoo Finance & SEC EDGAR data may be delayed"))
    canvas.drawRightString(PAGE_W - MARGIN, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(sheet: dict, compress: bool = True) -> bytes:
    """Render a tear-sheet dict (as returned by the API, without an 'error') to PDF bytes."""
    if sheet.get("error"):
        raise ValueError(sheet["error"])
    buf = io.BytesIO()
    symbol, as_of = sheet["symbol"], sheet.get("asOf") or str(date.today())
    doc = BaseDocTemplate(buf, pagesize=letter, pageCompression=1 if compress else 0, title=_txt(f"{symbol} Tear Sheet"),
                          author="StockMonitor", subject=_txt(sheet["profile"].get("name", symbol)))
    # Zero-padding frame: reportlab's default 6pt padding would indent paragraphs relative to
    # full-width tables and charts.
    frame = Frame(MARGIN, 0.7 * inch, W, PAGE_H - 0.55 * inch - 0.7 * inch, leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=lambda c, dd: _footer(c, dd, symbol, as_of))])
    story = []
    for part in (_header(sheet), _verdict_section(sheet), _takeaways(sheet), _business(sheet), _performance(sheet), _financials(sheet),
                 _balance(sheet), _valuation(sheet), _returns(sheet), _estimates(sheet), _analysts(sheet), _ownership(sheet)):
        story += part
    doc.build(story)
    return buf.getvalue()
