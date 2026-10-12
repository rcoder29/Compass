"""
Tests for the shared market-regime summary (Home card and digest section): the summarisers, change detection against a per-day history,
failure isolation, the endpoint, and the digest section and its rendering. No network.
Run: python -m pytest tests/test_regime_summary.py -v
"""
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import digest_builder
import digest_render
import regime_summary as rs
import routers.home_regime as router_mod
from tests.test_digest import build, ECON  # noqa: F401  (reuses the digest test helpers and fixtures)


def regime_raw(**over):
    d = {"asOf": "2026-08-01", "phase": {"id": "late", "name": "Late cycle"}, "quadrant": {"id": "slowdown", "name": "Slowdown"},
         "growth": {"label": "Growth above its norm and weakening"}, "inflation": {"label": "Inflation near its norm"},
         "recession": {"score": 31.4, "band": "Moderate", "curve": {"invertedNow": True},
                       "components": [{"name": "Sahm rule", "status": "high"}, {"name": "Payrolls", "status": "watch"}, {"name": "Claims", "status": "calm"}]}}
    d.update(over)
    return d


def scoreboard():
    def sec(sym, name, ret, excess):
        return {"symbol": sym, "name": name, "returns": {"3M": {"total": ret}}, "excess": {"3M": excess}}
    return {"asOf": "2026-10-09", "benchmark": {"returns": {"3M": {"total": 0.04}}},
            "sectors": [sec("XLK", "Technology", 0.12, 0.08), sec("XLE", "Energy", 0.10, 0.06), sec("XLV", "Health Care", 0.07, 0.03), sec("XLF", "Financials", 0.04, 0.0),
                        sec("XLY", "Consumer Disc", 0.01, -0.03), sec("XLP", "Staples", -0.01, -0.05), sec("XLU", "Utilities", -0.03, -0.07)]}


def themes_built():
    def th(i, name, ret): return {"id": i, "name": name, "short": name[:4], "basket": {"3M": {"mean": ret}}}
    return {"asOf": "2026-10-09", "benchmark": {"3M": 0.05}, "themes": [th("a", "Alpha", 0.15), th("b", "Beta", 0.09), th("c", "Gamma", 0.05), th("d", "Delta", 0.0), th("e", "Eps", -0.08)]}


def shorts_built():
    def r(sym, si, fee, key): return {"symbol": sym, "name": f"{sym} Inc", "siPctFloat": si, "changePct": 5.0, "borrow": {"fee": fee} if fee is not None else None,
                                      "displacement": {"key": key, "label": key.replace("_", " ")}}
    return {"settlement": "2026-09-15", "rows": [r("WOLF", 0.83, 1.2, "confirmed"), r("GRPN", 0.71, None, "none"), r("HTZ", 0.68, 13.5, "equity_leads"), r("LCID", 0.57, 2.0, "none"), r("SPRY", 0.48, 1.8, "none"), r("ONDS", 0.44, 2.3, "partial")],
            "summary": {"count": 100, "above30": 49, "hardToBorrow": 8, "displacement": {"confirmed": 7, "equity_leads": 34}, "biggestIncreases": [{"symbol": "USAR", "changePct": 26.9}]}}


class TestSummarisers:
    def test_regime(self):
        r = rs.summarize_regime(regime_raw())
        assert r["phase"] == {"id": "late", "name": "Late cycle"} and r["riskScore"] == 31.4 and r["riskBand"] == "Moderate"
        assert r["flashing"] == ["Sahm rule"] and r["watching"] == ["Payrolls"] and r["curveInverted"] is True and "weakening" in r["growth"]
        assert rs.summarize_regime(None) is None and rs.summarize_regime({}) is None

    def test_regime_without_recession_block(self):
        r = rs.summarize_regime(regime_raw(recession=None))
        assert r["riskScore"] is None and r["flashing"] == [] and r["curveInverted"] is None

    def test_sectors_leaders_and_laggards_against_spy(self):
        s = rs.summarize_sectors(scoreboard())
        assert [x["symbol"] for x in s["top"]] == ["XLK", "XLE", "XLV"] and [x["symbol"] for x in s["bottom"]] == ["XLU", "XLP", "XLY"] and s["spy3m"] == 0.04
        assert s["top"][0]["excess3m"] == 0.08 and s["bottom"][0]["name"] == "Utilities"            # the worst first

    def test_sectors_need_enough_data(self):
        sb = scoreboard(); sb["sectors"] = sb["sectors"][:4]
        assert rs.summarize_sectors(sb) is None and rs.summarize_sectors(None) is None and rs.summarize_sectors({"sectors": []}) is None
        sb2 = scoreboard(); sb2["sectors"][0]["excess"] = {}                                        # a sector missing its 3-month figure is skipped
        assert len(rs.summarize_sectors(sb2)["top"]) == 3

    def test_themes_ranked_by_return_over_spy(self):
        t = rs.summarize_themes(themes_built())
        assert [x["id"] for x in t["top"]] == ["a", "b", "c"] and [x["id"] for x in t["bottom"]] == ["e", "d"]
        assert t["top"][0]["vsSpy"] == pytest.approx(0.10) and t["bottom"][0]["vsSpy"] == pytest.approx(-0.13)

    def test_themes_absent_or_without_a_benchmark(self):
        assert rs.summarize_themes(None) is None and rs.summarize_themes({"themes": []}) is None
        b = themes_built(); b["benchmark"] = {}
        assert rs.summarize_themes(b) is None

    def test_shorts(self):
        s = rs.summarize_shorts(shorts_built())
        assert [x["symbol"] for x in s["top"]] == ["WOLF", "GRPN", "HTZ", "LCID", "SPRY"] and s["top"][0]["fee"] == 1.2 and s["top"][1]["fee"] is None
        assert s["settlement"] == "2026-09-15" and s["hardToBorrow"] == 8 and s["creditConfirms"] == 7 and s["biggestIncreases"][0]["symbol"] == "USAR"
        assert rs.summarize_shorts(None) is None and rs.summarize_shorts({"rows": []}) is None


class TestChanges:
    cur = rs.summarize_regime(regime_raw())

    def test_phase_change_and_risk_move(self):
        c = rs.changes_since(self.cur, {"2026-10-08": {"phase": "Mid-cycle expansion", "riskScore": 20.0}}, "2026-10-09")
        assert c == {"since": "2026-10-08", "phaseFrom": "Mid-cycle expansion", "phaseTo": "Late cycle", "riskFrom": 20.0, "riskTo": 31.4}

    def test_small_risk_moves_and_no_change_are_not_reported(self):
        assert rs.changes_since(self.cur, {"2026-10-08": {"phase": "Late cycle", "riskScore": 29.0}}, "2026-10-09") is None
        c = rs.changes_since(self.cur, {"2026-10-08": {"phase": "Late cycle", "riskScore": 20.0}}, "2026-10-09")
        assert c["phaseTo"] is None and c["riskFrom"] == 20.0

    def test_compares_with_the_latest_earlier_day_only(self):
        hist = {"2026-10-01": {"phase": "Early recovery", "riskScore": 5.0}, "2026-10-08": {"phase": "Late cycle", "riskScore": 30.0}, "2026-10-09": {"phase": "x", "riskScore": 99.0}}
        assert rs.changes_since(self.cur, hist, "2026-10-09") is None            # vs the 8th: nothing meaningful; today's own entry is ignored

    def test_no_history_or_no_regime(self):
        assert rs.changes_since(self.cur, {}, "2026-10-09") is None and rs.changes_since(None, {"2026-10-08": {"phase": "a", "riskScore": 1}}, "2026-10-09") is None

    def test_history_is_recorded_and_trimmed(self):
        h = rs.record_history({"2026-09-01": {"phase": "a", "riskScore": 1}, "2026-10-01": {"phase": "b", "riskScore": 2}}, "2026-10-09", self.cur)
        assert set(h) == {"2026-10-01", "2026-10-09"} and h["2026-10-09"] == {"phase": "Late cycle", "riskScore": 31.4}
        assert rs.record_history({"2026-10-01": {"phase": "b", "riskScore": 2}}, "2026-10-09", None) == {"2026-10-01": {"phase": "b", "riskScore": 2}}


class TestLoadSummary:
    def loaders(self, **over):
        base = {"regime": lambda: regime_raw(), "sectors": scoreboard, "themes": themes_built, "shorts": shorts_built}
        base.update(over)
        return base

    def test_assembles_everything_and_is_json_safe(self):
        out = rs.load_summary(date(2026, 10, 9), self.loaders())
        assert out["regime"]["phase"]["name"] == "Late cycle" and out["sectors"] and out["themes"] and out["shorts"] and out["errors"] == {} and out["date"] == "2026-10-09"
        json.dumps(out)

    def test_one_failing_source_is_isolated(self):
        out = rs.load_summary(date(2026, 10, 9), self.loaders(regime=lambda: (_ for _ in ()).throw(RuntimeError("FRED down"))))
        assert out["regime"] is None and out["sectors"] and "RuntimeError: FRED down" in out["errors"]["regime"]

    def test_cache_only_sources_may_simply_be_absent(self):
        out = rs.load_summary(date(2026, 10, 9), self.loaders(themes=lambda: None, shorts=lambda: None))
        assert out["themes"] is None and out["shorts"] is None and out["regime"] and out["errors"] == {}

    def test_history_accumulates_across_days_and_reports_a_change(self):
        rs.load_summary(date(2026, 10, 8), self.loaders(regime=lambda: regime_raw(phase={"id": "mid", "name": "Mid-cycle expansion"})))
        out = rs.load_summary(date(2026, 10, 9), self.loaders())
        assert out["changes"]["phaseFrom"] == "Mid-cycle expansion" and out["changes"]["phaseTo"] == "Late cycle" and out["changes"]["since"] == "2026-10-08"
        again = rs.load_summary(date(2026, 10, 9), self.loaders())
        assert again["changes"]["since"] == "2026-10-08"                           # a second load the same day still compares with the earlier day

    def test_no_regime_means_nothing_is_recorded(self):
        rs.load_summary(date(2026, 10, 9), self.loaders(regime=lambda: None))
        from database import cache_get
        from datetime import timedelta
        assert cache_get(rs.HISTORY_KEY, timedelta(days=30)) is None

    def test_default_loaders_read_cache_only_for_themes_and_shorts(self, monkeypatch):
        from database import cache_set
        cache_set("themes:built", themes_built()); cache_set("short:built:100:300", shorts_built())
        assert rs._themes_raw()["themes"] and rs._shorts_raw()["rows"]


class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch):
        store, calls = {}, []
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        monkeypatch.setattr(rs, "load_summary", lambda *a, **k: (calls.append(1), rs.assemble(regime_raw(), scoreboard(), None, None, {}, "2026-10-09"))[1])
        app = FastAPI(); app.include_router(router_mod.router)
        c = TestClient(app); c.store, c.calls = store, calls
        return c

    def test_returns_the_summary_and_caches_it(self, client):
        j = client.get("/api/home/regime").json()
        assert j["regime"]["riskBand"] == "Moderate" and j["sectors"]["top"][0]["symbol"] == "XLK" and j["themes"] is None
        client.get("/api/home/regime")
        assert len(client.calls) == 1 and "home:regime" in client.store

    def test_an_empty_result_is_not_cached(self, client, monkeypatch):
        monkeypatch.setattr(rs, "load_summary", lambda *a, **k: rs.assemble(None, None, None, None, {}, "2026-10-09", {"regime": "x"}))
        j = client.get("/api/home/regime").json()
        assert j["regime"] is None and "home:regime" not in client.store

    def test_failure_is_502(self, client, monkeypatch):
        monkeypatch.setattr(rs, "load_summary", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        r = client.get("/api/home/regime")
        assert r.status_code == 502 and "boom" in r.json()["detail"]


def summary(**over):
    return {**rs.assemble(regime_raw(), scoreboard(), themes_built(), shorts_built(), {"2026-10-08": {"phase": "Mid-cycle expansion", "riskScore": 20.0}}, "2026-10-09"), **over}


class TestDigestSection:
    def test_included_when_available(self):
        d = build(regime_fetch=lambda: summary())
        assert d["sections"]["regime"]["regime"]["phase"]["name"] == "Late cycle" and "regime" not in d["errors"]
        assert list(d["sections"])[:2] == ["market", "regime"]                  # sits right after the market section

    def test_omitted_when_nothing_loaded(self):
        for empty in (None, {}, {"regime": None, "sectors": None, "themes": None, "shorts": None}):
            assert build(regime_fetch=lambda e=empty: e)["sections"]["regime"] is None

    def test_a_failing_fetch_names_the_section_and_does_not_sink_the_digest(self):
        d = build(regime_fetch=lambda: (_ for _ in ()).throw(RuntimeError("FRED down")))
        assert d["sections"]["regime"] is None and "FRED down" in d["errors"]["regime"] and d["sections"]["market"]

    def test_partial_summary_is_enough(self):
        d = build(regime_fetch=lambda: summary(regime=None, themes=None, shorts=None))
        assert d["sections"]["regime"]["sectors"]


class TestDigestRender:
    def text(self, **over):
        return digest_render.render(build(regime_fetch=lambda: summary(**over)), "text")

    def test_text_covers_each_part(self):
        t = self.text()
        assert "Market regime" in t and "Late cycle · Slowdown · recession risk 31 (Moderate) · yield curve inverted" in t
        assert "Changed since 2026-10-08: phase Mid-cycle expansion → Late cycle; recession risk 20 → 31" in t
        assert "Warning signs flashing: Sahm rule" in t
        assert "Sectors, 3 months vs SPY: Technology ▲8.0%" in t and "lagging: Utilities ▼7.0%" in t
        assert "Themes, 3 months vs SPY:" in t and "Alph ▲10.0%" in t
        assert "Most shorted (% of float): WOLF 83% (borrow 1.2%), GRPN 71%, HTZ 68% (borrow 13.5%) · 8 hard to borrow, credit confirms on 7" in t

    def test_parts_are_left_out_when_absent(self):
        t = self.text(themes=None, shorts=None, changes=None)
        assert "Themes, 3 months" not in t and "Most shorted" not in t and "Changed since" not in t and "Sectors, 3 months" in t

    def test_section_is_absent_when_the_summary_is(self):
        t = digest_render.render(build(regime_fetch=lambda: None), "text")
        assert "Market regime" not in t

    def test_html_escapes_dynamic_values(self):
        s = summary()
        s["regime"] = {**s["regime"], "phase": {"id": "x", "name": "Late <b>cycle</b>"}}
        html = digest_render.render(build(regime_fetch=lambda: s), "html")
        assert "<b>Market regime</b>" in html and "Late &lt;b&gt;cycle&lt;/b&gt;" in html and "Late <b>cycle</b>" not in html

    def test_default_fetch_is_the_shared_summary(self):
        import inspect
        src = inspect.getsource(digest_builder)                                  # the test_digest fixture replaces the function object, so read the module source
        assert "def _default_regime_fetch" in src and "regime_summary.load_summary()" in src
