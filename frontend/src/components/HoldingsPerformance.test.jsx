import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import HoldingsPerformance, { fmtRet, heatStyle, periodValue, summarizeRows } from './HoldingsPerformance'

vi.mock('./ChartModal', () => ({
  default: ({ symbol, quote, onClose }) => (
    <div data-testid="chart-modal">
      chart for {symbol} {quote.name} {quote.changePercent}
      <button onClick={onClose}>close chart</button>
    </div>
  ),
}))

const PERIODS = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y', '10Y', 'LTD']
const ANN = ['3Y', '5Y', '10Y', 'LTD']

const ret = (over = {}) => ({ '1D': 0.01, '1W': 0.02, '1M': 0.03, '3M': 0.05, '6M': 0.1, YTD: 0.2, '1Y': 0.3, '3Y': 1.0, '5Y': 2.0, '10Y': 5.0, LTD: 40.0, ...over })

const holding = (symbol, name, sector, returns, annualised = {}, over = {}) => ({
  symbol, name, sector, weight: null, returns, annualised, ltdSince: '1980-12-08', price: 100, asOf: '2026-10-09', ...over,
})

const payload = (over = {}) => ({
  universe: { id: 'SP500', name: 'S&P 500', kind: 'index', partial: false, note: null, holdingCount: 4, withData: 4 },
  periods: PERIODS, annualisedPeriods: ANN, asOf: '2026-10-09',
  benchmark: { symbol: 'SPY', returns: ret({ YTD: 0.15, '1D': 0.006 }), annualised: { '3Y': 0.2 } },
  summary: {},
  holdings: [
    holding('NVDA', 'NVIDIA Corp', 'Information Technology', ret({ YTD: 0.5, '1Y': 0.2 }), { '3Y': 0.4, '5Y': 0.5 }),
    holding('AAPL', 'Apple Inc.', 'Information Technology', ret({ YTD: 0.24, '1Y': 0.33, LTD: 34.298 }), { '3Y': 0.24, LTD: 0.19 }),
    holding('JPM', 'JPMorgan Chase', 'Financials', ret({ YTD: -0.1, '1Y': 0.1 }), { '3Y': 0.1 }),
    holding('NEWCO', 'NewCo Holdings', 'Health Care', ret({ YTD: 0.9, '1Y': null, '3Y': null, '5Y': null, '10Y': null, LTD: 1.2 }), {}),
  ],
  missing: [], ...over,
})

const PRESETS = [
  { id: 'SP500', name: 'S&P 500', kind: 'index', benchmark: 'SPY' },
  { id: 'XLK', name: 'XLK — Information Technology (S&P 500 sector)', kind: 'sector-etf', benchmark: 'XLK' },
  { id: 'XLF', name: 'XLF — Financials (S&P 500 sector)', kind: 'sector-etf', benchmark: 'XLF' },
]

function mockApi(handlers = {}) {
  global.fetch = vi.fn(async url => {
    const u = String(url)
    if (u.includes('/universes')) return { ok: true, json: async () => ({ presets: PRESETS, periods: PERIODS }) }
    const key = decodeURIComponent(u.split('universe=')[1] || '')
    const h = handlers[key] ?? handlers.default
    const r = typeof h === 'function' ? await h(key) : h
    return r?.__error ? { ok: false, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r ?? payload() }
  })
}

const symbolsInOrder = () => screen.getAllByTestId('holding-row').map(r => within(r).getAllByRole('button')[0].textContent)
const cell = (symbol, period) => {
  const row = screen.getAllByTestId('holding-row').find(r => within(r).getAllByRole('button')[0].textContent === symbol)
  return row.querySelector(`[data-period="${period}"]`)
}
const header = name => screen.getAllByRole('columnheader').find(h => h.textContent.replace(/[▲▼\s]/g, '').startsWith(name.replace(/\s/g, '')))

async function loaded(handlers) {
  mockApi(handlers)
  render(<HoldingsPerformance />)
  await screen.findAllByTestId('holding-row')
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:csv')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => { vi.restoreAllMocks() })

describe('helpers', () => {
  it('formats returns, with thousands separators for huge gains and dashes for missing', () => {
    expect(fmtRet(0.153)).toBe('+15.3%')
    expect(fmtRet(-0.05)).toBe('-5.0%')
    expect(fmtRet(1.2345)).toBe('+123%')
    expect(fmtRet(34.298)).toBe('+3,430%')
    expect(fmtRet(0.153, false)).toBe('15.3%')
    expect(fmtRet(0)).toBe('0.0%')
    for (const v of [null, undefined, NaN]) expect(fmtRet(v)).toBe('—')
  })

  it('shades gains green and losses red, stronger for bigger moves, scaled per period', () => {
    expect(heatStyle(0.02, '1D', false).backgroundColor).toMatch(/^rgba\(16,185,129,/)
    expect(heatStyle(-0.02, '1D', false).backgroundColor).toMatch(/^rgba\(239,68,68,/)
    const alpha = s => Number(s.backgroundColor.match(/,([\d.]+)\)$/)[1])
    expect(alpha(heatStyle(0.04, '1D', false))).toBeGreaterThan(alpha(heatStyle(0.01, '1D', false)))
    expect(alpha(heatStyle(0.04, '1D', false))).toBeGreaterThan(alpha(heatStyle(0.04, 'YTD', false)))   // +4% is big for a day, small for a year
    expect(alpha(heatStyle(99, 'LTD', false))).toBeCloseTo(0.55)                                       // saturates
    expect(heatStyle(null, 'YTD', false)).toEqual({})
  })

  it('picks cumulative or annualised values', () => {
    const row = { returns: { '3Y': 1.0, YTD: 0.2 }, annualised: { '3Y': 0.26 } }
    expect(periodValue(row, '3Y', false, ANN)).toBe(1.0)
    expect(periodValue(row, '3Y', true, ANN)).toBe(0.26)
    expect(periodValue(row, 'YTD', true, ANN)).toBe(0.2)                  // short periods are never annualised
    expect(periodValue(row, '5Y', true, ANN)).toBeNull()
  })

  it('summarises rows: mean, median, share up, share beating the benchmark', () => {
    const rows = [0.3, 0.1, -0.1, 0.5].map(v => ({ returns: { YTD: v }, annualised: {} }))
    const s = summarizeRows(rows, 0.2, 'YTD', false, ANN)
    expect(s).toMatchObject({ n: 4, positive: 0.75, beating: 0.5 })
    expect(s.mean).toBeCloseTo(0.2) && expect(s.median).toBeCloseTo(0.2)
    expect(summarizeRows(rows.slice(0, 3), null, 'YTD', false, ANN).beating).toBeNull()
    expect(summarizeRows([], 0.1, 'YTD', false, ANN)).toEqual({ n: 0 })
    expect(summarizeRows([{ returns: {} }], 0.1, 'YTD', false, ANN)).toEqual({ n: 0 })
  })

  it('median of an odd-sized list is the middle value', () => {
    const rows = [0.1, 0.9, 0.2].map(v => ({ returns: { YTD: v }, annualised: {} }))
    expect(summarizeRows(rows, null, 'YTD', false, ANN).median).toBeCloseTo(0.2)
  })
})

describe('HoldingsPerformance', () => {
  it('loads the S&P 500 on open and shows its headline', async () => {
    await loaded()
    expect(global.fetch).toHaveBeenCalledWith('/api/holdings-performance?universe=SP500')
    expect(screen.getByText('S&P 500', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText(/4 holdings with data/)).toBeInTheDocument()
    expect(screen.getByText(/as of 2026-10-09/)).toBeInTheDocument()
  })

  it('has a column for every period, in order', async () => {
    await loaded()
    const heads = screen.getAllByRole('columnheader').map(h => h.textContent.replace(/[▲▼]/g, '').trim())
    expect(heads.slice(-11)).toEqual(PERIODS)
  })

  it('ranks by YTD, best first, by default', async () => {
    await loaded()
    expect(symbolsInOrder()).toEqual(['NEWCO', 'NVDA', 'AAPL', 'JPM'])
    expect(header('YTD')).toHaveAttribute('aria-sort', 'descending')
    expect(header('YTD').textContent).toContain('▼')
  })

  it('sorts by another period, then flips on a second click', async () => {
    await loaded()
    fireEvent.click(header('1Y'))
    expect(symbolsInOrder()).toEqual(['AAPL', 'NVDA', 'JPM', 'NEWCO'])          // NEWCO has no 1Y: sinks to the bottom
    expect(header('1Y')).toHaveAttribute('aria-sort', 'descending')
    fireEvent.click(header('1Y'))
    expect(symbolsInOrder()).toEqual(['JPM', 'NVDA', 'AAPL', 'NEWCO'])          // still last when ascending
    expect(header('1Y')).toHaveAttribute('aria-sort', 'ascending')
  })

  it('sorts text columns A to Z first', async () => {
    await loaded()
    fireEvent.click(header('Symbol'))
    expect(symbolsInOrder()).toEqual(['AAPL', 'JPM', 'NEWCO', 'NVDA'])
    fireEvent.click(header('Name'))
    expect(symbolsInOrder()).toEqual(['AAPL', 'JPM', 'NEWCO', 'NVDA'].sort((a, b) => ({ AAPL: 'Apple', JPM: 'JPMorgan', NEWCO: 'NewCo', NVDA: 'NVIDIA' }[a].localeCompare({ AAPL: 'Apple', JPM: 'JPMorgan', NEWCO: 'NewCo', NVDA: 'NVIDIA' }[b]))))
  })

  it('formats cells and colours them', async () => {
    await loaded()
    expect(cell('NVDA', 'YTD')).toHaveTextContent('+50.0%')
    expect(cell('JPM', 'YTD')).toHaveTextContent('-10.0%')
    expect(cell('JPM', 'YTD')).toHaveClass('text-red-300')
    expect(cell('NVDA', 'YTD')).toHaveClass('text-emerald-300')
    expect(cell('AAPL', 'LTD')).toHaveTextContent('+3,430%')
    expect(cell('NEWCO', '10Y')).toHaveTextContent('—')
    expect(cell('NVDA', 'YTD').style.backgroundColor).toMatch(/rgba\(16, ?185, ?129/)
  })

  it('shows when life-to-date starts in a tooltip', async () => {
    await loaded()
    expect(cell('AAPL', 'LTD')).toHaveAttribute('title', 'Since 1980-12-08')
  })

  it('pins the benchmark row', async () => {
    await loaded()
    const row = screen.getByTestId('benchmark-row')
    expect(row).toHaveTextContent('SPY')
    expect(row).toHaveTextContent('+15.0%')
    expect(row).toHaveTextContent('+0.6%')
  })

  it('summarises the holdings shown, against the benchmark', async () => {
    await loaded()
    const rows = Object.fromEntries(screen.getAllByTestId('summary-row').map(r => [r.querySelector('td').textContent, r]))
    expect(Object.keys(rows)).toEqual(['Average', 'Median', '% up', '% beating SPY'])
    const ytdIndex = PERIODS.indexOf('YTD')
    const val = r => r.querySelectorAll('td')[2 + ytdIndex].textContent          // symbol + "n shown" + periods
    expect(val(rows['% up'])).toBe('75%')                                         // 3 of 4 are up YTD
    expect(val(rows['% beating SPY'])).toBe('75%')                                // NEWCO, NVDA, AAPL beat +15%
    expect(val(rows.Average)).toBe('+38.5%')                                      // (0.9 + 0.5 + 0.24 - 0.1) / 4
  })

  it('filters by sector and recomputes the summary for what is left', async () => {
    await loaded()
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: 'Information Technology' } })
    expect(symbolsInOrder()).toEqual(['NVDA', 'AAPL'])
    const avg = screen.getAllByTestId('summary-row')[0]
    expect(avg).toHaveTextContent('2 shown')
    expect(avg.querySelectorAll('td')[2 + PERIODS.indexOf('YTD')].textContent).toBe('+37.0%')
  })

  it('filters by text on symbol or name and says when nothing matches', async () => {
    await loaded()
    fireEvent.change(screen.getByLabelText('Filter holdings'), { target: { value: 'jpm' } })
    expect(symbolsInOrder()).toEqual(['JPM'])
    fireEvent.change(screen.getByLabelText('Filter holdings'), { target: { value: 'apple' } })
    expect(symbolsInOrder()).toEqual(['AAPL'])
    fireEvent.change(screen.getByLabelText('Filter holdings'), { target: { value: 'zzzz' } })
    expect(screen.getByText('No holdings match the filter.')).toBeInTheDocument()
  })

  it('switches the multi-year columns to annualised figures', async () => {
    await loaded()
    expect(cell('AAPL', '3Y')).toHaveTextContent('+100%')
    fireEvent.click(screen.getByLabelText('Annualise 3Y+'))
    expect(header('3Y').textContent).toContain('3Y/yr')
    expect(cell('AAPL', '3Y')).toHaveTextContent('+24.0%')
    expect(cell('AAPL', 'LTD')).toHaveTextContent('+19.0%')
    expect(cell('AAPL', 'YTD')).toHaveTextContent('+24.0%')                        // short periods unchanged
    expect(cell('AAPL', '10Y')).toHaveTextContent('—')                             // no annualised figure available
    fireEvent.click(screen.getByLabelText('Annualise 3Y+'))
    expect(cell('AAPL', '3Y')).toHaveTextContent('+100%')
  })

  it('sorts by the annualised value when that mode is on', async () => {
    await loaded()
    fireEvent.click(screen.getByLabelText('Annualise 3Y+'))
    fireEvent.click(header('3Y'))
    expect(symbolsInOrder().slice(0, 3)).toEqual(['NVDA', 'AAPL', 'JPM'])          // 40% > 24% > 10%; NEWCO (none) last
    expect(symbolsInOrder()[3]).toBe('NEWCO')
  })

  it('switches universe from the quick buttons', async () => {
    await loaded({ NASDAQ100: payload({ universe: { id: 'NASDAQ100', name: 'Nasdaq-100', kind: 'index', partial: false, note: null, holdingCount: 4, withData: 4 } }) })
    fireEvent.click(screen.getByRole('button', { name: 'Nasdaq-100' }))
    await waitFor(() => expect(screen.getByText('Nasdaq-100', { selector: 'span' })).toBeInTheDocument())
    expect(global.fetch).toHaveBeenCalledWith('/api/holdings-performance?universe=NASDAQ100')
  })

  it('offers the sector ETFs from the server presets', async () => {
    await loaded()
    await waitFor(() => expect(screen.getByRole('option', { name: /XLK/ })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Sector ETF'), { target: { value: 'XLF' } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/holdings-performance?universe=XLF'))
  })

  it('looks up any ETF ticker, uppercased', async () => {
    await loaded()
    fireEvent.change(screen.getByLabelText('ETF or index ticker'), { target: { value: 'arkk' } })
    expect(screen.getByLabelText('ETF or index ticker')).toHaveValue('ARKK')
    fireEvent.click(screen.getByRole('button', { name: 'Show holdings' }))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/holdings-performance?universe=ARKK'))
  })

  it('does nothing for a blank ETF ticker', async () => {
    await loaded()
    expect(screen.getByRole('button', { name: 'Show holdings' })).toBeDisabled()
  })

  it('shows the server explanation when a ticker is not a fund', async () => {
    await loaded({ AAPL: { __error: "AAPL isn't an ETF or fund Yahoo has holdings for" } })
    fireEvent.change(screen.getByLabelText('ETF or index ticker'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByRole('button', { name: 'Show holdings' }))
    expect(await screen.findByRole('alert')).toHaveTextContent("AAPL isn't an ETF")
    expect(screen.queryByTestId('perf-table')).not.toBeInTheDocument()
  })

  it('shows a network failure', async () => {
    mockApi()
    global.fetch = vi.fn(async url => (String(url).includes('/universes') ? { ok: true, json: async () => ({ presets: [] }) } : Promise.reject(new Error('Network down'))))
    render(<HoldingsPerformance />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
  })

  it('explains the wait while loading', async () => {
    mockApi({ SP500: () => new Promise(() => {}) })
    render(<HoldingsPerformance />)
    expect(await screen.findByText(/first load of a full index takes 30–60 seconds/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nasdaq-100' })).toBeDisabled()
  })

  it('flags partial ETF data with a warning note and shows reported weights, hiding the sector column', async () => {
    const etf = payload({
      universe: { id: 'ARKK', name: 'ARKK — top holdings', kind: 'etf', partial: true, holdingCount: 2, withData: 2, note: 'Showing only the top 2 holdings: Yahoo doesn’t publish a fund’s full list.' },
      holdings: [holding('TSLA', 'Tesla', null, ret({ YTD: 0.3 }), {}, { weight: 10.5 }), holding('COIN', 'Coinbase', null, ret({ YTD: 0.1 }), {}, { weight: 8.25 })],
    })
    await loaded({ SP500: etf })
    expect(screen.getByText(/Showing only the top 2 holdings/)).toHaveClass('text-amber-300')
    expect(header('Weight')).toBeTruthy()
    expect(screen.getByText('10.50%')).toBeInTheDocument()
    expect(header('Sector')).toBeUndefined()
    expect(screen.queryByLabelText('Sector')).not.toBeInTheDocument()
  })

  it('shows an informational (not warning) note for complete lists', async () => {
    await loaded({ SP500: payload({ universe: { ...payload().universe, note: 'Dow 30 membership is the list maintained in this app.' } }) })
    expect(screen.getByText(/maintained in this app/)).not.toHaveClass('text-amber-300')
  })

  it('mentions holdings that had no price history', async () => {
    await loaded({ SP500: payload({ missing: ['GONE', 'OLD'] }) })
    expect(screen.getByText(/2 without price history/)).toBeInTheDocument()
  })

  it('keeps the newest response when overlapping loads resolve out of order (React StrictMode double-mounts)', async () => {
    let calls = 0
    const releases = []
    const named = name => payload({ universe: { ...payload().universe, name } })
    mockApi({
      SP500: () => new Promise(resolve => {
        const n = ++calls
        releases[n] = () => resolve(named(n === 1 ? 'First' : 'Second'))
      }),
    })
    render(<StrictMode><HoldingsPerformance /></StrictMode>)
    await waitFor(() => expect(calls).toBe(2))
    releases[2]()
    await screen.findAllByTestId('holding-row')
    expect(screen.getByText('Second', { selector: 'span' })).toBeInTheDocument()
    releases[1]()                                                       // the stale one finishes last
    await new Promise(r => setTimeout(r, 20))
    expect(screen.getByText('Second', { selector: 'span' })).toBeInTheDocument()
    expect(screen.queryByText('First', { selector: 'span' })).not.toBeInTheDocument()
  })

  it('opens the chart for a clicked symbol and closes it again', async () => {
    await loaded()
    fireEvent.click(screen.getByLabelText('Chart NVDA'))
    expect(screen.getByTestId('chart-modal')).toHaveTextContent('chart for NVDA NVIDIA Corp 1')
    fireEvent.click(screen.getByText('close chart'))
    expect(screen.queryByTestId('chart-modal')).not.toBeInTheDocument()
  })

  it('exports exactly the rows shown, in the current order and mode, as CSV', async () => {
    await loaded()
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: 'Information Technology' } })
    fireEvent.click(screen.getByLabelText('Annualise 3Y+'))
    const clicks = []
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(tag => {
      const el = realCreate(tag)
      if (tag === 'a') el.click = () => clicks.push(el.download)
      return el
    })
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    const blob = URL.createObjectURL.mock.calls[0][0]
    const text = await new Promise(resolve => { const fr = new FileReader(); fr.onload = () => resolve(fr.result); fr.readAsText(blob) })
    const lines = text.split('\n')
    expect(lines[0]).toContain('"Symbol","Name","Sector"')
    expect(lines[0]).toContain('3Y annualised %')
    expect(lines[0]).toContain('YTD %')
    expect(lines.filter(l => /^"(NVDA|AAPL)"/.test(l))).toHaveLength(2)
    expect(text).not.toContain('"JPM"')
    expect(lines[1]).toMatch(/^"NVDA"/)                                            // YTD order: NVDA (50%) before AAPL (24%)
    expect(text).toContain('Total returns (dividends reinvested) as of 2026-10-09')
    expect(clicks).toEqual(['SP500_performance_2026-10-09.csv'])
  })

  it('escapes quotes in CSV fields', async () => {
    await loaded({ SP500: payload({ holdings: [holding('Q', 'Quote "Corp"', 'Tech', ret())] }) })
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    const blob = URL.createObjectURL.mock.calls[0][0]
    const text = await new Promise(resolve => { const fr = new FileReader(); fr.onload = () => resolve(fr.result); fr.readAsText(blob) })
    expect(text).toContain('"Quote ""Corp"""')
  })

  it('describes the return conventions in a footnote', async () => {
    await loaded()
    expect(screen.getByText(/Returns use dividend-adjusted closes/)).toBeInTheDocument()
  })
})
