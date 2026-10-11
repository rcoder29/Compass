import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import TearSheet, { fmtMoney, fmtBig, fmtPct, fmtX, fmtQuarter, SankeyDiagram } from './TearSheet'

const sheet = (over = {}) => ({
  symbol: 'ACME',
  asOf: '2026-10-09',
  profile: { name: 'Acme Corp', sector: 'Technology', industry: 'Software', exchange: 'NasdaqGS', country: 'United States',
             employees: 12000, description: 'Acme builds widgets.', quoteType: 'EQUITY' },
  snapshot: { price: 100, changePct: 1.25, marketCap: 2.5e12, sharesOutstanding: 15.2e9, enterpriseValue: 2.4e12, week52High: 120, week52Low: 80,
              rangePosition: 0.5, beta: 1.1, nextEarnings: '2026-11-02' },
  performance: {
    returns: [{ period: '1Y', stock: 0.33, spy: 0.17, relative: 0.16 }, { period: '5Y', stock: null, spy: null, relative: null }],
    maxDrawdown5y: -0.3, volatility1y: 0.25, ma200: 95,
    series: { dates: ['2025-01-05', '2025-06-01', '2026-01-04'], close: [90, 95, 100], ma50: [null, 92, 96], ma200: [null, null, 95],
              stockRebased: [100, 105, 111], spyRebased: [100, 102, 104] },
  },
  financials: {
    history: [
      { fiscalYear: '2024-09-30', revenue: 100e9, netIncome: 20e9, freeCashFlow: 18e9, grossMargin: 0.4, operatingMargin: 0.3, netMargin: 0.2, eps: 2, epsGrowth: null, revenueGrowth: null, fcfMargin: 0.18 },
      { fiscalYear: '2025-09-30', revenue: 120e9, netIncome: 30e9, freeCashFlow: 25e9, grossMargin: 0.45, operatingMargin: 0.32, netMargin: 0.25, eps: 3, epsGrowth: 0.5, revenueGrowth: 0.2, fcfMargin: 0.21 },
    ],
    revenueCagr: 0.2, epsCagr: 0.5,
    ttm: { revenueGrowth: 0.16, earningsGrowth: 0.28 },
  },
  balanceSheet: { cash: 50e9, debt: 80e9, netDebt: 30e9, netDebtToEbitda: 0.5, debtToEquity: 120, currentRatio: 1.2,
                  interestCoverage: 20, roe: 0.4, roa: 0.2, payoutRatio: 0.15 },
  valuation: {
    multiples: { trailingPE: 30, forwardPE: 27, peg: 2.1, priceToSales: 8, priceToBook: 12, evToEbitda: 22, evToRevenue: 7,
                 fcfYield: 0.03, dividendYield: 0.005, earningsYieldForward: 0.037 },
    historicalPE: [{ fiscalYear: '2024-09-30', pe: 22, price: 60, eps: 2.7 }, { fiscalYear: '2025-09-30', pe: 28, price: 84, eps: 3 }],
    historicalPEMedian: 25, tenYearYield: 0.045, earningsYieldVsBond: -0.008,
    fairValues: [
      { method: 'Historical P/E', value: 90, basis: '25.0x avg FY-end P/E × $3.60 trailing EPS' },
      { method: 'PEG = 1', value: 70, basis: '14.0x × $5 forward EPS' },
      { method: 'DCF (FCF)', value: null, basis: 'Needs positive free cash flow' },
      { method: 'Analyst target', value: 110, basis: '$120 target discounted' },
    ],
    verdict: { label: 'Overvalued', tone: 'bad', fairValue: 90, premium: 0.111, low: 70, high: 110, methodsUsed: 3 },
    scenarios12m: [{ scenario: 'Bear', eps: 4, peMultiple: 21, price: 84, priceReturn: -0.16, totalReturn: -0.155 },
                   { scenario: 'Base', eps: 5, peMultiple: 27, price: 135, priceReturn: 0.35, totalReturn: 0.355 }],
    fiveYearReturns: [{ scenario: 'P/E compresses', exitPe: 17.5, endPrice: 160, annualisedReturn: 0.09 }],
  },
  estimates: {
    growthUsed: 0.14,
    eps: [{ period: '0y', label: 'Current FY', avg: 4.5, low: 4.2, high: 4.8, yearAgo: 3, growth: 0.5, analysts: 30 }],
    revenue: [{ period: '0y', label: 'Current FY', avg: 140e9, yearAgo: 120e9, growth: 0.16 }],
    revisions: [{ period: '0y', label: 'Current FY', current: 4.5, change30d: 0.01, change90d: -0.02 }],
  },
  earningsTrack: { quarters: [{ quarter: '2026-06-30', epsActual: 1.1, epsEstimate: 1.0, surprisePct: 0.1 }], beats: 1, total: 1, avgSurprisePct: 0.1 },
  analysts: {
    recommendation: 'buy', recommendationMean: 2.1, analystCount: 40, targetMean: 120, targetMedian: 118, targetHigh: 150, targetLow: 90,
    upsideToMean: 0.2,
    distribution: { strongBuy: 6, buy: 19, hold: 13, sell: 3, strongSell: 3 },
    distribution3mAgo: { strongBuy: 6, buy: 22, hold: 14, sell: 2, strongSell: 2 },
    recentChanges: [{ date: '2026-10-01', firm: 'Morgan Stanley', action: 'main', from: 'Overweight', to: 'Overweight', target: 355, priorTarget: 360 }],
  },
  ownership: { institutionsPct: 0.66, insidersPct: 0.016, shortPercentOfFloat: 0.009, shortRatio: 3, insiderActivity: null },
  scorecard: { pillars: [{ name: 'Growth', score: 56 }, { name: 'Valuation', score: 0 }, { name: 'Momentum', score: null }], overall: 55 },
  flags: { strengths: ['High net margin (25%)'], risks: ['Trades 11% above blended fair value'] },
  methodologyNote: 'Rules-based screen, not investment advice.',
  ...over,
})

const jsonRes = (body, ok = true) => ({ ok, json: () => Promise.resolve(body), headers: { get: () => null } })

// Routes by URL: `extra` can answer specific calls (e.g. the PDF download) before the default sheet payload.
function mockFetch(payload, { extra } = {}) {
  global.fetch = vi.fn(async (url, opts) => {
    if (extra) {
      const r = await extra(url, opts)
      if (r) return r
    }
    return jsonRes(payload)
  })
}

async function build(symbol = 'acme') {
  fireEvent.change(screen.getByLabelText('Ticker symbol'), { target: { value: symbol } })
  fireEvent.click(screen.getByText('Build tear sheet'))
}

describe('formatters', () => {
  it('formats money, big numbers, percents and multiples', () => {
    expect(fmtMoney(1234.5)).toBe('$1,234.50')
    expect(fmtBig(2.5e12)).toBe('$2.50T')
    expect(fmtBig(-3.2e9)).toBe('-$3.20B')
    expect(fmtBig(4.5e6)).toBe('$4.5M')
    expect(fmtPct(0.153)).toBe('15.3%')
    expect(fmtPct(0.153, 1, true)).toBe('+15.3%')
    expect(fmtPct(-0.05, 1, true)).toBe('-5.0%')
    expect(fmtX(27.04)).toBe('27.0x')
  })

  it('accepts a currency symbol', () => {
    expect(fmtBig(3.8e12, 'TWD ')).toBe('TWD 3.80T')
    expect(fmtBig(-2e9, 'TWD ')).toBe('-TWD 2.00B')
    expect(fmtMoney(331.25, 2, 'TWD ')).toBe('TWD 331.25')
  })

  it('renders a dash for missing values', () => {
    for (const f of [fmtMoney, fmtBig, fmtPct, fmtX]) {
      expect(f(null)).toBe('—')
      expect(f(undefined)).toBe('—')
      expect(f(NaN)).toBe('—')
    }
  })
})

describe('TearSheet', () => {
  beforeEach(() => { window.print = vi.fn() })
  afterEach(() => { vi.restoreAllMocks() })

  it('shows nothing but the form before a lookup', () => {
    render(<TearSheet />)
    expect(screen.getByText('Company Tear Sheet')).toBeInTheDocument()
    expect(screen.queryByTestId('verdict-label')).not.toBeInTheDocument()
  })

  it('calls the endpoint with the uppercased symbol and renders the verdict', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build('acme')
    await waitFor(() => expect(screen.getByTestId('verdict-label')).toHaveTextContent('Overvalued'))
    expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/ACME')
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getAllByText('$100.00').length).toBeGreaterThan(0)
  })

  it('shows shares outstanding beside market cap, without a currency symbol', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    const card = screen.getByText('Shares outstanding').parentElement
    expect(card).toHaveTextContent('15.20B')
    expect(card).not.toHaveTextContent('$')
  })

  it('renders every major section', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    for (const title of ['Is it cheap or expensive?', 'Key takeaways', 'Business overview', 'Past performance',
      'Financial track record', 'Balance sheet & returns on capital', 'Valuation multiples',
      'Projected earnings & returns', 'Consensus estimates & earnings record', 'Analyst ratings & price targets',
      'Ownership, insiders & short interest']) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }
  })

  it('shows fair-value models, including ones that could not run', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getAllByText('Historical P/E').length).toBe(2) // football-field row + basis list
    expect(screen.getByText('Needs positive free cash flow')).toBeInTheDocument()
    expect(screen.getByText('Fair value (median)')).toBeInTheDocument()
    expect(screen.getByText('Premium to fair')).toBeInTheDocument()
  })

  it('labels a discount when the stock trades below fair value', async () => {
    const s = sheet()
    s.valuation.verdict = { label: 'Undervalued', tone: 'good', fairValue: 130, premium: -0.23, low: 120, high: 140, methodsUsed: 3 }
    mockFetch(s)
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText('Discount to fair')).toBeInTheDocument()
  })

  it('explains itself instead of giving a verdict when too few models ran', async () => {
    const s = sheet()
    s.valuation.verdict = { label: 'Not enough data to judge', tone: 'neutral', fairValue: null, premium: null, low: 17, high: 17, methodsUsed: 1 }
    mockFetch(s)
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByTestId('verdict-label')).toHaveTextContent('Not enough data to judge')
    expect(screen.getByText(/Only 1 of 4 valuation models/)).toBeInTheDocument()
    expect(screen.queryByText('Fair value (median)')).not.toBeInTheDocument()
  })

  it('shows scenarios, 5-year returns, estimates and analyst changes', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText('Bear')).toBeInTheDocument()
    expect(screen.getByText('Base')).toBeInTheDocument()
    expect(screen.getByText('P/E compresses')).toBeInTheDocument()
    expect(screen.getByText('Morgan Stanley')).toBeInTheDocument()
    expect(screen.getByText('$355 (was $360)')).toBeInTheDocument()
    expect(screen.getAllByText('Current FY').length).toBeGreaterThan(0)
  })

  it('shows a ten-year track record, one column per fiscal year', async () => {
    const s = sheet()
    s.financials.history = Array.from({ length: 10 }, (_, i) => ({
      fiscalYear: `${2016 + i}-12-31`, revenue: (100 + i * 10) * 1e9, netIncome: 20e9, freeCashFlow: null, grossMargin: 0.4,
      operatingMargin: 0.3, netMargin: 0.2, eps: 2 + i * 0.1, epsGrowth: 0.05, revenueGrowth: 0.1, fcfMargin: null,
    }))
    s.financials.revenueCagr = 0.0743
    mockFetch(s)
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText(/Last 10 fiscal years, oldest to newest/)).toBeInTheDocument()
    expect(screen.queryByText(/all the annual history available/)).not.toBeInTheDocument()
    for (const y of ['FY2016', 'FY2025']) expect(screen.getAllByText(y).length).toBeGreaterThan(0)
    expect(screen.getByText('Revenue CAGR (9y)')).toBeInTheDocument()
    expect(screen.getByText('+7.4%')).toBeInTheDocument()
  })

  it('says so when fewer than ten years exist', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText(/Last 2 fiscal years.*all the annual history available for this ticker/)).toBeInTheDocument()
  })

  it('labels statement figures in the reporting currency when it differs from the trading currency', async () => {
    mockFetch(sheet({ currencyNote: { financial: 'TWD', trading: 'USD' } }))
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText(/reports in TWD but trades in USD/)).toBeInTheDocument()
    expect(screen.getAllByText('TWD 100.00B').length).toBeGreaterThan(0)
    expect(screen.queryByText('$100.00B')).not.toBeInTheDocument()
  })

  it('explains blank cash-flow rows for banks', async () => {
    mockFetch(sheet({ bankNote: true }))
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText(/aren't meaningful for banks/)).toBeInTheDocument()
  })

  it('shows neither note for an ordinary company', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.queryByText(/aren't meaningful for banks/)).not.toBeInTheDocument()
    expect(screen.queryByText(/but trades in/)).not.toBeInTheDocument()
  })

  it('shows the 10-year-yield comparison in plain language', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText('0.8% below')).toBeInTheDocument()
    expect(screen.getByText(/less earnings yield than a government bond/)).toBeInTheDocument()
  })

  it('degrades gracefully for a fund with no financials', async () => {
    const s = sheet({
      profile: { name: 'S&P ETF', quoteType: 'ETF' },
      financials: { history: [], revenueCagr: null, epsCagr: null, ttm: {} },
      estimates: { growthUsed: null, eps: [], revenue: [], revisions: [] },
      earningsTrack: { quarters: [], beats: 0, total: 0, avgSurprisePct: null },
      analysts: { recommendation: null, targetMean: null, targetLow: null, targetHigh: null, upsideToMean: null,
                  distribution: null, distribution3mAgo: null, recentChanges: [] },
      flags: { strengths: [], risks: [] },
    })
    s.valuation = { ...s.valuation, historicalPE: [], fairValues: s.valuation.fairValues.map(f => ({ ...f, value: null })),
                    verdict: { label: 'Not enough data to judge', tone: 'neutral', fairValue: null, premium: null, low: null, high: null, methodsUsed: 0 },
                    scenarios12m: [], fiveYearReturns: [] }
    mockFetch(s)
    render(<TearSheet />)
    await build('spy')
    await waitFor(() => screen.getByTestId('verdict-label'))
    expect(screen.getByText(/is not an operating company \(classified as ETF\)/)).toBeInTheDocument()
    expect(screen.getByText(/No annual financial statements/)).toBeInTheDocument()
    expect(screen.getByText('No EPS estimates.')).toBeInTheDocument()
    expect(screen.queryByText('Key takeaways')).not.toBeInTheDocument()
  })

  it('shows the API error and no sheet', async () => {
    mockFetch({ symbol: 'ZZZ', error: 'No price data available for this symbol.' })
    render(<TearSheet />)
    await build('zzz')
    expect(await screen.findByRole('alert')).toHaveTextContent('No price data available')
    expect(screen.queryByTestId('verdict-label')).not.toBeInTheDocument()
  })

  it('shows a network failure message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network down'))
    render(<TearSheet />)
    await build()
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
  })

  it('does not call the API for an empty ticker', () => {
    global.fetch = vi.fn()
    render(<TearSheet />)
    fireEvent.click(screen.getByText('Build tear sheet'))
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('loads immediately when given an initial symbol', async () => {
    mockFetch(sheet())
    render(<TearSheet initialSymbol="msft" />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/MSFT'))
  })

  it('quick-pick chips look up that ticker', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    fireEvent.click(screen.getByText('NVDA'))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/NVDA'))
  })

  it('print button opens the print dialog', async () => {
    mockFetch(sheet())
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
    fireEvent.click(screen.getByText('Print'))
    expect(window.print).toHaveBeenCalled()
  })
})

describe('TearSheet PDF export', () => {
  beforeEach(() => {
    window.print = vi.fn()
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
  })
  afterEach(() => { vi.restoreAllMocks() })

  const pdfRes = (over = {}) => ({
    ok: true, blob: () => Promise.resolve(new Blob(['%PDF-1.4'])),
    headers: { get: h => (h.toLowerCase() === 'content-disposition' ? 'attachment; filename="ACME_TearSheet_2026-10-09.pdf"' : null) },
    ...over,
  })

  async function loaded(opts) {
    mockFetch(sheet(), opts)
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
  }

  function captureDownloads() {
    const downloads = []
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(tag => {
      const el = realCreate(tag)
      if (tag === 'a') el.click = () => downloads.push({ href: el.href, download: el.download })
      return el
    })
    return downloads
  }

  it('offers Download PDF and Print, and no email controls', async () => {
    await loaded()
    expect(screen.getByText('Download PDF')).toBeInTheDocument()
    expect(screen.getByText('Print')).toBeInTheDocument()
    expect(screen.queryByText('Email…')).not.toBeInTheDocument()
    expect(global.fetch).not.toHaveBeenCalledWith('/api/tear-sheet-share/status')
  })

  it('downloads the PDF under the server-provided filename', async () => {
    const downloads = captureDownloads()
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? pdfRes() : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    await waitFor(() => expect(downloads).toHaveLength(1))
    expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/ACME/pdf')
    expect(downloads[0].download).toBe('ACME_TearSheet_2026-10-09.pdf')
    expect(downloads[0].href).toBe('blob:fake')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake')
  })

  it('falls back to a default filename when the header is missing', async () => {
    const downloads = captureDownloads()
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? pdfRes({ headers: { get: () => null } }) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    await waitFor(() => expect(downloads.map(d => d.download)).toEqual(['ACME_TearSheet.pdf']))
  })

  it('shows the server error when the PDF cannot be built', async () => {
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? jsonRes({ detail: 'No price data available for this symbol.' }, false) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    expect(await screen.findByRole('alert')).toHaveTextContent('No price data available')
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('falls back to a generic message when the error body is not JSON', async () => {
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? { ok: false, json: () => Promise.reject(new Error('not json')), headers: { get: () => null } } : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not build the PDF.')
  })

  it('shows a network failure', async () => {
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? Promise.reject(new Error('Network down')) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
  })

  it('disables the button while the PDF is being built', async () => {
    let release
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? new Promise(r => { release = () => r(pdfRes()) }) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    expect(await screen.findByText('Building PDF…')).toBeDisabled()
    release()
    await waitFor(() => expect(screen.getByText('Download PDF')).not.toBeDisabled())
  })

  it('clears a previous error on the next attempt', async () => {
    let fail = true
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? (fail ? jsonRes({ detail: 'boom' }, false) : pdfRes()) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    await screen.findByRole('alert')
    fail = false
    fireEvent.click(screen.getByText('Download PDF'))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('resets when a different ticker is loaded', async () => {
    await loaded({ extra: url => (String(url).endsWith('/pdf') ? jsonRes({ detail: 'boom' }, false) : null) })
    fireEvent.click(screen.getByText('Download PDF'))
    await screen.findByRole('alert')
    mockFetch(sheet({ symbol: 'MSFT' }))
    fireEvent.click(screen.getByText('MSFT'))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(screen.getByText('Download PDF')).toBeInTheDocument()
  })
})

// ── Quarterly income flow ─────────────────────────────────────────────────────

const node = (id, label, column, y, h, value, over = {}) => ({
  id, label, kind: 'profit', color: '#34d399', detail: null, x: 150 + column * 130, y, w: 12, h, value, pct: value / 100e9,
  labelSide: column === 0 ? 'left' : 'right', column, ...over,
})

const flowFixture = (over = {}) => ({
  width: 1000, height: 420,
  nodes: [
    node('stream:0', 'iPhone', 0, 10, 200, 60e9, { kind: 'stream', color: '#38bdf8' }),
    node('stream:1', 'Services', 0, 230, 120, 40e9, { kind: 'stream', color: '#818cf8' }),
    node('revenue', 'Revenue', 1, 10, 340, 100e9, { kind: 'revenue', color: '#3b82f6' }),
    node('gross', 'Gross profit', 2, 10, 200, 60e9),
    node('cost', 'Cost of revenue', 2, 230, 130, 40e9, { kind: 'cost', color: '#f87171' }),
    node('net', 'Net income', 3, 10, 100, 30e9, { kind: 'net', color: '#10b981' }),
    node('dividends', 'Dividends', 4, 10, 20, 4e9, { kind: 'dividend', color: '#a78bfa', detail: '$0.27/share' }),
  ],
  links: [
    { source: 'stream:0', target: 'revenue', value: 60e9, d: 'M162,110 C200,110 200,100 280,100', thickness: 200, color: '#38bdf8' },
    { source: 'revenue', target: 'gross', value: 60e9, d: 'M292,100 C330,100 330,100 410,100', thickness: 200, color: '#34d399' },
    { source: 'gross', target: 'net', value: 30e9, d: 'M422,100 C460,100 460,60 540,60', thickness: 0.1, color: '#10b981' },
  ],
  notes: [], hasStreams: true, ...over,
})

const pnlFixture = (over = {}) => ({
  quarter: '2026-06-30', revenue: 100e9, costOfRevenue: 40e9, grossProfit: 60e9, operatingIncome: 35e9, netIncome: 30e9,
  dividendsPaid: 4e9, buybacks: 20e9, dividendPerShare: 0.27, ...over,
})

const flowSheet = (over = {}) => sheet({
  incomeFlow: {
    quarters: [
      { quarter: '2026-06-30', pnl: pnlFixture(), revenueYoY: 0.164, flow: flowFixture(),
        streams: { axisLabel: 'Products & services', form: '10-Q', derived: false, streams: [
          { name: 'iPhone', value: 60e9, share: 0.6, yoy: 0.22 }, { name: 'Services', value: 40e9, share: 0.4, yoy: -0.05 }] } },
      { quarter: '2026-03-31', pnl: pnlFixture({ quarter: '2026-03-31', revenue: 90e9, netIncome: 25e9, dividendsPaid: null, buybacks: null }),
        revenueYoY: null, flow: flowFixture({ notes: ['No dividends or buybacks were paid this quarter, so all of net income is retained.'] }), streams: null },
    ],
  },
  ...over,
})

describe('formatters for the income flow', () => {
  it('formats a quarter-end date without timezone drift', () => {
    expect(fmtQuarter('2026-06-30')).toBe('Jun 2026')
    expect(fmtQuarter('2025-12-31')).toBe('Dec 2025')
    expect(fmtQuarter('2026-01-01')).toBe('Jan 2026')
    expect(fmtQuarter(null)).toBe('—')
    expect(fmtQuarter('garbage')).toBe('garbage')
  })
})

describe('SankeyDiagram', () => {
  it('draws a rectangle per node and a path per link', () => {
    const { container } = render(<SankeyDiagram flow={flowFixture()} />)
    expect(container.querySelectorAll('rect')).toHaveLength(7)
    expect(container.querySelectorAll('path')).toHaveLength(3)
    expect(screen.getByRole('img', { name: 'Income flow diagram' })).toHaveAttribute('viewBox', '0 0 1000 420')
  })

  it('labels each node with its value and share of revenue', () => {
    render(<SankeyDiagram flow={flowFixture()} />)
    const gross = document.querySelector('[data-node="gross"]')
    expect(gross).toHaveTextContent('Gross profit')
    expect(gross).toHaveTextContent('$60.00B · 60.0%')
    expect(document.querySelector('[data-node="revenue"]')).toHaveTextContent('$100.00B · 100.0%')
  })

  it('puts first-column labels on the left and the rest on the right', () => {
    render(<SankeyDiagram flow={flowFixture()} />)
    expect(document.querySelector('[data-node="stream:0"]')).toHaveAttribute('text-anchor', 'end')
    expect(document.querySelector('[data-node="gross"]')).toHaveAttribute('text-anchor', 'start')
    const x = id => Number(document.querySelector(`[data-node="${id}"]`).getAttribute('x'))
    expect(x('stream:0')).toBeLessThan(150)       // left of the node
    expect(x('gross')).toBeGreaterThan(150 + 2 * 130 + 12)   // right of the node
  })

  it('appends the per-share detail to the dividends label', () => {
    render(<SankeyDiagram flow={flowFixture()} />)
    expect(document.querySelector('[data-node="dividends"]')).toHaveTextContent('Dividends · $0.27/share')
  })

  it('clips long labels, leaving less room on the left', () => {
    const long = 'Wearables, Home and Accessories and more'
    const flow = flowFixture({ nodes: [node('a', long, 0, 10, 50, 5e9, { kind: 'stream' }), node('b', long, 1, 10, 50, 5e9)] })
    render(<SankeyDiagram flow={flow} />)
    const text = id => document.querySelector(`[data-node="${id}"] tspan`).textContent
    expect(text('a')).toHaveLength(22)
    expect(text('a').endsWith('…')).toBe(true)
    expect(text('b')).toHaveLength(26)
  })

  it('never draws a hairline link thinner than readable', () => {
    const { container } = render(<SankeyDiagram flow={flowFixture()} />)
    const widths = [...container.querySelectorAll('path')].map(p => Number(p.getAttribute('stroke-width')))
    expect(Math.min(...widths)).toBeGreaterThanOrEqual(0.6)
  })

  it('uses the given currency symbol', () => {
    render(<SankeyDiagram flow={flowFixture()} sym="TWD " />)
    expect(document.querySelector('[data-node="gross"]')).toHaveTextContent('TWD 60.00B')
  })

  it('exposes full details as tooltips', () => {
    const { container } = render(<SankeyDiagram flow={flowFixture()} />)
    const titles = [...container.querySelectorAll('title')].map(t => t.textContent)
    expect(titles).toContain('Gross profit: $60.00B (60.0% of revenue)')
  })
})

describe('TearSheet income flow section', () => {
  beforeEach(() => { window.print = vi.fn() })
  afterEach(() => { vi.restoreAllMocks() })

  async function loaded(payload) {
    mockFetch(payload)
    render(<TearSheet />)
    await build()
    await waitFor(() => screen.getByTestId('verdict-label'))
  }

  it('renders the section with the latest quarter selected', async () => {
    await loaded(flowSheet())
    expect(screen.getByText('Where the money goes — quarterly income flow')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Jun 2026' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Mar 2026' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByText('quarter ended 2026-06-30')).toBeInTheDocument()
    expect(screen.getByTestId('sankey')).toBeInTheDocument()
  })

  it('switches quarters when a tab is clicked', async () => {
    await loaded(flowSheet())
    fireEvent.click(screen.getByRole('tab', { name: 'Mar 2026' }))
    expect(screen.getByRole('tab', { name: 'Mar 2026' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('quarter ended 2026-03-31')).toBeInTheDocument()
    expect(screen.getByText(/No dividends or buybacks were paid this quarter/)).toBeInTheDocument()
  })

  it('shows the headline numbers for the selected quarter', async () => {
    await loaded(flowSheet())
    const flow = screen.getByTestId('income-flow').parentElement
    expect(flow).toHaveTextContent('$100.00B')
    expect(flow).toHaveTextContent('+16.4% vs. year ago')
    expect(flow).toHaveTextContent('30.0% net margin')
    expect(flow).toHaveTextContent('≈ $0.27 per share')
    expect(flow).toHaveTextContent('80% of net income returned')
  })

  it('shows None for dividends and buybacks that were not paid', async () => {
    await loaded(flowSheet())
    fireEvent.click(screen.getByRole('tab', { name: 'Mar 2026' }))
    const stats = screen.getByTestId('income-flow').parentElement
    expect(within(stats).getAllByText('None')).toHaveLength(2)
  })

  it('lists revenue by income stream with share and year-over-year change', async () => {
    await loaded(flowSheet())
    expect(screen.getByText(/Revenue by income stream \(products & services\) · source: SEC 10-Q/)).toBeInTheDocument()
    const section = screen.getByTestId('income-flow').parentElement
    expect(within(section).getAllByText('iPhone').length).toBeGreaterThan(0)
    expect(within(section).getByText('+22.0%')).toBeInTheDocument()
    expect(within(section).getByText('-5.0%')).toBeInTheDocument()
  })

  it('notes when Q4 revenue streams were derived', async () => {
    const p = flowSheet()
    p.incomeFlow.quarters[0].streams.derived = true
    p.incomeFlow.quarters[0].streams.form = '10-K'
    await loaded(p)
    expect(screen.getByText(/source: SEC 10-K — Q4 derived as fiscal year minus nine months/)).toBeInTheDocument()
  })

  it('omits the stream table when no breakdown is available', async () => {
    await loaded(flowSheet())
    fireEvent.click(screen.getByRole('tab', { name: 'Mar 2026' }))
    expect(screen.queryByText(/Revenue by income stream/)).not.toBeInTheDocument()
  })

  it('shows a four-quarter summary table', async () => {
    await loaded(flowSheet())
    expect(screen.getByText('Recent quarters')).toBeInTheDocument()
    for (const label of ['Gross margin', 'Operating margin', 'Net margin', 'Dividends paid', 'Share buybacks']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
  })

  it('explains itself when a quarter has no flow', async () => {
    const p = flowSheet()
    p.incomeFlow.quarters[0].flow = null
    await loaded(p)
    expect(screen.getByText(/don't have enough detail to draw the flow/)).toBeInTheDocument()
    expect(screen.queryByTestId('sankey')).not.toBeInTheDocument()
  })

  it.each([[null], [{ quarters: [] }]])('is hidden for companies without quarterly statements (%j)', async incomeFlow => {
    await loaded(flowSheet({ incomeFlow }))
    expect(screen.queryByText('Where the money goes — quarterly income flow')).not.toBeInTheDocument()
  })

  it('uses the reporting currency for foreign filers', async () => {
    await loaded(flowSheet({ currencyNote: { financial: 'TWD', trading: 'USD' } }))
    expect(document.querySelector('[data-node="gross"]')).toHaveTextContent('TWD 60.00B')
  })

  it('does not break when the quarter list shrinks on a new lookup', async () => {
    await loaded(flowSheet())
    fireEvent.click(screen.getByRole('tab', { name: 'Mar 2026' }))
    const one = flowSheet({ symbol: 'MSFT' })
    one.incomeFlow.quarters = one.incomeFlow.quarters.slice(0, 1)
    mockFetch(one)
    fireEvent.click(screen.getByText('MSFT'))
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Jun 2026' })).toBeInTheDocument())
    expect(screen.queryByRole('tab', { name: 'Mar 2026' })).not.toBeInTheDocument()
  })
})
