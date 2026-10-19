"""Famous investors the Manager Holdings page can follow.

Two kinds:
  - "13f": an institution that files a quarterly 13F with the SEC. Everything on the page for these comes from the filings.
  - "disclosed": a person with no filing. The page keeps a log of positions and rules they have stated publicly, each with its
    source, and nothing else: it is a record of what was said, not a reconstruction of their portfolio.

The SEC identifiers (CIKs) were checked against EDGAR. A manager is one filing entity: Berkshire's report covers Berkshire Hathaway's
investment portfolios, the Gates Foundation Trust's covers the foundation's endowment, and so on.
"""

MANAGERS = [
    {"id": "berkshire", "name": "Berkshire Hathaway", "person": "Warren Buffett", "kind": "13f", "cik": 1067983,
     "blurb": "Buffett's holding company. Its 13F covers the stock portfolios of its insurance and other businesses, run with a concentrated, long-term style."},
    {"id": "damodaran", "name": "Aswath Damodaran", "person": "NYU Stern professor of valuation", "kind": "disclosed", "cik": None,
     "blurb": "Does not file a 13F. This page logs the positions and portfolio rules he has stated publicly, each with its source; it is not a complete list."},
    {"id": "scion", "name": "Scion Asset Management", "person": "Michael Burry", "kind": "13f", "cik": 1649339,
     "blurb": "Burry's fund, known for contrarian and concentrated bets. Check the filing date: its latest 13F on record may be well out of date."},
    {"id": "pershing", "name": "Pershing Square", "person": "Bill Ackman", "kind": "13f", "cik": 1336528,
     "blurb": "Activist hedge fund known for a small number of very large positions."},
    {"id": "duquesne", "name": "Duquesne Family Office", "person": "Stanley Druckenmiller", "kind": "13f", "cik": 1536411,
     "blurb": "Druckenmiller's family office; a macro-influenced, higher-turnover portfolio."},
    {"id": "baupost", "name": "Baupost Group", "person": "Seth Klarman", "kind": "13f", "cik": 1061768,
     "blurb": "Value investor with a margin-of-safety focus; much of the fund is outside what a 13F shows."},
    {"id": "thirdpoint", "name": "Third Point", "person": "Dan Loeb", "kind": "13f", "cik": 1040273,
     "blurb": "Event-driven and activist hedge fund."},
    {"id": "appaloosa", "name": "Appaloosa", "person": "David Tepper", "kind": "13f", "cik": 1656456,
     "blurb": "Tepper's firm, now managing his family's money."},
    {"id": "himalaya", "name": "Himalaya Capital", "person": "Li Lu", "kind": "13f", "cik": 1709323,
     "blurb": "Concentrated long-term portfolio run by Li Lu, a long-time Charlie Munger associate."},
    {"id": "ruane", "name": "Ruane, Cunniff & Goldfarb", "person": "Sequoia Fund managers", "kind": "13f", "cik": 1720792,
     "blurb": "Manager of the Sequoia Fund; a quality-focused, concentrated long-only approach."},
    {"id": "icahn", "name": "Carl Icahn", "person": "Carl Icahn", "kind": "13f", "cik": 921669,
     "blurb": "Activist investor; positions are largely held through Icahn Enterprises."},
    {"id": "elliott", "name": "Elliott Investment Management", "person": "Paul Singer", "kind": "13f", "cik": 1791786,
     "blurb": "Large activist hedge fund."},
    {"id": "tiger", "name": "Tiger Global Management", "person": "Chase Coleman", "kind": "13f", "cik": 1167483,
     "blurb": "Growth and technology focused long/short manager."},
    {"id": "greenlight", "name": "Greenlight Capital", "person": "David Einhorn", "kind": "13f", "cik": 1079114,
     "blurb": "Einhorn's value-oriented fund. The latest 13F on record under this filer is for December 2023, so the data is old; see the warning on the page."},
    {"id": "pabrai", "name": "Dalal Street (Pabrai Funds)", "person": "Mohnish Pabrai", "kind": "13f", "cik": 1549575,
     "blurb": "Pabrai's funds: a very concentrated, low-turnover value portfolio that clones ideas from other investors."},
    {"id": "gates", "name": "Gates Foundation Trust", "person": "Bill & Melinda Gates Foundation", "kind": "13f", "cik": 1166559,
     "blurb": "Invests the foundation's endowment; large, stable positions."},
    {"id": "soros", "name": "Soros Fund Management", "person": "George Soros / family", "kind": "13f", "cik": 1029160,
     "blurb": "The Soros family office; macro heritage with an actively traded equity book."},
    {"id": "bridgewater", "name": "Bridgewater Associates", "person": "Founded by Ray Dalio", "kind": "13f", "cik": 1350694,
     "blurb": "One of the largest hedge fund firms; a very large, diversified 13F that is only a slice of what it manages."},
]
BY_ID = {m["id"]: m for m in MANAGERS}

# Public statements by people who do not file a 13F. confidence: "primary" = the person's own words; "secondary" = reported by someone
# else; entries added by the user are marked "user". As-of dates may be a month (YYYY-MM) when only that is known.
DISCLOSURE_SEEDS = {
    "damodaran": [
        {"symbol": "AAPL", "name": "Apple", "action": "owns", "as_of": "2024-02-09", "note": "Stated that he owns all of the 'Magnificent Seven'; the six besides Tesla had been in his portfolio much longer.", "confidence": "primary"},
        {"symbol": "MSFT", "name": "Microsoft", "action": "owns", "as_of": "2024-02-09", "note": "Same statement: long-held. He described the valuation as a larger overvaluation than the others he named.", "confidence": "primary"},
        {"symbol": "GOOGL", "name": "Alphabet", "action": "owns", "as_of": "2024-02-09", "note": "Same statement: long-held, with a mild overvaluation he said he could live with.", "confidence": "primary"},
        {"symbol": "AMZN", "name": "Amazon", "action": "owns", "as_of": "2024-02-09", "note": "Same statement: long-held, with a mild overvaluation he said he could live with.", "confidence": "primary"},
        {"symbol": "META", "name": "Meta Platforms", "action": "owns", "as_of": "2024-02-09", "note": "Same statement: long-held, with a mild overvaluation he said he could live with.", "confidence": "primary"},
        {"symbol": "NVDA", "name": "NVIDIA", "action": "owns", "as_of": "2024-02-09", "note": "Same statement: long-held at that date. He has since said he trimmed it; no dated source is logged here yet.", "confidence": "primary"},
        {"symbol": "TSLA", "name": "Tesla", "action": "bought", "as_of": "2024-01", "note": "Said he added Tesla about two weeks before the post.", "confidence": "primary"},
        {"symbol": None, "name": "Portfolio approach", "action": "approach", "as_of": None, "confidence": "secondary",
         "note": "As summarised by others from his talks: roughly 40 stocks, no more than about 5% in a new position, profits trimmed once a position reaches 15-20% of the portfolio, around a third in non-US stocks, low turnover. Not confirmed by a primary source here."},
    ],
}
DISCLOSURE_SOURCES = {
    "damodaran": [
        {"match": "primary", "title": "Aswath Damodaran on X, February 2024", "url": "https://x.com/AswathDamodaran/status/1755796882540904682"},
        {"match": "secondary", "title": "Bogleheads thread: how Damodaran manages his own portfolio", "url": "https://www.bogleheads.org/forum/viewtopic.php?t=459629"},
    ],
}
ACTIONS = ("owns", "bought", "added", "trimmed", "sold", "approach", "other")
