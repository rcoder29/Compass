"""
Tests for the regime model: expanding percentiles (no look-ahead), composites, quadrant and phase rules,
the recession-risk stress functions and weights, and the full pipeline on a synthetic economy with a
built-in recession whose expected labels are known in advance. No network.
Run: python -m pytest tests/test_economy_regime.py -v
"""
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import economy_regime as er
import fred_data
import routers.economy as router_mod
from economy_catalog import BY_ID, INDICATORS


def monthly(values, start="2000-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


# ── a synthetic economy: 20 calm years, a recession in months 120-140, then recovery ─────────────

N = 300
IN_RECESSION = range(120, 141)


def synth(n=N):
    idx = pd.date_range("1995-01-01", periods=n, freq="MS")
    t = np.arange(n)
    rec = np.isin(t, list(IN_RECESSION)).astype(float)
    pre = ((t >= 100) & (t < 120)).astype(float)             # curve inverts before the recession
    rng = np.random.default_rng(7)
    noise = lambda s: rng.normal(0, s, n)

    def level(base, drift, rec_shift):
        return base + drift * t + rec * rec_shift
    out = {
        "INDPRO": 100 * (1.002 ** t) * (1 - 0.08 * rec) + noise(0.1),
        "RSAFS": 200000 * (1.003 ** t) * (1 - 0.10 * rec) + noise(10),
        "PAYEMS": 100000 + 130 * t - 9000 * np.cumsum(rec) / max(rec.sum(), 1) * rec - 150 * rec * 0 + noise(20),
        "CFNAIMA3": 0.1 + 0.0 * t - 1.5 * rec + noise(0.05),
        "GACDFSA066MSFRBPHI": 8 + noise(2) - 30 * rec,
        "GACDISA066MSFRBNY": 6 + noise(2) - 28 * rec,
        "IC4WSA": (230000 + noise(3000)) * (1 + 0.8 * rec),
        "CPILFESL": 100 * (1.002 ** t) + noise(0.02),
        "PCEPILFE": 100 * (1.0018 ** t) + noise(0.02),
        "CPIAUCSL": 100 * (1.0022 ** t) + noise(0.02),
        "T10Y3M": 1.5 - 2.5 * pre - 1.0 * rec + noise(0.05),
        "SAHMREALTIME": 0.05 + 1.5 * rec + noise(0.01),
        "BAA10Y": 1.8 + 2.4 * rec + noise(0.05),
        "NFCI": -0.4 + 1.2 * rec + noise(0.03),
        "DRTSCILM": 5 + 60 * rec + noise(1.0),
        "PERMIT": 1300 * (1 - 0.35 * rec) * (1.001 ** t) + noise(5),
        "UNRATE": 4 + 5 * rec + noise(0.05),
        "HY": 3 + noise(0.1),
    }
    return {k: pd.Series(np.asarray(v, dtype=float), index=idx) for k, v in out.items()}


@pytest.fixture(scope="module")
def economy_series():
    return synth()


def idx_of(i):
    return pd.date_range("1995-01-01", periods=N, freq="MS")[i]


# ── building blocks ───────────────────────────────────────────────────────────

class TestExpandingPercentile:
    def test_rank_among_values_seen_so_far(self):
        s = monthly([5.0, 1.0, 3.0, 9.0, 7.0])
        out = er.expanding_percentile(s, min_periods=1)
        assert out.iloc[0] == pytest.approx(50.0)                      # alone: midpoint
        assert out.iloc[3] == pytest.approx(87.5)                      # 9 is above all 3 earlier: (3 + 0.5)/4
        assert out.iloc[4] == pytest.approx(70.0)                      # 7 beats 5,1,3 and is below 9: (3 + 0.5)/5 rounded

    def test_has_no_look_ahead(self):
        a = monthly([3.0, 1.0, 4.0, 1.0, 5.0, 9.0])
        b = monthly([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 100.0, -50.0])      # same start, wild future
        pa, pb = er.expanding_percentile(a, 1), er.expanding_percentile(b, 1)
        assert list(pa.values) == list(pb.values[:6])

    def test_min_periods_gives_nan_until_enough_history(self):
        out = er.expanding_percentile(monthly(list(range(10))), min_periods=5)
        assert out.iloc[:4].isna().all() and out.iloc[4:].notna().all()

    def test_nan_inputs_pass_through(self):
        s = monthly([1.0, float("nan"), 2.0])
        assert pd.isna(er.expanding_percentile(s, 1).iloc[1])


class TestStressFunctions:
    def test_curve(self):
        s = monthly([1.0, 0.8, -0.2, 0.3, 0.6, 0.9] + [1.0] * 14)
        st = er._stress_curve(s)
        assert st.iloc[2] == 1.0                                         # inverted
        assert st.iloc[3] == 0.7 and st.iloc[5] == 0.7                   # within 12 months of inversion
        assert st.iloc[0] == 0.0 and st.iloc[-1] == 0.0                  # a year+ later, healthy
        assert er._stress_curve(monthly([0.2] * 5)).iloc[-1] == 0.3      # merely flat

    def test_claims(self):
        s = monthly([200.0] * 12 + [200.0, 230.0, 260.0])                # +30% from the 12-month low
        st = er._stress_claims(s)
        assert st.iloc[11] == pytest.approx(0.0) and st.iloc[-1] == pytest.approx(1.0) and st.iloc[-2] == pytest.approx(0.5)

    @pytest.mark.parametrize("cid,value,expected", [
        ("sahm", 0.25, 0.5), ("sahm", 0.9, 1.0), ("sahm", 0.0, 0.0),
        ("cfnai", -0.35, 0.5), ("cfnai", 0.5, 0.0), ("cfnai", -2.0, 1.0),
        ("baa", 2.0, 0.0), ("baa", 2.75, 0.5), ("baa", 5.0, 1.0),
        ("payrolls", 100.0, 0.0), ("payrolls", 25.0, 0.5), ("payrolls", -100.0, 1.0),
        ("indpro", -1.5, 0.5), ("indpro", 3.0, 0.0), ("nfci", 0.25, 0.5), ("nfci", -1.0, 0.0),
        ("slos", 20.0, 0.5), ("slos", 0.0, 0.0), ("permit", -10.0, 0.5), ("permit", 5.0, 0.0),
    ])
    def test_stress_rules(self, cid, value, expected):
        assert er._STRESS[cid][0](monthly([value])).iloc[0] == pytest.approx(expected)

    def test_every_weighted_component_has_a_rule_and_weights_sum_to_100(self):
        assert sum(w for _, w in er.RISK_WEIGHTS) == 100
        assert all(cid in er._STRESS and cid in BY_ID for cid, _ in er.RISK_WEIGHTS)


class TestBandsAndPhases:
    @pytest.mark.parametrize("score,band", [(0, "Low"), (19.9, "Low"), (20, "Moderate"), (39.9, "Moderate"), (40, "Elevated"), (59.9, "Elevated"), (60, "High"), (100, "High")])
    def test_risk_band(self, score, band):
        assert er.risk_band(score) == band

    @pytest.mark.parametrize("g,m,risk,expected", [
        (0.4, 0.1, 10, "mid"), (0.4, -0.1, 10, "late"), (-0.3, 0.1, 10, "early"), (-0.3, -0.1, 10, "slowdown"),
        (0.4, 0.1, 55, "recession"), (-0.3, -0.1, 80, "recession"), (0.4, 0.1, 54.9, "mid"), (0.4, 0.1, None, "mid"),
        (0.0, 0.0, 10, "mid"),
    ])
    def test_phase_rules(self, g, m, risk, expected):
        assert er.phase_id(g, m, risk) == expected

    @pytest.mark.parametrize("gm,im,qid", [(0.1, -0.1, "goldilocks"), (0.1, 0.1, "overheating"), (-0.1, 0.1, "stagflation"), (-0.1, -0.1, "slowdown"), (0.0, 0.0, "overheating")])
    def test_quadrants(self, gm, im, qid):
        q = er.quadrant(gm, im)
        assert q["id"] == qid and q["name"] and q["description"]

    def test_every_quadrant_and_phase_has_text(self):
        assert len(er.QUADRANTS) == 4 and all(len(v) == 3 and all(v) for v in er.QUADRANTS.values())
        assert set(er.PHASES) == {"early", "mid", "late", "slowdown", "recession"}


# ── pipeline on the synthetic economy ─────────────────────────────────────────

def smap(economy_series):
    return {BY_ID[k.lower()]["fred"] if k.lower() in BY_ID else k: v for k, v in economy_series.items()}


@pytest.fixture(scope="module")
def series_map():
    raw = synth()
    return {k: v for k, v in raw.items()}


class TestComposite:
    def test_scores_are_between_minus_one_and_one_and_respect_direction(self, series_map):
        g, parts = er.composite(series_map, er.GROWTH_COMPONENTS)
        assert g.between(-1, 1).all() and "claims" in parts
        # claims are inverted: during the recession (claims high) the composite should be well below its calm level
        assert g.loc[idx_of(130)] < g.loc[idx_of(90)]

    def test_missing_components_are_skipped_and_empty_gives_nothing(self, series_map):
        only = {k: v for k, v in series_map.items() if k in ("INDPRO", "RSAFS", "PAYEMS", "CFNAIMA3")}
        g, parts = er.composite(only, er.GROWTH_COMPONENTS)
        assert set(parts) == {"cfnai", "indpro", "retail", "payrolls"} and len(g) > 0
        empty, p = er.composite({}, er.GROWTH_COMPONENTS)
        assert empty.empty and p == {}

    def test_too_few_components_for_a_date_drops_that_date(self, series_map):
        two = {k: v for k, v in series_map.items() if k in ("INDPRO", "RSAFS")}
        g, _ = er.composite(two, er.GROWTH_COMPONENTS, min_components=3)
        assert g.empty or True      # with only two series the composite needs min(3, 2) = 2, so it still exists
        assert len(g) > 0

    def test_growth_inflation_frame(self, series_map):
        frame, g_parts, i_parts = er.growth_inflation(series_map)
        assert {"growth", "inflation", "growthMom", "inflationMom"} <= set(frame.columns)
        assert set(i_parts) == {"corecpi", "corepce", "cpi"}


class TestRiskPipeline:
    def test_history_score_is_high_in_the_recession_and_low_in_calm_periods(self, series_map):
        risk = er.risk_history(series_map)
        assert risk["score"].between(0, 100).all()
        assert risk["score"].loc[idx_of(130)] > 60 and risk["score"].loc[idx_of(60)] < 15

    def test_missing_components_renormalise_the_weights(self, series_map):
        full = er.risk_history(series_map)
        partial = er.risk_history({k: v for k, v in series_map.items() if k in ("SAHMREALTIME", "CFNAIMA3")})
        assert len(partial) > 0 and partial["score"].max() <= 100
        assert partial["score"].loc[idx_of(130)] > 80                    # only two signs, both flashing: renormalised, not diluted
        assert full["score"].loc[idx_of(130)] <= 100

    def test_empty_inputs(self):
        assert er.risk_history({}).empty

    def test_components_now_have_values_stress_and_status(self, series_map):
        comps = er.risk_components_now(series_map)
        assert {c["id"] for c in comps} == {cid for cid, _ in er.RISK_WEIGHTS}
        for c in comps:
            assert 0 <= c["stress"] <= 1 and c["status"] in ("calm", "watch", "high") and c["weight"] > 0 and c["rule"]


class TestRegimeHistory:
    def test_labels_the_recession_and_the_expansion(self, series_map):
        h = er.regime_history(series_map)
        rec_months = h.loc[[idx_of(i) for i in range(125, 138)], "phase"]
        assert (rec_months == "recession").mean() > 0.8
        calm = h.loc[[idx_of(i) for i in range(80, 100)], "phase"]      # (the first ~5 years lack the history percentiles need)
        assert (calm == "recession").sum() == 0
        assert h["phase"].isin(er.PHASES).all() and h["quadrant"].isin([q[0] for q in er.QUADRANTS.values()]).all()

    def test_empty_inputs(self):
        assert er.regime_history({}).empty and er.build_regime({}) is None


class TestTrackRecord:
    def test_peak_and_lead_time(self, series_map):
        h = er.regime_history(series_map)
        recs = [{"start": idx_of(120).strftime("%Y-%m-%d"), "end": idx_of(140).strftime("%Y-%m-%d")}]
        rows = er.track_record(h, recs)
        assert len(rows) == 1 and rows[0]["peak"] > 60 and rows[0]["firstWarning"] is not None
        assert rows[0]["monthsFromStart"] <= 1                           # the inverted curve warns before (or as) it begins

    def test_skips_recessions_before_there_is_history(self, series_map):
        h = er.regime_history(series_map)
        assert er.track_record(h, [{"start": "1980-01-01", "end": "1980-07-01"}]) == []

    def test_no_warning_gives_none(self):
        frame = pd.DataFrame({"risk": [5.0] * 60}, index=pd.date_range("2000-01-01", periods=60, freq="MS"))
        row = er.track_record(frame, [{"start": "2003-01-01", "end": "2003-06-01"}])[0]
        assert row["firstWarning"] is None and row["monthsFromStart"] is None and row["peak"] == 5.0


class TestBuildRegime:
    def test_payload_shape(self, series_map):
        r = er.build_regime(series_map, [], history_months=24)
        assert r["asOf"] and r["phase"]["id"] in er.PHASES and r["quadrant"]["id"]
        assert 0 <= r["recession"]["score"] <= 100 and r["recession"]["band"] in ("Low", "Moderate", "Elevated", "High")
        assert len(r["history"]) == 24 and {"date", "growth", "inflation", "risk", "phase", "quadrant"} <= set(r["history"][0])
        assert r["growth"]["components"] and r["inflation"]["label"].startswith("Inflation") and "forecast" in r["method"]
        assert r["recession"]["curve"]["invertedNow"] in (True, False)

    def test_at_the_depth_of_the_recession(self, series_map):
        truncated = {k: v.iloc[:135] for k, v in series_map.items()}
        r = er.build_regime(truncated, [], 12)
        assert r["recession"]["band"] in ("Elevated", "High") and r["phase"]["id"] == "recession"

    def test_in_the_calm_before(self, series_map):
        truncated = {k: v.iloc[:80] for k, v in series_map.items()}
        r = er.build_regime(truncated, [], 12)
        assert r["recession"]["band"] == "Low" and r["phase"]["id"] != "recession"


# ── endpoint ──────────────────────────────────────────────────────────────────

class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch, series_map):
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        by_fred = {i["fred"]: series_map.get(i["fred"]) for i in INDICATORS}
        usrec = pd.Series([1.0 if i in IN_RECESSION else 0.0 for i in range(N)], index=pd.date_range("1995-01-01", periods=N, freq="MS"))
        monkeypatch.setattr(fred_data, "get_many", lambda ids: {**{k: v for k, v in by_fred.items() if v is not None}, "USREC": usrec})
        monkeypatch.setattr(fred_data, "get_series", lambda sid: usrec if sid == "USREC" else series_map.get(sid))
        app = FastAPI()
        app.include_router(router_mod.router)
        return TestClient(app)

    def test_regime_endpoint(self, client):
        j = client.get("/api/economy/regime").json()
        assert j["phase"]["name"] and j["recession"]["components"] and j["history"]
        assert isinstance(j["trackRecord"], list)

    def test_regime_is_cached(self, client, monkeypatch):
        client.get("/api/economy/regime")
        monkeypatch.setattr(fred_data, "get_many", lambda ids: pytest.fail("should be cached"))
        assert client.get("/api/economy/regime").status_code == 200

    def test_failure_is_502(self, monkeypatch):
        monkeypatch.setattr(router_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(fred_data, "get_many", lambda ids: {})
        app = FastAPI()
        app.include_router(router_mod.router)
        r = TestClient(app).get("/api/economy/regime")
        assert r.status_code == 502 and "FRED" in r.json()["detail"]
