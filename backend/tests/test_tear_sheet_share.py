"""
Tests for the Tear Sheet PDF: the renderer and the download endpoint. No network.
Run: python -m pytest tests/test_tear_sheet_share.py -v
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.tear_sheet as ts
import routers.tear_sheet_share as share
import tear_sheet_pdf as tp
from tests.test_tear_sheet import _edgar_row, _raw

@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(ts, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(ts, "cache_set", lambda *a, **k: None)


def make_sheet(**raw_over):
    edgar = [_edgar_row(f"{2016 + i}-12-31", 100.0 + 10 * i, 10.0 + i, eps=1.0 + 0.1 * i, freeCashFlow=8.0 + i) for i in range(10)]
    raw = _raw(edgar=edgar)
    raw.update(raw_over)
    return ts._build_tear_sheet("ACME", raw)


def page_count(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")


# ── PDF renderer ──────────────────────────────────────────────────────────────

class TestPdf:
    def test_produces_a_multi_page_pdf(self):
        pdf = tp.build_pdf(make_sheet())
        assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
        assert page_count(pdf) >= 2 and len(pdf) > 5_000

    def test_contains_every_section_and_key_facts(self):
        sheet = make_sheet()
        pdf = tp.build_pdf(sheet, compress=False)
        for needle in ["Acme Corp", sheet["valuation"]["verdict"]["label"], "Is it cheap or expensive?", "Key takeaways",
                       "Business overview", "Past performance", "Financial track record", "Balance sheet", "Valuation multiples",
                       "Projected earnings", "Consensus estimates", "Analyst ratings", "Ownership, insiders"]:
            assert needle.encode() in pdf, needle

    def test_ten_year_history_has_ten_year_columns(self):
        pdf = tp.build_pdf(make_sheet(), compress=False)
        assert b"Last 10 fiscal years" in pdf
        assert b"FY16" in pdf and b"FY25" in pdf

    def test_error_sheet_is_rejected(self):
        with pytest.raises(ValueError, match="No price"):
            tp.build_pdf({"symbol": "X", "error": "No price data available"})

    def test_fund_without_financials_still_renders(self):
        sheet = ts._build_tear_sheet("SPY", _raw(info={"currentPrice": 500.0, "quoteType": "ETF", "longName": "S&P ETF"},
                                                income=None, earn_est=None, targets=None))
        pdf = tp.build_pdf(sheet, compress=False)
        assert b"not an operating company" in pdf and b"Not enough data to judge" in pdf
        assert b"No annual financial statements" in pdf

    def test_currency_and_bank_notes_are_shown(self):
        info = {**_raw()["info"], "financialCurrency": "TWD", "currency": "USD"}
        assert b"reports in TWD but trades in USD" in tp.build_pdf(make_sheet(info=info), compress=False)
        info = {**_raw()["info"], "industry": "Banks - Diversified"}
        assert b"aren't meaningful for banks" in tp.build_pdf(make_sheet(info=info), compress=False)

    def test_renders_with_no_price_history_or_estimates(self):
        pdf = tp.build_pdf(make_sheet(hist=None, spy=None, earn_est=None, targets=None, recs=None), compress=False)
        assert pdf.startswith(b"%PDF-")

    def test_non_latin_company_name_does_not_crash(self):
        sheet = make_sheet()
        sheet["profile"]["name"] = "台灣積體電路製造 Taiwan Semi → ≥ test"
        sheet["profile"]["description"] = "Fabless “foundry” — ‘quotes’ & <tags> and 日本語"
        pdf = tp.build_pdf(sheet, compress=False)
        assert b"Taiwan Semi" in pdf

    def test_very_long_text_and_many_rows_paginate(self):
        sheet = make_sheet()
        sheet["profile"]["description"] = "Word " * 4000
        sheet["analysts"]["recentChanges"] = sheet["analysts"]["recentChanges"] * 40 or [
            {"date": "2026-10-01", "firm": "F", "action": "main", "from": "A", "to": "B", "target": 1.0, "priorTarget": 2.0}] * 40
        assert page_count(tp.build_pdf(sheet)) >= 4

    def test_compression_makes_it_smaller(self):
        sheet = make_sheet()
        assert len(tp.build_pdf(sheet, compress=True)) < len(tp.build_pdf(sheet, compress=False))

    def test_metadata_title(self):
        assert b"/Title (ACME Tear Sheet)" in tp.build_pdf(make_sheet(), compress=False)


class TestPdfHelpers:
    def test_txt_maps_known_symbols_and_replaces_the_rest(self):
        assert tp._txt("a → b − c ≥ d") == "a -> b - c >= d"
        assert tp._txt("日本") == "??"
        assert tp._txt(None) == ""
        assert tp._txt("café — ok") == "café — ok"        # cp1252 characters survive

    def test_formatters_match_the_web_page(self):
        assert tp.money(1234.5) == "$1,234.50" and tp.money(-3) == "-$3.00" and tp.money(None) == "—"
        assert tp.big(2.5e12) == "$2.50T" and tp.big(-3.2e9) == "-$3.20B" and tp.big(4.5e6) == "$4.5M"
        assert tp.big(2e9, "TWD ") == "TWD 2.00B"
        assert tp.pct(0.153) == "15.3%" and tp.pct(0.153, 1, True) == "+15.3%" and tp.pct(-0.05, 1, True) == "-5.0%"
        assert tp.mult(27.04) == "27.0x" and tp.mult(None) == "—" and tp.integer(1234.6) == "1,235"

    def test_charts_return_none_when_there_is_nothing_to_draw(self):
        assert tp._line_chart([], [{"values": [], "color": tp.BLUE}]) is None
        assert tp._line_chart(["2026-01-01", "2026-01-08"], [{"values": [None, None], "color": tp.BLUE}]) is None
        assert tp._grouped_bars([{"label": "FY25", "revenue": None}], [{"key": "revenue", "color": tp.BLUE}]) is None
        assert tp._rec_bar({}, "x") is None and tp._rec_bar({"buy": 0}, "x") is None
        assert tp._bars_hbar([]) is None

    def test_line_chart_breaks_the_line_at_missing_values(self):
        d = tp._line_chart([f"2026-01-{i:02d}" for i in range(1, 9)],
                           [{"values": [1, 2, 3, None, 5, 6, 7, 8], "color": tp.BLUE}])
        polylines = [s for s in d.contents if s.__class__.__name__ == "PolyLine"]
        assert len(polylines) == 2


# ── Quarterly income flow in the PDF ──────────────────────────────────────────

def quarterly_frame(n=5):
    import pandas as pd
    cols = [pd.Timestamp("2026-06-30") - pd.offsets.QuarterEnd(i) for i in range(n)]
    return pd.DataFrame({c: {"Total Revenue": 100.0e9 - i * 1e9, "Cost Of Revenue": 40.0e9, "Gross Profit": 60.0e9 - i * 1e9,
                             "Research And Development": 10.0e9, "Selling General And Administration": 15.0e9,
                             "Operating Income": 35.0e9 - i * 1e9, "Pretax Income": 36.0e9 - i * 1e9, "Tax Provision": 6.0e9,
                             "Net Income": 30.0e9 - i * 1e9} for i, c in enumerate(cols)})


def quarterly_cash():
    import pandas as pd
    return pd.DataFrame({pd.Timestamp("2026-06-27"): {"Cash Dividends Paid": -4.0e9, "Repurchase Of Capital Stock": -20.0e9}})


def quarterly_dividends():
    import pandas as pd
    return pd.Series([0.26, 0.27], index=pd.to_datetime(["2026-02-09", "2026-05-11"]))


STREAMS = {"2026-06-30": {"axisLabel": "Products & services", "total": 100.0e9, "priorTotal": 80.0e9, "form": "10-Q", "derived": False,
                          "streams": [{"name": "Hardware", "value": 60.0e9, "prior": 50.0e9}, {"name": "Cloud Services", "value": 40.0e9, "prior": 30.0e9}]}}


class TestPdfIncomeFlow:
    def sheet(self, **over):
        return make_sheet(q_income=quarterly_frame(), q_cash=quarterly_cash(), dividends=quarterly_dividends(), streams=STREAMS, **over)

    def test_section_headline_streams_and_quarter_table(self):
        pdf = tp.build_pdf(self.sheet(), compress=False)
        for needle in [b"quarterly income flow", b"Quarter ended 2026-06-30", b"Revenue by income stream", b"products & services",
                       b"source: SEC 10-Q", b"Hardware", b"Cloud Services", b"Recent quarters", b"Jun 2026", b"Mar 2026",
                       b"Dividends paid", b"Share buybacks", b"80% of net income returned"]:
            assert needle in pdf, needle

    def test_diagram_labels_are_drawn(self):
        pdf = tp.build_pdf(self.sheet(), compress=False)
        for needle in [b"Gross profit", b"Cost of revenue", b"Operating income", b"Net income", b"Dividends - $0.27/share", b"Share buybacks"]:
            assert needle in pdf, needle

    def test_no_section_without_quarterly_statements(self):
        pdf = tp.build_pdf(make_sheet(), compress=False)
        assert b"quarterly income flow" not in pdf

    def test_flow_less_quarter_explains_itself(self):
        sheet = self.sheet()
        sheet["incomeFlow"]["quarters"][0]["flow"] = None
        pdf = tp.build_pdf(sheet, compress=False)
        assert b"enough detail to draw the flow" in pdf

    def test_notes_are_printed_under_the_diagram(self):
        sheet = make_sheet(q_income=quarterly_frame(), q_cash=None)          # no cash flow -> no dividends or buybacks
        assert b"No dividends or buybacks were paid" in tp.build_pdf(sheet, compress=False)

    def test_derived_q4_streams_are_labelled(self):
        sheet = self.sheet()
        sheet["incomeFlow"]["quarters"][0]["streams"].update(derived=True, form="10-K")
        assert b"Q4 derived as fiscal year minus nine months" in tp.build_pdf(sheet, compress=False)

    def test_reporting_currency_is_used(self):
        info = {**_raw()["info"], "financialCurrency": "TWD", "currency": "USD"}
        assert b"TWD 60.00B" in tp.build_pdf(make_sheet(info=info, q_income=quarterly_frame(), q_cash=quarterly_cash()), compress=False)

    def test_section_adds_a_page_but_stays_readable(self):
        with_flow = tp.build_pdf(self.sheet())
        without = tp.build_pdf(make_sheet())
        assert page_count(with_flow) >= page_count(without) and len(with_flow) > len(without)


class TestSankeyDrawing:
    def flow(self):
        sheet = make_sheet(q_income=quarterly_frame(), q_cash=quarterly_cash(), dividends=quarterly_dividends(), streams=STREAMS)
        return sheet["incomeFlow"]["quarters"][0]["flow"]

    def test_draws_every_node_and_link(self):
        f = self.flow()
        d = tp._sankey_drawing(f)
        kinds = [type(x).__name__ for x in d.contents]
        assert kinds.count("Path") == len(f["links"]) and kinds.count("Rect") == len(f["nodes"])
        assert kinds.count("String") == 2 * len(f["nodes"])             # label + value line per node

    def test_scales_the_layout_to_the_requested_width_and_keeps_aspect(self):
        f = self.flow()
        d = tp._sankey_drawing(f, width=400)
        assert d.width == 400 and d.height == pytest.approx(400 * f["height"] / f["width"])

    def test_everything_is_inside_the_drawing(self):
        f = self.flow()
        d = tp._sankey_drawing(f)
        for shape in d.contents:
            if type(shape).__name__ == "Rect":
                assert 0 <= shape.x and shape.x + shape.width <= d.width + 0.01 and 0 <= shape.y and shape.y + shape.height <= d.height + 0.01

    def test_y_axis_is_flipped_for_pdf(self):
        f = self.flow()
        d = tp._sankey_drawing(f)
        top_node = min(f["nodes"], key=lambda n: n["y"])
        rects = [s for s in d.contents if type(s).__name__ == "Rect"]
        assert max(r.y + r.height for r in rects) == pytest.approx(d.height - top_node["y"] * (d.width / f["width"]), abs=0.01)

    def test_long_labels_are_clipped_and_non_latin_text_survives(self):
        f = self.flow()
        f["nodes"][0]["label"] = "Wearables, Home and Accessories and 日本語"
        f["nodes"][0]["labelSide"] = "left"
        d = tp._sankey_drawing(f)
        strings = [s.text for s in d.contents if type(s).__name__ == "String"]
        clipped = [t for t in strings if t.endswith("...")]
        assert clipped and all(len(t) == 22 for t in clipped)       # left-side labels get 22 characters including the dots

    def test_quarter_label(self):
        assert tp._quarter_label("2026-06-30") == "Jun 2026" and tp._quarter_label(None) == "—" and tp._quarter_label("junk") == "junk"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sheet():
    return make_sheet()


@pytest.fixture
def client(monkeypatch, sheet):
    async def fake_load(symbol):
        return sheet if symbol.upper() == "ACME" else {"symbol": symbol.upper(), "error": "No price data available for this symbol."}
    monkeypatch.setattr(share, "load_tear_sheet", fake_load)
    app = FastAPI()
    app.include_router(share.router)
    return TestClient(app)


class TestPdfEndpoint:
    def test_pdf_download(self, client, sheet):
        r = client.get("/api/tear-sheet/acme/pdf")
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"] == f'attachment; filename="ACME_TearSheet_{sheet["asOf"]}.pdf"'
        assert r.content.startswith(b"%PDF-")

    def test_unknown_symbol_is_404_with_the_reason(self, client):
        r = client.get("/api/tear-sheet/ZZZZ/pdf")
        assert r.status_code == 404 and "No price data" in r.json()["detail"]

    @pytest.mark.parametrize("bad", ["AAPL%0d%0aX", "A" * 20, "AA PL", "AAPL;ls"])
    def test_malformed_symbols_are_rejected(self, client, bad):
        assert client.get(f"/api/tear-sheet/{bad}/pdf").status_code in (400, 404)

    def test_filename(self, sheet):
        assert share.pdf_filename(sheet) == f"ACME_TearSheet_{sheet['asOf']}.pdf"
