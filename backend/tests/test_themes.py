"""
Tests for the thematic-investing section: catalog integrity, analyst-upside and risk rules, the candidate score,
basket maths (returns, equal-weight series, drawdown), scenarios, and the endpoints. No network.
Run: python -m pytest tests/test_themes.py -v
"""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import holdings_perf
import hundred_bagger_data as hd
import routers.themes as router_mod
import themes as th
import themes_catalog as cat


def metrics(symbol="XYZ", **over):
    m = {"symbol": symbol, "name": symbol, "price": 100.0, "marketCap": 20e9, "revenue": 1e9, "revenueGrowth": 0.25, "revenueCagr": 0.25, "revenueCagrYears": 3,
         "roe": 0.2, "grossMargin": 0.6, "operatingMargin": 0.15, "marginChange": 0.02, "debtToEquity": 0.2, "freeCashFlow": 1e8, "totalCash": 5e8, "totalDebt": 1e8,
         "insiders": 0.05, "forwardPE": 30.0, "trailingPE": 40.0, "priceToSales": 5.0, "targetMean": 125.0, "targetHigh": 160.0, "targetLow": 90.0,
         "analystCount": 20, "recommendation": 1.8, "week52High": 120.0, "week52Low": 60.0, "profitableYears": 4, "statementYears": 4}
    m.update(over)
    return m


def entry(symbol="XYZ", **over):
    e = {"symbol": symbol, "name": f"{symbol} Inc", "layer": "silicon", "role": "core", "exposure": 3, "why": "reason"}
    e.update(over)
    return e


RET = {"1D": 0.01, "1W": 0.02, "1M": 0.05, "3M": 0.20, "6M": 0.40, "YTD": 0.5, "1Y": 0.8, "3Y": 2.0, "5Y": 5.0}
BENCH = {"1D": 0.0, "1W": 0.01, "1M": 0.02, "3M": 0.05, "6M": 0.08, "YTD": 0.1, "1Y": 0.15, "3Y": 0.4, "5Y": 0.9}


class TestCatalog:
    def test_four_launch_themes_with_complete_content(self):
        assert [t["id"] for t in cat.THEMES] == ["ai", "robotics", "quantum", "space"]
        for t in cat.THEMES:
            assert t["name"] and t["tagline"] and t["thesis"] and t["whyNow"] and t["watch"] and t["navId"] and t["color"].startswith("#")
            for block in (t["shortTerm"], t["longTerm"]):
                assert len(block["risks"]) >= 2 and len(next(v for k, v in block.items() if k != "risks")) >= 2

    def test_every_stock_is_well_formed_and_unique_within_its_theme(self):
        for t in cat.THEMES:
            layers = {l["id"] for l in t["layers"]}
            syms = [s["symbol"] for s in t["stocks"]]
            assert len(syms) == len(set(syms)) and len(syms) >= 12, t["id"]
            for s in t["stocks"]:
                assert s["role"] in cat.ROLES and s["layer"] in layers and s["exposure"] in (1, 2, 3) and s["why"] and s["name"], s
            assert {"core", "enabler", "emerging"} <= {s["role"] for s in t["stocks"]}, f"{t['id']} should show leaders, suppliers and speculative names"
            assert all(layer in {s["layer"] for s in t["stocks"]} for layer in layers), f"{t['id']} has an empty value-chain layer"
            assert t["etfs"] and all(len(e) == 2 for e in t["etfs"])

    def test_catalog_makes_no_numeric_forecasts(self):
        import re
        text = json.dumps(cat.THEMES)
        assert not re.search(r"\$\d+\s?(billion|trillion|bn|tn|B|T)\b|\d+%\s*(CAGR|a year|per year)", text), "no market-size or growth numbers in editorial text"

    def test_symbol_lists(self):
        allsyms = cat.all_symbols()
        assert len(allsyms) == len(set(allsyms)) and "SPY" in allsyms and "NVDA" in allsyms and "BOTZ" in allsyms
        assert "BOTZ" not in cat.stock_symbols() and "NVDA" in cat.stock_symbols() and len(cat.stock_symbols()) == len(set(cat.stock_symbols()))

    def test_json_serialisable(self):
        json.dumps(cat.THEMES)


class TestUpsideAndRisk:
    def test_upside(self):
        u = th.upside(metrics())
        assert u["mean"] == pytest.approx(0.25) and u["high"] == pytest.approx(0.60) and u["low"] == pytest.approx(-0.10) and u["rating"] == "Buy" and u["count"] == 20

    @pytest.mark.parametrize("over", [{"analystCount": 2}, {"targetMean": None}, {"price": None}, {"price": 0}])
    def test_upside_needs_enough_analysts_and_prices(self, over):
        assert th.upside(metrics(**over)) is None
    def test_upside_of_nothing(self):
        assert th.upside(None) is None

    @pytest.mark.parametrize("mean,label", [(1.2, "Strong buy"), (2.0, "Buy"), (3.0, "Hold"), (4.2, "Underperform"), (None, None)])
    def test_recommendation_labels(self, mean, label):
        assert th.recommendation_label(mean) == label

    @pytest.mark.parametrize("over,level", [
        ({"marketCap": 500e9}, "Lower"), ({"marketCap": 20e9}, "Moderate"), ({"marketCap": 5e9}, "High"), ({"marketCap": 1e9}, "Very high"),
        ({"marketCap": 30e9, "operatingMargin": -0.1}, "High"), ({"marketCap": 5e9, "operatingMargin": -0.2, "freeCashFlow": -1e8}, "Very high"),
    ])
    def test_risk_level(self, over, level):
        assert th.risk_level(metrics(**over)) == level
        assert th.risk_level(None) == "Very high" and th.risk_level({"marketCap": None}) == "Very high"

    def test_size_labels(self):
        assert [th.size_label(x) for x in (6e11, 2e10, 3e9, 5e8, None)] == ["Large cap", "Mid cap", "Small cap", "Micro cap", "Unknown"]


class TestCandidateScore:
    def test_strong_name_scores_well_and_points_add_up(self):
        r = th.score_candidate(entry(), metrics(), RET, BENCH)
        assert r["score"] >= 68 and r["label"] == "Stronger setup"
        assert sum(f["points"] for f in r["factors"].values()) == pytest.approx(r["rawScore"], abs=0.3)
        assert set(r["factors"]) == set(th.WEIGHTS) and sum(th.WEIGHTS.values()) == 100

    def test_weak_name_scores_low(self):
        weak = metrics(revenueGrowth=-0.1, revenueCagr=-0.05, targetMean=70.0, operatingMargin=-0.3, freeCashFlow=-1e8, forwardPE=None, trailingPE=None, priceToSales=None)
        r = th.score_candidate(entry(exposure=1), weak, {"3M": -0.3, "6M": -0.5}, BENCH)
        assert r["score"] < 45 and r["label"] == "Weaker setup"

    def test_risk_haircut_and_label_caps(self):
        base = th.score_candidate(entry(), metrics(), RET, BENCH)
        assert base["riskMultiplier"] == 1.0 and base["rawScore"] == base["score"] and base["capReason"] is None
        small = th.score_candidate(entry(), metrics(marketCap=1e9), RET, BENCH)         # micro cap -> very high risk
        assert small["risk"] == "Very high" and small["riskMultiplier"] == 0.85 and small["score"] == pytest.approx(small["rawScore"] * 0.85, abs=0.1)
        assert small["label"] != "Stronger setup" and small["rawScore"] > 68 and "very high risk" in small["capReason"]
        high = th.score_candidate(entry(), metrics(marketCap=5e9), RET, BENCH)
        assert high["risk"] == "High" and high["riskMultiplier"] == 0.93
        crushed = th.score_candidate(entry(), metrics(), {**RET, "1Y": -0.55}, BENCH)
        assert crushed["label"] == "Mixed" and "down 55%" in crushed["capReason"]
        assert th.score_candidate(entry(), metrics(), {**RET, "1Y": -0.2}, BENCH)["label"] == "Stronger setup"

    def test_missing_inputs_are_marked_and_scored_conservatively(self):
        r = th.score_candidate(entry(), None, None, BENCH)
        for k in ("momentum", "analysts", "growth", "strength", "valuation"):
            assert r["factors"][k]["missing"] and r["factors"][k]["score"] == 30.0
        assert not r["factors"]["exposure"]["missing"]

    def test_exposure_matters(self):
        hi = th.score_candidate(entry(exposure=3), metrics(), RET, BENCH)["score"]
        lo = th.score_candidate(entry(exposure=1), metrics(), RET, BENCH)["score"]
        assert hi - lo == pytest.approx(0.2 * (100 - 35), abs=0.2)

    def test_momentum_is_relative_to_the_benchmark(self):
        flat_market = th.score_candidate(entry(), metrics(), {"3M": 0.1, "6M": 0.1}, {"3M": 0.1, "6M": 0.1})["factors"]["momentum"]["score"]
        lagging = th.score_candidate(entry(), metrics(), {"3M": 0.1, "6M": 0.1}, {"3M": 0.3, "6M": 0.3})["factors"]["momentum"]["score"]
        assert flat_market > lagging

    def test_analyst_factor_needs_three_analysts(self):
        assert th.score_candidate(entry(), metrics(analystCount=2), RET, BENCH)["factors"]["analysts"]["missing"]

    def test_labels(self):
        assert [th.setup_label(x) for x in (80, 68, 55, 52, 10)] == ["Stronger setup", "Stronger setup", "Mixed", "Mixed", "Weaker setup"]


class TestMemberView:
    def test_assembles_everything(self):
        v = th.member_view(entry("AAA"), metrics("AAA"), {"returns": RET, "annualised": {"3Y": 0.4, "5Y": 0.45}, "price": 101.0}, BENCH)
        assert v["available"] and v["price"] == 101.0 and v["size"] == "Mid cap" and v["risk"] == "Moderate"
        assert v["returns"]["3M"] == 0.20 and v["excess"]["3M"] == pytest.approx(0.15) and v["annualised"]["5Y"] == 0.45
        assert v["upside"]["mean"] == pytest.approx(0.25) and v["profitable"] is True and v["off52wHigh"] == pytest.approx(100 / 120 - 1)
        assert v["bagger"]["score"] > 0 and v["setup"]["score"] > 0 and not any(f.startswith("Already") for f in v["flags"])
        json.dumps(v)

    def test_unavailable_name(self):
        v = th.member_view(entry("GONE"), None, None, BENCH)
        assert not v["available"] and v["upside"] is None and v["bagger"] is None and v["profitable"] is None and v["risk"] == "Very high"
        assert v["excess"] == {"3M": None, "6M": None, "1Y": None}

    def test_prices_only_when_fundamentals_missing(self):
        v = th.member_view(entry(), None, {"returns": RET, "annualised": {}, "price": 5.0}, BENCH)
        assert v["available"] and v["price"] == 5.0 and v["returns"]["YTD"] == 0.5 and v["growth"] is None


def prices(n=400, drifts=None):
    idx = pd.bdate_range(end="2026-10-09", periods=n)
    drifts = drifts or {}
    out = {}
    for i, s in enumerate(["A", "B", "C", "D", "SPY"]):
        out[s] = pd.Series(100 * np.cumprod(np.full(n, 1 + drifts.get(s, 0.0005 * (i + 1)))), index=idx)
    return out


class TestBasket:
    def test_returns_average_the_members_with_data(self):
        views = [{"returns": {"3M": 0.1, "1Y": 0.5}}, {"returns": {"3M": 0.3, "1Y": None}}, {"returns": {"3M": -0.1, "1Y": 0.1}}]
        for v in views:
            v["returns"] = {p: v["returns"].get(p) for p in th.PERIODS}
        b = th.basket_returns(views)
        assert b["3M"]["mean"] == pytest.approx(0.1) and b["3M"]["median"] == 0.1 and b["3M"]["n"] == 3 and b["3M"]["positive"] == pytest.approx(2 / 3)
        assert b["1Y"]["n"] == 2 and b["1Y"]["mean"] == pytest.approx(0.3)
        assert b["5Y"]["mean"] is None and b["5Y"]["n"] == 0

    def test_series_is_rebased_with_drawdown_and_volatility(self):
        d = prices()
        s = th.basket_series(d, ["A", "B", "C", "D"])
        assert s["points"][0][1] == pytest.approx(100, abs=2) and s["points"][-1][1] > s["points"][0][1]
        assert s["points"][0][2] == pytest.approx(100, abs=2) and s["maxDrawdown"] == pytest.approx(0, abs=1e-6) and s["members"] == 4
        # a crash in one name shows up in the basket drawdown and volatility
        d2 = prices()
        d2["B"] = d2["B"].copy(); d2["B"].iloc[200:] *= 0.5
        s2 = th.basket_series(d2, ["A", "B", "C", "D"])
        assert s2["maxDrawdown"] < -0.05 and s2["volatility"] > s["volatility"]

    def test_series_needs_enough_names_and_a_benchmark(self):
        assert th.basket_series(prices(), ["A", "B"]) is None
        d = prices(); del d["SPY"]
        assert th.basket_series(d, ["A", "B", "C"]) is None

    def test_late_listing_does_not_break_the_series(self):
        d = prices()
        d["D"] = d["D"].iloc[250:]
        s = th.basket_series(d, ["A", "B", "C", "D"])
        assert s["members"] == 4 and len(s["points"]) > 40

    def test_scenarios_are_plain_compounding(self):
        sc = th.scenarios(10000)
        row = next(r for r in sc["rows"] if r["rate"] == 0.15)
        assert row["values"]["10"] == round(10000 * 1.15 ** 10) and row["values"]["1"] == 11500 and sc["years"] == [1, 3, 5, 10]


class TestOutlook:
    def views(self):
        return [th.member_view(entry(s), metrics(s, marketCap=cap, targetMean=tm, recommendation=rec), {"returns": RET, "annualised": {"3Y": 0.3, "5Y": 0.4}, "price": 100}, BENCH)
                for s, cap, tm, rec in [("A", 100e9, 130.0, 1.8), ("B", 10e9, 110.0, 2.0), ("C", 1e9, 80.0, 3.0)]]

    def test_aggregates(self):
        vs = self.views()
        o = th.outlook(vs, th.basket_returns(vs))
        assert o["analystUpsideMedian"] == pytest.approx(0.10) and o["analystNames"] == 3 and o["buyShare"] == pytest.approx(2 / 3)
        expected = (100 * 0.30 + 10 * 0.10 + 1 * -0.20) / 111
        assert o["analystUpsideCapWeighted"] == pytest.approx(expected)
        assert o["growthMedian"] == pytest.approx(0.25) and o["profitableShare"] == 1.0 and o["forwardPEMedian"] == 30.0

    def test_empty(self):
        o = th.outlook([], th.basket_returns([]))
        assert o["analystUpsideMedian"] is None and o["buyShare"] is None and o["analystNames"] == 0


class TestBuildTheme:
    def test_full_theme_and_summary(self):
        theme = cat.BY_ID["quantum"]
        ms = {s["symbol"]: metrics(s["symbol"]) for s in theme["stocks"][:10]}
        rows = {s["symbol"]: {"returns": RET, "annualised": {"3Y": 0.3, "5Y": 0.3}, "price": 10} for s in theme["stocks"][:10]}
        built = th.build_theme(theme, ms, rows, BENCH, None, {"QTUM": {"returns": RET, "price": 50}})
        assert built["id"] == "quantum" and len(built["members"]) == len(theme["stocks"])
        assert len(built["unavailable"]) == len(theme["stocks"]) - 10 and built["basket"]["3M"]["n"] == 10
        assert built["basket"]["3Y"]["annualised"] == pytest.approx(0.3) and built["etfs"][0]["symbol"] == "QTUM" and built["etfs"][0]["returns"]["1Y"] == 0.8
        assert built["top"] and len(built["top"]) == 5 and built["leaders3M"] and sum(built["roleCounts"].values()) == len(theme["stocks"])
        s = th.theme_summary(built)
        assert s["members"] == 10 and s["returns"]["3M"] == pytest.approx(0.2) and len(s["top"]) == 3 and "name" in s["top"][0]
        json.dumps(built)


# ── endpoints ─────────────────────────────────────────────────────────────────

class TestEndpoints:
    @pytest.fixture
    def client(self, monkeypatch):
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        syms = cat.all_symbols()
        d = {s: pd.Series(100 * np.cumprod(np.full(300, 1.0005)), index=pd.bdate_range(end="2026-10-09", periods=300)) for s in syms}
        monkeypatch.setattr(holdings_perf, "download_daily", lambda ss: {s: d[s] for s in ss if s in d})
        monkeypatch.setattr(holdings_perf, "load_anchors", lambda ss: {})
        monkeypatch.setattr(holdings_perf, "compute_returns", lambda daily, anchors: None if daily is None else {
            "returns": {p: 0.1 for p in holdings_perf.PERIODS}, "annualised": {}, "price": float(daily.iloc[-1]), "asOf": "2026-10-09"})
        state = {"missing": True}
        allm = {s: metrics(s) for s in cat.stock_symbols()}
        monkeypatch.setattr(hd, "cached_metrics", lambda ss: ([], list(ss)) if state["missing"] else (list(allm.values()), []))
        monkeypatch.setattr(hd, "start_scan", lambda k, ss: {"done": 5, "error": None, "running": True})
        monkeypatch.setattr(hd, "cooling_down", lambda k: False)
        app = FastAPI(); app.include_router(router_mod.router)
        c = TestClient(app); c.state = state; c.store = store
        return c

    def test_scan_progress_then_ready(self, client):
        j = client.get("/api/themes").json()
        assert j["status"] == "running" and j["progress"]["total"] == len(cat.stock_symbols()) and j["progress"]["done"] == 5
        client.state["missing"] = False
        j = client.get("/api/themes").json()
        assert j["status"] == "ready" and [t["id"] for t in j["themes"]] == ["ai", "robotics", "quantum", "space"]
        assert j["themes"][0]["returns"]["3M"] == pytest.approx(0.1) and j["partial"] is None and j["editorialDate"]
        json.dumps(j)

    def test_theme_detail(self, client):
        client.state["missing"] = False
        j = client.get("/api/themes/robotics").json()
        t = j["theme"]
        assert t["id"] == "robotics" and len(t["members"]) == len(cat.BY_ID["robotics"]["stocks"]) and {o["id"] for o in j["others"]} == {"ai", "quantum", "space"}
        assert t["members"][0]["upside"]["mean"] == pytest.approx(0.25) and t["series"]["points"] and t["scenarios"]["rows"]
        assert t["etfs"][0]["returns"]["3M"] == pytest.approx(0.1)

    def test_unknown_theme_404(self, client):
        assert client.get("/api/themes/nope").status_code == 404

    def test_result_is_cached(self, client, monkeypatch):
        client.state["missing"] = False
        client.get("/api/themes")
        monkeypatch.setattr(holdings_perf, "download_daily", lambda ss: pytest.fail("should be cached"))
        assert client.get("/api/themes/ai").json()["status"] == "ready"

    def test_partial_results_when_yahoo_refuses_fundamentals(self, client, monkeypatch):
        monkeypatch.setattr(hd, "cooling_down", lambda k: True)
        monkeypatch.setattr(hd, "retry_in", lambda k: 90)
        j = client.get("/api/themes/ai").json()
        assert j["status"] == "ready" and j["partial"]["retryInSeconds"] == 90 and "Prices and performance are complete" in j["partial"]["note"]
        assert j["theme"]["members"][0]["upside"] is None and j["theme"]["members"][0]["returns"]["3M"] == pytest.approx(0.1)
        assert "themes:built" not in client.store                              # a partial result is never cached

    def test_price_failure_is_502(self, client, monkeypatch):
        client.state["missing"] = False
        monkeypatch.setattr(holdings_perf, "download_daily", lambda ss: {})
        r = client.get("/api/themes")
        assert r.status_code == 502 and "rate-limiting" in r.json()["detail"]
