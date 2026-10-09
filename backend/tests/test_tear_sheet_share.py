"""
Tests for Tear Sheet sharing: the PDF renderer, the SMTP sender, and the download /
email endpoints. No network and no real SMTP server — smtplib is replaced by a fake.
Run: python -m pytest tests/test_tear_sheet_share.py -v
"""
import smtplib
import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import email_sender
import routers.tear_sheet as ts
import routers.tear_sheet_share as share
import tear_sheet_pdf as tp
from tests.test_tear_sheet import _edgar_row, _raw

SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_SECURITY", "EMAIL_ALLOWED_RECIPIENTS")


@pytest.fixture(autouse=True)
def clean_email_state(monkeypatch):
    for v in SMTP_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(ts, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(ts, "cache_set", lambda *a, **k: None)
    email_sender._send_times.clear()
    yield
    email_sender._send_times.clear()


def configure_smtp(monkeypatch, **over):
    env = {"SMTP_HOST": "smtp.example.com", "SMTP_USER": "me@example.com", "SMTP_PASSWORD": "s3cret-pw"}
    env.update(over)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


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


# ── email_sender ──────────────────────────────────────────────────────────────

class TestRecipients:
    def test_splits_on_commas_semicolons_spaces_and_newlines(self):
        valid, invalid = email_sender.parse_recipients("a@x.com, b@y.org; c@z.io\nd@w.net  e@v.co")
        assert valid == ["a@x.com", "b@y.org", "c@z.io", "d@w.net", "e@v.co"] and invalid == []

    def test_dedupes_case_insensitively_keeping_order(self):
        assert email_sender.parse_recipients("A@x.com, a@X.com, b@x.com")[0] == ["A@x.com", "b@x.com"]

    @pytest.mark.parametrize("bad", ["nope", "a@b", "@x.com", "a@.com", "Bcc:", "<a@x.com>", "a@x..",
                                     "x" * 250 + "@example.com"])
    def test_invalid_addresses_are_flagged(self, bad):
        valid, invalid = email_sender.parse_recipients(bad)
        assert valid == [] and invalid

    def test_a_space_is_a_separator_so_a_split_name_is_flagged(self):
        valid, invalid = email_sender.parse_recipients("a b@x.com")
        assert valid == ["b@x.com"] and invalid == ["a"]     # the endpoint rejects the whole request on any invalid entry

    def test_accepts_a_list_and_blank_input(self):
        assert email_sender.parse_recipients(["a@x.com", "b@y.com"])[0] == ["a@x.com", "b@y.com"]
        assert email_sender.parse_recipients("") == ([], []) and email_sender.parse_recipients(None) == ([], [])

    def test_header_injection_attempt_is_rejected(self):
        valid, invalid = email_sender.parse_recipients("victim@x.com\r\nBcc:evil@x.com")
        assert valid == ["victim@x.com"] and invalid == ["Bcc:evil@x.com"]


class TestAllowlist:
    def test_no_allowlist_allows_everyone(self):
        assert email_sender.disallowed_recipients(["a@x.com"]) == []

    def test_address_and_domain_rules(self, monkeypatch):
        monkeypatch.setenv("EMAIL_ALLOWED_RECIPIENTS", "boss@corp.com, @family.org")
        assert email_sender.disallowed_recipients(["BOSS@corp.com", "mom@family.org", "x@evil.com", "x@notfamily.org"]) \
            == ["x@evil.com", "x@notfamily.org"]


class TestRateLimit:
    def test_blocks_after_limit_and_recovers_after_an_hour(self):
        email_sender._send_times[:] = [1000.0] * email_sender.MAX_SENDS_PER_HOUR
        assert email_sender.rate_limited(now=1000.0 + 60) is True
        assert email_sender.rate_limited(now=1000.0 + 3601) is False

    def test_under_limit(self):
        email_sender._send_times[:] = [1000.0] * (email_sender.MAX_SENDS_PER_HOUR - 1)
        assert email_sender.rate_limited(now=1001.0) is False


class FakeSmtp:
    """Stands in for smtplib.SMTP / SMTP_SSL; records the conversation on the class."""
    log: list = []
    raise_on = None

    def __init__(self, host, port, timeout=None, context=None):
        FakeSmtp.log.append(("connect", type(self).__name__, host, port))
        self.ssl = context is not None and type(self).__name__ == "FakeSmtpSsl"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        FakeSmtp.log.append(("starttls",))

    def login(self, user, password):
        if FakeSmtp.raise_on == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials s3cret-pw")
        FakeSmtp.log.append(("login", user, password))

    def send_message(self, msg, to_addrs=None):
        if FakeSmtp.raise_on == "refused":
            raise smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"no")})
        if FakeSmtp.raise_on == "boom":
            raise RuntimeError("server exploded with password s3cret-pw inside")
        FakeSmtp.log.append(("send", msg, list(to_addrs)))


class FakeSmtpSsl(FakeSmtp):
    pass


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSmtp.log, FakeSmtp.raise_on = [], None
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtpSsl)
    return FakeSmtp


class TestSmtpConfig:
    def test_unconfigured_by_default(self):
        assert email_sender.EMAIL.configured() is False

    def test_needs_host_and_a_sender(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "h")
        assert email_sender.EMAIL.configured() is False
        monkeypatch.setenv("SMTP_FROM", "StockMonitor <me@x.com>")
        assert email_sender.EMAIL.configured() is True

    def test_sender_defaults_to_user(self, monkeypatch):
        configure_smtp(monkeypatch)
        assert email_sender.EMAIL._cfg()["sender"] == "me@example.com"

    def test_security_defaults_follow_the_port(self, monkeypatch):
        configure_smtp(monkeypatch)
        assert email_sender.EMAIL._cfg()["security"] == "starttls" and email_sender.EMAIL._cfg()["port"] == 587
        monkeypatch.setenv("SMTP_PORT", "465")
        assert email_sender.EMAIL._cfg()["security"] == "ssl"
        monkeypatch.setenv("SMTP_PORT", "garbage")
        assert email_sender.EMAIL._cfg()["port"] == 587


class TestSmtpSend:
    def test_unconfigured_send_fails_politely(self):
        r = email_sender.EMAIL.send(["a@x.com"], "s", "t")
        assert r["ok"] is False and "not configured" in r["error"]

    def test_starttls_login_and_attachment(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        r = email_sender.EMAIL.send(["a@x.com", "b@y.com"], "Subject", "plain body", "<b>html</b>",
                                    (("t.pdf", b"%PDF-1.4 fake", "application/pdf"),))
        assert r == {"ok": True, "error": None}
        kinds = [e[0] for e in fake_smtp.log]
        assert kinds == ["connect", "starttls", "login", "send"]
        assert fake_smtp.log[0][1:] == ("FakeSmtp", "smtp.example.com", 587)
        assert fake_smtp.log[2][1:] == ("me@example.com", "s3cret-pw")
        _, msg, to_addrs = fake_smtp.log[3]
        assert to_addrs == ["a@x.com", "b@y.com"] and msg["To"] == "a@x.com, b@y.com" and msg["From"] == "me@example.com"
        parts = list(msg.iter_attachments())
        assert len(parts) == 1 and parts[0].get_filename() == "t.pdf" and parts[0].get_content() == b"%PDF-1.4 fake"
        assert msg.get_body(("plain",)).get_content().strip() == "plain body"
        assert "<b>html</b>" in msg.get_body(("html",)).get_content()

    def test_port_465_uses_implicit_tls_without_starttls(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch, SMTP_PORT="465")
        assert email_sender.EMAIL.send(["a@x.com"], "s", "t")["ok"] is True
        assert fake_smtp.log[0][1] == "FakeSmtpSsl" and "starttls" not in [e[0] for e in fake_smtp.log]

    def test_no_login_without_a_user(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch, SMTP_USER="", SMTP_FROM="relay@example.com", SMTP_SECURITY="none")
        assert email_sender.EMAIL.send(["a@x.com"], "s", "t")["ok"] is True
        assert [e[0] for e in fake_smtp.log] == ["connect", "send"]

    def test_newlines_in_the_subject_cannot_inject_headers(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        email_sender.EMAIL.send(["a@x.com"], "Hello\r\nBcc: evil@x.com", "t")
        msg = fake_smtp.log[-1][1]
        assert msg["Bcc"] is None and "\n" not in msg["Subject"]

    def test_auth_failure_is_friendly_and_leaks_nothing(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        fake_smtp.raise_on = "auth"
        r = email_sender.EMAIL.send(["a@x.com"], "s", "t")
        assert r["ok"] is False and "app password" in r["error"] and "s3cret-pw" not in r["error"]

    def test_refused_recipient(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        fake_smtp.raise_on = "refused"
        assert "rejected the recipient" in email_sender.EMAIL.send(["a@x.com"], "s", "t")["error"]

    def test_connection_failure_names_host_and_port(self, monkeypatch):
        configure_smtp(monkeypatch)

        def refuse(*a, **k):
            raise socket.gaierror("no such host")
        monkeypatch.setattr(smtplib, "SMTP", refuse)
        err = email_sender.EMAIL.send(["a@x.com"], "s", "t")["error"]
        assert "smtp.example.com:587" in err

    def test_unexpected_errors_have_the_password_redacted(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        fake_smtp.raise_on = "boom"
        err = email_sender.EMAIL.send(["a@x.com"], "s", "t")["error"]
        assert "RuntimeError" in err and "s3cret-pw" not in err and "***" in err

    def test_success_counts_toward_the_rate_limit_failure_does_not(self, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        email_sender.EMAIL.send(["a@x.com"], "s", "t")
        assert len(email_sender._send_times) == 1
        fake_smtp.raise_on = "boom"
        email_sender.EMAIL.send(["a@x.com"], "s", "t")
        assert len(email_sender._send_times) == 1


# ── Endpoints ─────────────────────────────────────────────────────────────────

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


class TestStatusAndPdfEndpoint:
    def test_status_reports_configuration(self, client, monkeypatch):
        assert client.get("/api/tear-sheet-share/status").json() == {"emailConfigured": False, "maxRecipients": 10}
        configure_smtp(monkeypatch)
        assert client.get("/api/tear-sheet-share/status").json()["emailConfigured"] is True

    def test_status_never_exposes_credentials(self, client, monkeypatch):
        configure_smtp(monkeypatch)
        body = client.get("/api/tear-sheet-share/status").text
        assert "s3cret-pw" not in body and "smtp.example.com" not in body and "me@example.com" not in body

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


class TestEmailEndpoint:
    def post(self, client, to="friend@example.com", note="", symbol="ACME"):
        return client.post(f"/api/tear-sheet/{symbol}/email", json={"to": to, "note": note})

    def test_not_configured_is_503_and_sends_nothing(self, client):
        r = self.post(client)
        assert r.status_code == 503 and "SMTP_HOST" in r.json()["detail"]

    def test_sends_pdf_to_each_recipient(self, client, monkeypatch, fake_smtp, sheet):
        configure_smtp(monkeypatch)
        r = self.post(client, to="a@x.com, b@y.org", note="Thoughts?")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "sent": ["a@x.com", "b@y.org"], "filename": f"ACME_TearSheet_{sheet['asOf']}.pdf"}
        _, msg, to_addrs = fake_smtp.log[-1]
        assert to_addrs == ["a@x.com", "b@y.org"]
        assert sheet["valuation"]["verdict"]["label"] in msg["Subject"] and "ACME" in msg["Subject"]
        pdf = next(msg.iter_attachments())
        assert pdf.get_content_type() == "application/pdf" and pdf.get_content().startswith(b"%PDF-")
        assert "Thoughts?" in msg.get_body(("plain",)).get_content()

    def test_accepts_a_list_of_recipients(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        assert self.post(client, to=["a@x.com", "b@y.org"]).json()["sent"] == ["a@x.com", "b@y.org"]

    def test_invalid_address_is_400_and_nothing_is_built_or_sent(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        r = self.post(client, to="good@x.com, not-an-email")
        assert r.status_code == 400 and "not-an-email" in r.json()["detail"]
        assert fake_smtp.log == []

    def test_no_recipients_is_400(self, client, monkeypatch):
        configure_smtp(monkeypatch)
        assert self.post(client, to="  ").status_code == 400

    def test_too_many_recipients_is_400(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        many = ",".join(f"u{i}@x.com" for i in range(email_sender.MAX_RECIPIENTS + 1))
        r = self.post(client, to=many)
        assert r.status_code == 400 and "At most" in r.json()["detail"] and fake_smtp.log == []

    def test_allowlist_blocks_other_addresses(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch, EMAIL_ALLOWED_RECIPIENTS="@family.org")
        assert self.post(client, to="mom@family.org").status_code == 200
        r = self.post(client, to="stranger@evil.com")
        assert r.status_code == 403 and "stranger@evil.com" in r.json()["detail"]

    def test_hourly_limit_is_429(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        import time
        email_sender._send_times[:] = [time.time()] * email_sender.MAX_SENDS_PER_HOUR
        r = self.post(client)
        assert r.status_code == 429 and fake_smtp.log == []

    def test_smtp_failure_is_502_with_the_friendly_reason(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        fake_smtp.raise_on = "auth"
        r = self.post(client)
        assert r.status_code == 502 and "app password" in r.json()["detail"] and "s3cret-pw" not in r.text

    def test_unknown_ticker_is_404(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        assert self.post(client, symbol="ZZZZ").status_code == 404 and fake_smtp.log == []

    def test_note_is_length_limited(self, client, monkeypatch):
        configure_smtp(monkeypatch)
        assert self.post(client, note="x" * 1001).status_code == 422

    def test_note_html_is_escaped_in_the_html_part(self, client, monkeypatch, fake_smtp):
        configure_smtp(monkeypatch)
        self.post(client, note="<script>alert(1)</script> & more")
        html = fake_smtp.log[-1][1].get_body(("html",)).get_content()
        assert "<script>" not in html and "&lt;script&gt;" in html


class TestComposeEmail:
    def test_summary_includes_verdict_fair_value_and_flags(self, sheet):
        subject, text, html = share.compose_email(sheet)
        v = sheet["valuation"]["verdict"]
        assert subject == f"ACME tear sheet: {v['label']} (as of {sheet['asOf']})"
        assert "Acme Corp (ACME)" in text and v["label"] in text and "attached as a PDF" in text
        assert "not investment advice" in text and "<b>" in html
        # direction matters: premium > 0 means the PRICE is above fair value, not the reverse
        word = "above" if v["premium"] >= 0 else "below"
        assert f"the price is {abs(v['premium']) * 100:.0f}% {word} fair value" in text
        assert f"the price is {abs(v['premium']) * 100:.0f}% {word} fair value" in html

    def test_discount_reads_as_below_fair_value(self, sheet):
        sheet["valuation"]["verdict"].update({"premium": -0.23, "fairValue": 130.0, "low": 120.0, "high": 140.0, "label": "Undervalued"})
        assert "the price is 23% below fair value" in share.compose_email(sheet)[1]

    def test_no_verdict_still_composes(self):
        sheet = make_sheet(income=None, earn_est=None, targets=None, edgar=None)
        subject, text, _ = share.compose_email(sheet)
        assert "Not enough data to judge" in subject and "Blended fair value" not in text

    def test_note_leads_the_message(self, sheet):
        _, text, _ = share.compose_email(sheet, "  Look at this one  ")
        assert text.startswith("Look at this one")

    def test_filename(self, sheet):
        assert share.pdf_filename(sheet) == f"ACME_TearSheet_{sheet['asOf']}.pdf"
