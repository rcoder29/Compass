"""
Tests for the Tear Sheet peer comparison: metric cleaning, peer selection, per-metric statistics and ranks, the premium/quality read,
peer-implied prices, sector rules, the data layer, the endpoint and the PDF block. No network.
Run: python -m pytest tests/test_peer_valuation.py -v
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import hundred_bagger_data as scanner
import peer_data as data
import peer_valuation as pv
import routers.tear_sheet_peers as router_mod
import tear_sheet_pdf as tp


def rec(symbol, **over):
    d = {"symbol": symbol, "name": f"{symbol} Inc", "sector": "Technology", "industry": "Software", "industryKey": "software", "sectorKey": "technology",
         "quoteType": "EQUITY", "price": 100.0, "marketCap": 10e9, "trailingPE": 30.0, "forwardPE": 25.0, "evToEbitda": 20.0, "priceToSales": 6.0, "priceToBook": 8.0,
         "fcfYield": 0.03, "revenueGrowth": 0.15, "operatingMargin": 0.20, "roe": 0.18, "ebitda": 500e6, "netDebt": 1e9}
    d.update(over)
    return d


def peers(n=8):
    """Peers whose multiples rise with the index and whose fundamentals fall: peer 0 is cheapest and strongest."""
    return [rec(f"P{i}", forwardPE=15 + i * 2, trailingPE=20 + i * 2, evToEbitda=12 + i * 2, priceToSales=3 + i, priceToBook=4 + i, fcfYield=0.06 - i * 0.005,
                revenueGrowth=0.30 - i * 0.03, operatingMargin=0.30 - i * 0.02, roe=0.30 - i * 0.02, marketCap=(5 + i) * 1e9) for i in range(n)]


class TestMetricValue:
    @pytest.mark.parametrize("v,ok", [(25.0, True), (0, False), (-5.0, False), (150.0, True), (151.0, False), (None, False), ("x", False), (float("nan"), False)])
    def test_multiples_must_be_positive_and_sane(self, v, ok):
        assert (pv.metric_value({"forwardPE": v}, "forwardPE", (0, 150)) is not None) is ok

    def test_yields_and_margins_may_be_zero_or_negative(self):
        assert pv.metric_value({"operatingMargin": -0.4}, "operatingMargin", (-2, 1), True) == -0.4
        assert pv.metric_value({"operatingMargin": 0}, "operatingMargin", (-2, 1), True) == 0
        assert pv.metric_value({"operatingMargin": -3}, "operatingMargin", (-2, 1), True) is None
        assert pv.metric_value({"fcfYield": -0.02}, "fcfYield", (-0.5, 0.5), True) == -0.02

    def test_percentile(self):
        vals = list(range(1, 101))
        assert pv.percentile_of(vals, 25) == pytest.approx(25.75, abs=0.5) and pv.percentile_of(vals, 75) == pytest.approx(75.25, abs=0.5)
        assert pv.percentile_of([7.0], 25) == 7.0


class TestChoosePeers:
    def c(self, sym, cap): return {"symbol": sym, "marketCap": cap}

    def test_nearest_in_size_first_and_limited(self):
        got = pv.choose_peers(10e9, [self.c(f"S{i}", (i + 1) * 1e9) for i in range(20)], limit=5)
        assert [g["symbol"] for g in got] == ["S9", "S10", "S8", "S11", "S7"]       # closeness is by ratio: 11B is nearer 10B than 9B is

    def test_excludes_wildly_different_sizes_when_enough_remain(self):
        cands = [self.c(f"N{i}", 8e9 + i * 1e9) for i in range(6)] + [self.c("GIANT", 5e12), self.c("MID", 400e6)]
        assert {g["symbol"] for g in pv.choose_peers(10e9, cands)} == {f"N{i}" for i in range(6)}

    def test_widens_the_size_band_step_by_step_instead_of_dropping_the_filter(self):
        # KO-like: three near-sized peers, three at a fiftieth to a tenth of its size, and junk far outside any band
        cands = [self.c("A", 170e9), self.c("B", 85e9), self.c("C", 43e9), self.c("D", 13e9), self.c("E", 7e9), self.c("F", 6.5e9), self.c("JUNK", 3e6)]
        got = {g["symbol"] for g in pv.choose_peers(300e9, cands)}
        assert got == {"A", "B", "C", "D", "E", "F"} and "JUNK" not in got

    def test_micro_caps_are_never_peers_of_a_large_company(self):
        got = pv.choose_peers(50e9, [self.c("A", 40e9), self.c("B", 60e9), self.c("MICRO", 100e6)])
        assert {g["symbol"] for g in got} == {"A", "B"}

    def test_a_tiny_subject_can_have_tiny_peers(self):
        got = pv.choose_peers(200e6, [self.c(f"T{i}", (80 + i * 10) * 1e6) for i in range(8)])
        assert len(got) == 8

    def test_thin_industry_returns_what_fits_the_widest_band(self):
        got = pv.choose_peers(10e9, [self.c("A", 9e9), self.c("B", 11e9), self.c("GIANT", 5e12), self.c("TINY", 1e6)])
        assert {g["symbol"] for g in got} == {"A", "B"}

    def test_a_narrower_band_list_is_respected(self):
        cands = [self.c("A", 170e9), self.c("B", 85e9), self.c("C", 43e9), self.c("D", 13e9), self.c("E", 7e9), self.c("F", 6.5e9)]
        assert len(pv.choose_peers(300e9, cands)) == 6                                      # the loose bands reach them...
        assert [g["symbol"] for g in pv.choose_peers(300e9, cands, bands=pv.SIZE_BANDS[:1])] == ["A", "B", "C"]       # ...the tight band stops at 30B

    def test_no_subject_cap_takes_the_largest(self):
        assert [g["symbol"] for g in pv.choose_peers(None, [self.c("a", 1e9), self.c("b", 3e9), self.c("c", 2e9)], limit=2)] == ["b", "c"]

    def test_ignores_candidates_without_a_cap(self):
        assert pv.choose_peers(10e9, [{"symbol": "x"}, self.c("y", 9e9)]) == [self.c("y", 9e9)]


class TestCompare:
    def test_too_few_peers(self):
        assert pv.compare(rec("X"), peers(3)) is None

    def test_cheap_and_strong_stock(self):
        subject = rec("X", forwardPE=16, trailingPE=21, evToEbitda=13, priceToSales=3.5, priceToBook=4.5, fcfYield=0.058, revenueGrowth=0.29, operatingMargin=0.29, roe=0.29)
        r = pv.compare(subject, peers())
        assert r["expensiveRank"] <= 20 and r["qualityRank"] >= 80 and r["verdict"]["key"] == "discount_strong" and r["verdict"]["tone"] == "good"
        fwd = next(m for m in r["metrics"] if m["key"] == "forwardPE")
        assert fwd["median"] == pytest.approx(22.0) and fwd["premium"] == pytest.approx(16 / 22 - 1) and fwd["expensiveness"] == 12.5 and fwd["cheaperThan"] == 7
        assert r["medianPremium"] < 0 and r["premiumCount"] == 5

    def test_expensive_and_weak_stock(self):
        subject = rec("X", forwardPE=60, trailingPE=70, evToEbitda=40, priceToSales=20, priceToBook=25, fcfYield=0.001, revenueGrowth=0.0, operatingMargin=0.05, roe=0.02)
        r = pv.compare(subject, peers())
        assert r["expensiveRank"] == 100 and r["qualityRank"] <= 15 and r["verdict"]["key"] == "premium_unearned" and r["verdict"]["tone"] == "bad"
        assert r["medianPremium"] > 1.0

    def test_premium_with_strong_fundamentals_looks_earned(self):
        subject = rec("X", forwardPE=60, trailingPE=70, evToEbitda=40, priceToSales=20, priceToBook=25, fcfYield=0.001, revenueGrowth=0.50, operatingMargin=0.40, roe=0.50)
        assert pv.compare(subject, peers())["verdict"]["key"] == "premium_earned"

    def test_fcf_yield_counts_the_other_way(self):
        high_yield = pv.compare(rec("X", fcfYield=0.10), peers())
        low_yield = pv.compare(rec("X", fcfYield=0.0), peers())
        get = lambda r: next(m for m in r["metrics"] if m["key"] == "fcfYield")
        assert get(high_yield)["expensiveness"] == 0 and get(low_yield)["expensiveness"] == 100 and get(high_yield)["premium"] is None

    def test_metrics_without_enough_peer_data_are_left_out_of_the_rank(self):
        ps = peers()
        for p in ps[:6]:
            p["priceToBook"] = None
        r = pv.compare(rec("X"), ps)
        pb = next(m for m in r["metrics"] if m["key"] == "priceToBook")
        assert pb["median"] is None and pb["expensiveness"] is None and pb["peers"] == 2

    def test_negative_multiples_do_not_count(self):
        r = pv.compare(rec("X", forwardPE=-10, trailingPE=None), peers())
        assert next(m for m in r["metrics"] if m["key"] == "forwardPE")["value"] is None

    def test_banks_skip_ev_fcf_and_sales_and_reits_skip_earnings_multiples(self):
        bank = {m["key"] for m in pv.compare(rec("X", sector="Financial Services"), peers())["metrics"]}
        assert not {"evToEbitda", "fcfYield", "priceToSales"} & bank and {"forwardPE", "priceToBook"} <= bank
        reit = {m["key"] for m in pv.compare(rec("X", sector="Real Estate"), peers())["metrics"]}
        assert not {"trailingPE", "forwardPE", "fcfYield"} & reit and "evToEbitda" in reit

    def test_unknown_when_fewer_than_two_multiples_rank(self):
        ps = [rec(f"P{i}", forwardPE=None, trailingPE=None, evToEbitda=None, priceToSales=None, priceToBook=None, fcfYield=None) for i in range(5)]
        r = pv.compare(rec("X"), ps)
        assert r["expensiveRank"] is None and r["verdict"]["key"] == "unknown" and r["medianPremium"] is None

    @pytest.mark.parametrize("e,q,key", [(80, 80, "premium_earned"), (80, 50, "premium_unexplained"), (80, 20, "premium_unearned"), (80, None, "premium_unexplained"),
                                         (50, 80, "inline_strong"), (50, 50, "inline"), (50, 20, "inline_weak"), (20, 80, "discount_strong"), (20, 50, "discount"),
                                         (20, 20, "discount_deserved"), (20, None, "discount"), (65, 60, "premium_earned"), (35, 40, "discount_deserved"), (None, 50, "unknown")])
    def test_read_matrix(self, e, q, key):
        assert pv.read_verdict(e, q)["key"] == key


class TestImpliedPrice:
    def test_price_scales_with_the_multiple_and_ev_goes_through_net_debt(self):
        subject = rec("X", price=100.0, forwardPE=20, trailingPE=24, priceToSales=5, priceToBook=6, evToEbitda=15, marketCap=10e9, ebitda=1e9, netDebt=2e9)
        ps = [rec(f"P{i}", forwardPE=30, trailingPE=30, priceToSales=10, priceToBook=9, evToEbitda=20, fcfYield=0.03) for i in range(5)]
        r = pv.compare(subject, ps)
        by = {m["key"]: m["impliedPrice"] for m in r["metrics"] if m["impliedPrice"]}
        assert by["forwardPE"]["mid"] == pytest.approx(150.0) and by["priceToSales"]["mid"] == pytest.approx(200.0)
        assert "priceToBook" not in by                                                           # book value says little about a software company's price
        assert by["evToEbitda"]["mid"] == pytest.approx(100 * (20 * 1e9 - 2e9) / 10e9)           # EV = 20x EBITDA; less net debt; per share
        assert r["peerImplied"]["mid"] == pytest.approx(165.0) and r["peerImplied"]["vsPrice"] == pytest.approx(0.65)      # median of 125, 150, 180, 200 and "fcfYield" not in r["peerImplied"]["metrics"]

    def test_price_to_book_counts_for_banks_and_reits(self):
        subject = rec("X", sector="Financial Services", price=50.0, priceToBook=1.0, forwardPE=None, trailingPE=None)
        ps = [rec(f"P{i}", priceToBook=1.5, forwardPE=None, trailingPE=None) for i in range(5)]
        by = {m["key"]: m["impliedPrice"] for m in pv.compare(subject, ps)["metrics"] if m["impliedPrice"]}
        assert by["priceToBook"]["mid"] == pytest.approx(75.0)

    def test_flags_an_implied_price_far_from_the_market(self):
        near = pv.compare(rec("X"), peers())["peerImplied"]
        assert near["farFromPrice"] is False
        far = pv.compare(rec("X", forwardPE=2, trailingPE=3, priceToSales=0.5, evToEbitda=2), peers())["peerImplied"]
        assert far["farFromPrice"] is True and far["mid"] / far["price"] > 3

    def test_range_orders_low_mid_high(self):
        r = pv.compare(rec("X"), peers())
        imp = r["peerImplied"]
        assert imp["low"] <= imp["mid"] <= imp["high"] and imp["price"] == 100.0

    def test_no_implied_price_without_inputs(self):
        subject = rec("X", price=None)
        assert pv.compare(subject, peers())["peerImplied"] is None
        no_ebitda = pv.compare(rec("X", ebitda=None, forwardPE=None, trailingPE=None, priceToSales=None, priceToBook=None), peers())
        assert no_ebitda["peerImplied"] is None

    def test_negative_implied_values_are_dropped(self):
        subject = rec("X", ebitda=1e8, netDebt=50e9)                                           # debt far above any peer-multiple enterprise value
        r = pv.compare(subject, peers())
        assert "evToEbitda" not in r["peerImplied"]["metrics"]


class TestScatterAndText:
    def test_scatter_uses_growth_and_the_first_available_multiple(self):
        sc = pv.compare(rec("X"), peers())["scatter"]
        assert sc["yKey"] == "forwardPE" and sc["xLabel"] == "Revenue growth" and sum(1 for p in sc["points"] if p["isSubject"]) == 1 and len(sc["points"]) == 9

    def test_scatter_falls_back_when_the_first_multiple_is_missing(self):
        ps = [{**p, "forwardPE": None} for p in peers()]
        assert pv.compare(rec("X", forwardPE=None), ps)["scatter"]["yKey"] == "trailingPE"

    def test_scatter_needs_five_points(self):
        assert pv.scatter(rec("X"), peers(3)) is None

    def test_headline(self):
        r = pv.compare(rec("X", forwardPE=16, trailingPE=21, evToEbitda=13, priceToSales=3.5, priceToBook=4.5), peers())
        h = pv.headline("X", r)
        assert "discount to the peer median" in h and "At peer-median multiples" in h
        r2 = pv.compare(rec("X", forwardPE=60, trailingPE=70, evToEbitda=40, priceToSales=20, priceToBook=25), peers())
        assert "premium to the peer median" in pv.headline("X", r2)
        assert "not enough comparable multiples" in pv.headline("X", {"medianPremium": None})
        assert "based on only 2 multiples" in pv.headline("X", {"medianPremium": 0.5, "premiumCount": 2, "peerImplied": None})
        assert "median across 3 multiples" in pv.headline("X", {"medianPremium": 0.5, "premiumCount": 3, "peerImplied": None})

    def test_peer_row_and_json(self):
        row = pv.peer_row(rec("P1"))
        assert row["symbol"] == "P1" and row["forwardPE"] == 25.0 and "sector" not in row
        json.dumps(pv.compare(rec("X"), peers()))


class TestData:
    def test_record_from_info(self):
        r = data.record_from_info("ACME", {"shortName": "Acme", "marketCap": 2e9, "freeCashflow": 1e8, "totalDebt": 5e8, "totalCash": 2e8, "forwardPE": 18, "enterpriseToEbitda": 11,
                                           "operatingMargins": 0.2, "industryKey": "foo", "sector": "Technology", "currentPrice": 40})
        assert r["fcfYield"] == pytest.approx(0.05) and r["netDebt"] == 3e8 and r["evToEbitda"] == 11 and r["industryKey"] == "foo" and r["price"] == 40
        assert data.record_from_info("X", {"marketCap": None}) is None
        assert data.record_from_info("X", {"marketCap": 1e9})["fcfYield"] is None

    def test_fetch_caches_marks_empty_and_never_caches_failures(self, monkeypatch):
        class T:
            def __init__(self, s): self.s = s
            @property
            def info(self):
                if self.s == "BOOM":
                    raise RuntimeError("Too Many Requests. Rate limited.")
                return {} if self.s == "EMPTY" else {"shortName": "Ok", "marketCap": 1e9, "forwardPE": 12}
        monkeypatch.setattr(data.yf, "Ticker", T)
        monkeypatch.setattr(data.yahoo_limits, "_pause_until", 0.0)
        monkeypatch.setattr(data.yahoo_limits, "BACKOFF", (0, 0, 0))
        ok = data.fetch_peer("OK")
        assert ok["forwardPE"] == 12 and data.fetch_peer("OK") == ok
        assert data.fetch_peer("EMPTY") is None and data.cached_records(["EMPTY"]) == ({}, [])
        assert data.fetch_peer("BOOM") is None and data.cached_records(["BOOM"]) == ({}, ["BOOM"])
        have, missing = data.cached_records(["OK", "EMPTY", "NEW"])
        assert list(have) == ["OK"] and missing == ["NEW"]

    def test_company_lists_are_cached_and_failures_are_empty(self, monkeypatch):
        import pandas as pd
        calls = []

        class Ind:
            def __init__(self, key): calls.append(key)
            top_companies = pd.DataFrame({"name": ["a", "b"]}, index=["AAA", "BBB"])
        monkeypatch.setattr(data.yf, "Industry", Ind)
        assert data.company_list("industry", "k") == ["AAA", "BBB"] and data.company_list("industry", "k") == ["AAA", "BBB"] and calls == ["k"]

        class Bad:
            def __init__(self, key): raise RuntimeError("nope")
        monkeypatch.setattr(data.yf, "Sector", Bad)
        assert data.company_list("sector", "s") == []

    def test_candidates_prefer_the_industry_then_the_sector(self, monkeypatch):
        lists = {("industry", "ind"): ["X", "A", "B", "C", "D", "E"], ("sector", "sec"): ["X", "S1", "S2"], ("industry", "thin"): ["X", "A"]}
        monkeypatch.setattr(data, "company_list", lambda kind, key: lists.get((kind, key), []))
        assert data.candidate_symbols({"symbol": "X", "industryKey": "ind", "industry": "Ind", "sectorKey": "sec"}) == (["A", "B", "C", "D", "E"], "industry", "Ind")
        assert data.candidate_symbols({"symbol": "X", "industryKey": "thin", "sectorKey": "sec", "sector": "Sec"}) == (["S1", "S2"], "sector", "Sec")
        assert data.candidate_symbols({"symbol": "X"}) == ([], "none", "")


class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch):
        subject = rec("X", forwardPE=16, trailingPE=21, evToEbitda=13, priceToSales=3.5, priceToBook=4.5, revenueGrowth=0.29)
        pool = {p["symbol"]: p for p in peers(10)}
        state = {"loaded": False, "cooling": False, "scans": []}
        monkeypatch.setattr(data, "fetch_peer", lambda s: subject if s == "X" else pool.get(s))
        monkeypatch.setattr(data, "candidate_symbols", lambda subj: (list(pool), "industry", "Software"))
        monkeypatch.setattr(data, "cached_records", lambda syms: (dict(pool), []) if state["loaded"] else ({}, list(syms)))
        monkeypatch.setattr(scanner, "start_scan", lambda k, syms, fetch=None: (state["scans"].append((k, len(syms))), {"done": 3, "error": None, "running": True})[1])
        monkeypatch.setattr(scanner, "cooling_down", lambda k: state["cooling"])
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        app = FastAPI(); app.include_router(router_mod.router)
        c = TestClient(app); c.state, c.store, c.pool = state, store, pool
        return c

    def test_progress_then_ready(self, client):
        j = client.get("/api/tear-sheet/x/peers").json()
        assert j["status"] == "running" and j["progress"] == {"done": 3, "total": 10} and client.state["scans"] == [("peers:industry:Software", 10)]
        client.state["loaded"] = True
        j = client.get("/api/tear-sheet/X/peers").json()
        assert j["status"] == "ready" and j["symbol"] == "X" and j["peerCount"] == 10
        assert j["verdict"]["key"] in {"discount_strong", "discount"} and j["peers"][0]["marketCap"] >= j["peers"][-1]["marketCap"] and j["subject"]["symbol"] == "X"
        assert "Software" in j["note"] and "headline" in j and j["partial"] is None and "peers:built:X" in client.store
        json.dumps(j)

    def test_second_request_is_served_from_cache(self, client, monkeypatch):
        client.state["loaded"] = True
        client.get("/api/tear-sheet/X/peers")
        monkeypatch.setattr(data, "fetch_peer", lambda s: pytest.fail("cached"))
        assert client.get("/api/tear-sheet/X/peers").json()["status"] == "ready"

    def test_partial_when_cooling_down_is_not_cached(self, client, monkeypatch):
        client.state["cooling"] = True
        six = {p["symbol"]: p for p in peers(6)}
        monkeypatch.setattr(data, "cached_records", lambda syms: (dict(six), ["P8", "P9"]))
        j = client.get("/api/tear-sheet/X/peers").json()
        assert j["status"] == "ready" and j["partial"]["missing"] == 2 and "peers:built:X" not in client.store and j["peerCount"] == 6
        assert client.state["scans"] == []                                                  # no new scan while cooling down

    def test_unavailable_cases(self, client, monkeypatch):
        monkeypatch.setattr(data, "fetch_peer", lambda s: None)
        assert client.get("/api/tear-sheet/ZZZ/peers").json()["status"] == "unavailable"
        monkeypatch.setattr(data, "fetch_peer", lambda s: rec(s, quoteType="ETF"))
        assert "funds" in client.get("/api/tear-sheet/SPY/peers").json()["reason"]
        monkeypatch.setattr(data, "fetch_peer", lambda s: rec(s))
        monkeypatch.setattr(data, "candidate_symbols", lambda subj: ([], "none", ""))
        assert "doesn't list comparable" in client.get("/api/tear-sheet/X/peers").json()["reason"]

    def test_sector_fallback_uses_only_the_tight_size_band(self, client, monkeypatch):
        client.state["loaded"] = True
        monkeypatch.setattr(data, "candidate_symbols", lambda subj: (list(client.pool), "sector", "Industrials"))
        giants = {f"G{i}": rec(f"G{i}", marketCap=(500 + i) * 1e9) for i in range(8)}        # 50x the subject's 10B: fine for an industry, not for a sector
        monkeypatch.setattr(data, "cached_records", lambda syms: (giants, []))
        j = client.get("/api/tear-sheet/X/peers").json()
        assert j["status"] == "unavailable" and "No similarly sized companies" in j["reason"] and "Industrials" in j["reason"]

    def test_a_failed_lookup_is_reported_as_temporary_not_as_missing_data(self, client, monkeypatch):
        monkeypatch.setattr(data, "fetch_peer", lambda s: None)
        monkeypatch.setattr(data, "cached_records", lambda syms: ({}, list(syms)))             # no marker cached: the fetch failed
        j = client.get("/api/tear-sheet/AAPL/peers").json()
        assert j["status"] == "unavailable" and j["transient"] is True and "limiting requests" in j["reason"]
        monkeypatch.setattr(data, "cached_records", lambda syms: ({}, []))                       # a cached "nothing there" marker: genuinely no data
        j = client.get("/api/tear-sheet/ZZZ/peers").json()
        assert j["status"] == "unavailable" and "transient" not in j and "No market data was found" in j["reason"]

    def test_too_few_usable_peers_is_unavailable(self, client, monkeypatch):
        client.state["loaded"] = True
        monkeypatch.setattr(data, "cached_records", lambda syms: ({"P0": rec("P0"), "P1": rec("P1")}, []))
        j = client.get("/api/tear-sheet/X/peers").json()
        assert j["status"] == "unavailable" and "Only 2" in j["reason"]

    def test_bad_symbol_and_cached_helper(self, client):
        assert client.get("/api/tear-sheet/BAD$SYM/peers").status_code in (400, 404)
        assert router_mod.cached_peers("X") is None
        client.state["loaded"] = True
        client.get("/api/tear-sheet/X/peers")
        assert router_mod.cached_peers("X")["symbol"] == "X"


class TestPdf:
    def sheet_with(self, peers_payload):
        from tests.test_tear_sheet_share import make_sheet
        return {**make_sheet(), "peers": peers_payload}

    def payload(self):
        r = pv.compare(rec("ACME", forwardPE=16, trailingPE=21, evToEbitda=13, priceToSales=3.5, priceToBook=4.5), peers())
        return {"status": "ready", "symbol": "ACME", "scope": "industry", "scopeLabel": "Software", "peerCount": 8, "headline": pv.headline("ACME", r), **r,
                "peers": [pv.peer_row(p) for p in peers()], "note": "Peers are the companies closest in size within Yahoo's industry 'Software'."}

    def test_block_is_drawn_when_peers_are_present(self):
        payload = self.payload()
        pdf = tp.build_pdf(self.sheet_with(payload), compress=False)
        assert b"Versus peers" in pdf and payload["verdict"]["label"].encode() in pdf and b"Peer median" in pdf and b"At peer-median multiples" in pdf

    def test_far_from_price_warning_is_printed(self):
        payload = self.payload()
        payload["peerImplied"] = {**payload["peerImplied"], "farFromPrice": True}
        assert b"like-for-like" in tp.build_pdf(self.sheet_with(payload), compress=False)
        assert b"like-for-like" not in tp.build_pdf(self.sheet_with(self.payload()), compress=False)

    def test_absent_or_unavailable_peers_draw_nothing(self):
        from tests.test_tear_sheet_share import make_sheet
        assert b"Versus peers" not in tp.build_pdf(make_sheet(), compress=False)
        assert b"Versus peers" not in tp.build_pdf(self.sheet_with({"status": "unavailable", "reason": "x"}), compress=False)
        assert b"Versus peers" not in tp.build_pdf(self.sheet_with(None), compress=False)
