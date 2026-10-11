"""
Tests for the Short Interest Monitor: FINRA/IBKR parsing, candidate selection, ranking by share of float, borrow bands,
issuer-name matching, bond summaries, the interest-paid proxy, the equity-vs-credit displacement rules, the staged
endpoint and the data layer. No network. Run: python -m pytest tests/test_short_interest.py -v
"""
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import hundred_bagger_data as scanner
import routers.short_interest as router_mod
import short_interest as si
import short_interest_data as data

FINRA = "\n".join([
    '"accountingYearMonthNumber"|"symbolCode"|"issueName"|"issuerServicesGroupExchangeCode"|"marketClassCode"|"currentShortPositionQuantity"|"previousShortPositionQuantity"|"stockSplitFlag"|"averageDailyVolumeQuantity"|"daysToCoverQuantity"|"revisionFlag"|"changePercent"|"changePreviousNumber"|"settlementDate"',
    '"20260915"|"AAA"|"Alpha Inc. Common Stock"|"A"|"NYSE"|"20000000"|"16000000"||"4000000"|"5.0"||"25.0"|"4000000"|"2026-09-15"',
    '"20260915"|"BBB"|"Beta Corp"|"R"|"NNM"|"5000000"|"6000000"||"1000000"|"5.0"||"-16.67"|"-1000000"|"2026-09-15"',
    '"20260915"|"CCC"|"Gamma Warrants"|"A"|"NYSE"|"9000000"|"9000000"||"2000000"|"4.5"||"0"|"0"|"2026-09-15"',
    '"20260915"|"DDD"|"Delta ETF"|"E"|"ARCA"|"9000000"|"9000000"||"2000000"|"4.5"||"0"|"0"|"2026-09-15"',
    '"20260915"|"EEE"|"Thin Co"|"A"|"NYSE"|"900000"|"800000"||"900000"|"1.0"||"12.5"|"100000"|"2026-09-15"',
    '"20260915"|"FFF"|"Quiet Co"|"A"|"NYSE"|"3000000"|"3000000"||"50000"|"60.0"||"0"|"0"|"2026-09-15"',
    '"20260915"|"GGG"|"Otc Co"|"A"|"OTC"|"8000000"|"8000000"||"2000000"|"4.0"||"0"|"0"|"2026-09-15"',
    '"20260915"|"HHH"|"Squeezy Corp"|"A"|"SC"|"2000000"|"1500000"||"150000"|"13.3"||"33.3"|"500000"|"2026-09-15"',
    '"20260915"|"BAD"|"No Number"|"A"|"NYSE"|""|""||""|""||""|""|"2026-09-15"',
])

IBKR = """#BOF|2026.10.11|17:43:33
#SYM|CUR|NAME|CON|ISIN|REBATERATE|FEERATE|AVAILABLE|FIGI|
AAA|USD|ALPHA INC|1|X|-12.5000|16.0000|250000|BBG1|
BBB|USD|BETA CORP|2|X|3.6000|0.4000|>10000000|BBG2|
CCC|USD|GAMMA|3|X|NA|NA|2000||
HHH|USD|SQUEEZY|4|X|-30.0|33.5|0|BBG3|
short|line
#EOF|4
"""


def info(sym, **over):
    d = {"symbol": sym, "name": f"{sym} Corp", "sector": "Tech", "quoteType": "EQUITY", "price": 10.0, "marketCap": 1e9, "floatShares": 40e6,
         "sharesOutstanding": 50e6, "change52w": -0.3, "totalDebt": 400e6, "totalCash": 100e6}
    d.update(over)
    return d


class TestFinra:
    def test_parse(self):
        rows = si.parse_finra(FINRA)
        assert [r["symbol"] for r in rows] == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]          # the row with no number is skipped
        a = rows[0]
        assert a["short"] == 20_000_000 and a["prevShort"] == 16_000_000 and a["adv"] == 4_000_000 and a["daysToCover"] == 5.0
        assert a["changePct"] == 25.0 and a["exchange"] == "NYSE" and a["settlement"] == "2026-09-15"

    def test_candidates_keep_liquid_common_stock_only(self):
        syms = {r["symbol"] for r in si.select_candidates(si.parse_finra(FINRA))}
        assert syms == {"AAA", "BBB", "HHH"}
        # CCC warrants, DDD an ARCA ETF, EEE too small a position, FFF illiquid, GGG over-the-counter

    def test_candidates_union_of_biggest_positions_and_highest_days_to_cover(self):
        rows = [{"symbol": f"S{i}", "name": "Co", "exchange": "NYSE", "short": 10_000_000 - i * 1000, "prevShort": 1, "adv": 1e6, "daysToCover": 1.0, "changePct": 0, "settlement": "x"} for i in range(5)]
        rows.append({"symbol": "SMALLFLOAT", "name": "Co", "exchange": "NYSE", "short": 1_500_000, "prevShort": 1, "adv": 200_000, "daysToCover": 40.0, "changePct": 0, "settlement": "x"})
        got = [r["symbol"] for r in si.select_candidates(rows, by_short=2, by_dtc=1)]
        assert got == ["S0", "S1", "SMALLFLOAT"]                                  # the days-to-cover pick isn't lost to the shares-short cut


class TestBorrow:
    def test_parse(self):
        d, stamp = si.parse_ibkr(IBKR)
        assert stamp == "2026-10-11 17:43:33"
        assert d["AAA"] == {"fee": 16.0, "rebate": -12.5, "available": 250000.0, "availableCapped": False}
        assert d["BBB"]["available"] == 10_000_000 and d["BBB"]["availableCapped"] is True
        assert d["CCC"]["fee"] is None and d["CCC"]["rebate"] is None and d["CCC"]["available"] == 2000
        assert d["HHH"]["available"] == 0 and "short" not in d

    @pytest.mark.parametrize("fee,label", [(0.3, "General collateral"), (1.0, "Elevated"), (4.9, "Elevated"), (5.0, "Hard to borrow"), (24.9, "Hard to borrow"), (25.0, "Very hard to borrow"), (90, "Very hard to borrow")])
    def test_bands(self, fee, label):
        assert si.band(fee, si.BORROW_BANDS)["label"] == label
    def test_band_of_nothing(self):
        assert si.band(None, si.BORROW_BANDS) is None


class TestRanking:
    def test_ranked_by_share_of_float_with_filters(self):
        finra = {r["symbol"]: r for r in si.select_candidates(si.parse_finra(FINRA))}        # AAA 20m, BBB 5m, HHH 2m
        infos = {"AAA": info("AAA", floatShares=40e6), "BBB": info("BBB", floatShares=8e6), "HHH": info("HHH", floatShares=4e6, marketCap=100e6)}
        rows = si.rank_rows(finra, infos, min_cap=300e6)
        assert [r["symbol"] for r in rows] == ["BBB", "AAA"]                                  # 5m/8m = 62.5% beats 20m/40m = 50%
        assert rows[0]["siPctFloat"] == pytest.approx(0.625) and rows[1]["siPctFloat"] == pytest.approx(0.5) and [r["rank"] for r in rows] == [1, 2]
        assert {r["symbol"] for r in si.rank_rows(finra, infos, min_cap=50e6)} == {"AAA", "BBB", "HHH"}       # HHH returns when the cap floor drops

    def test_orders_highest_first_and_limits(self):
        finra = {f"S{i}": {"name": "x", "exchange": "NYSE", "short": (i + 1) * 1e6, "prevShort": 1, "changePct": 0, "adv": 1e6, "daysToCover": 1, "settlement": "d"} for i in range(5)}
        infos = {s: info(s, floatShares=10e6) for s in finra}
        rows = si.rank_rows(finra, infos, limit=3)
        assert [r["symbol"] for r in rows] == ["S4", "S3", "S2"] and rows[0]["siPctFloat"] == pytest.approx(0.5)

    def test_drops_non_equities_missing_float_and_missing_info(self):
        finra = {s: {"name": s, "exchange": "NYSE", "short": 5e6, "prevShort": 1, "changePct": 0, "adv": 1e6, "daysToCover": 1, "settlement": "d"} for s in "ABCDE"}
        infos = {"A": info("A"), "B": info("B", quoteType="ETF"), "C": info("C", floatShares=None, sharesOutstanding=None), "D": info("D", floatShares=None, sharesOutstanding=20e6)}
        got = {r["symbol"]: r for r in si.rank_rows(finra, infos)}
        assert set(got) == {"A", "D"} and got["D"]["floatShares"] == 20e6                       # falls back to shares outstanding; E has no record at all

    def test_percentile(self):
        assert si.percentile([1, 2, 3, 4], 4) == 100 and si.percentile([1, 2, 3, 4], 1) == 25 and si.percentile([], 1) == 0


class TestNameMatching:
    @pytest.mark.parametrize("raw,norm", [("Carvana Co. Class A Common Stock", "CARVANA"), ("AT&T Inc.", "AT AND T"), ("The Boeing Company", "BOEING"),
                                           ("Plug Power, Inc.", "PLUG POWER"), (None, ""), ("", "")])
    def test_normalize(self, raw, norm):
        assert si.normalize_name(raw) == norm

    @pytest.mark.parametrize("a,b,kind", [("CARVANA", "CARVANA", "exact"), ("PLUG POWER", "PLUG POWER FINANCE", "prefix"), ("CARNIVAL", "CARNIVAL FINANCE", "prefix"),
                                          ("WESTERN", "WESTERN UNION", None), ("WESTERN DIGITAL", "WESTERN UNION", None), ("UNITED", "UNITED STATES STEEL", None),
                                          ("", "X", None), ("X", "", None)])
    def test_match(self, a, b, kind):
        assert si.match_issuer(a, b) == kind
        assert si.match_issuer(b, a) == kind                                                    # symmetric


def bond_funds():
    def h(issuer, coupon, maturity, balance, value, cusip, default=False):
        return {"issuerName": issuer, "couponRate": coupon, "maturityDate": maturity, "balance": balance, "marketValue": value, "cusip": cusip, "isDefault": default}
    return {
        "LQD": ("IG", [h("ALPHA CORP", 4.0, "2030-01-01", 1e6, 0.98e6, "A1"), h("ALPHA CORP", 5.0, "2034-01-01", 3e6, 3.0e6, "A2"), h("OTHERCO", 3.0, "2029-01-01", 1e6, 1e6, "O1"),
                       h("TINY CO", 3.0, "2026-10-20", 1e6, 1e6, "T1")]),
        "HYG": ("HY", [h("ALPHA CORP", 5.0, "2034-01-01", 1e6, 1.0e6, "A2"), h("GAMMA INC", 8.0, "2031-01-01", 2e6, 1.5e6, "G1"), h("GAMMA INC", 9.0, "2032-01-01", 2e6, 1.6e6, "G2", True)]),
    }


def build_index():
    ytm = lambda price, coupon, years: round(coupon / price * 100, 3)          # crude but deterministic: current yield
    interp = lambda years, rates: 4.0
    price = lambda h: round(h["marketValue"] / h["balance"] * 100, 2) if h.get("balance") and h.get("marketValue") else None
    return si.build_bond_index(bond_funds(), [], date(2026, 10, 11), price, ytm, interp)


class TestBondIndex:
    def test_merges_by_cusip_prices_and_spreads(self):
        idx = build_index()
        alpha = idx["ALPHA"]["bonds"]
        assert sorted(b["cusip"] for b in alpha) == ["A1", "A2"]
        a2 = next(b for b in alpha if b["cusip"] == "A2")
        assert a2["mv"] == pytest.approx(4.0e6) and a2["grades"] == ["HY", "IG"]               # held by two funds: values add
        assert a2["price"] == 100.0 and a2["ytm"] == 5.0 and a2["spreadBps"] == 100 and a2["years"] == pytest.approx(7.22, abs=0.02)

    def test_drops_bonds_about_to_mature_or_unpriced(self):
        idx = build_index()
        assert "TINY" not in idx

    def test_company_summary_weights_by_market_value(self):
        s = si.company_bonds(build_index(), ["Alpha Corp."])
        assert s["matchType"] == "exact" and s["count"] == 2 and s["issuer"] == "ALPHA CORP"
        # A1 mv 0.98m (price 98 -> ytm 4.0816, spread 8), A2 mv 4.0m (spread 100): weights 0.197 / 0.803
        assert s["avgSpreadBps"] == round(8 * (0.98 / 4.98) + 100 * (4.0 / 4.98))
        assert s["avgCoupon"] == pytest.approx(4.0 * (0.98 / 4.98) + 5.0 * (4.0 / 4.98), abs=0.01)
        assert s["grade"] == "Mixed" and s["inDefault"] is False and s["nextMaturity"] == "2030-01-01" and s["lastMaturity"] == "2034-01-01"
        assert s["top"][0]["maturity"] == "2034-01-01" and len(s["top"]) == 2

    def test_default_flag_and_high_yield_grade(self):
        s = si.company_bonds(build_index(), ["Gamma Inc"])
        assert s["inDefault"] is True and s["grade"] == "HY" and s["count"] == 2

    def test_no_match_and_empty_index(self):
        assert si.company_bonds(build_index(), ["Nobody Ltd"]) is None
        assert si.company_bonds({}, ["Alpha"]) is None and si.company_bonds(build_index(), [None, ""]) is None

    def test_exact_match_beats_prefix(self):
        idx = build_index()
        idx["ALPHA FINANCE"] = {"issuer": "ALPHA FINANCE", "bonds": [{"coupon": 1.0, "maturity": "2030-01-01", "price": 90, "ytm": 2, "spreadBps": 900, "mv": 9e6, "grades": ["HY"], "default": False, "cusip": "Z"}]}
        s = si.company_bonds(idx, ["Alpha"])
        assert s["issuer"] == "ALPHA CORP" or s["count"] >= 1
        assert si.company_bonds(idx, ["Alpha Corp"])["count"] == 2                              # the exact issuer only; "ALPHA FINANCE" isn't pulled in


class TestInterestPaid:
    def test_proxy(self):
        p = si.credit_proxy({"interestExpense": -40e6, "totalDebt": 500e6, "ebit": 100e6, "totalCash": 50e6}, 4.2)
        assert p["impliedRate"] == 8.0 and p["proxySpreadBps"] == 380 and p["coverage"] == 2.5 and p["netDebt"] == 450e6

    def test_missing_pieces(self):
        assert si.credit_proxy(None, 4.0) is None
        p = si.credit_proxy({"interestExpense": None, "totalDebt": 100e6, "ebit": None, "totalCash": 40e6}, 4.0)
        assert p["impliedRate"] is None and p["proxySpreadBps"] is None and p["netDebt"] == 60e6
        assert si.credit_proxy({"interestExpense": 5e6, "totalDebt": 100e6, "ebit": 1e6}, None)["proxySpreadBps"] is None
        assert si.credit_proxy({"interestExpense": 0, "totalDebt": 0, "ebit": None}, 4.0) is None

    def test_absurd_implied_rates_are_ignored(self):
        assert si.credit_proxy({"interestExpense": 90e6, "totalDebt": 100e6, "ebit": 1}, 4.0)["impliedRate"] is None


class TestProxyUsability:
    cp = {"impliedRate": 8.0, "proxySpreadBps": 380, "totalDebt": 500e6}

    def test_meaningful_proxy_counts(self):
        assert si.proxy_usable(self.cp, 5e9) is True and si.proxy_usable(self.cp, None) is True

    def test_low_coupon_debt_says_nothing_about_credit(self):
        assert si.proxy_usable({**self.cp, "impliedRate": 2.9, "proxySpreadBps": -120}, 5e9) is False
        assert si.proxy_usable({**self.cp, "impliedRate": 3.0}, 5e9) is True

    def test_trivial_debt_is_not_a_credit_read(self):
        assert si.proxy_usable({**self.cp, "totalDebt": 50e6}, 5e9) is False                       # 1% of market cap
        assert si.proxy_usable({**self.cp, "totalDebt": 150e6}, 5e9) is True                       # 3%

    def test_missing_pieces(self):
        assert not si.proxy_usable(None, 1e9) and not si.proxy_usable({"impliedRate": None, "proxySpreadBps": None}, 1e9)
        assert not si.proxy_usable({"impliedRate": 8.0, "proxySpreadBps": None, "totalDebt": 1}, 1e9)

    def test_rows_use_the_rule(self):
        ranked = [{"symbol": "LOW", "name": "Lowco", "siPctFloat": 0.4, "marketCap": 5e9}, {"symbol": "OK", "name": "Okco", "siPctFloat": 0.3, "marketCap": 5e9}]
        credit = {"LOW": {"interestExpense": 1e6, "totalDebt": 800e6, "ebit": 5e6}, "OK": {"interestExpense": 60e6, "totalDebt": 800e6, "ebit": 100e6}}
        rows = {r["symbol"]: r for r in si.build_rows(ranked, {}, {}, credit, 4.0)}
        assert rows["LOW"]["spreadBps"] is None and rows["LOW"]["displacement"]["key"] == "none" and rows["LOW"]["interestPaid"]["impliedRate"] == 0.12      # still shown, just not used
        assert rows["OK"]["spreadBps"] == 350 and rows["OK"]["spreadIsProxy"] is True and rows["OK"]["displacement"]["key"] == "equity_leads"


class TestDisplacement:
    @pytest.mark.parametrize("spread,key", [(80, "equity_leads"), (399, "equity_leads"), (400, "partial"), (699, "partial"), (700, "confirmed"), (1500, "confirmed"), (None, "none")])
    def test_thresholds(self, spread, key):
        d = si.classify_displacement(0.3, spread)
        assert d["key"] == key and d["label"] and d["text"] and "30% of the float" in d["text"]

    def test_default_overrides_a_tight_spread(self):
        assert si.classify_displacement(0.2, 150, in_default=True)["key"] == "confirmed"

    def test_proxy_is_labelled(self):
        assert "implied-rate proxy" in si.classify_displacement(0.2, 600, is_proxy=True)["text"]
        assert "bond spreads" in si.classify_displacement(0.2, 600)["text"]

    def test_equity_leads_text_mentions_squeeze_risk(self):
        assert "squeeze" in si.classify_displacement(0.4, 100)["text"]


class TestBuildRows:
    def ranked(self):
        return [{"symbol": "AAA", "name": "Alpha Corp", "siPctFloat": 0.5, "sharesShort": 20e6, "prevShort": 16e6, "changePct": 25.0},
                {"symbol": "GGG", "name": "Gamma Inc", "siPctFloat": 0.4, "sharesShort": 10e6, "prevShort": 10e6, "changePct": 0.0},
                {"symbol": "ZZZ", "name": "Zeta Labs", "siPctFloat": 0.3, "sharesShort": 5e6, "prevShort": 6e6, "changePct": -16.0},
                {"symbol": "YYY", "name": "Yotta Ltd", "siPctFloat": 0.2, "sharesShort": 3e6, "prevShort": 3e6, "changePct": 1.0}]

    def test_attaches_borrow_bonds_proxy_and_displacement(self):
        borrow, _ = si.parse_ibkr(IBKR)
        credit = {"ZZZ": {"interestExpense": 30e6, "totalDebt": 300e6, "ebit": 60e6, "totalCash": 0}}
        rows = {r["symbol"]: r for r in si.build_rows(self.ranked(), borrow, build_index(), credit, 4.0)}
        a = rows["AAA"]
        assert a["borrow"]["fee"] == 16.0 and a["borrow"]["band"]["key"] == "hard" and a["bonds"]["count"] == 2 and a["spreadIsProxy"] is False
        assert a["displacement"]["key"] == "equity_leads" and a["spreadBps"] == a["bonds"]["avgSpreadBps"]
        assert rows["GGG"]["displacement"]["key"] == "confirmed" and rows["GGG"]["bonds"]["inDefault"]
        z = rows["ZZZ"]                                                                           # no bonds: falls back to the interest-paid proxy
        assert z["bonds"] is None and z["spreadIsProxy"] is True and z["spreadBps"] == 600 and z["displacement"]["key"] == "partial"
        y = rows["YYY"]
        assert y["borrow"] is None and y["spreadBps"] is None and y["spreadIsProxy"] is None and y["displacement"]["key"] == "none" and y["displacementScore"] is None

    def test_percentiles_and_displacement_score(self):
        rows = {r["symbol"]: r for r in si.build_rows(self.ranked(), {}, build_index(), {"ZZZ": {"interestExpense": 30e6, "totalDebt": 300e6}}, 4.0)}
        assert rows["AAA"]["equityPercentile"] == 100 and rows["YYY"]["equityPercentile"] == 25
        assert rows["AAA"]["creditPercentile"] is not None and rows["AAA"]["displacementScore"] == rows["AAA"]["equityPercentile"] - rows["AAA"]["creditPercentile"]

    def test_summary(self):
        borrow, _ = si.parse_ibkr(IBKR)
        s = si.summarize(si.build_rows(self.ranked(), borrow, build_index(), {}, 4.0))
        assert s["count"] == 4 and s["medianSi"] == 0.4 and s["above30"] == 3 and s["withBorrow"] == 1 and s["hardToBorrow"] == 1
        assert s["mostExpensive"][0] == {"symbol": "AAA", "fee": 16.0} and s["biggestIncreases"][0]["symbol"] == "AAA"
        assert s["withBonds"] == 2 and s["displacement"]["confirmed"] == 1 and s["displacement"]["equity_leads"] == 1 and s["displacement"]["none"] == 2
        json.dumps(s)

    def test_json_safe(self):
        borrow, _ = si.parse_ibkr(IBKR)
        json.dumps(si.build_rows(self.ranked(), borrow, build_index(), {}, 4.0))


class TestData:
    def test_latest_finra_text_walks_back_to_the_newest_file(self, monkeypatch):
        calls = []

        class R:
            def __init__(self, code, text=""): self.status_code, self.text = code, text
            def raise_for_status(self): pass
        monkeypatch.setattr(data.requests, "head", lambda url, **kw: (calls.append(url), R(200 if url.endswith("shrt20260915.csv") else 404))[1])
        monkeypatch.setattr(data.requests, "get", lambda url, **kw: R(200, "csv"))
        text, settlement = data.latest_finra_text(today=date(2026, 9, 20))
        assert (text, settlement) == ("csv", "2026-09-15") and len(calls) == 6

    def test_no_file_raises(self, monkeypatch):
        class R:
            status_code = 404
        monkeypatch.setattr(data.requests, "head", lambda *a, **k: R())
        with pytest.raises(RuntimeError):
            data.latest_finra_text(today=date(2026, 1, 1), lookback_days=3)

    def test_finra_candidates_are_cached(self, monkeypatch):
        calls = []
        monkeypatch.setattr(data, "latest_finra_text", lambda: (calls.append(1), (FINRA, "2026-09-15"))[1])
        a = data.finra_candidates()
        assert a["settlement"] == "2026-09-15" and {r["symbol"] for r in a["rows"]} == {"AAA", "BBB", "HHH"}
        assert data.finra_candidates() == a and len(calls) == 1

    def test_ibkr_is_parsed_filtered_and_cached(self, monkeypatch):
        made = []

        class FakeFTP:
            def __init__(self, host, timeout=0): made.append(host)
            def login(self, u, p): assert (u, p) == ("shortstock", "")
            def retrbinary(self, cmd, cb): cb(IBKR.encode())
            def quit(self): pass
        monkeypatch.setattr(data.ftplib, "FTP", FakeFTP)
        out = data.ibkr_borrow()
        assert out["stamp"] == "2026-10-11 17:43:33" and set(out["data"]) == {"AAA", "BBB", "CCC", "HHH"} and data.ibkr_borrow() == out and len(made) == 1

    def test_fetch_info_caches_marks_empty_and_never_caches_failures(self, monkeypatch):
        class T:
            def __init__(self, s): self.s = s
            @property
            def info(self):
                if self.s == "BOOM":
                    raise RuntimeError("Too Many Requests. Rate limited.")
                return {} if self.s == "EMPTY" else {"shortName": "Ok Co", "marketCap": 2e9, "floatShares": 5e7, "quoteType": "EQUITY", "currentPrice": 12.0, "52WeekChange": -0.4}
        monkeypatch.setattr(data.yf, "Ticker", T)
        monkeypatch.setattr(data.yahoo_limits, "_pause_until", 0.0)
        monkeypatch.setattr(data.yahoo_limits, "BACKOFF", (0, 0, 0))
        got = data.fetch_info("OK")
        assert got["name"] == "Ok Co" and got["floatShares"] == 5e7 and got["change52w"] == -0.4 and data.fetch_info("OK") == got
        assert data.fetch_info("EMPTY") is None and data.cached_many("si:info:", ["EMPTY"]) == ({}, [])           # a clean "nothing there" is remembered
        assert data.fetch_info("BOOM") is None and data.cached_many("si:info:", ["BOOM"]) == ({}, ["BOOM"])        # a rate-limit is not

    def test_fetch_credit_reads_the_newest_non_empty_year(self, monkeypatch):
        import pandas as pd

        class T:
            def __init__(self, s): pass
            income_stmt = pd.DataFrame([[None, -30e6, -25e6], [90e6, 80e6, 70e6]], index=["Interest Expense", "EBIT"], columns=[2025, 2024, 2023])
        monkeypatch.setattr(data.yf, "Ticker", T)
        assert data.fetch_credit("X") == {"ok": True, "interestExpense": -30e6, "ebit": 90e6}

    def test_ust10(self):
        assert data.ust10([{"years": 5, "yield": 3.9}, {"years": 10, "yield": 4.2}]) == 4.2 and data.ust10([{"years": 5, "yield": 3.9}]) is None


class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch):
        finra_rows = si.select_candidates(si.parse_finra(FINRA))
        monkeypatch.setattr(data, "finra_candidates", lambda: {"settlement": "2026-09-15", "rows": finra_rows})
        state = {"info": False, "credit": False, "funds": False, "cooling": set(), "scans": []}
        infos = {"AAA": info("AAA", name="Alpha Corp", floatShares=40e6), "BBB": info("BBB", floatShares=8e6, name="Beta Corp"), "HHH": info("HHH", floatShares=4e6, marketCap=100e6)}

        def many(prefix, syms, ttl=None):
            if prefix == "si:info:":
                return ({s: infos[s] for s in syms if s in infos}, []) if state["info"] else ({}, list(syms))
            return ({s: {"ok": True, "interestExpense": 10e6, "ebit": 50e6} for s in syms}, []) if state["credit"] else ({}, list(syms))
        monkeypatch.setattr(data, "cached_many", many)
        monkeypatch.setattr(data, "bond_funds_ready", lambda: (data.BOND_FUNDS, []) if state["funds"] else ([], list(data.BOND_FUNDS)))
        monkeypatch.setattr(data, "bond_index", lambda: build_index())
        monkeypatch.setattr(data, "ibkr_borrow", lambda: {"stamp": "2026-10-11 17:43:33", "data": si.parse_ibkr(IBKR)[0]})
        monkeypatch.setattr(data, "treasury_curve", lambda: [{"years": 10, "yield": 4.0}])
        monkeypatch.setattr(scanner, "start_scan", lambda k, syms, fetch=None: (state["scans"].append((k, len(syms))), {"done": 1, "error": None, "running": True})[1])
        monkeypatch.setattr(scanner, "cooling_down", lambda k: k in state["cooling"])
        store = {}
        monkeypatch.setattr(router_mod, "cache_get", lambda k, ttl=None: store.get(k))
        monkeypatch.setattr(router_mod, "cache_set", lambda k, v: store.__setitem__(k, v))
        app = FastAPI(); app.include_router(router_mod.router)
        c = TestClient(app); c.state, c.store = state, store
        return c

    def test_stages_report_progress_in_order(self, client):
        j = client.get("/api/short-interest").json()
        assert j["status"] == "running" and j["stage"] == 1 and j["stages"] == 3 and "float" in j["stageLabel"] and j["progress"]["total"] == 3
        client.state["info"] = True
        j = client.get("/api/short-interest").json()
        assert j["stage"] == 2 and "interest" in j["stageLabel"]
        client.state["credit"] = True
        j = client.get("/api/short-interest").json()
        assert j["stage"] == 3 and "bond" in j["stageLabel"] and j["progress"]["total"] == len(data.BOND_FUNDS)
        assert [k for k, _ in client.state["scans"]] == [data.CANDIDATE_JOB, data.CREDIT_JOB, data.BOND_JOB]

    def test_ready_payload(self, client):
        client.state.update(info=True, credit=True, funds=True)
        j = client.get("/api/short-interest?limit=100&min_cap=300").json()
        assert j["status"] == "ready" and j["settlement"] == "2026-09-15" and j["borrowAsOf"] == "2026-10-11 17:43:33" and j["treasury10y"] == 4.0
        assert [r["symbol"] for r in j["rows"]] == ["BBB", "AAA"]                                       # 5m/8m = 62.5% beats 20m/40m = 50%
        a = next(r for r in j["rows"] if r["symbol"] == "AAA")
        assert a["borrow"]["fee"] == 16.0 and a["bonds"]["count"] == 2 and a["displacement"]["key"] == "equity_leads"
        assert j["summary"]["count"] == 2 and j["partial"] is None and j["bondFunds"] == data.BOND_FUNDS
        json.dumps(j)

    def test_min_cap_changes_the_list_and_results_are_cached_per_setting(self, client):
        client.state.update(info=True, credit=True, funds=True)
        assert len(client.get("/api/short-interest?min_cap=300").json()["rows"]) == 2
        assert len(client.get("/api/short-interest?min_cap=100").json()["rows"]) == 3
        assert "short:built:100:300" in client.store and "short:built:100:100" in client.store

    def test_partial_when_a_stage_is_cooling_down(self, client):
        client.state.update(info=True, credit=False, funds=False, cooling={data.CREDIT_JOB, data.BOND_JOB})
        j = client.get("/api/short-interest").json()
        assert j["status"] == "ready" and j["partial"] and "Interest-paid" in j["partial"]["note"] and "Bond holdings" in j["partial"]["note"]
        assert all(r["bonds"] is None for r in j["rows"]) and not client.store                  # partial results are never cached

    def test_borrow_outage_is_reported_not_fatal(self, client, monkeypatch):
        client.state.update(info=True, credit=True, funds=True)
        monkeypatch.setattr(data, "ibkr_borrow", lambda: (_ for _ in ()).throw(OSError("ftp down")))
        j = client.get("/api/short-interest").json()
        assert j["status"] == "ready" and all(r["borrow"] is None for r in j["rows"]) and any("Borrow rates are unavailable" in n for n in j["notes"])

    def test_validation_and_failure(self, client, monkeypatch):
        assert client.get("/api/short-interest?limit=5").status_code == 422
        assert client.get("/api/short-interest?min_cap=-1").status_code == 422
        monkeypatch.setattr(data, "finra_candidates", lambda: (_ for _ in ()).throw(RuntimeError("finra down")))
        r = client.get("/api/short-interest")
        assert r.status_code == 502 and "finra down" in r.json()["detail"]
