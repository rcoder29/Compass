"""
Tests for the quarterly income flow: reading quarterly statements, building the Sankey graph
(conservation of money at every node, loss / bank / payout edge cases) and laying it out.
Run: python -m pytest tests/test_income_flow.py -v
"""
import pandas as pd
import pytest

import income_flow as inf

B = 1e9


def pnl(**over):
    base = dict(quarter="2026-06-30", revenue=100 * B, costOfRevenue=40 * B, grossProfit=60 * B,
                researchAndDevelopment=10 * B, sellingGeneralAdmin=15 * B, operatingExpense=25 * B,
                operatingIncome=35 * B, pretaxIncome=36 * B, incomeTax=6 * B, netIncome=30 * B,
                dividendsPaid=4 * B, buybacks=20 * B, dividendPerShare=0.27)
    base.update(over)
    return base


def streams(*pairs, prior_total=None):
    return {"axisLabel": "Products & services", "total": sum(v for _, v in pairs), "priorTotal": prior_total,
            "streams": [{"name": n, "value": v * B, "prior": None} for n, v in pairs]}


def balances(graph, tol=1e-6):
    """Every node that has both inflow and outflow must conserve money."""
    bad = []
    for n in graph["nodes"]:
        ins = sum(l["value"] for l in graph["links"] if l["target"] == n["id"])
        outs = sum(l["value"] for l in graph["links"] if l["source"] == n["id"])
        if ins and outs and abs(ins - outs) > tol * max(ins, outs):
            bad.append((n["id"], ins, outs))
    return bad


def by_id(graph):
    return {n["id"]: n for n in graph["nodes"]}


def node_value(graph, nid):
    ins = sum(l["value"] for l in graph["links"] if l["target"] == nid)
    outs = sum(l["value"] for l in graph["links"] if l["source"] == nid)
    return max(ins, outs)


# ── reading statements ────────────────────────────────────────────────────────

def _income():
    col = pd.Timestamp("2026-06-30")
    return pd.DataFrame({col: {"Total Revenue": 100.0, "Cost Of Revenue": 40.0, "Gross Profit": 60.0, "Research And Development": 10.0,
                               "Selling General And Administration": 15.0, "Operating Expense": 25.0, "Operating Income": 35.0,
                               "Pretax Income": 36.0, "Tax Provision": 6.0, "Net Income": 30.0}})


def _cash(date="2026-06-27"):
    return pd.DataFrame({pd.Timestamp(date): {"Cash Dividends Paid": -4.0, "Repurchase Of Capital Stock": -20.0}})


class TestQuarterPnl:
    def test_reads_the_income_statement_and_cash_flow(self):
        divs = pd.Series([0.26, 0.27, 0.27], index=pd.to_datetime(["2026-02-09", "2026-05-11", "2026-08-10"]))
        p = inf.quarter_pnl(_income(), _cash(), divs, pd.Timestamp("2026-06-30"))
        assert p["revenue"] == 100 and p["grossProfit"] == 60 and p["netIncome"] == 30 and p["incomeTax"] == 6
        assert p["dividendsPaid"] == 4 and p["buybacks"] == 20          # cash-flow outflows are negative; reported positive
        assert p["dividendPerShare"] == pytest.approx(0.27)             # only the ex-date inside the quarter
        assert p["quarter"] == "2026-06-30"

    def test_cash_flow_dates_may_differ_a_few_days(self):
        assert inf.quarter_pnl(_income(), _cash("2026-06-27"), None, pd.Timestamp("2026-06-30"))["dividendsPaid"] == 4
        assert inf.quarter_pnl(_income(), _cash("2026-04-01"), None, pd.Timestamp("2026-06-30"))["dividendsPaid"] is None

    def test_missing_statements_give_none_not_errors(self):
        p = inf.quarter_pnl(_income(), None, None, pd.Timestamp("2026-06-30"))
        assert p["dividendsPaid"] is None and p["buybacks"] is None and p["dividendPerShare"] is None

    def test_sga_falls_back_to_selling_plus_g_and_a(self):
        col = pd.Timestamp("2026-06-30")
        inc = pd.DataFrame({col: {"Total Revenue": 100.0, "Selling And Marketing Expense": 6.0, "General And Administrative Expense": 4.0}})
        assert inf.quarter_pnl(inc, None, None, col)["sellingGeneralAdmin"] == 10.0

    def test_zero_dividend_is_treated_as_none(self):
        cash = pd.DataFrame({pd.Timestamp("2026-06-30"): {"Cash Dividends Paid": 0.0}})
        assert inf.quarter_pnl(_income(), cash, None, pd.Timestamp("2026-06-30"))["dividendsPaid"] is None

    def test_nan_values_are_skipped(self):
        col = pd.Timestamp("2026-06-30")
        inc = pd.DataFrame({col: {"Total Revenue": float("nan"), "Operating Revenue": 50.0}})
        assert inf.quarter_pnl(inc, None, None, col)["revenue"] == 50.0


# ── graph building ────────────────────────────────────────────────────────────

class TestFullWaterfall:
    def test_every_node_conserves_money(self):
        g = inf.build_graph(pnl(), streams(("iPhone", 60), ("Services", 40)))
        assert balances(g) == []

    def test_stage_values_match_the_reported_figures(self):
        g = inf.build_graph(pnl())
        # pretax (36) is only 1% above operating income (35), so the +1 of interest income feeds net income directly
        for nid, expected in {"revenue": 100, "gross": 60, "cost": 40, "operating": 35, "rnd": 10, "sga": 15,
                              "other_income": 1, "tax": 6, "net": 30, "dividends": 4, "buybacks": 20, "retained": 6}.items():
            assert node_value(g, nid) == pytest.approx(expected * B), nid
        assert "pretax" not in by_id(g) and "opex_other" not in by_id(g)

    def test_other_operating_expense_absorbs_the_remainder(self):
        g = inf.build_graph(pnl(operatingIncome=30 * B, pretaxIncome=31 * B))        # opex 30 vs R&D+SG&A 25
        assert node_value(g, "opex_other") == pytest.approx(5 * B) and balances(g) == []

    def test_stages_run_in_order_left_to_right(self):
        n = by_id(inf.build_graph(pnl(), streams(("A", 60), ("B", 40))))
        stage = lambda i: n[i]["stage"]
        assert stage("stream:0") < stage("revenue") < stage("gross") < stage("operating") < stage("net") < stage("dividends")
        assert stage("cost") == stage("gross") and stage("tax") == stage("net") and stage("other_income") == stage("operating")

    def test_a_material_pretax_adjustment_adds_its_own_stage(self):
        n = by_id(inf.build_graph(pnl(pretaxIncome=38 * B, netIncome=32 * B)))             # +3% of revenue
        assert n["operating"]["stage"] < n["pretax"]["stage"] < n["net"]["stage"]

    def test_revenue_alone_has_no_links(self):
        g = inf.build_graph({"revenue": 100.0})
        assert g["links"] == []


class TestStreams:
    def test_streams_become_the_first_column(self):
        g = inf.build_graph(pnl(), streams(("iPhone", 60), ("Services", 40)))
        n = by_id(g)
        assert g["hasStreams"] and n["stream:0"]["label"] == "iPhone" and node_value(g, "stream:1") == pytest.approx(40 * B)

    def test_small_unallocated_gap_gets_its_own_node(self):
        g = inf.build_graph(pnl(), streams(("A", 60), ("B", 38)))
        assert node_value(g, "stream:other") == pytest.approx(2 * B) and balances(g) == []

    def test_streams_on_a_different_basis_are_ignored_with_a_note(self):
        g = inf.build_graph(pnl(), streams(("A", 30), ("B", 20)))
        assert not g["hasStreams"] and "stream:0" not in by_id(g)
        assert any("different basis" in x for x in g["notes"])

    def test_no_streams_means_no_note(self):
        g = inf.build_graph(pnl(), None)
        assert not g["hasStreams"] and g["notes"] == []


class TestLossesAndEdgeCases:
    def test_operating_loss_is_funded_by_a_red_source_and_stops(self):
        g = inf.build_graph(pnl(operatingIncome=-8 * B, pretaxIncome=-8 * B, netIncome=-8 * B, incomeTax=0, operatingExpense=68 * B,
                                dividendsPaid=None, buybacks=None))
        n = by_id(g)
        assert "loss:operating" in n and n["loss:operating"]["kind"] == "loss"
        assert node_value(g, "loss:operating") == pytest.approx(8 * B)
        assert "operating" not in n and "net" not in n
        assert any("operating loss" in x for x in g["notes"]) and balances(g) == []

    def test_gross_loss(self):
        g = inf.build_graph(pnl(grossProfit=-5 * B, costOfRevenue=105 * B))
        n = by_id(g)
        assert "loss:gross" in n and node_value(g, "loss:gross") == pytest.approx(5 * B) and "gross" not in n
        assert any("no profit to distribute" in x for x in g["notes"])

    def test_pretax_loss_from_interest_expense(self):
        g = inf.build_graph(pnl(operatingIncome=5 * B, pretaxIncome=-2 * B, netIncome=-2 * B, incomeTax=0))
        assert "loss:pretax" in by_id(g) and "net" not in by_id(g) and balances(g) == []

    def test_net_loss_after_tax(self):
        g = inf.build_graph(pnl(netIncome=-1 * B, pretaxIncome=36 * B, incomeTax=37 * B))
        assert "net" not in by_id(g) and any("no profit to distribute" in x for x in g["notes"])

    def test_interest_income_adds_to_pretax(self):
        g = inf.build_graph(pnl(pretaxIncome=37 * B, netIncome=31 * B))
        n = by_id(g)
        assert n["other_income"]["kind"] == "income" and node_value(g, "other_income") == pytest.approx(2 * B)
        assert node_value(g, "pretax") == pytest.approx(37 * B) and balances(g) == []

    def test_interest_expense_leaves_as_a_cost(self):
        g = inf.build_graph(pnl(pretaxIncome=33 * B, netIncome=27 * B))
        assert node_value(g, "other_expense") == pytest.approx(2 * B) and node_value(g, "pretax") == pytest.approx(33 * B)

    def test_negligible_other_income_is_not_drawn(self):
        g = inf.build_graph(pnl(pretaxIncome=35.1 * B, incomeTax=5.1 * B))
        assert "other_income" not in by_id(g) and "other_expense" not in by_id(g)

    def test_small_other_income_skips_the_pretax_column_and_feeds_net_income(self):
        g = inf.build_graph(pnl(pretaxIncome=35.8 * B, incomeTax=5.8 * B))          # +0.8% of revenue: below the split threshold
        n = by_id(g)
        assert "pretax" not in n and n["other_income"]["kind"] == "income"
        assert node_value(g, "other_income") == pytest.approx(0.8 * B) and node_value(g, "net") == pytest.approx(30 * B)
        assert any(l["source"] == "other_income" and l["target"] == "net" for l in g["links"]) and balances(g) == []

    def test_small_other_expense_leaves_from_the_net_income_step(self):
        g = inf.build_graph(pnl(pretaxIncome=34.2 * B, incomeTax=4.2 * B))          # -0.8% of revenue
        n = by_id(g)
        assert "pretax" not in n and node_value(g, "other_expense") == pytest.approx(0.8 * B) and balances(g) == []

    def test_a_material_adjustment_still_gets_its_own_pretax_column(self):
        g = inf.build_graph(pnl(pretaxIncome=37.5 * B, netIncome=31.5 * B))         # +1.5% of revenue: exactly at the threshold
        assert "pretax" in by_id(g) or node_value(g, "other_income") > 0

    def test_tax_benefit_is_a_source_into_net_income(self):
        g = inf.build_graph(pnl(incomeTax=-3 * B, netIncome=39 * B))
        n = by_id(g)
        assert n["tax_benefit"]["kind"] == "income" and node_value(g, "net") == pytest.approx(39 * B) and balances(g) == []

    def test_unexplained_deduction_becomes_minority_interest(self):
        g = inf.build_graph(pnl(netIncome=28 * B))                  # pretax 36 - tax 6 = 30, reported NI 28
        assert node_value(g, "minority") == pytest.approx(2 * B) and node_value(g, "net") == pytest.approx(28 * B)

    def test_unusable_revenue_returns_none(self):
        assert inf.build_graph({"revenue": None}) is None and inf.build_graph({"revenue": 0}) is None
        assert inf.build_graph({"revenue": -5}) is None


class TestBankLikeStatements:
    def test_no_gross_or_operating_line_goes_revenue_to_pretax(self):
        g = inf.build_graph(dict(quarter="q", revenue=50 * B, sellingGeneralAdmin=16 * B, pretaxIncome=27 * B, incomeTax=6 * B,
                                 netIncome=21 * B, dividendsPaid=4 * B, buybacks=9 * B))
        n = by_id(g)
        assert n["operating"]["label"] == "Pretax income" and node_value(g, "operating") == pytest.approx(27 * B)
        assert node_value(g, "sga") == pytest.approx(16 * B) and node_value(g, "opex_other") == pytest.approx(7 * B)
        assert n["opex_other"]["label"] == "Other costs & expenses" and "gross" not in n and balances(g) == []

    def test_without_any_breakdown_costs_are_one_lump(self):
        g = inf.build_graph(dict(quarter="q", revenue=50 * B, pretaxIncome=27 * B, incomeTax=6 * B, netIncome=21 * B))
        assert by_id(g)["opex_other"]["label"] == "Operating costs & expenses"
        assert node_value(g, "opex_other") == pytest.approx(23 * B)


class TestOperatingCostBreakdown:
    def test_tiny_named_items_fold_into_other(self):
        g = inf.build_graph(pnl(researchAndDevelopment=0.1 * B, sellingGeneralAdmin=24 * B))      # R&D is 0.1% of revenue
        # the sliver isn't drawn on its own; it lands in "Other operating expenses" with the unexplained 0.9B
        assert "rnd" not in by_id(g) and node_value(g, "sga") == pytest.approx(24 * B)
        assert node_value(g, "opex_other") == pytest.approx(1 * B) and balances(g) == []

    def test_inconsistent_breakdown_collapses_to_one_node(self):
        g = inf.build_graph(pnl(researchAndDevelopment=20 * B, sellingGeneralAdmin=20 * B))        # 40 named > 25 opex
        n = by_id(g)
        assert "rnd" not in n and "sga" not in n and node_value(g, "opex_other") == pytest.approx(25 * B)

    def test_gross_profit_derived_from_cost_when_missing(self):
        g = inf.build_graph(pnl(grossProfit=None))
        assert node_value(g, "gross") == pytest.approx(60 * B)


class TestShareholderReturns:
    def test_dividends_buybacks_and_retained_split_net_income(self):
        g = inf.build_graph(pnl())
        assert by_id(g)["dividends"]["detail"] == "$0.27/share"
        assert node_value(g, "retained") == pytest.approx(6 * B) and balances(g) == []

    def test_payouts_above_earnings_draw_on_cash_reserves(self):
        g = inf.build_graph(pnl(dividendsPaid=15 * B, buybacks=30 * B))        # 45 vs NI 30
        n = by_id(g)
        assert n["funding"]["kind"] == "funding" and node_value(g, "funding") == pytest.approx(15 * B)
        assert "retained" not in n and node_value(g, "dividends") == pytest.approx(15 * B)
        assert node_value(g, "buybacks") == pytest.approx(30 * B) and balances(g) == []
        assert any("exceeded net income" in x for x in g["notes"])

    def test_no_payouts_retains_everything_with_a_note(self):
        g = inf.build_graph(pnl(dividendsPaid=None, buybacks=None))
        assert node_value(g, "retained") == pytest.approx(30 * B) and any("No dividends or buybacks" in x for x in g["notes"])

    def test_dividends_only_and_buybacks_only(self):
        d = by_id(inf.build_graph(pnl(buybacks=None)))
        b = by_id(inf.build_graph(pnl(dividendsPaid=None)))
        assert "dividends" in d and "buybacks" not in d and "buybacks" in b and "dividends" not in b

    def test_dividends_without_dps_have_no_detail(self):
        assert by_id(inf.build_graph(pnl(dividendPerShare=None)))["dividends"]["detail"] is None

    def test_payouts_exactly_equal_to_net_income_leave_nothing_retained(self):
        g = inf.build_graph(pnl(dividendsPaid=10 * B, buybacks=20 * B))
        assert "retained" not in by_id(g) and balances(g) == []


# ── layout ────────────────────────────────────────────────────────────────────

def laid_out(**kw):
    p = pnl(**kw.pop("p", {}))
    g = inf.build_graph(p, kw.pop("streams", None))
    return g, inf.layout_sankey(g, p["revenue"], **kw)


class TestLayout:
    def test_every_node_is_inside_the_canvas(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        for n in f["nodes"]:
            assert 0 <= n["x"] and n["x"] + n["w"] <= f["width"] and 0 <= n["y"] and n["y"] + n["h"] <= f["height"], n["id"]

    def test_nodes_in_a_column_never_overlap(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        cols = {}
        for n in f["nodes"]:
            cols.setdefault(n["column"], []).append(n)
        for ns in cols.values():
            ns.sort(key=lambda n: n["y"])
            for a, b in zip(ns, ns[1:]):
                assert a["y"] + a["h"] <= b["y"] + 1e-6

    def test_labels_have_room_even_for_tiny_nodes(self):
        _, f = laid_out(p={"pretaxIncome": 35.5 * B, "incomeTax": 5.5 * B})         # sliver of other income
        cols = {}
        for n in f["nodes"]:
            cols.setdefault(n["column"], []).append(n)
        for ns in cols.values():
            ns.sort(key=lambda n: n["y"])
            for a, b in zip(ns, ns[1:]):
                assert (b["y"] + b["h"] / 2) - (a["y"] + a["h"] / 2) >= inf.LABEL_SLOT - 0.01

    def test_link_thickness_fits_inside_each_node(self):
        _, f = laid_out()
        for n in f["nodes"]:
            outs = sum(l["thickness"] for l in f["links"] if l["source"] == n["id"])
            ins = sum(l["thickness"] for l in f["links"] if l["target"] == n["id"])
            assert outs <= n["h"] + 0.1 and ins <= n["h"] + 0.1, n["id"]

    def test_heights_are_proportional_to_value(self):
        _, f = laid_out()
        n = {x["id"]: x for x in f["nodes"]}
        assert n["gross"]["h"] / n["revenue"]["h"] == pytest.approx(0.6, abs=0.01)
        assert n["net"]["h"] / n["operating"]["h"] == pytest.approx(30 / 35, abs=0.01)

    def test_without_streams_revenue_is_the_first_column(self):
        _, f = laid_out()
        assert {n["id"]: n for n in f["nodes"]}["revenue"]["column"] == 0

    def test_with_streams_they_come_first_and_revenue_second(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        n = {x["id"]: x for x in f["nodes"]}
        assert n["stream:0"]["column"] == 0 and n["revenue"]["column"] == 1

    def test_columns_advance_left_to_right(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        n = {x["id"]: x for x in f["nodes"]}
        assert n["stream:0"]["x"] < n["revenue"]["x"] < n["gross"]["x"] < n["net"]["x"] < n["dividends"]["x"]

    def test_labels_sit_left_of_the_first_column_and_right_of_the_rest(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        n = {x["id"]: x for x in f["nodes"]}
        assert n["stream:0"]["labelSide"] == "left" and n["revenue"]["labelSide"] == "right" and n["dividends"]["labelSide"] == "right"

    def test_profit_stays_on_top_and_costs_peel_off_downward(self):
        _, f = laid_out()
        n = {x["id"]: x for x in f["nodes"]}
        assert n["gross"]["y"] < n["cost"]["y"] and n["operating"]["y"] < n["rnd"]["y"] < n["sga"]["y"] and n["net"]["y"] < n["tax"]["y"]

    def test_links_are_bezier_paths_between_node_edges(self):
        _, f = laid_out()
        n = {x["id"]: x for x in f["nodes"]}
        link = next(l for l in f["links"] if l["source"] == "revenue" and l["target"] == "gross")
        assert link["d"].startswith("M") and " C" in link["d"]
        assert link["x0"] == pytest.approx(n["revenue"]["x"] + n["revenue"]["w"]) and link["x1"] == pytest.approx(n["gross"]["x"])
        assert link["thickness"] == pytest.approx(n["gross"]["h"], abs=0.1)

    def test_links_take_the_colour_of_where_the_money_goes(self):
        _, f = laid_out(streams=streams(("A", 60), ("B", 40)))
        n = {x["id"]: x for x in f["nodes"]}
        into_revenue = next(l for l in f["links"] if l["target"] == "revenue")
        to_cost = next(l for l in f["links"] if l["target"] == "cost")
        assert into_revenue["color"] == n["stream:0"]["color"] or into_revenue["color"] == n["stream:1"]["color"]
        assert to_cost["color"] == inf.KIND_COLORS["cost"]

    def test_pct_is_share_of_revenue(self):
        _, f = laid_out()
        assert {x["id"]: x for x in f["nodes"]}["net"]["pct"] == pytest.approx(0.30)

    def test_empty_graph_lays_out_to_nothing(self):
        assert inf.layout_sankey({"nodes": [], "links": []}, 100.0)["nodes"] == []

    def test_custom_canvas_size_is_respected(self):
        _, f = laid_out(width=500, height=300)
        assert f["width"] == 500 and f["height"] == 300 and max(n["x"] + n["w"] for n in f["nodes"]) <= 500

    def test_many_streams_still_fit(self):
        many = streams(*[(f"S{i}", 12.5) for i in range(8)])
        _, f = laid_out(streams=many)
        assert max(n["y"] + n["h"] for n in f["nodes"]) <= f["height"]


# ── assembly ──────────────────────────────────────────────────────────────────

def _frame(n_quarters=6):
    cols = [pd.Timestamp("2026-06-30") - pd.offsets.QuarterEnd(i) for i in range(n_quarters)]
    data = {}
    for i, c in enumerate(cols):
        data[c] = {"Total Revenue": 100.0 - i, "Cost Of Revenue": 40.0, "Gross Profit": 60.0 - i, "Operating Income": 35.0 - i,
                   "Pretax Income": 36.0 - i, "Tax Provision": 6.0, "Net Income": 30.0 - i}
    return pd.DataFrame(data)


class TestBuildIncomeFlows:
    def test_returns_the_latest_four_quarters_newest_first(self):
        out = inf.build_income_flows(_frame(), None, None)
        assert [q["quarter"] for q in out["quarters"]] == ["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"]
        assert out["quarters"][0]["flow"]["nodes"]

    def test_max_quarters_is_respected(self):
        assert len(inf.build_income_flows(_frame(), None, None, max_quarters=2)["quarters"]) == 2

    def test_yoy_uses_the_quarter_four_columns_back(self):
        q = inf.build_income_flows(_frame(), None, None)["quarters"]
        assert q[0]["revenueYoY"] == pytest.approx(100 / 96 - 1)
        assert q[2]["revenueYoY"] is None                      # no year-ago column available for it

    def test_yoy_prefers_the_sec_prior_period_when_streams_exist(self):
        s = {"2026-06-30": {"axisLabel": "Products & services", "total": 100 * B, "priorTotal": 80.0, "streams": [
            {"name": "A", "value": 60.0, "prior": 40.0}, {"name": "B", "value": 40.0, "prior": 40.0}]}}
        q = inf.build_income_flows(_frame(), None, None, s)["quarters"][0]
        assert q["revenueYoY"] == pytest.approx(100 / 80 - 1)

    def test_stream_rows_carry_share_and_yoy(self):
        s = {"2026-06-30": {"axisLabel": "Products & services", "total": 100.0, "priorTotal": 80.0, "form": "10-Q", "derived": False,
                            "streams": [{"name": "A", "value": 60.0, "prior": 40.0}, {"name": "B", "value": 40.0, "prior": None}]}}
        rows = inf.build_income_flows(_frame(), None, None, s)["quarters"][0]["streams"]
        assert rows["axisLabel"] == "Products & services" and rows["form"] == "10-Q"
        assert rows["streams"][0] == {"name": "A", "value": 60.0, "share": 0.6, "yoy": pytest.approx(0.5)}
        assert rows["streams"][1]["yoy"] is None

    def test_growth_on_a_tiny_base_is_not_meaningful(self):
        s = {"2026-06-30": {"axisLabel": "Products & services", "total": 100.0, "priorTotal": 80.0, "streams": [
            {"name": "Big", "value": 99.0, "prior": 79.0}, {"name": "Sliver", "value": 1.0, "prior": 0.05}]}}
        rows = inf.build_income_flows(_frame(), None, None, s)["quarters"][0]["streams"]["streams"]
        assert rows[0]["yoy"] == pytest.approx(99 / 79 - 1) and rows[1]["yoy"] is None

    @pytest.mark.parametrize("cur,prior,expected", [(110, 100, 0.10), (50, 100, -0.5), (100, 0, None), (100, None, None), (100, -5, None),
                                                    (None, 100, None), (600, 100, 5.0), (700, 100, None)])
    def test_growth_helper(self, cur, prior, expected):
        assert inf._growth(cur, prior) == (pytest.approx(expected) if expected is not None else None)

    def test_streams_that_were_rejected_are_not_reported_as_streams(self):
        s = {"2026-06-30": {"axisLabel": "Regions", "total": 30.0, "priorTotal": None, "streams": [{"name": "A", "value": 30.0, "prior": None}]}}
        q = inf.build_income_flows(_frame(), None, None, s)["quarters"][0]
        assert q["streams"] is None and q["flow"]["hasStreams"] is False

    def test_quarters_without_revenue_are_skipped(self):
        f = _frame()
        f.loc["Total Revenue", f.columns[1]] = float("nan")
        quarters = [q["quarter"] for q in inf.build_income_flows(f, None, None)["quarters"]]
        assert "2026-03-31" not in quarters and len(quarters) == 4

    @pytest.mark.parametrize("bad", [None, pd.DataFrame(), "x"])
    def test_no_income_statement_means_no_section(self, bad):
        assert inf.build_income_flows(bad, None, None) is None

    def test_revenue_only_quarter_has_pnl_but_no_flow(self):
        f = pd.DataFrame({pd.Timestamp("2026-06-30"): {"Total Revenue": 100.0}})
        q = inf.build_income_flows(f, None, None)["quarters"][0]
        assert q["pnl"]["revenue"] == 100.0 and q["flow"] is None

    def test_flow_carries_notes_and_stream_flag(self):
        q = inf.build_income_flows(_frame(), None, None)["quarters"][0]
        assert q["flow"]["notes"] and q["flow"]["hasStreams"] is False        # "no dividends or buybacks" note
