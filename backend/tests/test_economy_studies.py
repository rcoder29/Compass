"""
Tests for Indicator Studies: episode detection and merging, forward-return alignment (publication lag,
no look-ahead), baseline/statistics maths, histogram binning, state builders, and the endpoints.
No network. Run: python -m pytest tests/test_economy_studies.py -v
"""
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import economy_studies as es
import fred_data
import market_history as mh
import routers.economy as router_mod


def idx(n, start="2000-01-01"):
    return pd.date_range(start, periods=n, freq="MS")


def bools(pattern, start="2000-01-01"):
    return pd.Series([c == "1" for c in pattern], index=idx(len(pattern), start))


# ── market_history helpers ────────────────────────────────────────────────────

class TestForwardReturns:
    def test_values(self):
        p = pd.Series([100.0, 110.0, 121.0, 133.1], index=idx(4))
        fr = mh.forward_returns(p, 1)
        assert fr.iloc[0] == pytest.approx(0.10) and fr.iloc[2] == pytest.approx(0.10) and pd.isna(fr.iloc[3])
        assert mh.forward_returns(p, 3).iloc[0] == pytest.approx(0.331)
        assert mh.forward_returns(p, 3).iloc[1:].isna().all()

    def test_single_entry(self):
        p = pd.Series([100.0, 150.0, 90.0], index=idx(3))
        assert mh.forward_return(p, idx(3)[0], 2) == pytest.approx(-0.10)
        assert mh.forward_return(p, idx(3)[1], 2) is None            # runs past the data
        assert mh.forward_return(p, pd.Timestamp("1990-01-01"), 1) is None

    def test_missing_month_in_the_middle_gives_nan_not_a_wrong_window(self):
        i = idx(6).delete(3)                                         # drop the 4th month
        p = pd.Series([100.0, 101.0, 102.0, 104.0, 105.0], index=i)
        fr = mh.forward_returns(p, 2)
        assert pd.isna(fr.iloc[1])                                   # Feb + 2 months = Apr, which doesn't exist


class TestMonthlyHistory:
    def test_caches_and_converts(self, monkeypatch):
        store, calls = {}, []
        monkeypatch.setattr(mh, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(mh, "cache_set", lambda k, v: store.__setitem__(k, v))
        daily = pd.DataFrame({"Close": [10.0, 11.0, 12.0, 13.0]}, index=pd.DatetimeIndex(
            ["2020-01-15", "2020-01-31", "2020-02-14", "2020-02-28"], tz="America/New_York"))

        class T:
            def __init__(self, s): pass
            def history(self, **kw):
                calls.append(kw)
                return daily
        monkeypatch.setattr(mh.yf, "Ticker", T)
        m = mh.get_monthly("ZZZ")
        assert list(m.values) == [11.0, 13.0] and m.index.tz is None and m.index[0] == pd.Timestamp("2020-01-01")
        assert calls[0]["interval"] == "1d" and calls[0]["period"] == "max"
        again = mh.get_monthly("ZZZ")
        assert len(calls) == 1 and list(again.values) == [11.0, 13.0]

    def test_failure_returns_none_and_is_not_cached(self, monkeypatch):
        store = {}
        monkeypatch.setattr(mh, "cache_get", lambda k, ttl=None: None)
        monkeypatch.setattr(mh, "cache_set", lambda k, v: store.__setitem__(k, v))

        class T:
            def __init__(self, s): pass
            def history(self, **kw): raise RuntimeError("boom")
        monkeypatch.setattr(mh.yf, "Ticker", T)
        assert mh.get_monthly("ZZZ") is None and store == {}

    def test_get_many_drops_failures(self, monkeypatch):
        monkeypatch.setattr(mh, "get_monthly", lambda s: None if s == "BAD" else pd.Series([1.0], index=idx(1)))
        assert set(mh.get_many_monthly(["A", "BAD", "A", "B"])) == {"A", "B"}


# ── episodes ──────────────────────────────────────────────────────────────────

class TestEpisodes:
    def test_runs(self):
        eps = es.episodes(bools("0011100000000000110"), min_gap=3)
        assert [(e["start"].strftime("%Y-%m"), e["months"]) for e in eps] == [("2000-03", 3), ("2001-05", 2)]

    def test_runs_close_together_merge(self):
        eps = es.episodes(bools("111000111"), min_gap=6)
        assert len(eps) == 1 and eps[0]["months"] == 9
        assert len(es.episodes(bools("111000111"), min_gap=2)) == 2

    def test_open_ended_run_and_empty(self):
        assert es.episodes(bools("0001"))[0]["months"] == 1
        assert es.episodes(bools("0000")) == []

    def test_nan_counts_as_false(self):
        s = pd.Series([True, np.nan, True], index=idx(3), dtype=object)
        assert len(es.episodes(s, min_gap=0)) == 2

    def test_entry_lag(self):
        assert es._entry(pd.Timestamp("2000-03-01"), 2) == pd.Timestamp("2000-05-01")


# ── statistics ────────────────────────────────────────────────────────────────

class TestStats:
    def test_basic(self):
        s = es._stats([0.10, -0.05, 0.20, 0.0])
        assert s["n"] == 4 and s["mean"] == pytest.approx(0.0625) and s["median"] == pytest.approx(0.05)
        assert s["pctPositive"] == 0.5 and s["best"] == 0.20 and s["worst"] == -0.05

    def test_ignores_nan_and_none_and_handles_empty(self):
        assert es._stats([None, float("nan"), 0.1])["n"] == 1
        assert es._stats([]) is None and es._stats([None]) is None

    def test_baseline_only_counts_from_sample_start(self):
        p = pd.Series(np.arange(100, 160, dtype=float), index=idx(60))
        b_all = es.baseline(p, 12, pd.Timestamp("2000-01-01"))
        b_late = es.baseline(p, 12, pd.Timestamp("2003-01-01"))
        assert b_all["n"] == 48 and b_late["n"] == 12 and b_all["pctPositive"] == 1.0


class TestHistogram:
    def test_bins_sum_to_100_and_clip_extremes(self):
        h = es.histogram([-0.7, -0.35, -0.05, 0.05, 0.05, 0.15, 1.5])
        assert sum(h) == pytest.approx(100.0, abs=0.5) and len(h) == len(es.HISTOGRAM_EDGES) - 1
        assert h[0] > 0 and h[-1] > 0                                 # -70% and +150% land in the open-ended end bins
        i = es.HISTOGRAM_EDGES.index(0)
        assert h[i] == pytest.approx(2 / 7 * 100, abs=0.1)            # two values in [0, 10)

    def test_empty(self):
        assert es.histogram([]) == [0.0] * (len(es.HISTOGRAM_EDGES) - 1)


# ── state builders ────────────────────────────────────────────────────────────

class TestStates:
    def test_fed_cutting_and_hiking(self):
        ff = pd.Series([5.0] * 30 + [5.0 - 0.25 * i for i in range(1, 11)] + [2.5] * 20, index=idx(60), dtype=float)
        m = {"FEDFUNDS": ff}
        cut = es.st_fed_cutting(m)
        assert not cut.iloc[20] and cut.iloc[40]
        hike_series = pd.Series([1.0] * 30 + [1.0 + 0.5 * i for i in range(1, 9)] + [5.0] * 22, index=idx(60), dtype=float)
        hike = es.st_fed_hiking({"FEDFUNDS": hike_series})
        assert not hike.iloc[20] and hike.iloc[37]

    def test_missing_inputs_return_none(self):
        for fn in (es.st_fed_cutting, es.st_curve_inverted, es.st_sahm, es.st_real_yield, es.st_dollar, es.st_oil, es.st_risk):
            assert fn({}) is None

    def test_short_series_return_none(self):
        assert es.st_real_yield({"DFII10": pd.Series([2.5] * 10, index=idx(10))}) is None

    def test_real_yield_threshold(self):
        s = pd.Series([1.0] * 30 + [2.5] * 10, index=idx(40), dtype=float)
        st = es.st_real_yield({"DFII10": s})
        assert not st.iloc[10] and st.iloc[-1]

    def test_oil_spike_is_year_over_year(self):
        s = pd.Series([50.0] * 24 + [80.0] * 12, index=idx(36), dtype=float)
        st = es.st_oil({"DCOILWTICO": s})
        assert st.iloc[-1] and not st.iloc[23]


# ── a whole study on synthetic data ───────────────────────────────────────────

def market(n=360):
    """A market that goes up 1%/month except it falls 3%/month for 12 months after months 60, 160 and 260."""
    r = np.full(n, 0.01)
    for s in (60, 160, 260):
        r[s + 1:s + 13] = -0.03
    return pd.Series(100 * np.cumprod(1 + r), index=idx(n))


class FakeStudy:
    def __init__(self, state, lag=0):
        self.d = {"id": "t", "name": "Test condition", "condition": "c", "question": "q", "indicators": ["x"], "lag": lag,
                  "state": lambda m: state}

    def __getitem__(self, k): return self.d[k]


class TestRunStudy:
    def state(self):
        s = pd.Series(False, index=idx(360))
        for e in (60, 160, 260):
            s.iloc[e:e + 3] = True
        return s

    def test_forward_returns_measured_from_entry_and_beat_nothing_by_construction(self):
        sp = market()
        r = es.run_study(FakeStudy(self.state()), {}, sp, {}, None)
        assert r["episodeCount"] == 3 and r["thin"] is True            # 3 < THIN_EPISODES
        h12 = next(h for h in r["horizons"] if h["months"] == 12)
        assert h12["episodes"]["n"] == 3 and h12["episodes"]["mean"] < 0 < h12["baseline"]["mean"]
        assert h12["episodes"]["pctPositive"] == 0.0
        assert r["episodes"][0]["entry"] == "2005-01" and r["episodes"][0]["forward"]["12"] == pytest.approx(0.97 * 0.97 ** 11 - 1 + 0.0, abs=0.35)

    def test_publication_lag_shifts_entry_and_changes_results(self):
        sp = market()
        base = es.run_study(FakeStudy(self.state(), lag=0), {}, sp, {}, None)
        lagged = es.run_study(FakeStudy(self.state(), lag=2), {}, sp, {}, None)
        assert lagged["episodes"][0]["entry"] == "2005-03" and base["episodes"][0]["entry"] == "2005-01"
        assert lagged["episodes"][0]["forward"]["12"] != base["episodes"][0]["forward"]["12"]
        assert lagged["study"]["lagMonths"] == 2

    def test_never_true_or_no_data_returns_none(self):
        sp = market()
        assert es.run_study(FakeStudy(pd.Series(False, index=idx(360))), {}, sp, {}, None) is None
        assert es.run_study(FakeStudy(None), {}, sp, {}, None) is None

    def test_currently_active_flag(self):
        s = pd.Series(False, index=idx(360)); s.iloc[-3:] = True
        assert es.run_study(FakeStudy(s), {}, market(), {}, None)["currentlyActive"] is True

    def test_episode_with_no_full_window_is_excluded_from_that_horizon(self):
        s = pd.Series(False, index=idx(360)); s.iloc[100:102] = True; s.iloc[-4:] = True      # last episode can't see 12m ahead
        r = es.run_study(FakeStudy(s), {}, market(), {}, None)
        assert r["episodeCount"] == 2
        assert next(h for h in r["horizons"] if h["months"] == 12)["episodes"]["n"] == 1
        assert next(h for h in r["horizons"] if h["months"] == 1)["episodes"]["n"] == 2

    def test_sector_response_uses_excess_over_spy(self):
        sp = market()
        spy = pd.Series(100 * 1.01 ** np.arange(360), index=idx(360))
        etfs = {"XLK": pd.Series(100 * 1.02 ** np.arange(360), index=idx(360)), "XLU": pd.Series(100 * 1.005 ** np.arange(360), index=idx(360))}
        s = pd.Series(False, index=idx(360)); s.iloc[250:252] = True; s.iloc[300:302] = True
        r = es.run_study(FakeStudy(s), {}, sp, etfs, spy)
        syms = [x["symbol"] for x in r["sectors12m"]]
        assert syms == ["XLK", "XLU"]                                  # sorted best first
        assert r["sectors12m"][0]["avgExcess"] > 0 > r["sectors12m"][1]["avgExcess"] and r["sectors12m"][0]["thin"] is True

    def test_json_safe(self):
        import json
        json.dumps(es.run_study(FakeStudy(self.state()), {}, market(), {}, None))


class TestHeadlineAndNotes:
    def test_headline_mentions_numbers_and_sample(self):
        sp = market()
        s = pd.Series(False, index=idx(360))
        for e in (30, 90, 160, 200, 260):
            s.iloc[e:e + 2] = True
        r = es.run_study(FakeStudy(s), {}, sp, {}, None)
        text = es.headline(r)
        assert "\u201cTest condition\u201d began" in text and "5 episodes" in text and "S&P 500" in text

    def test_notes_flag_thin_samples_and_lag(self):
        assert "too few" in es.notes(2, 0)[0] and "Still a small sample" in es.notes(10, 0)[0]
        assert "2 months after" in es.notes(10, 2)[1] and "observation month" in es.notes(10, 0)[1]
        assert "1 independent episode " in es.notes(1, 0)[0]


class TestCatalog:
    def test_unique_ids_and_complete_fields(self):
        ids = [s["id"] for s in es.STUDIES]
        assert len(ids) == len(set(ids)) and len(ids) >= 15
        for s in es.STUDIES:
            assert s["name"] and s["condition"] and s["question"] and callable(s["state"]) and s["lag"] in (0, 1, 2)
            assert all(i in __import__("economy_catalog").BY_ID for i in s["indicators"])

    def test_list_has_no_callables(self):
        import json
        json.dumps(es.study_list())


# ── endpoints ─────────────────────────────────────────────────────────────────

class TestEndpoints:
    @pytest.fixture
    def client(self, monkeypatch):
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        ff = pd.Series([5.0] * 100 + [5.0 - 0.25 * i for i in range(1, 11)] + [2.5] * 250, index=idx(360), dtype=float)
        monkeypatch.setattr(fred_data, "get_many", lambda ids: {"FEDFUNDS": ff})
        monkeypatch.setattr(mh, "get_many_monthly", lambda syms: {"^GSPC": market(), "SPY": market()})
        app = FastAPI(); app.include_router(router_mod.router)
        return TestClient(app)

    def test_list(self, client):
        j = client.get("/api/economy/studies").json()
        assert len(j["studies"]) >= 15 and {"id", "name", "question", "condition"} <= set(j["studies"][0])

    def test_study(self, client):
        j = client.get("/api/economy/studies/fed-cutting").json()
        assert j["episodeCount"] >= 1 and j["horizons"] and "headline" in j

    def test_unavailable_study_is_200_with_flag(self, client):
        j = client.get("/api/economy/studies/sahm").json()
        assert j["unavailable"] is True and j["study"]["id"] == "sahm"

    def test_unknown_404(self, client):
        assert client.get("/api/economy/studies/nope").status_code == 404

    def test_cached(self, client, monkeypatch):
        client.get("/api/economy/studies/fed-cutting")
        monkeypatch.setattr(fred_data, "get_many", lambda ids: pytest.fail("cached"))
        assert client.get("/api/economy/studies/fed-cutting").status_code == 200

    def test_no_market_data_is_502(self, client, monkeypatch):
        monkeypatch.setattr(mh, "get_many_monthly", lambda syms: {})
        assert client.get("/api/economy/studies/fed-cutting").status_code == 502
