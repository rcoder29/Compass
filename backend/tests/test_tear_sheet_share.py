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
