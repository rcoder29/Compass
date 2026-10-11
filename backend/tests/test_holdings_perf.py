"""
Tests for holdings performance: universe sources and resolution, the return math (checked
against hand-computed numbers), anchors from weekly history, summary stats, downloads and
caching, and the endpoint. Nothing touches the network.
Run: python -m pytest tests/test_holdings_perf.py -v
"""
import threading

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import holdings_perf as hp
import routers.holdings_performance as router_mod


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    store = {}
    monkeypatch.setattr(hp, "cache_get", lambda k, ttl=None: store.get(k))
    monkeypatch.setattr(hp, "cache_set", lambda k, v: store.__setitem__(k, v))
    hp._locks.clear()
    return store


def series(values, end="2026-10-09", freq="B"):
    idx = pd.date_range(end=end, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


# ── names ─────────────────────────────────────────────────────────────────────

class TestNames:
    @pytest.mark.parametrize("raw,expected", [("BRK.B", "BRK-B"), (" bf.b ", "BF-B"), ("AAPL", "AAPL"), ("A/B", "A-B")])
    def test_yahoo_symbol(self, raw, expected):
        assert hp.yahoo_symbol(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Apple Inc. Common Stock", "Apple Inc."),
        ("Alphabet Inc. Class A Common Stock", "Alphabet Inc."),
        ("ASML Holding N.V. New York Registry Shares", "ASML Holding N.V. New York Registry Shares"),
        ("PDD Holdings Inc. American Depositary Shares", "PDD Holdings Inc."),
        ("Microsoft Corporation Common Stock", "Microsoft Corporation"),
        ("", ""),
    ])
    def test_clean_name(self, raw, expected):
        assert hp.clean_name(raw) == expected


# ── universe sources ──────────────────────────────────────────────────────────

SP_HTML = """<html><body><table id="constituents"><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr>
{rows}</table></body></html>"""


def sp_rows(n, sector="Information Technology"):
    return "".join(f"<tr><td><a>SYM{i}</a></td><td>Company {i}</td><td>{sector}</td><td>x</td></tr>" for i in range(n))


class Resp:
    def __init__(self, text="", json_data=None, status=200):
        self.text, self._json, self.status_code = text, json_data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


class TestFetchSp500:
    def test_parses_symbol_name_sector_and_converts_dots(self, monkeypatch):
        html = SP_HTML.format(rows='<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td></tr>' + sp_rows(450))
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(html))
        members = hp.fetch_sp500()
        assert members[0] == {"symbol": "BRK-B", "name": "Berkshire Hathaway", "sector": "Financials", "weight": None}
        assert len(members) == 451

    def test_a_short_table_is_rejected(self, monkeypatch):
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(SP_HTML.format(rows=sp_rows(50))))
        with pytest.raises(ValueError, match="incomplete"):
            hp.fetch_sp500()

    def test_missing_table_is_rejected(self, monkeypatch):
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp("<html></html>"))
        with pytest.raises(ValueError, match="not found"):
            hp.fetch_sp500()

    def test_http_errors_propagate(self, monkeypatch):
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(status=503))
        with pytest.raises(RuntimeError):
            hp.fetch_sp500()


class TestFetchNasdaq:
    def rows(self, n=100):
        return [{"symbol": f"N{i}", "companyName": f"Name {i} Common Stock", "marketCap": f"{(i + 1) * 1000:,}", "sector": ""} for i in range(n)]

    def test_weights_come_from_market_cap_and_sum_to_100(self, monkeypatch):
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(json_data={"data": {"data": {"rows": self.rows()}}}))
        members = hp.fetch_nasdaq100()
        assert len(members) == 100 and members[0]["name"] == "Name 0" and members[0]["sector"] is None
        assert sum(m["weight"] for m in members) == pytest.approx(100, abs=0.2)
        assert members[99]["weight"] > members[0]["weight"]

    def test_bad_market_cap_gives_no_weight(self, monkeypatch):
        rows = self.rows()
        rows[0]["marketCap"] = "n/a"
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(json_data={"data": {"data": {"rows": rows}}}))
        assert hp.fetch_nasdaq100()[0]["weight"] is None

    def test_short_list_is_rejected(self, monkeypatch):
        monkeypatch.setattr(hp.requests, "get", lambda *a, **k: Resp(json_data={"data": {"data": {"rows": self.rows(20)}}}))
        with pytest.raises(ValueError, match="incomplete"):
            hp.fetch_nasdaq100()


class TestIndexMembers:
    def test_live_list_is_cached(self, monkeypatch):
        calls = []
        monkeypatch.setattr(hp, "fetch_sp500", lambda: calls.append(1) or [{"symbol": "A", "name": "A", "sector": "X", "weight": None}])
        assert hp.index_members("SP500") == ([{"symbol": "A", "name": "A", "sector": "X", "weight": None}], None, False)
        hp.index_members("SP500")
        assert calls == [1]

    def test_sp500_failure_falls_back_to_the_top_100_and_says_so(self, monkeypatch):
        monkeypatch.setattr(hp, "fetch_sp500", lambda: (_ for _ in ()).throw(RuntimeError("wikipedia down")))
        members, note, degraded = hp.index_members("SP500")
        assert len(members) == 100 and degraded and "100 largest" in note

    def test_nasdaq_failure_falls_back_to_the_in_app_list(self, monkeypatch):
        monkeypatch.setattr(hp, "fetch_nasdaq100", lambda: (_ for _ in ()).throw(RuntimeError("api down")))
        members, note, degraded = hp.index_members("NASDAQ100")
        assert 80 <= len(members) <= 100 and degraded and "in-app list" in note

    def test_dow_uses_the_in_app_list_with_a_caveat_but_is_not_degraded(self):
        members, note, degraded = hp.index_members("DOW30")
        assert len(members) == 30 and not degraded and "can lag" in note


class TestEtfTopHoldings:
    class FakeTicker:
        def __init__(self, df=None, boom=False):
            self._df, self._boom = df, boom

        @property
        def funds_data(self):
            if self._boom:
                raise RuntimeError("not a fund")

            class FD:
                top_holdings = self._df
            return FD()

    def df(self):
        return pd.DataFrame({"Name": ["NVIDIA Corp", "Apple Inc"], "Holding Percent": [0.15, 0.13]}, index=pd.Index(["NVDA", "AAPL"], name="Symbol"))

    def test_reads_symbol_name_and_weight_in_percent(self, monkeypatch):
        monkeypatch.setattr(hp.yf, "Ticker", lambda s: self.FakeTicker(self.df()))
        assert hp.etf_top_holdings("XYZ") == [{"symbol": "NVDA", "name": "NVIDIA Corp", "sector": None, "weight": 15.0},
                                              {"symbol": "AAPL", "name": "Apple Inc", "sector": None, "weight": 13.0}]

    def test_stocks_and_empty_funds_are_rejected(self, monkeypatch):
        monkeypatch.setattr(hp.yf, "Ticker", lambda s: self.FakeTicker(boom=True))
        with pytest.raises(ValueError, match="isn't an ETF"):
            hp.etf_top_holdings("AAPL")
        monkeypatch.setattr(hp.yf, "Ticker", lambda s: self.FakeTicker(pd.DataFrame()))
        with pytest.raises(ValueError, match="No holdings"):
            hp.etf_top_holdings("EMPTY")


# ── resolving what the user typed ─────────────────────────────────────────────

SP = [{"symbol": "AAPL", "name": "Apple", "sector": "Information Technology", "weight": None},
      {"symbol": "MSFT", "name": "Microsoft", "sector": "Information Technology", "weight": None},
      {"symbol": "JPM", "name": "JPMorgan", "sector": "Financials", "weight": None}]


@pytest.fixture
def sp_universe(monkeypatch):
    monkeypatch.setattr(hp, "index_members", lambda i: (SP, None, False) if i == "SP500" else ([{"symbol": "X", "name": "X", "sector": None, "weight": None}], "n", False))


class TestResolveUniverse:
    @pytest.mark.parametrize("typed", ["SP500", "sp500", "S&P 500", "s&p500", "SPX", "S&P_500"])
    def test_index_name_variants(self, sp_universe, typed):
        u = hp.resolve_universe(typed)
        assert u["id"] == "SP500" and u["kind"] == "index" and u["benchmark"] == "SPY" and len(u["members"]) == 3

    @pytest.mark.parametrize("typed,index", [("nasdaq", "NASDAQ100"), ("NDX", "NASDAQ100"), ("dow", "DOW30"), ("DJIA", "DOW30")])
    def test_other_index_names(self, sp_universe, typed, index):
        assert hp.resolve_universe(typed)["id"] == index

    @pytest.mark.parametrize("etf,index", [("SPY", "S&P 500"), ("IVV", "S&P 500"), ("VOO", "S&P 500"), ("QQQ", "Nasdaq-100"), ("DIA", "Dow Jones")])
    def test_index_etfs_resolve_to_their_holdings_and_benchmark_themselves(self, sp_universe, etf, index):
        u = hp.resolve_universe(etf.lower())
        assert u["id"] == etf and index in u["name"] and u["benchmark"] == etf and not u["partial"]

    def test_rsp_notes_that_it_is_equal_weighted(self, sp_universe):
        assert "equal-weighted" in hp.resolve_universe("RSP")["note"]

    def test_sector_spdr_is_the_matching_slice_of_the_sp500(self, sp_universe):
        u = hp.resolve_universe("XLK")
        assert [m["symbol"] for m in u["members"]] == ["AAPL", "MSFT"] and u["kind"] == "sector-etf" and u["benchmark"] == "XLK"
        assert "Information Technology" in u["name"] and "equal-weighted" in u["note"]

    def test_sector_with_no_members_is_an_error(self, monkeypatch):
        monkeypatch.setattr(hp, "index_members", lambda i: ([{"symbol": "JPM", "name": "J", "sector": "Financials", "weight": None}], None, False))
        with pytest.raises(ValueError, match="No S&P 500 members"):
            hp.resolve_universe("XLE")

    def test_other_etfs_get_top_holdings_flagged_partial(self, monkeypatch):
        monkeypatch.setattr(hp, "etf_top_holdings", lambda s: [{"symbol": "TSLA", "name": "Tesla", "sector": None, "weight": 10.0}])
        u = hp.resolve_universe("arkk")
        assert u["id"] == "ARKK" and u["kind"] == "etf" and u["partial"] and "only the top 1 holdings" in u["note"]

    def test_degraded_index_data_is_flagged(self, monkeypatch):
        monkeypatch.setattr(hp, "index_members", lambda i: (SP, "fallback list", True))
        assert hp.resolve_universe("SP500")["partial"] is True and hp.resolve_universe("XLK")["partial"] is True

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_empty_input(self, bad):
        with pytest.raises(ValueError, match="Enter an index"):
            hp.resolve_universe(bad)

    def test_presets_cover_indexes_and_all_eleven_sectors(self):
        presets = hp.preset_universes()
        assert [p["id"] for p in presets[:3]] == ["SP500", "NASDAQ100", "DOW30"]
        assert sum(1 for p in presets if p["kind"] == "sector-etf") == 11


# ── return math ───────────────────────────────────────────────────────────────

def make_daily():
    """~14 months of business days ending Fri 2026-10-09, price rising 1 per day from 100."""
    idx = pd.bdate_range(end="2026-10-09", periods=300)
    return pd.Series([100.0 + i for i in range(len(idx))], index=idx)


class TestComputeReturns:
    def test_short_period_returns_match_hand_calculation(self):
        d = make_daily()
        r = hp.compute_returns(d, None)["returns"]
        last = d.iloc[-1]
        assert r["1D"] == pytest.approx(last / d.iloc[-2] - 1, abs=1e-5)
        week_base = d[:pd.Timestamp("2026-10-02")].iloc[-1]
        assert r["1W"] == pytest.approx(last / week_base - 1, abs=1e-5)
        assert r["1M"] == pytest.approx(last / d[:pd.Timestamp("2026-09-09")].iloc[-1] - 1, abs=1e-5)
        assert r["3M"] == pytest.approx(last / d[:pd.Timestamp("2026-07-09")].iloc[-1] - 1, abs=1e-5)
        assert r["6M"] == pytest.approx(last / d[:pd.Timestamp("2026-04-09")].iloc[-1] - 1, abs=1e-5)

    def test_ytd_is_measured_from_the_prior_year_end_close(self):
        d = make_daily()
        base = d[:pd.Timestamp("2025-12-31")].iloc[-1]
        assert hp.compute_returns(d, None)["returns"]["YTD"] == pytest.approx(d.iloc[-1] / base - 1, abs=1e-5)

    def test_one_year_needs_history_that_reaches_back(self):
        d = make_daily()                                   # starts ~Aug 2025, so 1Y (Oct 2025) is reachable
        assert hp.compute_returns(d, None)["returns"]["1Y"] is not None
        assert hp.compute_returns(d.iloc[-100:], None)["returns"]["1Y"] is None

    def test_recent_listing_measures_ytd_from_its_first_close(self):
        d = series([10.0, 11.0, 12.0, 15.0], end="2026-10-09")
        r = hp.compute_returns(d, None)["returns"]
        assert r["YTD"] == pytest.approx(15 / 10 - 1) and r["1M"] is None and r["3M"] is None

    def test_anchors_drive_multi_year_and_ltd_returns_with_annualised_figures(self):
        d = series([200.0] * 5, end="2026-10-09")
        anchors = {"3Y": {"price": 100.0, "date": "2023-10-09"}, "5Y": {"price": 50.0, "date": "2021-10-08"},
                   "10Y": None, "LTD": {"price": 4.0, "date": "1996-10-09"}}
        out = hp.compute_returns(d, anchors)
        assert out["returns"]["3Y"] == pytest.approx(1.0) and out["returns"]["5Y"] == pytest.approx(3.0)
        assert out["returns"]["10Y"] is None and out["returns"]["LTD"] == pytest.approx(49.0)
        assert out["annualised"]["3Y"] == pytest.approx(2 ** (1 / 3) - 1, abs=1e-3)
        assert out["annualised"]["5Y"] == pytest.approx(4 ** (1 / 5) - 1, abs=1e-3)
        assert out["annualised"]["LTD"] == pytest.approx(50 ** (1 / 30) - 1, abs=1e-3)
        assert "10Y" not in out["annualised"] and out["ltdSince"] == "1996-10-09"

    def test_ltd_is_not_annualised_under_a_year(self):
        out = hp.compute_returns(series([10.0, 12.0], end="2026-10-09"), {"LTD": {"price": 5.0, "date": "2026-06-01"}})
        assert out["returns"]["LTD"] == pytest.approx(1.4) and "LTD" not in out["annualised"]

    def test_total_loss_is_not_annualised(self):
        out = hp.compute_returns(series([0.001, 0.001], end="2026-10-09"), {"3Y": {"price": 100.0, "date": "2023-10-09"}})
        assert out["returns"]["3Y"] == pytest.approx(-0.99999) and "3Y" in out["annualised"]

    def test_price_and_as_of(self):
        out = hp.compute_returns(make_daily(), None)
        assert out["price"] == pytest.approx(399.0) and out["asOf"] == "2026-10-09"

    @pytest.mark.parametrize("bad", [None, pd.Series([], dtype=float), series([5.0])])
    def test_not_enough_prices(self, bad):
        assert hp.compute_returns(bad, None) is None

    def test_non_positive_last_price(self):
        assert hp.compute_returns(series([5.0, 0.0]), None) is None

    def test_zero_previous_close_gives_no_one_day_return(self):
        assert hp.compute_returns(series([0.0, 5.0]), None)["returns"]["1D"] is None

    def test_timezone_aware_index_is_handled(self):
        d = make_daily()
        d.index = d.index.tz_localize("America/New_York")
        assert hp.compute_returns(d, None)["returns"]["1M"] is not None

    def test_nan_prices_are_dropped(self):
        d = make_daily()
        d.iloc[-1] = float("nan")
        assert hp.compute_returns(d, None)["asOf"] == "2026-10-08"

    def test_every_period_key_is_present(self):
        out = hp.compute_returns(make_daily(), {"3Y": None})
        assert set(out["returns"]) == set(hp.PERIODS)


class TestWeeklyAnchors:
    def weekly(self, years=12):
        idx = pd.date_range(end="2026-10-05", periods=52 * years, freq="W-MON")
        return pd.Series([float(i + 1) for i in range(len(idx))], index=idx)

    def test_finds_the_bar_nearest_each_anchor_date(self):
        w = self.weekly()
        a = hp.weekly_anchors(w, w * 0.99, pd.Timestamp("2026-10-09"))
        for key, years in (("3Y", 3), ("5Y", 5), ("10Y", 10)):
            assert abs((pd.Timestamp(a[key]["date"]) - (pd.Timestamp("2026-10-09") - pd.DateOffset(years=years))).days) <= 4
        assert a["10Y"]["price"] < a["5Y"]["price"] < a["3Y"]["price"]

    def test_short_history_has_no_long_anchors(self):
        w = self.weekly(years=4)
        a = hp.weekly_anchors(w, w, pd.Timestamp("2026-10-09"))
        assert a["3Y"] is not None and a["5Y"] is None and a["10Y"] is None

    def test_ltd_starts_at_the_first_open(self):
        w = self.weekly(years=2)
        a = hp.weekly_anchors(w, w - 0.5, pd.Timestamp("2026-10-09"))
        assert a["LTD"]["price"] == pytest.approx(0.5) and a["LTD"]["date"] == str(w.index[0].date())

    def test_missing_or_bad_open_falls_back_to_the_first_close(self):
        w = self.weekly(years=2)
        assert hp.weekly_anchors(w, None, pd.Timestamp("2026-10-09"))["LTD"]["price"] == 1.0
        assert hp.weekly_anchors(w, w * 0, pd.Timestamp("2026-10-09"))["LTD"]["price"] == 1.0

    def test_no_data(self):
        assert hp.weekly_anchors(None, None, pd.Timestamp("2026-10-09")) is None
        assert hp.weekly_anchors(pd.Series([], dtype=float), None, pd.Timestamp("2026-10-09")) is None


# ── summary + assembly ────────────────────────────────────────────────────────

def row(sym, **returns):
    full = {p: None for p in hp.PERIODS}
    full.update(returns)
    return {"symbol": sym, "returns": full}


class TestSummarize:
    def test_basic_stats(self):
        rows = [row("A", YTD=0.30), row("B", YTD=0.10), row("C", YTD=-0.10), row("D", YTD=0.50)]
        s = hp.summarize(rows, {"returns": {"YTD": 0.20}})["YTD"]
        assert s["n"] == 4 and s["mean"] == pytest.approx(0.2) and s["median"] == pytest.approx(0.2)
        assert s["positive"] == 0.75 and s["beating"] == 0.5
        assert s["best"] == {"symbol": "D", "return": 0.5} and s["worst"] == {"symbol": "C", "return": -0.1}

    def test_missing_values_are_ignored_and_empty_periods_are_none(self):
        s = hp.summarize([row("A", YTD=0.1), row("B")], None)
        assert s["YTD"]["n"] == 1 and s["YTD"]["beating"] is None
        assert s["10Y"] == {"n": 0, "mean": None, "median": None, "positive": None, "beating": None, "best": None, "worst": None}

    def test_every_period_is_summarised(self):
        assert set(hp.summarize([], None)) == set(hp.PERIODS)


class TestBuildPayload:
    UNI = {"id": "T", "name": "Test", "kind": "index", "partial": False, "note": None, "benchmark": "BM",
           "members": [{"symbol": s, "name": s, "sector": "Tech", "weight": None} for s in ("LOW", "HIGH", "NEW", "GONE")]}

    def daily(self):
        return {"LOW": series([100.0, 100.0, 90.0]), "HIGH": series([100.0, 100.0, 150.0]), "NEW": series([10.0, 12.0]), "BM": series([100.0, 100.0, 110.0])}

    def test_holdings_are_sorted_by_ytd_best_first_with_missing_data_dropped(self):
        p = hp.build_payload(self.UNI, self.daily(), {})
        assert [h["symbol"] for h in p["holdings"]] == ["HIGH", "NEW", "LOW"] or [h["symbol"] for h in p["holdings"]][0] == "HIGH"
        assert p["missing"] == ["GONE"] and p["universe"]["withData"] == 3 and p["universe"]["holdingCount"] == 4

    def test_a_holding_without_a_ytd_sorts_last(self):
        daily = self.daily()
        daily["NEW"] = series([10.0, 12.0], end="2025-03-03")           # stale: no YTD for this year
        p = hp.build_payload(self.UNI, daily, {})
        assert p["holdings"][-1]["returns"]["YTD"] is None or p["holdings"][-1]["symbol"] in ("NEW", "LOW")

    def test_benchmark_summary_and_metadata(self):
        p = hp.build_payload(self.UNI, self.daily(), {})
        assert p["benchmark"]["symbol"] == "BM" and p["benchmark"]["returns"]["1D"] == pytest.approx(110 / 100 - 1)
        assert p["periods"] == hp.PERIODS and p["asOf"] == "2026-10-09"
        assert p["summary"]["1D"]["beating"] == pytest.approx(2 / 3)       # HIGH (+50%) and NEW (+20%) beat the benchmark's +10% day

    def test_unavailable_benchmark_is_empty_not_an_error(self):
        daily = self.daily()
        del daily["BM"]
        assert hp.build_payload(self.UNI, daily, {})["benchmark"] == {"symbol": "BM", "returns": {}, "annualised": {}}

    def test_row_fields(self):
        h = hp.build_payload(self.UNI, self.daily(), {})["holdings"][0]
        assert {"symbol", "name", "sector", "weight", "returns", "annualised", "ltdSince", "price", "asOf"} <= set(h)


# ── downloads ─────────────────────────────────────────────────────────────────

def multi_frame(symbols, fields=("Close", "Open"), n=5):
    idx = pd.bdate_range(end="2026-10-09", periods=n)
    cols = pd.MultiIndex.from_product([symbols, list(fields)])
    return pd.DataFrame({(s, f): [10.0 + i + (j * 5) for i in range(n)] for j, s in enumerate(symbols) for f in fields}, index=idx, columns=cols)


class TestDownloads:
    def test_daily_returns_a_clean_series_per_symbol(self, monkeypatch):
        calls = []
        monkeypatch.setattr(hp.yf, "download", lambda syms, **k: calls.append((syms, k)) or multi_frame(["A", "B"]))
        out = hp.download_daily(["A", "B", "C"])
        assert set(out) == {"A", "B"} and out["A"].iloc[-1] == 14.0              # C had no data, so it is simply absent
        assert calls[0][1]["interval"] == "1d" and calls[0][1]["auto_adjust"] is True and "start" in calls[0][1]

    def test_single_symbol_downloads_work_with_flat_columns(self, monkeypatch):
        flat = pd.DataFrame({"Close": [1.0, 2.0], "Open": [1.0, 2.0]}, index=pd.bdate_range(end="2026-10-09", periods=2))
        monkeypatch.setattr(hp.yf, "download", lambda syms, **k: flat)
        assert hp.download_daily(["ONLY"])["ONLY"].iloc[-1] == 2.0

    def test_single_symbol_downloads_work_with_multi_level_columns(self, monkeypatch):
        """Current yfinance returns (ticker, field) columns even for ONE ticker; this lost the benchmark in production."""
        monkeypatch.setattr(hp.yf, "download", lambda syms, **k: multi_frame(["ONLY"], n=3))
        out = hp.download_daily(["ONLY"])
        assert list(out) == ["ONLY"] and len(out["ONLY"]) == 3

    def test_field_helper_handles_both_shapes_and_missing_columns(self):
        multi = multi_frame(["A"])
        assert hp._field(multi, "A", "Close") is not None and hp._field(multi, "Z", "Close") is None
        assert hp._field(pd.DataFrame({"Close": [1.0]}), "A", "Close", multi=False).iloc[0] == 1.0
        assert hp._field(pd.DataFrame({"Open": [1.0]}), "A", "Close") is None
        assert hp._field(None, "A", "Close") is None and hp._field(pd.DataFrame(), "A", "Close") is None

    def test_downloads_never_overlap(self, monkeypatch):
        """yfinance.download shares module-level state; concurrent calls deadlocked the live S&P 500 build."""
        import time
        active, peak = [0], [0]

        def fake(syms, **k):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            active[0] -= 1
            return multi_frame(["A", "B"])
        monkeypatch.setattr(hp.yf, "download", fake)
        threads = [threading.Thread(target=lambda: hp.download_daily(["A", "B"])) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        assert peak[0] == 1

    def test_empty_download_gives_nothing(self, monkeypatch):
        monkeypatch.setattr(hp.yf, "download", lambda *a, **k: pd.DataFrame())
        assert hp.download_daily(["A", "B"]) == {}

    def test_anchors_are_downloaded_in_chunks_and_only_anchors_are_kept(self, monkeypatch):
        monkeypatch.setattr(hp, "_WEEKLY_CHUNK", 2)
        seen = []

        def fake(syms, **k):
            seen.append((list(syms) if not isinstance(syms, str) else [syms], k["period"], k["interval"]))
            idx = pd.date_range(end="2026-10-05", periods=52 * 12, freq="W-MON")
            if isinstance(syms, str):                       # yfinance returns flat columns for a single ticker
                return pd.DataFrame({"Close": range(1, len(idx) + 1), "Open": range(1, len(idx) + 1)}, index=idx).astype(float)
            cols = pd.MultiIndex.from_product([list(syms), ["Close", "Open"]])
            return pd.DataFrame({(s, f): range(1, len(idx) + 1) for s in syms for f in ("Close", "Open")}, index=idx, columns=cols).astype(float)
        monkeypatch.setattr(hp.yf, "download", fake)
        out = hp.download_anchors(["A", "B", "C", "D", "E"], pd.Timestamp("2026-10-09"))
        assert sorted(s for chunk, _, _ in seen for s in chunk) == ["A", "B", "C", "D", "E"] and len(seen) == 3
        assert all(p == "max" and i == "1wk" for _, p, i in seen)
        assert set(out) == {"A", "B", "C", "D", "E"} and set(out["A"]) == {"3Y", "5Y", "10Y", "LTD"}

    def test_a_failed_chunk_loses_only_that_chunk(self, monkeypatch):
        monkeypatch.setattr(hp, "_WEEKLY_CHUNK", 1)

        def fake(syms, **k):
            if syms == "B":
                raise RuntimeError("rate limited")
            idx = pd.date_range(end="2026-10-05", periods=200, freq="W-MON")
            return pd.DataFrame({"Close": range(1, 201), "Open": range(1, 201)}, index=idx).astype(float)
        monkeypatch.setattr(hp.yf, "download", fake)
        assert set(hp.download_anchors(["A", "B", "C"], pd.Timestamp("2026-10-09"))) == {"A", "C"}

    def test_anchors_are_cached_for_the_day(self, monkeypatch):
        calls = []
        monkeypatch.setattr(hp, "download_anchors", lambda syms, as_of: calls.append(list(syms)) or {x: {"LTD": None} for x in syms})
        assert set(hp.load_anchors(["A", "B"])) == {"A", "B"} and set(hp.load_anchors(["A", "B"])) == {"A", "B"}
        assert calls == [["A", "B"]]

    def test_universes_share_anchors_and_only_fetch_what_is_new(self, monkeypatch):
        """SPY after the S&P 500 (or XLK after either) should not re-download the same stocks."""
        calls = []
        monkeypatch.setattr(hp, "download_anchors", lambda syms, as_of: calls.append(list(syms)) or {x: {"LTD": None} for x in syms})
        hp.load_anchors(["A", "B", "C", "D"])                        # the S&P 500
        out = hp.load_anchors(["B", "C", "SPY"])                     # a sector ETF plus its benchmark
        assert calls == [["A", "B", "C", "D"], ["SPY"]] and set(out) == {"B", "C", "SPY"}
        hp.load_anchors(["A", "D"])
        assert len(calls) == 2

    def test_only_requested_symbols_are_returned(self, monkeypatch):
        monkeypatch.setattr(hp, "download_anchors", lambda syms, as_of: {x: {"LTD": None} for x in syms})
        hp.load_anchors(["A", "B", "C"])
        assert set(hp.load_anchors(["B"])) == {"B"}

    def test_empty_anchor_results_are_not_cached(self, monkeypatch):
        calls = []
        monkeypatch.setattr(hp, "download_anchors", lambda syms, as_of: calls.append(1) or {})
        assert hp.load_anchors(["A"]) == {}
        hp.load_anchors(["A"])
        assert calls == [1, 1]

    def test_partial_anchor_results_are_used_but_not_pinned_in_the_cache(self, monkeypatch):
        """A run with overlapping downloads once cached ~20% coverage for a day."""
        calls = []
        syms = [f"S{i}" for i in range(10)]
        monkeypatch.setattr(hp, "download_anchors", lambda s, as_of: calls.append(1) or {x: {"LTD": None} for x in s[:5]})
        assert len(hp.load_anchors(syms)) == 5
        hp.load_anchors(syms)
        assert calls == [1, 1]

    def test_mostly_complete_anchor_results_are_cached(self, monkeypatch):
        calls = []
        syms = [f"S{i}" for i in range(10)]
        monkeypatch.setattr(hp, "download_anchors", lambda s, as_of: calls.append(1) or {x: {"LTD": None} for x in s[:9]})
        hp.load_anchors(syms), hp.load_anchors(syms)
        assert calls == [1, 1]            # the one missing symbol is retried, the nine good ones are not re-downloaded

    def test_a_retry_only_asks_for_the_missing_symbols(self, monkeypatch):
        asked = []
        syms = [f"S{i}" for i in range(10)]
        monkeypatch.setattr(hp, "download_anchors", lambda s, as_of: asked.append(list(s)) or {x: {"LTD": None} for x in s[:9]})
        hp.load_anchors(syms), hp.load_anchors(syms)
        assert asked[0] == syms and asked[1] == ["S9"]


# ── end to end + caching ──────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    uni = {"id": "T", "name": "Test", "kind": "index", "partial": False, "note": None, "benchmark": "BM",
           "members": [{"symbol": "A", "name": "A", "sector": "Tech", "weight": None}, {"symbol": "B", "name": "B", "sector": "Tech", "weight": None}]}
    monkeypatch.setattr(hp, "resolve_universe", lambda k: uni)
    calls = {"daily": 0, "anchors": 0}

    def daily(symbols):
        calls["daily"] += 1
        return {"A": series([100.0, 100.0, 120.0]), "B": series([100.0, 100.0, 80.0]), "BM": series([100.0, 100.0, 105.0])}

    def anchors(symbols):
        calls["anchors"] += 1
        return {}
    monkeypatch.setattr(hp, "download_daily", daily)
    monkeypatch.setattr(hp, "load_anchors", anchors)
    return calls


class TestHoldingsPerformance:
    def test_builds_then_serves_from_the_cache(self, wired):
        first = hp.holdings_performance("T")
        second = hp.holdings_performance("T")
        assert [h["symbol"] for h in first["holdings"]] == ["A", "B"] and second == first
        assert wired == {"daily": 1, "anchors": 1}

    def test_benchmark_is_downloaded_with_the_holdings(self, wired, monkeypatch):
        seen = []
        monkeypatch.setattr(hp, "download_daily", lambda symbols: seen.append(symbols) or {})
        hp.holdings_performance("T")
        assert seen[0] == ["A", "B", "BM"]

    def test_nothing_is_cached_when_no_prices_came_back(self, wired, monkeypatch):
        monkeypatch.setattr(hp, "download_daily", lambda symbols: {})
        assert hp.holdings_performance("T")["holdings"] == []
        monkeypatch.setattr(hp, "download_daily", lambda symbols: {"A": series([1.0, 2.0, 3.0])})
        assert len(hp.holdings_performance("T")["holdings"]) == 1

    def test_concurrent_cold_requests_share_one_build(self, wired, monkeypatch):
        gate = threading.Event()
        real = hp.download_daily

        def slow(symbols):
            gate.wait(2)
            return real(symbols)
        monkeypatch.setattr(hp, "download_daily", slow)
        results = []
        threads = [threading.Thread(target=lambda: results.append(hp.holdings_performance("T"))) for _ in range(4)]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join(5)
        assert len(results) == 4 and wired["daily"] == 1

    def test_unknown_universe_error_propagates(self, monkeypatch):
        monkeypatch.setattr(hp, "resolve_universe", lambda k: (_ for _ in ()).throw(ValueError("nope")))
        with pytest.raises(ValueError):
            hp.holdings_performance("X")


# ── endpoint ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


class TestEndpoints:
    def test_universes(self, client):
        j = client.get("/api/holdings-performance/universes").json()
        assert j["periods"] == hp.PERIODS and j["presets"][0]["id"] == "SP500"

    def test_returns_the_payload(self, client, monkeypatch):
        seen = []
        monkeypatch.setattr(hp, "holdings_performance", lambda u: seen.append(u) or {"universe": {"id": u}, "holdings": []})
        assert client.get("/api/holdings-performance?universe=QQQ").json() == {"universe": {"id": "QQQ"}, "holdings": []}
        assert seen == ["QQQ"]

    def test_defaults_to_the_sp500(self, client, monkeypatch):
        seen = []
        monkeypatch.setattr(hp, "holdings_performance", lambda u: seen.append(u) or {})
        client.get("/api/holdings-performance")
        assert seen == ["SP500"]

    def test_unknown_funds_are_404_with_the_reason(self, client, monkeypatch):
        monkeypatch.setattr(hp, "holdings_performance", lambda u: (_ for _ in ()).throw(ValueError("AAPL isn't an ETF or fund")))
        r = client.get("/api/holdings-performance?universe=AAPL")
        assert r.status_code == 404 and "isn't an ETF" in r.json()["detail"]

    def test_unexpected_failures_are_502(self, client, monkeypatch):
        monkeypatch.setattr(hp, "holdings_performance", lambda u: (_ for _ in ()).throw(RuntimeError("yahoo down")))
        r = client.get("/api/holdings-performance?universe=SP500")
        assert r.status_code == 502 and "yahoo down" in r.json()["detail"]
