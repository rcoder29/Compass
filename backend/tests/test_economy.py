"""
Tests for the economy engine: FRED parsing/caching, transforms, percentile/trend/signal maths against
hand-computed numbers, the indicator catalog's integrity, and the endpoints. No network.
Run: python -m pytest tests/test_economy.py -v
"""
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import economy
import economy_catalog as cat
import fred_data
import routers.economy as router_mod


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    store = {}
    for mod in (fred_data, router_mod):
        monkeypatch.setattr(mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(mod, "cache_set", lambda k, v: store.__setitem__(k, v))
    return store


def monthly(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def meta(**over):
    base = {"id": "x", "fred": "X", "name": "X", "category": "growth", "unit": "%", "transform": "level", "freq": "M", "hib": True,
            "lead": "coincident", "horizon": "medium", "what": "w", "why": "y", "read": "r", "scale": 1.0}
    base.update(over)
    return base


# ── FRED loader ───────────────────────────────────────────────────────────────

class TestFredParsing:
    def test_parses_values_and_treats_dots_as_missing(self):
        s = fred_data._parse_csv("observation_date,UNRATE\n2026-01-01,4.1\n2026-02-01,.\n2026-03-01,4.3\n")
        assert list(s.values) == [4.1, 4.3] and s.index[0] == pd.Timestamp("2026-01-01")

    def test_sorts_by_date(self):
        s = fred_data._parse_csv("DATE,X\n2026-03-01,3\n2026-01-01,1\n")
        assert list(s.values) == [1.0, 3.0]

    @pytest.mark.parametrize("text", ["", "a\n", "DATE,X\n", "DATE,X\n2026-01-01,.\n", "not,csv,at,all\nx"])
    def test_unusable_input_is_none(self, text):
        assert fred_data._parse_csv(text) is None


class Resp:
    def __init__(self, text="DATE,X\n2026-01-01,1\n2026-02-01,2\n", status=200):
        self.text, self.status_code = text, status


class TestGetSeries:
    def test_fetches_then_serves_from_cache(self, monkeypatch):
        calls = []
        monkeypatch.setattr(fred_data.requests, "get", lambda *a, **k: calls.append(k["params"]) or Resp())
        a = fred_data.get_series("UNRATE")
        b = fred_data.get_series("UNRATE")
        assert list(a.values) == [1.0, 2.0] and list(b.values) == [1.0, 2.0] and calls == [{"id": "UNRATE"}]

    def test_http_error_is_none_and_not_cached(self, monkeypatch, isolate):
        monkeypatch.setattr(fred_data.requests, "get", lambda *a, **k: Resp(status=404))
        assert fred_data.get_series("NOPE") is None and isolate == {}

    def test_retries_once_after_a_network_error(self, monkeypatch):
        attempts = []

        def flaky(*a, **k):
            attempts.append(1)
            if len(attempts) == 1:
                raise ConnectionError("reset")
            return Resp()
        monkeypatch.setattr(fred_data.requests, "get", flaky)
        assert fred_data.get_series("X") is not None and len(attempts) == 2

    def test_gives_up_after_two_failures(self, monkeypatch):
        monkeypatch.setattr(fred_data.requests, "get", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("slow")))
        assert fred_data.get_series("X") is None

    def test_get_many_returns_only_what_loaded(self, monkeypatch):
        monkeypatch.setattr(fred_data, "get_series", lambda sid: monthly([1.0, 2.0, 3.0]) if sid != "BAD" else None)
        out = fred_data.get_many(["A", "BAD", "B", "A"])
        assert set(out) == {"A", "B"}


class TestRecessionPeriods:
    def test_finds_spans(self):
        s = monthly([0, 1, 1, 0, 0, 1, 0])
        assert fred_data.recession_periods(s) == [{"start": "2020-02-01", "end": "2020-03-01"}, {"start": "2020-06-01", "end": "2020-06-01"}]

    def test_ongoing_recession_ends_at_the_last_observation(self):
        assert fred_data.recession_periods(monthly([0, 0, 1, 1])) == [{"start": "2020-03-01", "end": "2020-04-01"}]

    def test_none_and_empty(self):
        assert fred_data.recession_periods(None) == [] and fred_data.recession_periods(monthly([0, 0, 0])) == []


# ── transforms ────────────────────────────────────────────────────────────────

class TestTransforms:
    def test_level_applies_scale(self):
        assert list(economy.transform(monthly([1000.0, 2000.0]), "level", 0.001).values) == [1.0, 2.0]

    def test_yoy_matches_hand_calculation(self):
        s = monthly([100.0 + i for i in range(30)])                    # +1/month
        y = economy.transform(s, "yoy")
        assert y.index[0] == pd.Timestamp("2021-01-01")                # first month with a year-ago value
        assert y.iloc[0] == pytest.approx((112 / 100 - 1) * 100)
        assert y.iloc[-1] == pytest.approx((129 / 117 - 1) * 100)

    def test_yoy_needs_a_year_of_history(self):
        assert economy.transform(monthly([1.0] * 11), "yoy").empty

    def test_yoy_skips_when_the_year_ago_point_is_missing(self):
        s = monthly([100.0] * 24).drop(pd.Timestamp("2020-06-01"))
        y = economy.transform(s, "yoy")
        assert pd.Timestamp("2021-06-01") not in y.index                 # a gap, not a bogus ratio

    def test_yoy_with_zero_base_is_dropped(self):
        s = monthly([0.0] + [1.0] * 12)
        assert pd.Timestamp("2021-01-01") not in economy.transform(s, "yoy").index

    def test_avg3_chg(self):
        s = monthly([100.0, 110.0, 130.0, 160.0, 200.0])               # diffs 10, 20, 30, 40
        out = economy.transform(s, "avg3_chg")
        assert list(out.values) == [20.0, 30.0]                         # mean(10,20,30), mean(20,30,40)

    def test_unknown_transform_raises(self):
        with pytest.raises(ValueError):
            economy.transform(monthly([1.0]), "log")

    def test_drops_nans_and_sorts(self):
        s = pd.Series([3.0, float("nan"), 1.0], index=pd.to_datetime(["2020-03-01", "2020-02-01", "2020-01-01"]))
        assert list(economy.transform(s, "level").values) == [1.0, 3.0]


class TestLagged:
    def test_finds_the_value_one_year_back(self):
        s = monthly(list(range(24)))
        assert economy.lagged(s, pd.DateOffset(years=1), 50).iloc[12] == 0.0

    def test_nan_when_history_is_too_short(self):
        assert economy.lagged(monthly(list(range(24))), pd.DateOffset(years=1), 50).iloc[:12].isna().all()

    def test_tolerance_rejects_a_stale_match(self):
        s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2020-01-01", "2021-12-01"]))
        assert pd.isna(economy.lagged(s, pd.DateOffset(years=1), 30).iloc[1])       # nearest earlier point is ~11 months off


# ── statistics ────────────────────────────────────────────────────────────────

class TestStats:
    def test_percentile_rank(self):
        s = monthly([1.0, 2.0, 3.0, 4.0, 5.0])
        assert economy.percentile_rank(s, 5.0) == pytest.approx(90.0)     # 4 below + half of 1 tie, over 5
        assert economy.percentile_rank(s, 0.0) == 0.0 and economy.percentile_rank(s, 99.0) == 100.0

    def test_percentile_of_empty_is_nan(self):
        assert pd.isna(economy.percentile_rank(pd.Series([], dtype=float), 1.0))

    def test_zscore(self):
        s = monthly([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 20.0])
        assert economy.zscore(s) == pytest.approx((20 - s.mean()) / s.std())

    def test_zscore_needs_enough_data_and_variance(self):
        assert economy.zscore(monthly([1.0] * 5)) is None and economy.zscore(monthly([2.0] * 12)) is None


class TestTrend:
    def test_rising_falling_and_flat(self):
        base = [100.0 + (i % 3) * 0.2 for i in range(60)]                  # tiny wiggle
        assert economy.trend(monthly(base + [110.0]))["direction"] == "rising"
        assert economy.trend(monthly(base + [90.0]))["direction"] == "falling"
        assert economy.trend(monthly(base + [base[-3]]))["direction"] == "flat"

    def test_change3m_is_the_difference_to_three_months_ago(self):
        assert economy.trend(monthly([1.0, 2.0, 3.0, 5.0]))["change3m"] == pytest.approx(4.0)

    def test_a_crisis_spike_does_not_turn_every_move_into_noise(self):
        """Regression: a plain standard deviation made normal moves look flat after 2020."""
        calm = [100.0 + (i % 4) * 0.5 for i in range(100)]
        spike = calm[:40] + [200.0] + calm[40:]                           # one huge outlier
        out = economy.trend(monthly(spike + [spike[-3] + 5.0]))
        assert out["direction"] == "rising"

    def test_constant_series_with_a_move(self):
        assert economy.trend(monthly([5.0] * 20 + [6.0]))["direction"] == "rising"
        assert economy.trend(monthly([5.0] * 21))["direction"] == "flat"

    def test_short_series_has_no_three_month_change(self):
        assert economy.trend(monthly([1.0, 2.0]))["change3m"] is None


# ── signal ────────────────────────────────────────────────────────────────────

class TestSignal:
    def test_warning_levels_override_everything(self):
        m = meta(warn_below=0.0)
        assert economy.signal(m, -1.0, "rising")["status"] == "cautionary"
        assert economy.signal(meta(warn_above=0.5), 0.6, "falling")["status"] == "cautionary"

    def test_comfort_band(self):
        m = meta(hib=False, band=(1.5, 3.0))
        assert economy.signal(m, 2.0, "rising")["status"] == "supportive"
        assert economy.signal(m, 3.4, "falling")["status"] == "cautionary" and "Above" in economy.signal(m, 3.4, "falling")["reason"]
        assert "Below" in economy.signal(m, 1.0, "rising")["reason"]

    def test_direction_versus_which_way_is_better(self):
        assert economy.signal(meta(hib=True), 5, "rising")["status"] == "supportive"
        assert economy.signal(meta(hib=True), 5, "falling")["status"] == "cautionary"
        assert economy.signal(meta(hib=False), 5, "falling")["status"] == "supportive"
        assert economy.signal(meta(hib=False), 5, "rising")["status"] == "cautionary"

    def test_flat_is_neutral_and_undirected_indicators_are_neutral(self):
        assert economy.signal(meta(hib=True), 5, "flat")["status"] == "neutral"
        assert economy.signal(meta(hib=None), 5, "rising")["status"] == "neutral"

    def test_improving_from_an_extreme_is_only_neutral(self):
        s = economy.signal(meta(hib=True), 5, "rising", pct=3.0)
        assert s["status"] == "neutral" and "weakest" in s["reason"]
        assert economy.signal(meta(hib=False), 5, "falling", pct=97.0)["status"] == "neutral"

    def test_softening_from_a_strong_level_is_neutral(self):
        s = economy.signal(meta(hib=True), 5, "falling", pct=96.0)
        assert s["status"] == "neutral" and "strongest" in s["reason"]

    def test_mid_history_keeps_the_directional_signal(self):
        assert economy.signal(meta(hib=True), 5, "rising", pct=50.0)["status"] == "supportive"

    def test_warning_level_beats_the_percentile_tempering(self):
        assert economy.signal(meta(hib=True, warn_below=0.0), -1.0, "rising", pct=2.0)["status"] == "cautionary"


# ── summaries ─────────────────────────────────────────────────────────────────

class TestSummarize:
    def series(self):
        return monthly([100.0 + i for i in range(40)], start="2023-01-01")

    def test_row_contents(self):
        row = economy.summarize(meta(), self.series())
        assert row["value"] == 139.0 and row["previous"] == 138.0 and row["date"] == "2026-04-01"
        assert row["change3m"] == 3.0 and row["change1y"] == 12.0
        assert row["percentile"] > 95 and len(row["spark"]) == 24 and row["historyStart"] == "2023-01-01"
        assert {"trend", "signal", "reason", "zscore10y", "stale"} <= set(row)

    def test_yoy_transform_is_applied(self):
        row = economy.summarize(meta(transform="yoy"), self.series())
        assert row["value"] == pytest.approx((139 / 127 - 1) * 100, abs=1e-3)

    def test_unusable_series_give_none(self):
        assert economy.summarize(meta(), None) is None and economy.summarize(meta(), monthly([1.0, 2.0])) is None

    def test_old_data_is_flagged_stale(self):
        old = monthly([1.0] * 30, start="2015-01-01")
        assert economy.summarize(meta(), old)["stale"] is True
        this_month = pd.Timestamp.now().normalize().replace(day=1)
        recent = pd.Series(range(30), index=pd.date_range(end=this_month, periods=30, freq="MS"), dtype=float)
        assert economy.summarize(meta(), recent)["stale"] is False


class TestBuildCatalog:
    def test_groups_by_category_with_counts_and_lists_missing(self):
        s = monthly([100.0 + i for i in range(40)], start="2023-01-01")
        out = economy.build_catalog({"UNRATE": s, "CPIAUCSL": s})
        names = [c["id"] for c in out["categories"]]
        assert names == ["growth", "labor", "inflation", "rates", "credit", "housing", "consumer", "global"][:0] or set(names) <= {"labor", "inflation"}
        assert sum(out["overall"].values()) == 2 and "gdp" in out["missing"] and "unrate" not in out["missing"]
        assert out["asOf"] == "2026-04-01"
        for c in out["categories"]:
            assert sum(c["counts"].values()) == len(c["indicators"])

    def test_empty_input(self):
        out = economy.build_catalog({})
        assert out["categories"] == [] and out["asOf"] is None and len(out["missing"]) == len(cat.INDICATORS)


class TestDetail:
    def test_points_stats_and_related(self):
        s = monthly([100.0 + i for i in range(60)], start="2020-01-01")
        d = economy.detail(meta(id="unrate"), s, [{"start": "2020-03-01", "end": "2020-04-01"}])
        assert len(d["points"]) == 60 and d["points"][0] == ["2020-01-01", 100.0]
        assert d["recessions"] == [{"start": "2020-03-01", "end": "2020-04-01"}]
        assert d["stats"]["allTime"]["min"] == 100.0 and d["stats"]["allTime"]["max"] == 159.0 and d["stats"]["observations"] == 60
        assert d["stats"]["tenYear"] is not None and d["meta"]["what"] == "w" and d["summary"]["value"] == 159.0

    def test_daily_series_are_thinned_to_weekly(self):
        s = pd.Series(range(5000), index=pd.date_range("2000-01-03", periods=5000, freq="B"), dtype=float)
        d = economy.detail(meta(freq="D"), s, [])
        assert len(d["points"]) < 1200

    def test_missing_series(self):
        assert economy.detail(meta(), None, []) is None


# ── catalog integrity ─────────────────────────────────────────────────────────

class TestCatalog:
    def test_unique_ids_and_known_categories(self):
        ids = [i["id"] for i in cat.INDICATORS]
        assert len(ids) == len(set(ids)) and len(ids) >= 45
        assert {i["category"] for i in cat.INDICATORS} <= {c["id"] for c in cat.CATEGORIES}

    def test_every_category_is_used(self):
        assert {c["id"] for c in cat.CATEGORIES} == {i["category"] for i in cat.INDICATORS}

    @pytest.mark.parametrize("field", ["name", "what", "why", "read", "fred", "unit"])
    def test_required_text_is_present(self, field):
        assert all(str(i[field]).strip() for i in cat.INDICATORS)

    def test_enumerated_fields_are_valid(self):
        for i in cat.INDICATORS:
            assert i["transform"] in ("level", "yoy", "avg3_chg"), i["id"]
            assert i["freq"] in ("D", "W", "M", "Q"), i["id"]
            assert i["lead"] in ("leading", "coincident", "lagging", "market"), i["id"]
            assert i["horizon"] in ("short", "medium", "long"), i["id"]
            assert i["hib"] in (True, False, None), i["id"]

    def test_bands_and_warnings_are_sane(self):
        for i in cat.INDICATORS:
            if i.get("band"):
                lo, hi = i["band"]
                assert lo < hi, i["id"]
            if i.get("warn_above") is not None and i.get("warn_below") is not None:
                assert i["warn_below"] < i["warn_above"], i["id"]

    def test_explanations_are_not_placeholders_and_end_cleanly(self):
        for i in cat.INDICATORS:
            for f in ("what", "why", "read"):
                assert len(i[f]) > 25 and i[f].rstrip()[-1] in ".)'", (i["id"], f)

    def test_indicators_the_regime_model_relies_on_exist(self):
        needed = {"cfnai", "indpro", "retail", "payrolls", "claims", "philly", "empire", "corecpi", "corepce", "be5y5y",
                  "curve10_3m", "curve10_2", "sahm", "baa", "nfci", "permit", "umcsent", "unrate", "hy", "slos"}
        assert needed <= set(cat.BY_ID)


# ── endpoints ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    s = monthly([100.0 + i for i in range(40)], start="2023-01-01")
    monkeypatch.setattr(fred_data, "get_many", lambda ids: {i: s for i in ids})
    monkeypatch.setattr(fred_data, "get_series", lambda sid: monthly([0, 0, 1, 1, 0] * 8, start="2020-01-01") if sid == "USREC" else s)
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


class TestEndpoints:
    def test_catalog(self, client):
        j = client.get("/api/economy/indicators").json()
        assert j["overall"] and j["categories"] and j["asOf"] and j["missing"] == []

    def test_catalog_is_cached(self, client, monkeypatch):
        client.get("/api/economy/indicators")
        monkeypatch.setattr(fred_data, "get_many", lambda ids: pytest.fail("should be served from cache"))
        assert client.get("/api/economy/indicators").status_code == 200

    def test_catalog_failure_is_502(self, monkeypatch):
        monkeypatch.setattr(fred_data, "get_many", lambda ids: {})
        app = FastAPI()
        app.include_router(router_mod.router)
        r = TestClient(app).get("/api/economy/indicators")
        assert r.status_code == 502 and "FRED" in r.json()["detail"]

    def test_detail_includes_recessions(self, client):
        j = client.get("/api/economy/indicator/unrate").json()
        assert j["meta"]["id"] == "unrate" and j["points"] and j["recessions"] and j["meta"]["what"]

    def test_unknown_indicator_is_404(self, client):
        assert client.get("/api/economy/indicator/nope").status_code == 404

    def test_detail_failure_is_502(self, monkeypatch):
        monkeypatch.setattr(fred_data, "get_series", lambda sid: None)
        app = FastAPI()
        app.include_router(router_mod.router)
        assert TestClient(app).get("/api/economy/indicator/unrate").status_code == 502
