"""
Tests for revenue-by-income-stream extraction from SEC XBRL: parsing instance documents,
picking the members that reconcile to total revenue, Q4 derivation, labels, and orchestration.
All inputs are synthetic; nothing touches the network.
Run: python -m pytest tests/test_sec_revenue_streams.py -v
"""
from datetime import date

import pytest

import sec_revenue_streams as srs

B = 1e9


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(srs, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(srs, "cache_set", lambda *a, **k: None)


# ── building synthetic instance documents ─────────────────────────────────────

NS = ('xmlns="http://www.xbrl.org/2003/instance" xmlns:xbrli="http://www.xbrl.org/2003/instance" '
      'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:us-gaap="http://fasb.org/us-gaap/2026" '
      'xmlns:co="http://co.example/2026" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')


def ctx(cid, start, end, dims=(), typed=False, instant=False):
    seg = ""
    if dims or typed:
        members = "".join(f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in dims)
        if typed:
            members += '<xbrldi:typedMember dimension="co:CustomerAxis"><co:id>1</co:id></xbrldi:typedMember>'
        seg = f"<xbrli:segment>{members}</xbrli:segment>"
    period = f"<xbrli:instant>{end}</xbrli:instant>" if instant else f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>"
    return f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>{seg}</xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>'


def fact(concept, cid, value, nil=False):
    if nil:
        return f'<us-gaap:{concept} contextRef="{cid}" xsi:nil="true"/>'
    return f'<us-gaap:{concept} contextRef="{cid}" unitRef="usd" decimals="-6">{value}</us-gaap:{concept}>'


def xml(*parts):
    return f"<xbrli:xbrl {NS}>{''.join(parts)}</xbrli:xbrl>".encode()


PROD = "us-gaap:ProductOrServiceAxis"
SEG = "us-gaap:StatementBusinessSegmentsAxis"
REG = "us-gaap:StatementGeographicalAxis"
REVC = "RevenueFromContractWithCustomerExcludingAssessedTax"


# ── parse_instance ────────────────────────────────────────────────────────────

class TestParseInstance:
    def rows(self, *parts):
        return srs.parse_instance(xml(*parts))

    def test_consolidated_total_and_a_product_member(self):
        rows = self.rows(ctx("t", "2026-04-01", "2026-06-30"), ctx("p", "2026-04-01", "2026-06-30", [(PROD, "co:IPhoneMember")]),
                         fact(REVC, "t", 100), fact(REVC, "p", 60))
        assert {"start": "2026-04-01", "end": "2026-06-30", "axis": None, "member": None, "value": 100.0} in rows
        assert {"start": "2026-04-01", "end": "2026-06-30", "axis": "ProductOrServiceAxis", "member": "co:IPhoneMember", "value": 60.0} in rows

    def test_cross_tabs_are_ignored(self):
        rows = self.rows(ctx("x", "2026-04-01", "2026-06-30", [(PROD, "co:A"), (REG, "co:B")]), fact(REVC, "x", 5))
        assert rows == []

    def test_typed_dimension_contexts_are_ignored(self):
        assert self.rows(ctx("x", "2026-04-01", "2026-06-30", typed=True), fact(REVC, "x", 5)) == []

    def test_instant_contexts_are_ignored(self):
        assert self.rows(ctx("x", None, "2026-06-30", instant=True), fact(REVC, "x", 5)) == []

    def test_operating_segment_marker_is_allowed_alongside_the_segment_axis(self):
        rows = self.rows(ctx("s", "2026-04-01", "2026-06-30", [("us-gaap:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember"), (SEG, "co:CloudSegmentMember")]),
                         fact(REVC, "s", 40))
        assert rows[0]["axis"] == "StatementBusinessSegmentsAxis" and rows[0]["member"] == "co:CloudSegmentMember"

    def test_other_consolidation_members_such_as_eliminations_are_ignored(self):
        rows = self.rows(ctx("e", "2026-04-01", "2026-06-30", [("us-gaap:ConsolidationItemsAxis", "us-gaap:IntersegmentEliminationMember")]),
                         fact(REVC, "e", -3))
        assert rows == []

    def test_operating_segments_marker_alone_counts_as_a_total(self):
        rows = self.rows(ctx("s", "2026-04-01", "2026-06-30", [("us-gaap:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember")]), fact("Revenues", "s", 96))
        assert rows[0]["axis"] is None and rows[0]["value"] == 96.0

    def test_unrelated_axes_and_concepts_are_ignored(self):
        rows = self.rows(ctx("a", "2026-04-01", "2026-06-30", [("us-gaap:CustomerConcentrationAxis", "co:BigCo")]), ctx("t", "2026-04-01", "2026-06-30"),
                         fact(REVC, "a", 9), fact("CostOfRevenue", "t", 7), fact("NetIncomeLoss", "t", 3))
        assert rows == []

    def test_nil_and_non_numeric_facts_are_ignored(self):
        rows = self.rows(ctx("t", "2026-04-01", "2026-06-30"), fact(REVC, "t", None, nil=True),
                         '<us-gaap:Revenues contextRef="t" unitRef="usd">n/a</us-gaap:Revenues>')
        assert rows == []

    def test_higher_priority_concept_wins_for_the_same_context(self):
        rows = self.rows(ctx("t", "2026-04-01", "2026-06-30"), fact("Revenues", "t", 90), fact(REVC, "t", 100))
        assert [r["value"] for r in rows] == [100.0]

    def test_fact_pointing_at_an_unknown_context_is_ignored(self):
        assert self.rows(fact(REVC, "missing", 5)) == []


# ── period_values ─────────────────────────────────────────────────────────────

def row(start, end, axis=None, member=None, value=1.0):
    return {"start": start, "end": end, "axis": axis, "member": member, "value": value}


class TestPeriodValues:
    ROWS = [row("2026-04-01", "2026-06-30", None, None, 100), row("2026-04-01", "2026-06-30", "ProductOrServiceAxis", "co:A", 60),
            row("2026-01-01", "2026-06-30", None, None, 190),            # 6-month YTD, wrong length for a quarter
            row("2025-04-01", "2025-06-30", None, None, 80), row("2025-04-01", "2025-06-30", "ProductOrServiceAxis", "co:A", 40)]

    def test_picks_the_quarter_ending_at_the_target(self):
        total, axes = srs.period_values(self.ROWS, date(2026, 6, 30), 80, 100)
        assert total == 100 and axes == {"ProductOrServiceAxis": {"co:A": 60}}

    def test_year_ago_quarter(self):
        assert srs.period_values(self.ROWS, date(2025, 6, 30), 80, 100)[0] == 80

    def test_end_date_tolerance(self):
        assert srs.period_values(self.ROWS, date(2026, 6, 27), 80, 100)[0] == 100
        assert srs.period_values(self.ROWS, date(2026, 5, 1), 80, 100) == (None, {})

    def test_length_window_selects_ytd_or_full_year(self):
        assert srs.period_values(self.ROWS, date(2026, 6, 30), 170, 190)[0] == 190

    def test_closest_end_wins_when_several_are_in_tolerance(self):
        rows = [row("2026-04-01", "2026-06-27", None, None, 99), row("2026-04-01", "2026-06-30", None, None, 100)]
        assert srs.period_values(rows, date(2026, 6, 30), 80, 100)[0] == 100


# ── choose_partition ──────────────────────────────────────────────────────────

class TestChoosePartition:
    def test_ignores_an_aggregate_and_returns_its_children(self):
        members = {"Products": 79.0, "iPhone": 54.0, "Mac": 10.0, "iPad": 6.0, "Wearables": 9.0, "Services": 30.0}
        assert sorted(srs.choose_partition(members, 109.0)) == ["Mac", "Services", "Wearables", "iPad", "iPhone"]

    def test_prefers_the_finer_partition(self):
        members = {"Products": 79.0, "Services": 30.0, "iPhone": 54.0, "Other products": 25.0}
        assert sorted(srs.choose_partition(members, 109.0)) == ["Other products", "Services", "iPhone"]

    def test_none_when_nothing_adds_up(self):
        assert srs.choose_partition({"A": 60.0, "B": 25.0}, 100.0) is None

    def test_a_single_member_is_not_a_breakdown(self):
        assert srs.choose_partition({"All": 100.0}, 100.0) is None

    def test_accidental_near_sums_are_rejected_by_the_tight_tolerance(self):
        assert srs.choose_partition({"A": 40.0, "B": 59.0}, 100.0) is None       # 1% off: not a real partition

    def test_small_unallocated_item_within_tolerance_is_accepted(self):
        assert sorted(srs.choose_partition({"A": 60.0, "B": 39.8}, 100.0)) == ["A", "B"]

    def test_non_positive_members_and_totals(self):
        assert srs.choose_partition({"A": 60.0, "B": 40.0, "Elim": -5.0, "Zero": 0.0}, 100.0) == ["A", "B"]
        assert srs.choose_partition({"A": 1.0, "B": 1.0}, 0) is None and srs.choose_partition({"A": 1.0}, None) is None

    def test_many_members_stay_fast(self):
        members = {f"M{i}": 1.0 + i * 0.37 for i in range(40)}
        assert srs.choose_partition(members, 12345.0) is None


# ── streams_from_values ───────────────────────────────────────────────────────

class TestStreamsFromValues:
    def test_products_axis_is_preferred_over_segments(self):
        axes = {"StatementBusinessSegmentsAxis": {"co:S1": 60.0, "co:S2": 40.0}, "ProductOrServiceAxis": {"co:P1": 70.0, "co:P2": 30.0}}
        out = srs.streams_from_values(100.0, axes)
        assert out["axisLabel"] == "Products & services" and [s["member"] for s in out["streams"]] == ["co:P1", "co:P2"]

    def test_falls_through_to_the_next_axis_that_reconciles(self):
        axes = {"ProductOrServiceAxis": {"co:P1": 20.0, "co:P2": 10.0}, "StatementGeographicalAxis": {"co:US": 55.0, "co:EU": 45.0}}
        assert srs.streams_from_values(100.0, axes)["axisLabel"] == "Regions"

    def test_none_when_no_axis_reconciles(self):
        assert srs.streams_from_values(100.0, {"ProductOrServiceAxis": {"co:P1": 20.0, "co:P2": 10.0}}) is None
        assert srs.streams_from_values(None, {}) is None and srs.streams_from_values(100.0, {}) is None

    def test_streams_sorted_largest_first_with_prior_values(self):
        out = srs.streams_from_values(100.0, {"ProductOrServiceAxis": {"co:A": 30.0, "co:B": 70.0}}, 90.0,
                                      {"ProductOrServiceAxis": {"co:A": 20.0, "co:B": 60.0}})
        assert [(s["member"], s["value"], s["prior"]) for s in out["streams"]] == [("co:B", 70.0, 60.0), ("co:A", 30.0, 20.0)]
        assert out["priorTotal"] == 90.0

    def test_long_tails_fold_into_other(self):
        members = {f"co:M{i}": 10.0 + i for i in range(10)}
        total = sum(members.values())
        out = srs.streams_from_values(total, {"ProductOrServiceAxis": members}, None, {"ProductOrServiceAxis": {k: 1.0 for k in members}})
        assert len(out["streams"]) == 8 and out["streams"][-1]["name"] == "Other"
        assert out["streams"][-1]["value"] == pytest.approx(sum(sorted(members.values())[:3]))
        assert out["streams"][-1]["prior"] == 3.0
        assert sum(s["value"] for s in out["streams"]) == pytest.approx(total)

    def test_other_has_no_prior_if_any_tail_member_lacks_one(self):
        members = {f"co:M{i}": 10.0 + i for i in range(10)}
        prior = {k: 1.0 for k in list(members)[1:]}
        out = srs.streams_from_values(sum(members.values()), {"ProductOrServiceAxis": members}, None, {"ProductOrServiceAxis": prior})
        assert out["streams"][-1]["prior"] is None

    def test_labels_are_applied(self):
        out = srs.streams_from_values(100.0, {"ProductOrServiceAxis": {"aapl:IPhoneMember": 60.0, "aapl:MacMember": 40.0}}, labels={"aapl_IPhoneMember": "iPhone"})
        assert [s["name"] for s in out["streams"]] == ["iPhone", "Mac"]


# ── naming ────────────────────────────────────────────────────────────────────

class TestNames:
    def test_label_map_wins(self):
        assert srs.prettify_member("aapl:IPhoneMember", {"aapl_IPhoneMember": "iPhone"}) == "iPhone"

    @pytest.mark.parametrize("raw,expected", [
        ("co:AmericasSegmentMember", "Americas"),
        ("co:RestOfAsiaPacificMember", "Rest of Asia Pacific"),
        ("co:ServerProductsAndCloudServicesMember", "Server Products and Cloud Services"),
        ("co:MicrosoftThreeSixFiveCommercialMember", "Microsoft 365 Commercial"),
        ("co:EnergyGenerationAndStorageSalesMember", "Energy Generation and Storage Sales"),
        ("co:USMember", "US"),
    ])
    def test_heuristic_when_no_label(self, raw, expected):
        assert srs.prettify_member(raw) == expected

    def test_never_returns_empty(self):
        assert srs.prettify_member("co:Member") == "co:Member"

    def test_parse_labels_reads_standard_member_labels_only(self):
        lab = b"""<linkbase xmlns="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><labelLink>
          <loc xlink:href="co.xsd#co_CloudSegmentMember" xlink:label="l1"/><labelArc xlink:from="l1" xlink:to="t1"/>
          <label xlink:label="t1" xlink:role="http://www.xbrl.org/2003/role/label">Intelligent Cloud Segment [Member]</label>
          <loc xlink:href="co.xsd#co_RevenueMember" xlink:label="l2"/><labelArc xlink:from="l2" xlink:to="t2"/>
          <label xlink:label="t2" xlink:role="http://www.xbrl.org/2003/role/documentation">docs only</label>
          <loc xlink:href="co.xsd#co_Revenues" xlink:label="l3"/><labelArc xlink:from="l3" xlink:to="t3"/>
          <label xlink:label="t3" xlink:role="http://www.xbrl.org/2003/role/label">Revenues</label></labelLink></linkbase>"""
        assert srs.parse_labels(lab) == {"co_CloudSegmentMember": "Intelligent Cloud"}

    def test_parse_labels_survives_garbage(self):
        assert srs.parse_labels(b"<not xml") == {}

    def test_parse_metalinks_prefers_the_terse_label(self):
        meta = (b'{"instance": {"x_htm.xml": {"tag": {"msft_LinkedInCorporationMember": {"lang": {"en-us": {"role": '
                b'{"terseLabel": "LinkedIn", "label": "Linked In Corporation [Member]"}}}}, '
                b'"msft_GamingMember": {"lang": {"en-us": {"role": {"label": "Gaming [Member]"}}}}, '
                b'"msft_Revenues": {"lang": {"en-us": {"role": {"label": "Revenue"}}}}}}}}')
        assert srs.parse_metalinks(meta) == {"msft_LinkedInCorporationMember": "LinkedIn", "msft_GamingMember": "Gaming"}

    def test_parse_metalinks_survives_garbage(self):
        assert srs.parse_metalinks(b"nope") == {} and srs.parse_metalinks(b"[]") == {}


# ── quarter_streams (10-Q and derived Q4) ─────────────────────────────────────

def q_rows(start, end, total, **members):
    out = [row(start, end, None, None, total)]
    out += [row(start, end, "ProductOrServiceAxis", f"co:{k}", v) for k, v in members.items()]
    return out


FILINGS = [
    {"form": "10-K", "reportDate": "2026-09-30", "accession": "K26"},
    {"form": "10-Q", "reportDate": "2026-06-30", "accession": "Q3-26"},
    {"form": "10-Q", "reportDate": "2026-03-31", "accession": "Q2-26"},
    {"form": "10-K", "reportDate": "2025-09-30", "accession": "K25"},
    {"form": "10-Q", "reportDate": "2025-06-30", "accession": "Q3-25"},
]
ROWS = {
    # Q2 FY26 10-Q: quarter and year-ago quarter
    "Q2-26": q_rows("2026-01-01", "2026-03-31", 100, A=60, B=40) + q_rows("2025-01-01", "2025-03-31", 80, A=45, B=35),
    # Q3 FY26 10-Q: quarter plus nine-month YTD (and year-ago equivalents)
    "Q3-26": q_rows("2026-04-01", "2026-06-30", 110, A=65, B=45) + q_rows("2025-10-01", "2026-06-30", 310, A=180, B=130)
             + q_rows("2025-04-01", "2025-06-30", 90, A=50, B=40) + q_rows("2024-10-01", "2025-06-30", 255, A=145, B=110),
    # FY26 10-K: full year and prior full year
    "K26": q_rows("2025-10-01", "2026-09-30", 430, A=250, B=180) + q_rows("2024-10-01", "2025-09-30", 350, A=200, B=150),
}


def rows_for(f):
    return ROWS.get(f["accession"], [])


class TestQuarterStreams:
    def test_ten_q_quarter_with_year_ago_comparison(self):
        out = srs.quarter_streams(date(2026, 3, 31), FILINGS, rows_for)
        assert out["form"] == "10-Q" and out["derived"] is False and out["filing"] == "Q2-26"
        assert out["total"] == 100 and out["priorTotal"] == 80
        assert [(s["member"], s["value"], s["prior"]) for s in out["streams"]] == [("co:A", 60, 45), ("co:B", 40, 35)]

    def test_q4_is_the_fiscal_year_minus_nine_months(self):
        out = srs.quarter_streams(date(2026, 9, 30), FILINGS, rows_for)
        assert out["derived"] is True and out["form"] == "10-K"
        assert out["total"] == 430 - 310
        assert [(s["member"], s["value"]) for s in out["streams"]] == [("co:A", 70), ("co:B", 50)]

    def test_q4_year_ago_comparison_uses_the_prior_years_figures(self):
        out = srs.quarter_streams(date(2026, 9, 30), FILINGS, rows_for)
        assert out["priorTotal"] == 350 - 255
        assert {s["member"]: s["prior"] for s in out["streams"]} == {"co:A": 200 - 145, "co:B": 150 - 110}

    def test_q4_needs_the_q3_filing(self):
        no_q3 = [f for f in FILINGS if f["accession"] != "Q3-26"]
        assert srs.quarter_streams(date(2026, 9, 30), no_q3, rows_for) is None

    def test_q4_members_missing_from_the_ytd_are_dropped_and_may_break_reconciliation(self):
        rows = dict(ROWS)
        rows["Q3-26"] = [r for r in ROWS["Q3-26"] if r["member"] != "co:B"]
        assert srs.quarter_streams(date(2026, 9, 30), FILINGS, lambda f: rows.get(f["accession"], [])) is None

    def test_no_filing_near_the_quarter(self):
        assert srs.quarter_streams(date(2024, 1, 31), FILINGS, rows_for) is None

    def test_quarter_date_tolerance_for_52_53_week_calendars(self):
        assert srs.quarter_streams(date(2026, 6, 27), FILINGS, rows_for)["filing"] == "Q3-26"

    def test_unreconcilable_quarter_gives_none(self):
        rows = {"Q2-26": q_rows("2026-01-01", "2026-03-31", 100, A=10, B=10)}
        assert srs.quarter_streams(date(2026, 3, 31), FILINGS, lambda f: rows.get(f["accession"], [])) is None

    def test_filing_without_revenue_facts(self):
        assert srs.quarter_streams(date(2026, 3, 31), FILINGS, lambda f: []) is None


# ── orchestration ─────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    calls = {"rows": [], "labels": []}
    import edgar_utils
    monkeypatch.setattr(edgar_utils, "_get_cik", lambda s: "0000001" if s != "NOCIK" else None)
    monkeypatch.setattr(srs, "list_filings", lambda cik: FILINGS)

    def fake_rows(cik, acc):
        calls["rows"].append(acc)
        if acc == "BOOM":
            raise RuntimeError("download failed")
        return ROWS.get(acc, [])
    monkeypatch.setattr(srs, "filing_rows", fake_rows)

    def fake_labels(cik, acc):
        calls["labels"].append(acc)
        return {"Q2-26": {"co_A": "Alpha"}, "Q3-26": {"co_A": "Stale alpha", "co_B": "Beta"}}.get(acc, {})
    monkeypatch.setattr(srs, "filing_labels", fake_labels)
    return calls


class TestStreamsForQuarters:
    def test_resolves_quarters_and_applies_merged_labels_newest_first(self, wired):
        out = srs.streams_for_quarters("ACME", [date(2026, 6, 30), date(2026, 3, 31)])
        assert sorted(out) == ["2026-03-31", "2026-06-30"]
        assert [s["name"] for s in out["2026-06-30"]["streams"]] == ["Stale alpha", "Beta"]      # newest filing's label wins

    def test_q4_prefetches_the_q3_filing_too(self, wired):
        out = srs.streams_for_quarters("ACME", [date(2026, 9, 30)])
        assert sorted(wired["rows"]) == ["K26", "Q3-26"] and out["2026-09-30"]["derived"] is True

    def test_no_cik_or_no_quarters(self, wired):
        assert srs.streams_for_quarters("NOCIK", [date(2026, 3, 31)]) == {}
        assert srs.streams_for_quarters("ACME", []) == {}

    def test_no_filings(self, wired, monkeypatch):
        monkeypatch.setattr(srs, "list_filings", lambda cik: [])
        assert srs.streams_for_quarters("ACME", [date(2026, 3, 31)]) == {}

    def test_a_failed_download_only_loses_that_quarter(self, wired, monkeypatch):
        monkeypatch.setattr(srs, "list_filings", lambda cik: FILINGS + [{"form": "10-Q", "reportDate": "2025-12-31", "accession": "BOOM"}])
        out = srs.streams_for_quarters("ACME", [date(2026, 3, 31), date(2025, 12, 31)])
        assert list(out) == ["2026-03-31"]

    def test_label_failures_fall_back_to_heuristic_names(self, wired, monkeypatch):
        def boom(cik, acc):
            raise RuntimeError("no labels")
        monkeypatch.setattr(srs, "filing_labels", boom)
        out = srs.streams_for_quarters("ACME", [date(2026, 3, 31)])
        assert [s["name"] for s in out["2026-03-31"]["streams"]] == ["A", "B"]


# ── filing download + cache ───────────────────────────────────────────────────

class TestFilingRows:
    def test_downloads_the_extracted_instance_and_caches_rows(self, monkeypatch):
        inst = xml(ctx("t", "2026-04-01", "2026-06-30"), fact(REVC, "t", 100))
        monkeypatch.setattr(srs, "_filing_files", lambda cik, acc: [{"name": "x.xsd", "size": "10"}, {"name": "acme-20260630_htm.xml", "size": str(len(inst))}])

        class Resp:
            content = inst
        urls, writes = [], []
        monkeypatch.setattr(srs, "_req", lambda url: urls.append(url) or Resp())
        monkeypatch.setattr(srs, "cache_set", lambda k, v: writes.append((k, v)))
        rows = srs.filing_rows("1", "0000001-26-000001")
        assert rows[0]["value"] == 100.0 and urls == ["https://www.sec.gov/Archives/edgar/data/1/000000126000001/acme-20260630_htm.xml"]
        assert writes[0][0] == "sec_rev_rows:1:0000001-26-000001"

    def test_cached_rows_skip_the_download(self, monkeypatch):
        monkeypatch.setattr(srs, "cache_get", lambda *a, **k: [{"cached": True}])
        monkeypatch.setattr(srs, "_filing_files", lambda *a: pytest.fail("should not hit the network"))
        assert srs.filing_rows("1", "acc") == [{"cached": True}]

    def test_falls_back_to_a_plain_xml_instance_and_skips_linkbases(self, monkeypatch):
        inst = xml(ctx("t", "2026-04-01", "2026-06-30"), fact(REVC, "t", 7))
        files = [{"name": "a_cal.xml", "size": "5"}, {"name": "a_lab.xml", "size": "5"}, {"name": "FilingSummary.xml", "size": "5"},
                 {"name": "R2.xml", "size": "5"}, {"name": "acme-20260630.xml", "size": str(len(inst))}]
        monkeypatch.setattr(srs, "_filing_files", lambda *a: files)
        got = []

        class Resp:
            content = inst
        monkeypatch.setattr(srs, "_req", lambda url: got.append(url) or Resp())
        assert srs.filing_rows("1", "a-b")[0]["value"] == 7.0 and got[0].endswith("acme-20260630.xml")

    def test_oversized_or_missing_instances_yield_no_rows(self, monkeypatch):
        monkeypatch.setattr(srs, "_filing_files", lambda *a: [{"name": "huge_htm.xml", "size": str(srs._MAX_INSTANCE_BYTES + 1)}])
        monkeypatch.setattr(srs, "_req", lambda url: pytest.fail("must not download"))
        assert srs.filing_rows("1", "a-b") == []
        monkeypatch.setattr(srs, "_filing_files", lambda *a: [{"name": "readme.txt", "size": "1"}])
        assert srs.filing_rows("1", "a-b") == []


class TestFilingLabels:
    def _wire(self, monkeypatch, files, payloads):
        monkeypatch.setattr(srs, "_filing_files", lambda *a: files)

        class Resp:
            def __init__(self, content):
                self.content = content
        monkeypatch.setattr(srs, "_req", lambda url: Resp(payloads[url.rsplit("/", 1)[-1]]))

    def test_uses_the_label_linkbase_when_present(self, monkeypatch):
        lab = b"""<linkbase xmlns="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><labelLink>
          <loc xlink:href="x.xsd#co_AMember" xlink:label="l1"/><labelArc xlink:from="l1" xlink:to="t1"/>
          <label xlink:label="t1" xlink:role="http://www.xbrl.org/2003/role/label">Alpha [Member]</label></labelLink></linkbase>"""
        self._wire(monkeypatch, [{"name": "x_lab.xml"}, {"name": "MetaLinks.json"}], {"x_lab.xml": lab})
        assert srs.filing_labels("1", "a-b") == {"co_AMember": "Alpha"}

    def test_falls_back_to_metalinks(self, monkeypatch):
        meta = b'{"instance": {"i": {"tag": {"co_AMember": {"lang": {"en-us": {"role": {"terseLabel": "Alpha"}}}}}}}}'
        self._wire(monkeypatch, [{"name": "MetaLinks.json"}], {"MetaLinks.json": meta})
        assert srs.filing_labels("1", "a-b") == {"co_AMember": "Alpha"}

    def test_no_label_source_means_no_labels(self, monkeypatch):
        self._wire(monkeypatch, [{"name": "other.htm"}], {})
        assert srs.filing_labels("1", "a-b") == {}
