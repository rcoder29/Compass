"""
Tests for the Company Tear Sheet: the pure valuation / scoring math, the
statement and price-history shaping, and the endpoint against mocked fetches.
Run: python -m pytest tests/test_tear_sheet.py -v
"""
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.tear_sheet as ts


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    monkeypatch.setattr(ts, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(ts, "cache_set", lambda *a, **k: None)


# ── scale / discount rate ─────────────────────────────────────────────────────

class TestScale:
    def test_maps_and_clamps(self):
        assert ts._scale(0.5, 0, 1) == 50
        assert ts._scale(-5, 0, 1) == 0
        assert ts._scale(5, 0, 1) == 100

    def test_none_passes_through(self):
        assert ts._scale(None, 0, 1) is None


class TestDiscountRate:
    def test_beta_one(self):
        assert ts._discount_rate(1.0) == pytest.approx(0.095)

    def test_clamped_both_ends(self):
        assert ts._discount_rate(0.0) == 0.07
        assert ts._discount_rate(5.0) == 0.12

    def test_missing_beta_defaults_to_market(self):
        assert ts._discount_rate(None) == ts._discount_rate(1.0)


# ── DCF ───────────────────────────────────────────────────────────────────────

class TestDcf:
    def test_positive_fcf_gives_positive_value(self):
        v = ts._dcf_value_per_share(100.0, 10.0, 0.08, 0.09, 0.0, 0.0)
        assert v is not None and v > 0

    def test_higher_growth_gives_higher_value(self):
        lo = ts._dcf_value_per_share(100.0, 10.0, 0.02, 0.09, 0, 0)
        hi = ts._dcf_value_per_share(100.0, 10.0, 0.12, 0.09, 0, 0)
        assert hi > lo

    def test_higher_discount_rate_lowers_value(self):
        lo = ts._dcf_value_per_share(100.0, 10.0, 0.08, 0.07, 0, 0)
        hi = ts._dcf_value_per_share(100.0, 10.0, 0.08, 0.12, 0, 0)
        assert lo > hi

    def test_net_cash_adds_and_debt_subtracts(self):
        base = ts._dcf_value_per_share(100.0, 10.0, 0.05, 0.09, 0, 0)
        assert ts._dcf_value_per_share(100.0, 10.0, 0.05, 0.09, 100, 0) == pytest.approx(base + 10)
        assert ts._dcf_value_per_share(100.0, 10.0, 0.05, 0.09, 0, 100) == pytest.approx(base - 10)

    def test_growth_is_capped_at_15pct(self):
        capped = ts._dcf_value_per_share(100.0, 10.0, 0.15, 0.09, 0, 0)
        assert ts._dcf_value_per_share(100.0, 10.0, 0.60, 0.09, 0, 0) == pytest.approx(capped)

    @pytest.mark.parametrize("fcf,shares", [(None, 10), (0, 10), (-50, 10), (100, 0), (100, None)])
    def test_unusable_inputs_return_none(self, fcf, shares):
        assert ts._dcf_value_per_share(fcf, shares, 0.05, 0.09, 0, 0) is None

    def test_debt_exceeding_value_returns_none(self):
        assert ts._dcf_value_per_share(1.0, 10.0, 0.05, 0.09, 0, 1e9) is None


# ── fair values / verdict ─────────────────────────────────────────────────────

def _fv(**over):
    args = dict(price=100.0, eps_ttm=5.0, eps_fwd=6.0, growth=0.10,
                hist_pes=[{"pe": 20.0}, {"pe": 24.0}], fcf=500.0, shares=100.0,
                beta=1.0, cash=0.0, debt=0.0, target_mean=130.0)
    args.update(over)
    return ts._fair_values(**args)


class TestFairValues:
    def test_all_four_methods_computed(self):
        by = {f["method"]: f["value"] for f in _fv()}
        assert by["Historical P/E"] == pytest.approx(22.0 * 5.0)
        assert by["PEG = 1"] == pytest.approx(10.0 * 6.0)
        assert by["DCF (FCF)"] > 0
        assert by["Analyst target"] == pytest.approx(130.0 / 1.095, abs=0.01)

    def test_peg_multiple_is_clamped(self):
        low = {f["method"]: f["value"] for f in _fv(growth=0.01)}
        high = {f["method"]: f["value"] for f in _fv(growth=0.90)}
        assert low["PEG = 1"] == pytest.approx(8 * 6.0)
        assert high["PEG = 1"] == pytest.approx(40 * 6.0)

    def test_missing_inputs_leave_methods_none_not_missing(self):
        out = _fv(hist_pes=[], growth=None, fcf=None, target_mean=None)
        assert [f["method"] for f in out] == ["Historical P/E", "PEG = 1", "DCF (FCF)", "Analyst target"]
        assert all(f["value"] is None for f in out)

    def test_negative_eps_blocks_pe_models(self):
        by = {f["method"]: f["value"] for f in _fv(eps_ttm=-2.0, eps_fwd=-1.0)}
        assert by["Historical P/E"] is None and by["PEG = 1"] is None


class TestVerdict:
    def _fvs(self, *vals):
        return [{"method": f"m{i}", "value": v} for i, v in enumerate(vals)]

    def test_median_of_methods_and_premium(self):
        v = ts._verdict(120.0, self._fvs(80, 100, 120))
        assert v["fairValue"] == 100 and v["premium"] == pytest.approx(0.20)
        assert (v["low"], v["high"]) == (80, 120)

    @pytest.mark.parametrize("price,label,tone", [
        (70, "Significantly undervalued", "good"),
        (85, "Undervalued", "good"),
        (100, "Fairly valued", "neutral"),
        (115, "Overvalued", "bad"),
        (130, "Significantly overvalued", "bad"),
    ])
    def test_labels_against_fair_value_100(self, price, label, tone):
        v = ts._verdict(price, self._fvs(100, 100))
        assert v["label"] == label and v["tone"] == tone

    def test_single_model_is_not_enough(self):
        v = ts._verdict(50.0, self._fvs(None, None, None, 200))
        assert v["label"] == "Not enough data to judge"
        assert v["fairValue"] is None and v["premium"] is None
        assert v["methodsUsed"] == 1

    def test_no_models(self):
        v = ts._verdict(50.0, self._fvs(None, None))
        assert v["label"] == "Not enough data to judge" and v["low"] is None

    def test_non_positive_values_ignored(self):
        assert ts._verdict(50.0, self._fvs(-10, 0, 60))["methodsUsed"] == 1


# ── scenarios / 5-year returns ────────────────────────────────────────────────

class TestScenarios:
    def test_base_return_equals_eps_growth_when_multiple_holds(self):
        out = ts._scenarios_12m(100.0, 5.0, {"low": 5.5, "avg": 6.0, "high": 7.0}, 0.02)
        base = next(s for s in out if s["scenario"] == "Base")
        assert base["priceReturn"] == pytest.approx(0.20)
        assert base["totalReturn"] == pytest.approx(0.22)

    def test_bear_below_base_below_bull(self):
        out = {s["scenario"]: s["price"] for s in
               ts._scenarios_12m(100.0, 5.0, {"low": 5.5, "avg": 6.0, "high": 7.0}, None)}
        assert out["Bear"] < out["Base"] < out["Bull"]

    def test_bear_applies_20pct_derating(self):
        bear = next(s for s in ts._scenarios_12m(100.0, 5.0, {"low": 5.0, "avg": 5.0, "high": 5.0}, 0)
                    if s["scenario"] == "Bear")
        assert bear["price"] == pytest.approx(80.0)

    @pytest.mark.parametrize("eps_cur", [None, 0, -1.0])
    def test_unusable_current_eps_returns_empty(self, eps_cur):
        assert ts._scenarios_12m(100.0, eps_cur, {"low": 1, "avg": 1, "high": 1}, 0) == []

    def test_skips_scenarios_with_non_positive_eps(self):
        out = ts._scenarios_12m(100.0, 5.0, {"low": -1.0, "avg": 6.0, "high": 7.0}, 0)
        assert [s["scenario"] for s in out] == ["Base", "Bull"]


class TestFiveYearReturns:
    def test_unchanged_pe_with_zero_growth_is_zero_return(self):
        out = ts._five_year_returns(100.0, 5.0, 0.0, 20.0, None, 0.0)
        unchanged = next(s for s in out if s["scenario"] == "P/E unchanged")
        assert unchanged["annualisedReturn"] == pytest.approx(0.0, abs=1e-9)

    def test_growth_compounds(self):
        out = ts._five_year_returns(100.0, 5.0, 0.10, 20.0, None, 0.0)
        unchanged = next(s for s in out if s["scenario"] == "P/E unchanged")
        assert unchanged["annualisedReturn"] == pytest.approx(0.10, abs=1e-6)

    def test_compression_scenario_is_worst(self):
        out = ts._five_year_returns(100.0, 5.0, 0.10, 20.0, 15.0, 0.0)
        rets = [s["annualisedReturn"] for s in out]
        assert rets[0] == min(rets)

    def test_growth_is_capped_at_25pct(self):
        a = ts._five_year_returns(100.0, 5.0, 0.25, 20.0, None, 0)
        b = ts._five_year_returns(100.0, 5.0, 0.90, 20.0, None, 0)
        assert a == b

    @pytest.mark.parametrize("eps", [None, 0, -3.0])
    def test_unusable_eps_returns_empty(self, eps):
        assert ts._five_year_returns(100.0, eps, 0.1, 20.0, None, 0) == []


# ── scorecard / flags ─────────────────────────────────────────────────────────

class TestScorecard:
    def test_strong_company_scores_high_and_weak_scores_low(self):
        strong = ts._scorecard(dict(revenueGrowth=0.30, epsGrowthFwd=0.30, netMargin=0.25, operatingMargin=0.35,
                                    roe=0.30, netDebtToEbitda=-2.0, currentRatio=2.0, interestCoverage=15,
                                    premium=-0.40, recommendationMean=1.0, upside=0.30, relative1y=0.30,
                                    above200=True, rangePosition=1.0))
        weak = ts._scorecard(dict(revenueGrowth=-0.10, epsGrowthFwd=-0.10, netMargin=0.0, operatingMargin=0.0,
                                  roe=0.0, netDebtToEbitda=4.0, currentRatio=0.5, interestCoverage=1,
                                  premium=0.30, recommendationMean=5.0, upside=-0.15, relative1y=-0.30,
                                  above200=False, rangePosition=0.0))
        assert strong["overall"] > 90 and weak["overall"] < 15

    def test_missing_pillars_are_none_and_excluded_from_overall(self):
        out = ts._scorecard({"netMargin": 0.25, "operatingMargin": 0.35, "roe": 0.30})
        by = {p["name"]: p["score"] for p in out["pillars"]}
        assert by["Profitability"] == 100 and by["Growth"] is None
        assert out["overall"] == 100

    def test_empty_metrics_give_no_overall(self):
        assert ts._scorecard({})["overall"] is None


class TestFlags:
    def test_flags_split_into_strengths_and_risks(self):
        f = ts._flags(dict(revenueGrowth=0.2, netMargin=0.2, fcfPositive=True, premium=0.4,
                           above200=False, shortPercentOfFloat=0.2, beta=2.0))
        assert any("Revenue growing 20%" in s for s in f["strengths"])
        assert any("above blended fair value" in r for r in f["risks"])
        assert any("200-day" in r for r in f["risks"])
        assert any("short interest" in r for r in f["risks"])

    def test_no_empty_strings_and_empty_input_ok(self):
        f = ts._flags({})
        assert f == {"strengths": [], "risks": []}
        g = ts._flags(dict(revenueGrowth=0.0, netMargin=0.0, roe=0.0))
        assert all(g["strengths"]) and all(g["risks"])

    def test_negative_net_margin_flagged(self):
        assert any("unprofitable" in r for r in ts._flags(dict(netMargin=-0.1))["risks"])


# ── statements ────────────────────────────────────────────────────────────────

def _income():
    cols = [pd.Timestamp("2025-09-30"), pd.Timestamp("2024-09-30"), pd.Timestamp("2023-09-30")]
    return pd.DataFrame({
        cols[0]: {"Total Revenue": 200.0, "Gross Profit": 100.0, "Operating Income": 50.0, "Net Income": 40.0,
                  "Diluted EPS": 4.0, "Diluted Average Shares": 10.0},
        cols[1]: {"Total Revenue": 150.0, "Gross Profit": 70.0, "Operating Income": 30.0, "Net Income": 20.0,
                  "Diluted EPS": 2.0, "Diluted Average Shares": 10.0},
        cols[2]: {"Total Revenue": 100.0, "Gross Profit": 40.0, "Operating Income": 10.0, "Net Income": 5.0,
                  "Diluted EPS": 0.5, "Diluted Average Shares": 10.0},
    })


class TestFinancialHistory:
    def test_sorted_oldest_first_with_margins_and_growth(self):
        h = ts._financial_history(_income(), None, None)
        assert [r["fiscalYear"] for r in h] == ["2023-09-30", "2024-09-30", "2025-09-30"]
        assert h[-1]["grossMargin"] == pytest.approx(0.5)
        assert h[-1]["netMargin"] == pytest.approx(0.2)
        assert h[-1]["revenueGrowth"] == pytest.approx(200 / 150 - 1)
        assert h[0]["revenueGrowth"] is None

    def test_missing_cashflow_and_balance_do_not_break(self):
        h = ts._financial_history(_income(), None, None)
        assert h[-1]["freeCashFlow"] is None and h[-1]["totalDebt"] is None

    def test_empty_or_missing_income_returns_empty(self):
        assert ts._financial_history(None, None, None) == []
        assert ts._financial_history(pd.DataFrame(), None, None) == []


class TestCagr:
    def test_basic(self):
        assert ts._cagr(100, 121, 2) == pytest.approx(0.10)

    @pytest.mark.parametrize("a,b,y", [(None, 1, 1), (0, 1, 1), (-5, 10, 1), (5, -1, 1), (5, 10, 0)])
    def test_unusable_returns_none(self, a, b, y):
        assert ts._cagr(a, b, y) is None


# ── price history ─────────────────────────────────────────────────────────────

def _series(n=400, start=100.0, step=0.1):
    idx = pd.date_range(end="2026-10-08", periods=n, freq="D")
    return pd.Series([start + step * i for i in range(n)], index=idx)


class TestPriceHistory:
    def test_period_return(self):
        s = _series()
        r = ts._period_return(s, 30)
        assert r == pytest.approx(s.iloc[-1] / s.iloc[-31] - 1)

    def test_period_return_none_when_history_too_short(self):
        assert ts._period_return(_series(n=100), 365) is None

    def test_period_return_handles_missing_series(self):
        assert ts._period_return(None, 30) is None

    def test_max_drawdown(self):
        s = pd.Series([100, 120, 60, 90], index=pd.date_range("2026-01-01", periods=4))
        assert ts._max_drawdown(s) == pytest.approx(-0.5)

    def test_performance_has_relative_returns_and_series(self):
        stock, spy = _series(step=0.2), _series(step=0.1)
        perf = ts._price_performance(stock, spy)
        one_y = next(r for r in perf["returns"] if r["period"] == "1Y")
        assert one_y["relative"] == pytest.approx(one_y["stock"] - one_y["spy"])
        assert perf["series"]["dates"] and len(perf["series"]["close"]) == len(perf["series"]["dates"])
        assert perf["series"]["stockRebased"][0] == 100.0
        assert perf["ma200"] is not None

    def test_performance_without_benchmark(self):
        perf = ts._price_performance(_series(), None)
        assert perf["series"]["spyRebased"] is None
        assert all(r["spy"] is None for r in perf["returns"])

    def test_performance_without_any_prices(self):
        perf = ts._price_performance(None, None)
        assert perf["series"] is None and perf["maxDrawdown5y"] is None

    def test_historical_pes_use_price_at_fiscal_year_end(self):
        stock = pd.Series([50.0, 80.0], index=pd.to_datetime(["2024-09-30", "2025-09-30"]))
        hist = [{"fiscalYear": "2024-09-30", "eps": 5.0}, {"fiscalYear": "2025-09-30", "eps": 4.0},
                {"fiscalYear": "2023-09-30", "eps": -1.0}]
        out = ts._historical_pes(stock, hist)
        assert [o["pe"] for o in out] == [10.0, 20.0]

    def test_naive_close_strips_timezone(self):
        idx = pd.date_range("2026-01-01", periods=3, tz="America/New_York")
        s = ts._naive_close(pd.DataFrame({"Close": [1.0, 2.0, 3.0]}, index=idx))
        assert s.index.tz is None


# ── analysts / estimates / earnings ───────────────────────────────────────────

class TestAnalysts:
    def test_upside_and_distribution(self):
        recs = pd.DataFrame([
            {"period": "0m", "strongBuy": 6, "buy": 19, "hold": 13, "sell": 3, "strongSell": 3},
            {"period": "-3m", "strongBuy": 6, "buy": 22, "hold": 14, "sell": 2, "strongSell": 2},
        ])
        out = ts._analyst_section({"recommendationKey": "buy", "numberOfAnalystOpinions": 44},
                                  {"mean": 120.0, "high": 150.0, "low": 90.0, "median": 118.0}, recs, None, 100.0)
        assert out["upsideToMean"] == pytest.approx(0.20)
        assert out["distribution"]["buy"] == 19 and out["distribution3mAgo"]["buy"] == 22

    def test_zero_price_targets_become_none(self):
        updown = pd.DataFrame(
            [{"Firm": "X", "ToGrade": "Hold", "FromGrade": "Hold", "Action": "reit",
              "currentPriceTarget": 0.0, "priorPriceTarget": 0.0}],
            index=pd.to_datetime(["2026-10-01"]))
        out = ts._analyst_section({}, None, None, updown, 100.0)
        assert out["recentChanges"][0]["target"] is None
        assert out["upsideToMean"] is None

    def test_everything_missing(self):
        out = ts._analyst_section({}, None, None, None, 100.0)
        assert out["distribution"] is None and out["recentChanges"] == []


class TestEstimates:
    def test_rows_labelled_and_ordered(self):
        df = pd.DataFrame(
            {"avg": [2.0, 9.0], "low": [1.9, 8.0], "high": [2.1, 10.0], "yearAgoEps": [1.8, 8.0],
             "numberOfAnalysts": [27, 39], "growth": [0.1, 0.12]}, index=["0q", "0y"])
        rows = ts._estimate_rows(df)
        assert [r["label"] for r in rows] == ["Current Qtr", "Current FY"]
        assert rows[1]["analysts"] == 39 and rows[1]["yearAgo"] == 8.0

    def test_revisions_compute_percent_change(self):
        df = pd.DataFrame({"current": [10.0], "30daysAgo": [8.0], "90daysAgo": [5.0]}, index=["0y"])
        r = ts._revisions(df)[0]
        assert r["change30d"] == pytest.approx(0.25) and r["change90d"] == pytest.approx(1.0)

    def test_empty_frames(self):
        assert ts._estimate_rows(None) == [] and ts._revisions(pd.DataFrame()) == []


class TestEarningsTrack:
    def test_beat_count_and_average_surprise(self):
        df = pd.DataFrame({"epsActual": [1.1, 0.9, 1.3, 1.0], "epsEstimate": [1.0, 1.0, 1.0, 1.0],
                           "surprisePercent": [0.1, -0.1, 0.3, 0.0]},
                          index=pd.to_datetime(["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]))
        t = ts._earnings_track(df)
        assert t["beats"] == 2 and t["total"] == 4
        assert t["avgSurprisePct"] == pytest.approx(0.075)

    def test_empty(self):
        assert ts._earnings_track(None) == {"quarters": [], "beats": 0, "total": 0, "avgSurprisePct": None}


class TestInsiders:
    def test_parses_six_month_summary(self):
        df = pd.DataFrame({"Insider Purchases Last 6m": ["Purchases", "Sales", "Net Shares Purchased (Sold)"],
                           "Shares": [800.0, 500.0, 300.0], "Trans": [12, 17, 29]})
        out = ts._insider_section(df)
        assert out["boughtShares6m"] == 800 and out["soldShares6m"] == 500 and out["netShares6m"] == 300
        assert out["buyTransactions6m"] == 12

    def test_missing(self):
        assert ts._insider_section(None) is None


# ── end to end (mocked fetch) ─────────────────────────────────────────────────

def _raw(**over):
    raw = {
        "info": {"currentPrice": 100.0, "trailingEps": 5.0, "forwardEps": 6.0, "beta": 1.0,
                 "sharesOutstanding": 100.0, "totalCash": 1000.0, "totalDebt": 500.0,
                 "freeCashflow": 600.0, "marketCap": 10000.0, "longName": "Acme Corp",
                 "recommendationKey": "buy", "recommendationMean": 2.0, "trailingAnnualDividendYield": 0.01},
        "income": _income(), "cashflow": None, "balance": None,
        "earn_est": pd.DataFrame({"avg": [5.5, 6.5], "low": [5.0, 6.0], "high": [6.0, 7.0],
                                  "yearAgoEps": [5.0, 5.5], "numberOfAnalysts": [10, 10],
                                  "growth": [0.10, 0.18]}, index=["0y", "+1y"]),
        "rev_est": None, "eps_trend": None, "earn_hist": None,
        "targets": {"mean": 130.0, "high": 150.0, "low": 90.0, "median": 128.0},
        "recs": None, "updown": None, "insider": None, "calendar": {}, "hist": None, "spy": None, "tnx": 0.04,
    }
    raw.update(over)
    return raw


class TestBuildTearSheet:
    def test_full_shape(self):
        out = ts._build_tear_sheet("ACME", _raw())
        assert out["symbol"] == "ACME" and "error" not in out
        assert out["profile"]["name"] == "Acme Corp"
        for key in ("snapshot", "performance", "financials", "balanceSheet", "valuation", "estimates",
                    "earningsTrack", "analysts", "ownership", "scorecard", "flags", "methodologyNote"):
            assert key in out
        assert out["estimates"]["growthUsed"] == pytest.approx(0.14)
        assert out["valuation"]["verdict"]["methodsUsed"] >= 2
        assert out["valuation"]["scenarios12m"]
        assert out["valuation"]["multiples"]["fcfYield"] == pytest.approx(0.06)
        assert out["balanceSheet"]["netDebt"] == -500.0

    def test_earnings_yield_vs_bond_uses_ten_year(self):
        v = ts._build_tear_sheet("ACME", _raw())["valuation"]
        assert v["tenYearYield"] == 0.04
        assert v["earningsYieldVsBond"] == pytest.approx(6.0 / 100.0 - 0.04)

    def test_no_price_is_an_error(self):
        out = ts._build_tear_sheet("NOPE", _raw(info={}))
        assert out["error"]

    def test_price_falls_back_to_history(self):
        out = ts._build_tear_sheet("ACME", _raw(info={"longName": "Acme"}, hist=pd.DataFrame({"Close": _series(60)})))
        assert out["snapshot"]["price"] == pytest.approx(_series(60).iloc[-1])

    def test_fund_like_symbol_degrades_without_crashing(self):
        out = ts._build_tear_sheet("SPY", _raw(info={"currentPrice": 500.0, "quoteType": "ETF", "longName": "S&P ETF"},
                                              income=None, earn_est=None, targets=None))
        assert out["profile"]["quoteType"] == "ETF"
        assert out["financials"]["history"] == []
        assert out["valuation"]["verdict"]["label"] == "Not enough data to judge"


class TestEndpoint:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(ts.router)
        return TestClient(app)

    def test_returns_computed_sheet_and_uppercases_symbol(self, client, monkeypatch):
        seen = []
        monkeypatch.setattr(ts, "_compute_tear_sheet", lambda s: seen.append(s) or {"symbol": s, "ok": True})
        r = client.get("/api/tear-sheet/ acme ")
        assert r.status_code == 200 and r.json() == {"symbol": "ACME", "ok": True}
        assert seen == ["ACME"]

    def test_errors_are_not_cached(self, client, monkeypatch):
        writes = []
        monkeypatch.setattr(ts, "cache_set", lambda k, v: writes.append(k))
        monkeypatch.setattr(ts, "_compute_tear_sheet", lambda s: {"symbol": s, "error": "boom"})
        assert client.get("/api/tear-sheet/BAD").json()["error"] == "boom"
        assert writes == []

    def test_success_is_cached_under_symbol_key(self, client, monkeypatch):
        writes = []
        monkeypatch.setattr(ts, "cache_set", lambda k, v: writes.append(k))
        monkeypatch.setattr(ts, "_compute_tear_sheet", lambda s: {"symbol": s})
        client.get("/api/tear-sheet/aapl")
        assert writes == ["tearsheet:AAPL"]

    def test_cache_hit_skips_compute(self, client, monkeypatch):
        monkeypatch.setattr(ts, "cache_get", lambda *a, **k: {"symbol": "AAPL", "cached": True})
        monkeypatch.setattr(ts, "_compute_tear_sheet", lambda s: pytest.fail("should not recompute"))
        assert client.get("/api/tear-sheet/AAPL").json()["cached"] is True

    def test_compute_failure_returns_error_payload(self, monkeypatch):
        monkeypatch.setattr(ts, "_fetch_raw", lambda s: (_ for _ in ()).throw(RuntimeError("network down")))
        assert ts._compute_tear_sheet("X") == {"symbol": "X", "error": "network down"}
