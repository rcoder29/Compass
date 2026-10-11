"""
Tests for the Sectors engine and router: period returns and annualising, risk metrics, calendar years,
scoreboard shape, rotation quadrants, rank maths, screener weighting/explanations, cycle-fit grouping,
backtest mechanics (no look-ahead, costs, completed months only) and endpoints. No network.
Run: python -m pytest tests/test_sectors.py -v
"""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import market_history as mh
import routers.sectors as router_mod
import sectors as sc


def bdays(n, end="2026-09-30"):
    return pd.bdate_range(end=end, periods=n)


def grow(n, daily, end="2026-09-30", start_price=100.0):
    idx = bdays(n, end)
    return pd.Series(start_price * np.cumprod(np.full(n, 1 + daily)), index=idx)


def universe(n=2800, drift=None):
    drift = drift or {}
    out = {sc.BENCH: grow(n, 0.0004), sc.EQUAL_WEIGHT: grow(n, 0.00035)}
    for i, s in enumerate(sc.SYMBOLS):
        out[s] = grow(n, drift.get(s, 0.0002 + i * 0.00006))
    return out


# ── returns ───────────────────────────────────────────────────────────────────

class TestReturns:
    def test_period_returns_on_a_known_series(self):
        idx = pd.to_datetime(["2025-09-30", "2026-03-31", "2026-08-28", "2026-09-23", "2026-09-29", "2026-09-30"])
        s = pd.Series([100.0, 120.0, 150.0, 160.0, 180.0, 200.0], index=idx)
        assert sc.period_return(s, "1D") == pytest.approx(200 / 180 - 1)
        assert sc.period_return(s, "1W") == pytest.approx(200 / 160 - 1)
        assert sc.period_return(s, "1M") == pytest.approx(200 / 150 - 1)
        assert sc.period_return(s, "1Y") == pytest.approx(1.0)
        assert sc.period_return(s, "LTD") == pytest.approx(1.0)

    def test_ytd_uses_prior_year_end(self):
        idx = pd.to_datetime(["2025-12-31", "2026-06-30", "2026-09-30"])
        s = pd.Series([100.0, 110.0, 130.0], index=idx)
        assert sc.period_return(s, "YTD") == pytest.approx(0.30)

    def test_too_short_history_is_none_not_a_shorter_window(self):
        s = grow(300, 0.001)
        assert sc.period_return(s, "1Y") is not None
        assert sc.period_return(s, "3Y") is None and sc.period_return(s, "10Y") is None

    def test_annualise(self):
        assert sc.annualise(1.0, 3) == pytest.approx(2 ** (1 / 3) - 1)
        assert sc.annualise(None, 3) is None and sc.annualise(-1.0, 3) is None and sc.annualise(0.5, 0) is None

    def test_returns_row_shape(self):
        row = sc.returns_row(grow(2800, 0.0005))
        assert set(row) == set(sc.PERIODS)
        assert row["3Y"]["annualised"] is not None and row["1Y"]["annualised"] is None and row["LTD"]["annualised"] is not None
        assert row["10Y"]["total"] > row["5Y"]["total"] > row["1Y"]["total"] > 0

    def test_calendar_years(self):
        idx = pd.to_datetime(["2023-12-29", "2024-12-31", "2025-12-31", "2026-09-30"])
        cal = sc.calendar_years(pd.Series([100.0, 110.0, 99.0, 108.9], index=idx), count=4)
        assert cal["2024"] == pytest.approx(0.10) and cal["2025"] == pytest.approx(-0.10) and cal["2026"] == pytest.approx(0.10)
        assert cal["2023"] is None                                    # no prior year-end to measure from


class TestRisk:
    def test_max_drawdown(self):
        assert sc.max_drawdown(pd.Series([100, 120, 90, 100, 130, 117.0])) == pytest.approx(-0.25)
        assert sc.max_drawdown(pd.Series([1.0, 2.0])) is None

    def test_beta_and_capture_for_a_two_times_levered_copy(self):
        rng = np.random.default_rng(3)
        n = 1200
        base = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n)), index=bdays(n))
        lev = 100 * np.cumprod(1 + 2 * base.pct_change().fillna(0).values)
        lev = pd.Series(lev, index=base.index)
        r = sc.risk_metrics(lev, base)
        assert r["beta"] == pytest.approx(2.0, abs=0.15)
        assert r["upCapture"] == pytest.approx(2.0, abs=0.25) and r["downCapture"] == pytest.approx(2.0, abs=0.25)
        assert r["volatility"] > sc.risk_metrics(base, base)["volatility"] * 1.7

    def test_short_history_is_flagged_and_sparse(self):
        s = grow(400, 0.0005)
        r = sc.risk_metrics(s, s)
        assert r["short"] is True
        assert sc.risk_metrics(grow(20, 0.001), grow(20, 0.001))["volatility"] is None


# ── scoreboard ────────────────────────────────────────────────────────────────

class TestScoreboard:
    def test_shape_and_excess(self):
        sb = sc.build_scoreboard(universe())
        assert sb["asOf"] == "2026-09-30" and len(sb["sectors"]) == 11 and sb["benchmark"]["symbol"] == "SPY" and sb["equalWeight"]["symbol"] == "RSP"
        xlk = next(r for r in sb["sectors"] if r["symbol"] == "XLK")
        assert xlk["excess"]["1Y"] == pytest.approx(xlk["returns"]["1Y"]["total"] - sb["benchmark"]["returns"]["1Y"]["total"], abs=1e-4)
        assert xlk["trend"]["above200"] is not None and list(xlk["calendar"])[-1] == "2026"
        json.dumps(sb)

    def test_young_sectors_have_none_for_long_periods(self):
        u = universe()
        u["XLC"] = u["XLC"].iloc[-600:]
        sb = sc.build_scoreboard(u)
        xlc = next(r for r in sb["sectors"] if r["symbol"] == "XLC")
        assert xlc["returns"]["10Y"]["total"] is None and xlc["returns"]["1Y"]["total"] is not None and xlc["excess"]["10Y"] is None

    def test_needs_benchmark(self):
        u = universe(); del u[sc.BENCH]
        assert sc.build_scoreboard(u) is None
        assert sc.build_scoreboard({sc.BENCH: grow(100, 0.001)}) is None

    def test_missing_sector_is_skipped(self):
        u = universe(); del u["XLU"]
        assert len(sc.build_scoreboard(u)["sectors"]) == 10

    def test_trend_flags(self):
        up = grow(300, 0.002)
        assert sc.trend_flags(up)["above200"] and sc.trend_flags(up)["ma50Above200"]
        down = grow(300, -0.002)
        assert not sc.trend_flags(down)["above200"] and sc.trend_flags(down)["pctFrom200"] < 0
        assert sc.trend_flags(grow(50, 0.001))["above200"] is None


# ── rotation ──────────────────────────────────────────────────────────────────

class TestRotation:
    def test_quadrants(self):
        for (r, m), qid in {(True, True): "leading", (True, False): "weakening", (False, False): "lagging", (False, True): "improving"}.items():
            assert sc.RRG_QUADRANTS[(r, m)][0] == qid

    def test_outperformer_is_above_100_and_underperformer_below(self):
        n = 1500
        bench = grow(n, 0.0004)
        # accelerating outperformer vs steady underperformer
        out = pd.Series(100 * np.cumprod(1 + np.linspace(0.0004, 0.0016, n)), index=bench.index)
        under = grow(n, 0.0001)
        up, dn = sc.rrg_points(out, bench), sc.rrg_points(under, bench)
        assert len(up) == 8 and up[-1]["ratio"] > 100 > dn[-1]["ratio"]
        assert up[-1]["date"] > up[0]["date"]

    def test_short_history_has_no_point(self):
        assert sc.rrg_points(grow(100, 0.001), grow(100, 0.0005)) is None

    def test_build_rotation_payload(self):
        r = sc.build_rotation(universe())
        assert len(r["sectors"]) == 11 and all(s["quadrant"] in ("leading", "weakening", "lagging", "improving") for s in r["sectors"])
        assert all(len(s["trail"]) == 8 for s in r["sectors"]) and "clockwise" in r["note"]
        json.dumps(r)


# ── screener ──────────────────────────────────────────────────────────────────

class TestRanks:
    def test_pct_rank(self):
        r = sc.pct_rank({"a": 1.0, "b": 2.0, "c": 3.0, "d": None})
        assert r == {"a": 0.0, "b": 50.0, "c": 100.0, "d": None}

    def test_ties_share_midpoint(self):
        r = sc.pct_rank({"a": 1.0, "b": 1.0, "c": 5.0})
        assert r["a"] == r["b"] == 25.0 and r["c"] == 100.0

    def test_single_value(self):
        assert sc.pct_rank({"a": 3.0, "b": None}) == {"a": 50.0, "b": None}

    @pytest.mark.parametrize("score,t", [(80, "Overweight"), (62, "Overweight"), (50, "Neutral"), (38, "Underweight"), (5, "Underweight")])
    def test_tier(self, score, t):
        assert sc.tier(score) == t


class TestScreener:
    def test_strong_trending_sector_ranks_first_and_scores_are_bounded(self):
        u = universe(drift={"XLK": 0.0012, "XLU": -0.0002})
        r = sc.build_screener(u, "intermediate")
        assert r["sectors"][0]["symbol"] == "XLK" and r["sectors"][-1]["symbol"] == "XLU"
        assert all(0 <= s["score"] <= 100 for s in r["sectors"]) and [s["rank"] for s in r["sectors"]] == list(range(1, 12))
        top = r["sectors"][0]
        assert top["tier"] == "Overweight" and r["sectors"][-1]["tier"] == "Underweight" and top["why"]
        json.dumps(r)

    def test_contributions_sum_to_score_and_weights_to_100(self):
        r = sc.build_screener(universe(drift={"XLK": 0.001}), "tactical")
        for s in r["sectors"]:
            assert sum(f["contribution"] for f in s["factors"].values()) == pytest.approx(s["score"], abs=0.3)
            assert sum(f["weight"] for f in s["factors"].values()) == pytest.approx(100, abs=0.3)

    def test_custom_weights_change_the_ranking(self):
        u = universe(drift={"XLK": 0.0011, "XLP": 0.0001})
        a = sc.build_screener(u, "tactical", {"momentum": 100})
        assert list(a["sectors"][0]["factors"]) == ["momentum"] and a["sectors"][0]["symbol"] == "XLK"
        b = sc.build_screener(u, "tactical", {"seasonality": 100})
        assert list(b["sectors"][0]["factors"]) == ["seasonality"] and b["weights"] == {"seasonality": 100.0}
        assert a["sectors"][0]["factors"]["momentum"]["contribution"] == a["sectors"][0]["score"]

    def test_unknown_factor_or_zero_weights_are_ignored(self):
        u = universe()
        assert sc.build_screener(u, "tactical", {"bogus": 50, "momentum": 0}) is None
        assert sc.build_screener(u, "nope") is None

    def test_cycle_factor_only_when_evidence_is_supplied(self):
        u = universe()
        without = sc.build_screener(u, "intermediate")
        assert "cycle" not in without["weights"]
        fit = {s: (i - 5) / 1000 for i, s in enumerate(sc.SYMBOLS)}
        withc = sc.build_screener(u, "intermediate", cycle_fit=fit, cycle_phase_name="Mid-cycle expansion")
        assert withc["weights"]["cycle"] == 25 and withc["cyclePhase"] == "Mid-cycle expansion"
        assert "cycle" in withc["sectors"][0]["factors"]

    def test_missing_factor_data_renormalises(self):
        u = universe()
        u["XLC"] = u["XLC"].iloc[-400:]                                # too short for 3Y risk
        r = sc.build_screener(u, "strategic")
        xlc = next(s for s in r["sectors"] if s["symbol"] == "XLC")
        assert sum(f["weight"] for f in xlc["factors"].values()) == pytest.approx(100, abs=0.3)

    def test_seasonality(self):
        idx = pd.date_range("2000-01-01", "2020-12-31", freq="D")
        bench = pd.Series(100.0, index=idx)
        s = pd.Series(100 * np.cumprod(np.where(idx.month.isin([1, 2, 3]), 1.001, 1.0)), index=idx)
        assert sc.seasonal_excess(s, bench, 1) > 0.02
        assert sc.seasonal_excess(s, bench, 7) == pytest.approx(0.0, abs=0.001)
        assert sc.seasonal_excess(s.iloc[:500], bench.iloc[:500], 1) is None


# ── cycle fit ─────────────────────────────────────────────────────────────────

class TestCycleFit:
    def regimes(self, idx):
        labels = ["early" if (i // 12) % 2 == 0 else "late" for i in range(len(idx))]
        return pd.DataFrame({"phase": labels, "quadrant": ["goldilocks"] * len(idx)}, index=idx)

    def test_groups_excess_by_phase(self):
        idx = pd.date_range("2005-01-01", "2024-12-31", freq="D")
        spy = pd.Series(100.0 * np.cumprod(np.full(len(idx), 1.0003)), index=idx)
        # sector beats SPY only in "early" years
        factors = np.where([(m.year - 2005) % 2 == 0 for m in idx], 1.0008, 1.0003)
        sec = pd.Series(100.0 * np.cumprod(factors), index=idx)
        months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
        # regime label for a month: "early" in even years
        reg = pd.DataFrame({"phase": ["early" if (d.year - 2005) % 2 == 0 else "late" for d in months]}, index=months)
        prices = {sc.BENCH: spy, "XLK": sec}
        fit = sc.cycle_fit(prices, reg)
        cells = fit["sectors"][0]["cells"]
        assert cells["early"]["avgMonthlyExcess"] > 0.005 > cells["late"]["avgMonthlyExcess"] - 0.0001
        assert cells["early"]["months"] > 100 and cells["early"]["episodes"] >= 5 and 0 <= cells["early"]["hitRate"] <= 1
        assert fit["samples"]["early"] == 120 and "few distinct episodes" in fit["note"]

    def test_empty_inputs(self):
        assert sc.cycle_fit({}, pd.DataFrame()) is None
        assert sc.cycle_fit({sc.BENCH: grow(100, 0.001)}, pd.DataFrame({"phase": []})) is None

    def test_cycle_fit_for_phase_requires_six_months(self):
        fit = {"sectors": [{"symbol": "XLK", "cells": {"mid": {"avgMonthlyExcess": 0.01, "months": 30}, "late": {"avgMonthlyExcess": 0.02, "months": 4}}}]}
        assert sc.cycle_fit_for_phase(fit, "mid") == {"XLK": 0.01}
        assert sc.cycle_fit_for_phase(fit, "late") is None and sc.cycle_fit_for_phase(None, "mid") is None


# ── backtest ──────────────────────────────────────────────────────────────────

class TestBacktest:
    def test_completed_month_ends_drops_the_unfinished_month(self):
        s = pd.Series(1.0, index=pd.bdate_range("2026-07-01", "2026-09-10"))
        ends = sc.completed_month_ends(s)
        assert [d.strftime("%Y-%m-%d") for d in ends] == ["2026-07-31", "2026-08-31"]
        full = pd.Series(1.0, index=pd.bdate_range("2026-07-01", "2026-09-30"))
        assert sc.completed_month_ends(full)[-1] == pd.Timestamp("2026-09-30")

    def test_momentum_strategy_beats_spy_when_one_sector_trends_hard(self):
        u = universe(n=3000, drift={"XLK": 0.0010})
        bt = sc.run_backtest(u, top_n=1, cost_bps=0, defensive_switch=False, start="2016-01-01")
        assert bt["strategy"]["cagr"] > bt["spy"]["cagr"] and bt["months"] > 100
        assert bt["latestHoldings"] == ["XLK"] and bt["monthsBeatingSpy"] > 0.6
        json.dumps(bt)

    def test_costs_reduce_returns(self):
        u = universe(n=3000, drift={"XLK": 0.0008, "XLE": 0.0007})
        free = sc.run_backtest(u, 3, 0, False, "2016-01-01")
        costly = sc.run_backtest(u, 3, 100, False, "2016-01-01")
        assert costly["strategy"]["cagr"] <= free["strategy"]["cagr"]

    def test_defensive_switch_moves_to_defensives_in_a_downtrend(self):
        u = universe(n=3000)
        u[sc.BENCH] = pd.concat([grow(2700, 0.0006, end="2026-05-29"), grow(300, -0.002, end="2026-09-30", start_price=0)]) if False else u[sc.BENCH]
        n = len(u[sc.BENCH])
        r = np.concatenate([np.full(n - 260, 0.0005), np.full(260, -0.002)])
        u[sc.BENCH] = pd.Series(100 * np.cumprod(1 + r), index=u[sc.BENCH].index)
        bt = sc.run_backtest(u, 3, 10, True, "2016-01-01")
        assert bt["riskOffMonths"] > 0 and set(bt["latestHoldings"]) <= set(sc.DEFENSIVE)

    def test_no_look_ahead_future_data_does_not_change_past_scores(self):
        u = universe(n=3000)
        d = u[sc.BENCH].index[2200]
        a = sc._month_end_scores(u, d)
        mutated = {k: v.copy() for k, v in u.items()}
        for k in mutated:
            mutated[k].iloc[2201:] *= 5
        assert sc._month_end_scores(mutated, d) == a

    def test_too_little_history(self):
        assert sc.run_backtest({sc.BENCH: grow(300, 0.001)}) is None
        assert sc.run_backtest({}) is None


# ── endpoints ─────────────────────────────────────────────────────────────────

class TestEndpoints:
    @pytest.fixture
    def client(self, monkeypatch):
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        u = universe(n=3000)
        monkeypatch.setattr(mh, "get_many_daily", lambda syms: u)
        monkeypatch.setattr(router_mod, "_regime_months", lambda: None)
        app = FastAPI(); app.include_router(router_mod.router)
        return TestClient(app)

    def test_scoreboard_rotation_screener_backtest(self, client):
        assert len(client.get("/api/sectors/scoreboard").json()["sectors"]) == 11
        assert len(client.get("/api/sectors/rotation").json()["sectors"]) == 11
        s = client.get("/api/sectors/screener?horizon=strategic").json()
        assert s["horizon"] == "strategic" and s["cyclePhase"] is None and "cycle" not in s["weights"]
        assert client.get("/api/sectors/backtest?top_n=2&cost_bps=5&defensive=false").json()["params"]["topN"] == 2

    def test_screener_weights_and_validation(self, client):
        j = client.get('/api/sectors/screener?horizon=tactical&weights={"momentum":100}').json()
        assert j["weights"] == {"momentum": 100.0}
        assert client.get("/api/sectors/screener?horizon=zzz").status_code == 404
        assert client.get("/api/sectors/screener?weights=not-json").status_code == 400
        assert client.get('/api/sectors/screener?weights=[1,2]').status_code == 400
        assert client.get("/api/sectors/backtest?top_n=99").status_code == 422
        assert client.get("/api/sectors/cycle-fit?group=zzz").status_code == 422

    def test_cycle_fit_unavailable_without_fred_is_502(self, client):
        assert client.get("/api/sectors/cycle-fit").status_code == 502

    def test_no_prices_is_502(self, monkeypatch):
        monkeypatch.setattr(router_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(mh, "get_many_daily", lambda syms: {})
        app = FastAPI(); app.include_router(router_mod.router)
        r = TestClient(app).get("/api/sectors/scoreboard")
        assert r.status_code == 502 and "price history" in r.json()["detail"]

    def test_results_are_cached(self, client, monkeypatch):
        client.get("/api/sectors/scoreboard")
        monkeypatch.setattr(mh, "get_many_daily", lambda syms: pytest.fail("cached"))
        assert client.get("/api/sectors/scoreboard").status_code == 200
