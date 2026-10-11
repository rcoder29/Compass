"""
Tests for the 100-bagger screen: the 100x arithmetic, metric extraction from Yahoo-shaped data, each factor's
thresholds, caps and flags, ranking, universe parsing, caching, the background scan and the endpoints. No network.
Run: python -m pytest tests/test_hundred_bagger.py -v
"""
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import hundred_bagger as hb
import hundred_bagger_data as hd
import yahoo_limits
import routers.hundred_baggers as router_mod


def good(**over):
    """A textbook candidate: small, fast-growing, high returns, owner-run, no debt, sensibly priced."""
    m = {"symbol": "GOOD", "name": "Good Co", "sector": "Technology", "marketCap": 1.5e9, "revenue": 4e8, "revenueGrowth": 0.30,
         "revenueCagr": 0.30, "revenueCagrYears": 4, "roe": 0.30, "grossMargin": 0.65, "operatingMargin": 0.25, "marginChange": 0.05,
         "debtToEquity": 0.0, "freeCashFlow": 5e7, "totalCash": 1e8, "totalDebt": 0, "insiders": 0.25, "forwardPE": 25, "trailingPE": 30,
         "priceToSales": 4, "profitableYears": 4, "statementYears": 4}
    m.update(over)
    return m


class TestArithmetic:
    def test_required_cagr(self):
        assert hb.required_cagr(20) == pytest.approx(0.2589, abs=1e-3)
        assert hb.required_cagr(10) == pytest.approx(0.5849, abs=1e-3)
        assert hb.required_cagr(30) == pytest.approx(0.1659, abs=1e-3)

    def test_years_to_multiple_is_the_inverse(self):
        assert hb.years_to_multiple(hb.required_cagr(20)) == pytest.approx(20)
        assert hb.years_to_multiple(0.0) is None and hb.years_to_multiple(-0.1) is None and hb.years_to_multiple(None) is None
        assert hb.years_to_multiple(1.0, 2) == pytest.approx(1.0)

    def test_interp_clamps_and_interpolates(self):
        pts = [(0, 0), (10, 100)]
        assert hb.interp(-5, pts) == 0 and hb.interp(50, pts) == 100 and hb.interp(5, pts) == 50

    def test_cagr_from_series(self):
        c, y = hb.cagr_from_series([200.0, 150.0, 100.0])
        assert y == 2 and c == pytest.approx(2 ** 0.5 - 1)
        assert hb.cagr_from_series([100.0, 90.0]) == (None, 0)
        assert hb.cagr_from_series([100.0, None, -5.0, 70.0, 50.0]) == (pytest.approx(2 ** (1 / 4) - 1), 4)
        assert hb.cagr_from_series([100.0, None, -5.0, 50.0]) == (None, 0)                 # only two usable points
        assert hb.cagr_from_series([]) == (None, 0)


class TestMetrics:
    def info(self, **over):
        i = {"shortName": "Acme", "sector": "Industrials", "marketCap": 2e9, "totalRevenue": 5e8, "revenueGrowth": 0.2, "returnOnEquity": 0.2,
             "grossMargins": 0.5, "operatingMargins": 0.15, "debtToEquity": 45.0, "heldPercentInsiders": 0.12, "freeCashflow": 3e7,
             "trailingPE": 30, "forwardPE": 22, "priceToSalesTrailing12Months": 4, "totalCash": 5e7, "totalDebt": 4e7}
        i.update(over)
        return i

    def test_extracts_and_normalises(self):
        m = hb.metrics_from_yahoo("ACME", self.info(), [500, 400, 300, 200], [75, 50, 30, 10], [40, 30, 20, 5])
        assert m["revenueCagr"] == pytest.approx((500 / 200) ** (1 / 3) - 1) and m["revenueCagrYears"] == 3
        assert m["debtToEquity"] == pytest.approx(0.45)               # Yahoo reports percent
        assert m["marginChange"] == pytest.approx(0.15 - 0.05) and m["profitableYears"] == 4 and m["statementYears"] == 4
        assert m["name"] == "Acme"

    def test_carries_analyst_fields_for_the_themes_pages(self):
        m = hb.metrics_from_yahoo("ACME", self.info(targetMeanPrice=15.5, targetHighPrice=20, targetLowPrice=9, numberOfAnalystOpinions=12,
                                                    recommendationMean=1.8, fiftyTwoWeekHigh=14, fiftyTwoWeekLow=6, beta=1.4), [], [], [])
        assert (m["targetMean"], m["targetHigh"], m["targetLow"], m["analystCount"], m["recommendation"]) == (15.5, 20, 9, 12, 1.8)
        assert m["week52High"] == 14 and m["week52Low"] == 6 and m["beta"] == 1.4
        assert hb.metrics_from_yahoo("X", {}, [], [], [])["analystCount"] == 0

    def test_missing_and_nan_values_become_none(self):
        m = hb.metrics_from_yahoo("X", {"marketCap": float("nan"), "returnOnEquity": "n/a"}, [], [], [])
        assert m["marketCap"] is None and m["roe"] is None and m["revenueCagr"] is None and m["marginChange"] is None

    def test_falls_back_to_statement_margin_when_info_lacks_it(self):
        m = hb.metrics_from_yahoo("X", self.info(operatingMargins=None), [100, 90, 80], [20, 15, 10], [1, 1, 1])
        assert m["operatingMargin"] == pytest.approx(0.20)


class TestFactors:
    @pytest.mark.parametrize("cap,lo,hi", [(5e8, 99, 100), (1e9, 99, 100), (1e10, 55, 70), (3e10, 30, 45), (1e11, 5, 20), (2e11, 0, 0)])
    def test_size(self, cap, lo, hi):
        assert lo <= hb.score_size({"marketCap": cap})[0] <= hi

    def test_size_note_shows_the_100x_cap(self):
        assert hb.score_size({"marketCap": 1.5e9})[1] == "$1.5B market cap; 100x would be $150B"
        assert hb.money(4e12) == "$4.0T" and hb.money(2.5e10) == "$25B"
        assert hb.score_size({})[0] is None

    @pytest.mark.parametrize("g,lo,hi", [(-0.2, 0, 0), (0.0, 5, 10), (0.15, 60, 65), (0.35, 99, 100), (0.9, 99, 100)])
    def test_growth(self, g, lo, hi):
        assert lo <= hb.score_growth({"revenueGrowth": g})[0] <= hi

    def test_growth_blends_cagr_and_latest_and_clamps(self):
        assert hb.blended_growth({"revenueCagr": 0.10, "revenueGrowth": 0.30}) == pytest.approx(0.18)
        assert hb.blended_growth({"revenueCagr": 0.10}) == 0.10 and hb.blended_growth({"revenueGrowth": 0.2}) == 0.2
        assert hb.blended_growth({"revenueCagr": 3.0, "revenueGrowth": 2.0}) == hb.MAX_GROWTH
        assert hb.blended_growth({}) is None

    def test_returns_discounts_debt_fuelled_roe(self):
        clean = hb.score_returns({"roe": 0.30, "debtToEquity": 0.2})[0]
        levered = hb.score_returns({"roe": 0.30, "debtToEquity": 3.0})
        assert levered[0] == pytest.approx(clean * 0.7) and "heavy debt" in levered[1]
        assert hb.score_returns({"roe": -0.1})[0] == 0 and hb.score_returns({})[0] is None

    def test_margins_reward_widening_and_punish_narrowing(self):
        base = {"grossMargin": 0.5, "operatingMargin": 0.15}
        up, flat, down = (hb.score_margins({**base, "marginChange": c})[0] for c in (0.06, 0.0, -0.06))
        assert up == flat + 8 and down == flat - 8
        assert hb.score_margins({})[0] is None and hb.score_margins({"grossMargin": 0.7})[0] > 90

    def test_balance(self):
        assert hb.score_balance({"totalCash": 10, "totalDebt": 5, "debtToEquity": 0.5})[0] == 100       # net cash
        assert hb.score_balance({"debtToEquity": 1.0})[0] == 55 and hb.score_balance({"debtToEquity": 4.0})[0] == 0
        pos = hb.score_balance({"debtToEquity": 0.5, "freeCashFlow": 5})
        neg = hb.score_balance({"debtToEquity": 0.5, "freeCashFlow": -5})
        assert neg[0] == pytest.approx(pos[0] * 0.75) and "negative free cash flow" in neg[1]
        assert hb.score_balance({})[0] is None

    @pytest.mark.parametrize("ins,lo,hi", [(0.0, 10, 10), (0.05, 50, 50), (0.10, 75, 75), (0.5, 100, 100)])
    def test_owners(self, ins, lo, hi):
        assert lo <= hb.score_owners({"insiders": ins})[0] <= hi

    def test_valuation_uses_peg_then_pe_then_sales(self):
        cheap = hb.score_valuation({"forwardPE": 15, "revenueGrowth": 0.30})
        dear = hb.score_valuation({"forwardPE": 90, "revenueGrowth": 0.30})
        assert cheap[0] > 80 > 30 > dear[0] and "PEG" in cheap[1]
        assert "growth too low" in hb.score_valuation({"forwardPE": 20, "revenueGrowth": 0.0})[1]
        assert "No earnings" in hb.score_valuation({"priceToSales": 3, "revenueGrowth": 0.3})[1]
        assert hb.score_valuation({})[0] is None


class TestScore:
    def test_weights_sum_to_100_and_every_factor_has_a_scorer(self):
        assert sum(hb.WEIGHTS.values()) == 100 and set(hb.WEIGHTS) == set(hb.SCORERS) == set(hb.FACTOR_NAMES)

    def test_textbook_candidate_scores_high_and_points_add_up(self):
        r = hb.score(good())
        assert r["score"] >= 85 and r["tier"] == "Strong fit"
        assert sum(f["points"] for f in r["factors"].values()) == pytest.approx(r["score"], abs=0.2)

    def test_mega_cap_and_shrinking_company_score_low(self):
        bad = hb.score(good(marketCap=2e12, revenueGrowth=-0.05, revenueCagr=-0.02, insiders=0.001, roe=0.02, forwardPE=60))
        assert bad["score"] < 40 and bad["tier"] in ("Weak fit", "Partial fit")

    def test_missing_data_is_marked_and_scored_conservatively(self):
        r = hb.score({"marketCap": 1e9})
        assert r["factors"]["growth"]["missing"] and r["factors"]["growth"]["score"] == hb.MISSING_SCORE
        assert not r["factors"]["size"]["missing"]

    def test_never_profitable_is_capped(self):
        r = hb.score(good(profitableYears=0))
        assert r["score"] == hb.UNPROFITABLE_CAP and r["capped"] and r["tier"] == "Promising"
        assert not hb.score(good())["capped"]
        assert not hb.score(good(profitableYears=0, statementYears=2))["capped"]        # too little history to judge

    def test_tiers(self):
        assert [hb.tier(x) for x in (80, 70, 60, 45, 10)] == ["Strong fit", "Strong fit", "Promising", "Partial fit", "Weak fit"]


class TestTraitsAndFlags:
    def test_traits(self):
        t = {x["id"]: x["met"] for x in hb.traits(good())}
        assert all(t.values()) and len(t) == 7
        t2 = {x["id"]: x["met"] for x in hb.traits(good(marketCap=50e9, insiders=0.01, roe=0.05))}
        assert not t2["small"] and not t2["owners"] and not t2["returns"] and t2["growth"]

    def test_flags(self):
        assert hb.flags(good()) == []
        f = hb.flags(good(marketCap=60e9, revenueGrowth=-0.1, operatingMargin=-0.1, debtToEquity=3, freeCashFlow=-1, marginChange=-0.1,
                          profitableYears=0, revenueCagrYears=0))
        for text in ("Already $60B: 100x would need $6.0T", "Revenue shrinking", "Operating at a loss", "Heavily indebted", "Burning cash", "Margins narrowing", "Never profitable", "Short track record"):
            assert any(text in x for x in f), text


class TestResults:
    def test_ranking_exclusions_and_counts(self):
        ms = [good(symbol="A"), good(symbol="B", revenueGrowth=0.05, revenueCagr=0.05), good(symbol="HUGE", marketCap=500e9),
              {"symbol": "NOCAP", "marketCap": None}, {"symbol": "NODATA", "marketCap": 1e9}]
        r = hb.build_results(ms)
        assert [x["symbol"] for x in r["rows"]] == ["A", "B"] and [x["rank"] for x in r["rows"]] == [1, 2]
        assert r["counts"] == {"scored": 2, "tooBig": 1, "noData": 2} and sum(r["tierCounts"].values()) == 2
        assert len(r["timeline"]) == 5
        json.dumps(r)

    def test_row_math(self):
        row = hb.build_row(good())
        assert row["capAt100x"] == 1.5e11 and row["yearsTo100x"] == pytest.approx(hb.years_to_multiple(0.30), abs=0.05)
        assert row["traitsMet"] == 7 and row["growthUsed"] == pytest.approx(0.30)

    def test_max_cap_override(self):
        assert hb.build_results([good(marketCap=50e9)], max_cap=20e9)["counts"]["tooBig"] == 1
        assert hb.build_results([good(marketCap=50e9)])["counts"]["scored"] == 1


HTML = """<table id="constituents"><tr><th>Symbol</th><th>Security</th><th>GICS</th></tr>
<tr><td>BRK.B</td><td>Berkshire</td><td>Financials</td></tr><tr><td>AAA</td><td>Alpha Inc</td><td>Tech</td></tr><tr><td>X</td></tr></table>"""


class TestData:
    def test_parse_constituents(self):
        rows = hd.parse_constituents(HTML)
        assert [r["symbol"] for r in rows] == ["BRK-B", "AAA"] and rows[1]["sector"] == "Tech"
        with pytest.raises(ValueError):
            hd.parse_constituents("<html></html>")

    def test_clean_symbols(self):
        assert hd.clean_symbols(["aapl", " msft ", "AAPL", "bad sym", "", "x" * 20, "brk.b"]) == ["AAPL", "MSFT", "BRK-B"]
        assert len(hd.clean_symbols([f"S{i}" for i in range(1000)])) == hd.MAX_CUSTOM

    def test_fetch_metrics_builds_caches_and_marks_empty(self, monkeypatch):
        import pandas as pd
        calls = []

        class T:
            def __init__(self, s):
                self.s = s
                calls.append(s)

            @property
            def info(self):
                return {"marketCap": 2e9, "totalRevenue": 4e8, "shortName": "Z"} if self.s == "Z" else {}

            @property
            def income_stmt(self):
                idx = ["Total Revenue", "Operating Income", "Net Income"]
                return pd.DataFrame([[400.0, 300.0, 200.0], [60.0, 40.0, 20.0], [30.0, 20.0, 10.0]], index=idx, columns=[2025, 2024, 2023])
        monkeypatch.setattr(hd.yf, "Ticker", T)
        m = hd.fetch_metrics("Z")
        assert m["revenueCagrYears"] == 2 and m["profitableYears"] == 3
        assert hd.fetch_metrics("Z")["symbol"] == "Z" and calls.count("Z") == 1                 # cached
        assert hd.fetch_metrics("EMPTY") is None and hd.fetch_metrics("EMPTY") is None and calls.count("EMPTY") == 1   # negative-cached
        have, missing = hd.cached_metrics(["Z", "EMPTY", "NEW"])
        assert [h["symbol"] for h in have] == ["Z"] and missing == ["NEW"]

    def test_fetch_failure_is_not_cached(self, monkeypatch):
        class T:
            def __init__(self, s): pass
            @property
            def info(self): raise RuntimeError("rate limited")
        monkeypatch.setattr(hd.yf, "Ticker", T)
        assert hd.fetch_metrics("Q") is None
        assert hd.cached_metrics(["Q"]) == ([], ["Q"])

    def test_scan_runs_in_background_and_reports_progress(self, monkeypatch):
        seen = []
        monkeypatch.setattr(hd, "fetch_metrics", lambda s: seen.append(s) or None)
        monkeypatch.setattr(hd, "_jobs", {})
        job = hd.start_scan("k", ["A", "B", "C"])
        for _ in range(100):
            if not job["running"]:
                break
            time.sleep(0.02)
        assert sorted(seen) == ["A", "B", "C"] and job["done"] == 3 and not job["running"] and hd.progress("k") is job
        assert hd.start_scan("k", ["Z"]) is not job                               # finished job is replaced by a new one

    def test_running_scan_is_joined_not_duplicated(self, monkeypatch):
        import threading
        gate = threading.Event()
        monkeypatch.setattr(hd, "fetch_metrics", lambda s: gate.wait(2) and None)
        monkeypatch.setattr(hd, "_jobs", {})
        a = hd.start_scan("k", ["A"])
        assert hd.start_scan("k", ["A", "B"]) is a
        gate.set()


class TestRateLimiting:
    def test_detects_rate_limit_messages(self):
        assert yahoo_limits.is_rate_limit(RuntimeError("Too Many Requests. Rate limited. Try after a while."))
        assert yahoo_limits.is_rate_limit(RuntimeError("HTTP Error 429")) and not yahoo_limits.is_rate_limit(RuntimeError("KeyError: marketCap"))

    def test_rate_limit_pauses_workers_grows_the_pause_and_resets_on_success(self, monkeypatch):
        import pandas as pd
        monkeypatch.setattr(yahoo_limits, "_pause_until", 0.0)
        monkeypatch.setattr(yahoo_limits, "_strikes", 0)
        monkeypatch.setattr(yahoo_limits, "BACKOFF", (5, 10, 20))

        class Limited:
            def __init__(self, s): pass
            @property
            def info(self): raise RuntimeError("Too Many Requests. Rate limited.")
        monkeypatch.setattr(hd.yf, "Ticker", Limited)
        t0 = time.time()
        assert hd.fetch_metrics("A1") is None
        first = yahoo_limits._pause_until - t0
        assert 4 < first <= 6 and yahoo_limits._strikes == 1
        monkeypatch.setattr(yahoo_limits, "_pause_until", 0.0)                              # let the next call through without sleeping
        assert hd.fetch_metrics("A2") is None
        assert yahoo_limits._strikes == 2 and 9 < yahoo_limits._pause_until - time.time() <= 11     # pause doubles on consecutive hits
        assert hd.cached_metrics(["A1", "A2"]) == ([], ["A1", "A2"])             # failures are never cached
        monkeypatch.setattr(yahoo_limits, "_pause_until", 0.0)

        class Ok:
            def __init__(self, s): pass
            info = {"marketCap": 1e9, "totalRevenue": 1e8}
            income_stmt = pd.DataFrame()
        monkeypatch.setattr(hd.yf, "Ticker", Ok)
        assert hd.fetch_metrics("B1")["symbol"] == "B1" and yahoo_limits._strikes == 0     # success resets the back-off

    def test_cooldown_after_a_scan_with_failures(self, monkeypatch):
        monkeypatch.setattr(hd, "_jobs", {"k": {"running": False, "finished": time.time() - 10, "done": 1, "total": 2, "error": None}})
        assert hd.cooling_down("k") and 280 < hd.retry_in("k") <= 290
        monkeypatch.setattr(hd, "_jobs", {"k": {"running": False, "finished": time.time() - 400, "done": 1, "total": 2, "error": None}})
        assert not hd.cooling_down("k") and hd.retry_in("k") == 0
        assert not hd.cooling_down("none") and hd.retry_in("none") == 0


class TestEndpoints:
    @pytest.fixture
    def client(self, monkeypatch):
        members = [{"symbol": f"S{i}", "name": f"Stock {i}", "sector": "Tech"} for i in range(5)]
        monkeypatch.setattr(hd, "universe_members", lambda uid: members)
        store = {f"S{i}": good(symbol=f"S{i}", marketCap=1e9 * (i + 1)) for i in range(5)}
        state = {"ready": False}
        monkeypatch.setattr(hd, "cached_metrics", lambda syms: (([store[s] for s in syms if s in store], []) if state["ready"]
                                                                 else ([store[syms[0]]], list(syms[1:]))))
        monkeypatch.setattr(hd, "start_scan", lambda k, syms: {"done": 1, "error": None, "running": True})
        app = FastAPI(); app.include_router(router_mod.router)
        c = TestClient(app); c.state = state
        return c

    def test_universes(self, client):
        j = client.get("/api/hundred-baggers/universes").json()
        assert {u["id"] for u in j["universes"]} == {"SP600", "SP400"} and sum(j["weights"].values()) == 100 and len(j["timeline"]) == 5

    def test_running_then_ready(self, client):
        j = client.get("/api/hundred-baggers?universe=SP600").json()
        assert j["status"] == "running" and j["progress"] == {"done": 2, "total": 5}
        client.state["ready"] = True
        j = client.get("/api/hundred-baggers?universe=sp600").json()
        assert j["status"] == "ready" and len(j["rows"]) == 5 and j["rows"][0]["sector"] == "Tech" and j["universe"]["name"] == "S&P SmallCap 600"
        assert [r["rank"] for r in j["rows"]] == [1, 2, 3, 4, 5]

    def test_partial_results_during_cooldown_do_not_restart_the_scan(self, client, monkeypatch):
        started = []
        monkeypatch.setattr(hd, "start_scan", lambda k, syms: started.append(k) or {"done": 0, "error": None, "running": True})
        monkeypatch.setattr(hd, "cooling_down", lambda k: True)
        monkeypatch.setattr(hd, "retry_in", lambda k: 120)
        j = client.get("/api/hundred-baggers?universe=SP600").json()
        assert j["status"] == "ready" and j["partial"]["missing"] == 4 and j["partial"]["retryInSeconds"] == 120 and "Yahoo" in j["partial"]["note"]
        assert len(j["rows"]) == 1 and started == []
        client.state["ready"] = True
        assert client.get("/api/hundred-baggers?universe=SP600").json()["partial"] is None

    def test_custom_symbols(self, client):
        client.state["ready"] = True
        j = client.get("/api/hundred-baggers?symbols=s1,s2,bad sym").json()
        assert j["status"] == "ready" and j["universe"]["name"] == "Your tickers" and {r["symbol"] for r in j["rows"]} == {"S1", "S2"}

    def test_validation(self, client):
        assert client.get("/api/hundred-baggers?universe=NOPE").status_code == 404
        assert client.get("/api/hundred-baggers?symbols=!!!").status_code == 400

    def test_upstream_failure_is_502(self, client, monkeypatch):
        monkeypatch.setattr(hd, "universe_members", lambda uid: (_ for _ in ()).throw(RuntimeError("wiki down")))
        r = client.get("/api/hundred-baggers?universe=SP600")
        assert r.status_code == 502 and "wiki down" in r.json()["detail"]
