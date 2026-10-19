"""13F maths (thirteenf.py), filing discovery (thirteenf_data.py) and the Manager Holdings endpoints."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import managers_catalog as catalog
import thirteenf as tf
import thirteenf_data as tfd
from routers import manager_holdings as mh

NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"


def xml(*rows):
    body = ""
    for name, cusip, value, shares, unit, pc in rows:
        body += (f"<infoTable><nameOfIssuer>{name}</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>{cusip}</cusip><value>{value}</value>"
                 f"<shrsOrPrnAmt><sshPrnamt>{shares}</sshPrnamt><sshPrnamtType>{unit}</sshPrnamtType></shrsOrPrnAmt>"
                 + (f"<putCall>{pc}</putCall>" if pc else "") + "</infoTable>")
    return f'<informationTable xmlns="{NS}">{body}</informationTable>'


def agg(*rows):
    return tf.aggregate(tf.parse_infotable(xml(*rows), "2026-08-14"))


# ── parsing / aggregation ─────────────────────────────────────────────────────

class TestParse:
    def test_reads_rows(self):
        r = tf.parse_infotable(xml(("APPLE", "037833100", 1000, 10, "SH", None)), "2026-08-14")
        assert r[0]["cusip"] == "037833100" and r[0]["value"] == 1000 and r[0]["shares"] == 10

    def test_old_filings_report_thousands(self):
        r = tf.parse_infotable(xml(("APPLE", "037833100", 1000, 10, "SH", None)), "2022-11-14")
        assert r[0]["value"] == 1_000_000

    def test_boundary_date_is_dollars(self):
        assert tf.parse_infotable(xml(("A", "1", 5, 1, "SH", None)), "2023-01-03")[0]["value"] == 5
        assert tf.parse_infotable(xml(("A", "1", 5, 1, "SH", None)), "2023-01-02")[0]["value"] == 5000

    def test_prefixed_namespace(self):
        x = xml(("APPLE", "037833100", 1000, 10, "SH", None)).replace('xmlns="', 'xmlns:ns1="').replace("<", "<ns1:").replace("<ns1:/", "</ns1:")
        r = tf.parse_infotable(x, "2026-08-14")
        assert len(r) == 1 and r[0]["cusip"] == "037833100" and r[0]["value"] == 1000

    def test_filer_reporting_thousands_after_the_change_is_detected(self):
        rows = [("A", "1", 15455, 403100, "SH", None), ("B", "2", 23303, 2784110, "SH", None), ("C", "3", 40000, 1000000, "SH", None)]
        assert [r["value"] for r in tf.parse_infotable(xml(*rows), "2026-08-14")] == [15_455_000, 23_303_000, 40_000_000]

    def test_normal_dollar_values_are_left_alone(self):
        rows = [("A", "1", 15_455_000, 403100, "SH", None), ("B", "2", 3_000_000, 10_000, "SH", None), ("C", "3", 900, 10, "SH", None)]
        assert [r["value"] for r in tf.parse_infotable(xml(*rows), "2026-08-14")] == [15_455_000, 3_000_000, 900]

    def test_penny_stock_portfolio_needs_three_positions_to_trigger_the_check(self):
        assert tf.parse_infotable(xml(("A", "1", 50, 1000, "SH", None), ("B", "2", 60, 1000, "SH", None)), "2026-08-14")[0]["value"] == 50

    def test_without_namespace(self):
        plain = "<informationTable><infoTable><nameOfIssuer>X</nameOfIssuer><cusip>abc</cusip><value>7</value><shrsOrPrnAmt><sshPrnamt>3</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable></informationTable>"
        r = tf.parse_infotable(plain, "2026-01-01")
        assert r[0]["cusip"] == "ABC" and r[0]["shares"] == 3

    def test_garbage_numbers_become_zero(self):
        r = tf.parse_infotable(xml(("X", "1", "n/a", "", "SH", None)), "2026-01-01")
        assert r[0]["value"] == 0 and r[0]["shares"] == 0


class TestAggregate:
    def test_sums_sub_accounts_by_cusip(self):
        a = agg(("ALLY", "C1", 100, 10, "SH", None), ("ALLY", "C1", 50, 5, "SH", None), ("KO", "C2", 200, 20, "SH", None))
        assert a["positions"]["C1"]["value"] == 150 and a["positions"]["C1"]["shares"] == 15
        assert a["totalValue"] == 350

    def test_options_and_bonds_not_counted_as_shares(self):
        a = agg(("X", "C1", 100, 10, "SH", None), ("X", "C1", 40, 4, "SH", "Call"), ("B", "C3", 70, 70, "PRN", None))
        assert a["positions"]["C1"]["shares"] == 10 and "C3" not in a["positions"]
        assert a["optionsValue"] == 40 and a["bondsValue"] == 70 and a["totalValue"] == 100


class TestAmendments:
    def test_new_holdings_amendment_adds_positions(self):
        base, amd = agg(("A", "C1", 100, 10, "SH", None)), agg(("B", "C2", 50, 5, "SH", None))
        m = tf.merge_amendment(base, amd, "NEW HOLDINGS")
        assert set(m["positions"]) == {"C1", "C2"} and m["totalValue"] == 150

    def test_restatement_replaces(self):
        base, amd = agg(("A", "C1", 100, 10, "SH", None)), agg(("B", "C2", 50, 5, "SH", None))
        assert set(tf.merge_amendment(base, amd, "RESTATEMENT")["positions"]) == {"C2"}

    def test_does_not_mutate_base(self):
        base, amd = agg(("A", "C1", 100, 10, "SH", None)), agg(("A", "C1", 20, 2, "SH", None))
        tf.merge_amendment(base, amd, "NEW HOLDINGS")
        assert base["positions"]["C1"]["shares"] == 10


# ── comparing quarters ────────────────────────────────────────────────────────

class TestStatus:
    @pytest.mark.parametrize("sh,prev,exp", [(10, None, "new"), (10, 0, "new"), (15, 10, "added"), (5, 10, "reduced"), (10, 10, "unchanged"), (1004, 1000, "unchanged")])
    def test_status(self, sh, prev, exp):
        assert tf.status_of(sh, prev)[0] == exp

    def test_percent(self):
        assert tf.status_of(15, 10)[1] == pytest.approx(0.5)


class TestCompare:
    def setup_method(self):
        self.prev = agg(("A", "C1", 100, 10, "SH", None), ("B", "C2", 100, 10, "SH", None), ("GONE", "C9", 50, 5, "SH", None))
        self.cur = agg(("A", "C1", 300, 15, "SH", None), ("B", "C2", 100, 4, "SH", None), ("NEW", "C3", 100, 1, "SH", None))

    def test_ranking_weights_and_statuses(self):
        c = tf.compare(self.cur, self.prev)
        rows = {r["cusip"]: r for r in c["positions"]}
        assert [r["cusip"] for r in c["positions"]] == ["C1", "C2", "C3"]
        assert rows["C1"]["status"] == "added" and rows["C2"]["status"] == "reduced" and rows["C3"]["status"] == "new"
        assert rows["C1"]["weight"] == pytest.approx(0.6) and rows["C1"]["rank"] == 1
        assert rows["C1"]["shareChange"] == 5 and rows["C3"]["shareChange"] == 1

    def test_exited(self):
        c = tf.compare(self.cur, self.prev)
        assert [e["cusip"] for e in c["exited"]] == ["C9"] and c["exited"][0]["prevWeight"] == pytest.approx(50 / 250)

    def test_weights_sum_to_one(self):
        assert sum(r["weight"] for r in tf.compare(self.cur, self.prev)["positions"]) == pytest.approx(1.0)

    def test_without_previous_is_unknown(self):
        c = tf.compare(self.cur, None)
        assert {r["status"] for r in c["positions"]} == {"unknown"} and c["exited"] == []

    def test_history_aligns_to_periods(self):
        c = tf.compare(self.cur, self.prev, history=[self.prev, self.cur])
        assert {r["cusip"]: r["history"] for r in c["positions"]}["C1"] == [10, 15]
        assert {r["cusip"]: r["history"] for r in c["positions"]}["C3"] == [0, 1]

    def test_empty_current(self):
        c = tf.compare(tf.aggregate([]), self.prev)
        assert c["positions"] == [] and len(c["exited"]) == 3


class TestSummary:
    def test_counts_and_concentration(self):
        prev = agg(("A", "C1", 100, 10, "SH", None), ("G", "C9", 100, 5, "SH", None))
        cur = agg(("A", "C1", 300, 10, "SH", None), ("N", "C3", 100, 1, "SH", None))
        c = tf.compare(cur, prev)
        s = tf.summarize(c["positions"], c["exited"], cur, prev)
        assert s["counts"] == {"new": 1, "added": 0, "reduced": 0, "unchanged": 1, "exited": 1}
        assert s["top5"] == pytest.approx(1.0) and s["largestWeight"] == pytest.approx(0.75)
        assert s["valueChangePct"] == pytest.approx(1.0)

    def test_concentration_series(self):
        out = tf.concentration_series([{"period": "2026-03-31", "data": agg(("A", "C1", 100, 1, "SH", None), ("B", "C2", 100, 1, "SH", None))}])
        assert out[0]["positions"] == 2 and out[0]["top5"] == pytest.approx(1.0)


class TestReturns:
    def test_weighted_return_and_coverage(self):
        rows = [{"value": 300, "priceQE": 100, "priceNow": 110}, {"value": 100, "priceQE": 50, "priceNow": 40}, {"value": 100, "priceQE": None, "priceNow": 5}]
        r = tf.weighted_return(rows, "priceQE")
        assert r["return"] == pytest.approx((300 * 0.10 + 100 * -0.20) / 400) and r["coverage"] == pytest.approx(0.8)

    def test_none_when_no_prices(self):
        assert tf.weighted_return([{"value": 1, "priceQE": None, "priceNow": None}], "priceQE") is None

    @pytest.mark.parametrize("pe,exp", [("2026-06-30", "2026-11-14"), ("2026-09-30", "2027-02-14"), ("2026-12-31", "2027-05-15"), ("2026-03-31", "2026-08-14")])
    def test_next_deadline(self, pe, exp):
        assert tf.next_deadline(pe) == exp


# ── filing discovery ──────────────────────────────────────────────────────────

SUBS = {"filings": {"recent": {
    "form": ["13F-HR", "4", "13F-HR/A", "13F-HR", "13F-HR"], "accessionNumber": ["a2", "x", "a2b", "a1", "a0"],
    "filingDate": ["2026-08-14", "2026-08-01", "2026-09-30", "2026-05-15", "2026-02-17"],
    "reportDate": ["2026-06-30", "2026-07-30", "2026-06-30", "2026-03-31", "2025-12-31"]}}}


class TestFilings:
    def test_parse_keeps_only_13f(self):
        assert {f["accession"] for f in tfd.parse_submissions(SUBS)} == {"a2", "a2b", "a1", "a0"}

    def test_group_pairs_amendments_with_original(self):
        p = tfd.group_periods(tfd.parse_submissions(SUBS))
        assert [e["period"] for e in p] == ["2026-06-30", "2026-03-31", "2025-12-31"]
        assert p[0]["original"]["accession"] == "a2" and [a["accession"] for a in p[0]["amendments"]] == ["a2b"]

    def test_amendment_without_original_ignored(self):
        subs = {"filings": {"recent": {"form": ["13F-HR/A"], "accessionNumber": ["z"], "filingDate": ["2026-01-01"], "reportDate": ["2025-09-30"]}}}
        assert tfd.group_periods(tfd.parse_submissions(subs)) == []


class TestTicker:
    def test_prefers_us_listing(self):
        res = [{"ticker": "AAPL", "exchCode": "UA", "securityType": "Common Stock"}, {"ticker": "AAPL", "exchCode": "US", "securityType": "Common Stock"}]
        assert tfd.pick_ticker(res) == "AAPL"

    def test_skips_non_equity_then_falls_back(self):
        assert tfd.pick_ticker([{"ticker": "X", "exchCode": "US", "securityType": "Warrant"}]) == "X"
        assert tfd.pick_ticker([]) is None

    def test_override_used_without_network(self, monkeypatch):
        monkeypatch.setattr(tfd.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network for overrides")))
        assert tfd.tickers_for(["H1467J104"]) == {"H1467J104": "CB"}

    def test_lookup_failure_gives_none_and_is_not_cached(self, monkeypatch):
        monkeypatch.setattr(tfd.requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
        assert tfd.tickers_for(["ZZZ"]) == {"ZZZ": None}
        from datetime import timedelta
        from database import cache_get
        assert cache_get("figi:ZZZ", timedelta(days=1)) is None


class TestFigiClient:
    class Resp:
        def __init__(self, code, body=None): self.status_code, self._b = code, body or []
        def json(self): return self._b
        def raise_for_status(self):
            if self.status_code >= 400: raise RuntimeError(self.status_code)

    def test_retries_after_a_429_then_succeeds(self, monkeypatch):
        calls = iter([self.Resp(429), self.Resp(200, [{"data": [{"ticker": "AAA", "exchCode": "US", "securityType": "Common Stock"}]}])])
        monkeypatch.setattr(tfd.time, "sleep", lambda s: None)
        monkeypatch.setattr(tfd.requests, "post", lambda *a, **k: next(calls))
        assert tfd.tickers_for(["037833100"]) == {"037833100": "AAA"}

    def test_gives_up_after_repeated_429_and_caches_nothing(self, monkeypatch):
        monkeypatch.setattr(tfd.time, "sleep", lambda s: None)
        monkeypatch.setattr(tfd.requests, "post", lambda *a, **k: self.Resp(429))
        assert tfd.tickers_for(["037833100"]) == {"037833100": None}
        from datetime import timedelta
        from database import cache_get
        assert cache_get("figi:037833100", timedelta(days=1)) is None

    def test_foreign_cusip_falls_back_to_a_name_search(self, monkeypatch):
        monkeypatch.setattr(tfd.time, "sleep", lambda s: None)
        monkeypatch.setattr(tfd.requests, "post", lambda *a, **k: self.Resp(200, [{"warning": "No identifier found."}, {"warning": "No identifier found."}]))
        monkeypatch.setattr(tfd, "ticker_by_name", lambda n: "AON")
        assert tfd.tickers_for(["G0403H108", "037833100"], {"G0403H108": "AON PLC", "037833100": "APPLE"}) == {"G0403H108": "AON", "037833100": None}


class TestNameMatch:
    @pytest.mark.parametrize("a,b,ok", [("AON PLC", "Aon plc", True), ("AON PLC", "Aonic Corp", False), ("NORWEGIAN CRUISE LINE HLDGS", "Norwegian Cruise Line Holdings Ltd.", True),
                                        ("LINDE PLC", "Linde plc", True), ("LINDE PLC", "Lindt & Sprungli", False), ("", "Anything", False), ("HERBALIFE LTD", "Herbalife Ltd.", True), ("ARES ACQUISITION CORP III", "Ares Acquisition Corporation", False),
                                        ("ARES ACQUISITION CORP", "Ares Acquisition Corporation II", False), ("SMURFIT WESTROCK PLC", "Smurfit Westrock plc", True),
                                        ("NEBIUS GROUP N.V.", "Nebius Group N.V.", True), ("AXALTA COATING SYS LTD", "Axalta Coating Systems Ltd.", True)])
    def test_cautious(self, a, b, ok):
        assert tfd.name_matches(a, b) is ok


class TestPriceHelpers:
    def test_price_on_or_before_unwraps(self):
        s = pd.Series([10.0, 11.0, 12.0], index=pd.to_datetime(["2026-06-26", "2026-06-29", "2026-06-30"]))
        assert tfd.price_on_or_before(s, "2026-06-30") == 12.0 and tfd.price_on_or_before(s, "2026-06-28") == 10.0
        assert tfd.price_on_or_before(s, "2020-01-01") is None and tfd.price_on_or_before(None, "2026-06-30") is None

    def test_attach_prices(self):
        s = pd.Series([100.0, 110.0, 120.0], index=pd.to_datetime(["2026-06-30", "2026-08-14", "2026-10-16"]))
        rows = [{"ticker": "AAA"}, {"ticker": None}]
        tfd.attach_prices(rows, "2026-06-30", "2026-08-14", {"AAA": s})
        assert rows[0]["retSinceQE"] == pytest.approx(0.2) and rows[0]["retSinceFiled"] == pytest.approx(120 / 110 - 1)
        assert rows[1]["retSinceQE"] is None


# ── endpoints ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    from main import app
    # the disclosed-investor view looks up prices; keep it offline
    monkeypatch.setattr(tfd, "load_prices", lambda syms: {})
    return TestClient(app)


class TestCatalog:
    def test_ids_unique_and_complete(self):
        ids = [m["id"] for m in catalog.MANAGERS]
        assert len(ids) == len(set(ids)) and {"berkshire", "damodaran"} <= set(ids)

    def test_13f_managers_have_cik_and_disclosed_do_not(self):
        for m in catalog.MANAGERS:
            assert (m["kind"] == "13f") == bool(m["cik"])

    def test_seed_sources_exist_for_every_confidence_level_used(self):
        for mid, seeds in catalog.DISCLOSURE_SEEDS.items():
            have = {s["match"] for s in catalog.DISCLOSURE_SOURCES[mid]}
            assert {s["confidence"] for s in seeds} <= have

    def test_seeds_have_valid_actions_and_dates(self):
        import re
        for seeds in catalog.DISCLOSURE_SEEDS.values():
            for s in seeds:
                assert s["action"] in catalog.ACTIONS and (s["as_of"] is None or re.match(r"^\d{4}-\d{2}(-\d{2})?$", s["as_of"]))


class TestEndpoints:
    def test_unknown_manager(self, client):
        assert client.get("/api/managers/nobody").status_code == 404

    def test_list_survives_a_failing_filing_lookup(self, client, monkeypatch):
        monkeypatch.setattr(tfd, "filings_for", lambda cik: (_ for _ in ()).throw(RuntimeError("sec down")))
        out = client.get("/api/managers").json()["managers"]
        assert len(out) == len(catalog.MANAGERS) and next(m for m in out if m["id"] == "berkshire")["error"] is True

    def test_report_failure_is_502_and_not_cached(self, client, monkeypatch):
        monkeypatch.setattr(mh, "build_report", lambda m: (_ for _ in ()).throw(RuntimeError("boom")))
        assert client.get("/api/managers/berkshire").status_code == 502
        monkeypatch.setattr(mh, "build_report", lambda m: {"ok": True})
        assert client.get("/api/managers/berkshire").json() == {"ok": True}

    def test_full_report_from_stubbed_sec(self, client, monkeypatch):
        filings = [{"form": "13F-HR", "accession": "n", "filed": "2026-08-14", "period": "2026-06-30"}, {"form": "13F-HR", "accession": "o", "filed": "2026-05-15", "period": "2026-03-31"}]
        data = {"n": agg(("APPLE", "C1", 700, 7, "SH", None), ("NEW", "C2", 300, 3, "SH", None)), "o": agg(("APPLE", "C1", 500, 5, "SH", None), ("OLD", "C9", 100, 1, "SH", None))}
        monkeypatch.setattr(tfd, "filings_for", lambda cik: filings)
        monkeypatch.setattr(tfd, "fetch_aggregate", lambda cik, f: data[f["accession"]])
        monkeypatch.setattr(tfd, "tickers_for", lambda cs, names=None: {"C1": "AAPL", "C2": None, "C9": "OLD"})
        monkeypatch.setattr(tfd, "load_prices", lambda syms: {"AAPL": pd.Series([100.0, 110.0, 120.0], index=pd.to_datetime(["2026-06-30", "2026-08-14", "2026-10-16"])),
                                                              "SPY": pd.Series([10.0, 10.0, 11.0], index=pd.to_datetime(["2026-06-30", "2026-08-14", "2026-10-16"]))})
        d = client.get("/api/managers/berkshire").json()
        assert d["filing"]["period"] == "2026-06-30" and d["filing"]["nextExpected"] == "2026-11-14"
        assert [p["ticker"] for p in d["positions"]] == ["AAPL", None] and d["positions"][0]["status"] == "added"
        assert d["exited"][0]["ticker"] == "OLD" and d["summary"]["counts"]["new"] == 1
        assert d["performance"]["sinceQE"]["return"] == pytest.approx(0.2) and d["performance"]["sinceQE"]["coverage"] == pytest.approx(0.7)
        assert d["performance"]["benchmark"]["sinceQE"] == pytest.approx(0.1)
        assert [h["period"] for h in d["history"]["series"]] == ["2026-03-31", "2026-06-30"]


class TestDisclosures:
    def test_seeded_once_with_sources(self, client):
        d = client.get("/api/managers/damodaran").json()
        syms = {p["symbol"] for p in d["positions"]}
        assert {"AAPL", "TSLA", "NVDA"} <= syms and len(d["approach"]) == 1
        assert all(p["sourceUrl"] for p in d["positions"]) and d["approach"][0]["confidence"] == "secondary"

    def test_deleting_a_seed_stays_deleted(self, client):
        first = client.get("/api/managers/damodaran").json()["positions"][0]
        assert client.delete(f"/api/managers/damodaran/disclosures/{first['id']}").status_code == 200
        assert first["id"] not in {p["id"] for p in client.get("/api/managers/damodaran").json()["positions"]}

    def test_add_validates_and_stores(self, client):
        ok = client.post("/api/managers/damodaran/disclosures", json={"symbol": " brk-b ", "action": "bought", "asOf": "2026-02", "sourceUrl": "https://example.com/x"})
        assert ok.status_code == 200 and ok.json()["symbol"] == "BRK-B" and ok.json()["confidence"] == "user"
        assert "BRK-B" in {p["symbol"] for p in client.get("/api/managers/damodaran").json()["positions"]}

    @pytest.mark.parametrize("body", [{"symbol": "X", "action": "flipped"}, {"symbol": "X", "action": "owns", "asOf": "last year"},
                                      {"symbol": "X", "action": "owns", "sourceUrl": "javascript:alert(1)"}, {"action": "owns"}])
    def test_add_rejects_bad_input(self, client, body):
        assert client.post("/api/managers/damodaran/disclosures", json=body).status_code == 400

    def test_cannot_log_for_a_13f_manager(self, client):
        assert client.post("/api/managers/berkshire/disclosures", json={"symbol": "X", "action": "owns"}).status_code == 400

    def test_delete_missing_is_404(self, client):
        assert client.delete("/api/managers/damodaran/disclosures/99999").status_code == 404
