import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import TearSheet, { fmtMoney, fmtBig, fmtPct, fmtX } from './TearSheet'

const sheet = (over = {}) => ({
  symbol: 'ACME',
  asOf: '2026-10-09',
  profile: { name: 'Acme Corp', sector: 'Technology', industry: 'Software', exchange: 'NasdaqGS', country: 'United States',
             employees: 12000, description: 'Acme builds widgets.', quoteType: 'EQUITY' },
  snapshot: { price: 100, changePct: 1.25, marketCap: 2.5e12, enterpriseValue: 2.4e12, week52High: 120, week52Low: 80,
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
