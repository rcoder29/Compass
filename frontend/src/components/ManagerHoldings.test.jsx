import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import ManagerHoldings, { fmtUsd, fmtShares, toCsv } from './ManagerHoldings'

vi.mock('./ChartModal', () => ({ default: ({ symbol, onClose }) => <div data-testid="chart-modal">chart {symbol}<button onClick={onClose}>close chart</button></div> }))
afterEach(() => vi.restoreAllMocks())

const LIST = { managers: [
  { id: 'berkshire', name: 'Berkshire Hathaway', person: 'Warren Buffett', kind: '13f', blurb: 'Holding company.' },
  { id: 'damodaran', name: 'Aswath Damodaran', person: 'NYU professor', kind: 'disclosed', blurb: 'No 13F.' },
] }
const pos = (rank, ticker, name, over = {}) => ({ cusip: `C${rank}`, rank, ticker, name, class: 'COM', shares: 1e7, value: 5e9, weight: 0.3 / rank, status: 'unchanged', sharesChangePct: 0, prevShares: 1e7,
  retSinceQE: 0.05, priceNow: 100, history: [1, 1, 2, 2, 3, 3], ...over })
const REPORT = {
  manager: LIST.managers[0],
  filing: { period: '2026-06-30', filed: '2026-08-14', form: '13F-HR', url: 'https://sec.gov/x/', amendments: [], previousPeriod: '2026-03-31', nextExpected: '2026-11-14', daysSinceFiled: 65 },
  summary: { totalValue: 299.25e9, positions: 3, top5: 0.7, top10: 0.9, largestWeight: 0.3, counts: { new: 1, added: 1, reduced: 1, unchanged: 0, exited: 1 }, valueChangePct: 0.137 },
  positions: [pos(1, 'AAPL', 'APPLE INC', { status: 'added', sharesChangePct: 0.45 }), pos(2, 'KO', 'COCA COLA CO', { status: 'new', sharesChangePct: null }), pos(3, null, 'CHUBB LIMITED', { status: 'reduced', sharesChangePct: -0.2, retSinceQE: null })],
  exited: [{ cusip: 'X', ticker: 'STZ', name: 'CONSTELLATION', prevWeight: 0.02 }], otherPositions: 0,
  highlights: { new: [pos(2, 'KO', 'COCA COLA CO')], added: [pos(1, 'AAPL', 'APPLE INC', { sharesChangePct: 0.45 })], reduced: [pos(3, null, 'CHUBB LIMITED', { sharesChangePct: -0.2 })] },
  history: { periods: ['2026-03-31', '2026-06-30'], series: [{ period: '2026-03-31', totalValue: 263e9, positions: 29, top5: 0.67 }, { period: '2026-06-30', totalValue: 299e9, positions: 29, top5: 0.69 }] },
  performance: { sinceQE: { return: 0.061, coverage: 0.96 }, sinceFiled: { return: 0.006, coverage: 0.96 }, benchmark: { sinceQE: 0.025 } },
}
const DISCLOSED = {
  manager: LIST.managers[1],
  positions: [{ id: 1, symbol: 'AAPL', name: 'Apple', action: 'owns', asOf: '2024-02-09', note: 'Owns all seven.', sourceTitle: 'Damodaran on X', sourceUrl: 'https://x.com/a/1', confidence: 'primary', price: 343.5, ret1y: 0.37 }],
  approach: [{ id: 2, symbol: null, name: 'Portfolio approach', action: 'approach', asOf: null, note: 'About 40 stocks.', sourceTitle: 'Bogleheads', sourceUrl: 'https://bogle/x', confidence: 'secondary' }], sources: [],
}

function mockFetch({ report = REPORT, disclosed = DISCLOSED, fail = {}, post } = {}) {
  const calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    calls.push([url, opts.method || 'GET'])
    const ok = body => ({ ok: true, status: 200, json: async () => body })
    if (opts.method === 'POST') return post ? post(opts) : ok({ id: 9 })
    if (opts.method === 'DELETE') return ok({ ok: true })
    if (url === '/api/managers') return ok(LIST)
    const id = url.split('/api/managers/')[1].split('?')[0]
    if (fail[id]) return { ok: false, status: 502, json: async () => ({ detail: fail[id] }) }
    return ok(id === 'damodaran' ? disclosed : report)
  })
  return calls
}

describe('formatters', () => {
  it('fmtUsd', () => { expect(fmtUsd(299.25e9)).toBe('$299.3B'); expect(fmtUsd(2.5e12)).toBe('$2.50T'); expect(fmtUsd(5e6)).toBe('$5M'); expect(fmtUsd(null)).toBe('—') })
  it('fmtShares', () => { expect(fmtShares(227917808)).toBe('227.9M'); expect(fmtShares(2.5e9)).toBe('2.50B'); expect(fmtShares(null)).toBe('—') })
  it('toCsv quotes names and leaves blanks for missing values', () => {
    const csv = toCsv([pos(3, null, 'A "B" CO', { retSinceQE: null, sharesChangePct: null })])
    expect(csv.split('\n')[1]).toContain('"A ""B"" CO"')
    expect(csv.split('\n')[1].endsWith(',,')).toBe(true)
  })
})

describe('13F manager view', () => {
  const inTable = () => within(screen.getByRole('table'))
  it('shows filing details, summary and the limits of a 13F', async () => {
    mockFetch()
    render(<ManagerHoldings />)
    await screen.findByRole('table')
    expect(inTable().getByText('APPLE INC')).toBeTruthy()
    expect(screen.getByText('$299.3B')).toBeTruthy()
    expect(screen.getByText(/next report due by/i)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'SEC filing' }).getAttribute('href')).toBe('https://sec.gov/x/')
    fireEvent.click(screen.getByText('Read this first'))
    expect(screen.getByText(/not Warren Buffett personally/i)).toBeTruthy()
  })

  it('lists what changed, including positions sold out', async () => {
    mockFetch()
    render(<ManagerHoldings />)
    await screen.findByRole('table')
    expect(screen.getByText('New (1)')).toBeTruthy()
    expect(screen.getByText('Sold out (1)')).toBeTruthy()
    expect(screen.getByText('CONSTELLATION')).toBeTruthy()
  })

  it('filters by status and by search', async () => {
    mockFetch()
    render(<ManagerHoldings />)
    await screen.findByRole('table')
    const table = () => within(screen.getByRole('table'))
    fireEvent.click(screen.getByRole('button', { name: 'Reduced' }))
    expect(table().queryByText('APPLE INC')).toBeNull()
    expect(table().getByText('CHUBB LIMITED')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    fireEvent.change(screen.getByLabelText('Find a holding'), { target: { value: 'coca' } })
    expect(table().getByText('COCA COLA CO')).toBeTruthy()
    expect(table().queryByText('APPLE INC')).toBeNull()
    fireEvent.change(screen.getByLabelText('Find a holding'), { target: { value: 'zzz' } })
    expect(screen.getByText('No holdings match.')).toBeTruthy()
  })

  it('opens a chart only for holdings that have a ticker', async () => {
    mockFetch()
    render(<ManagerHoldings />)
    await screen.findByRole('table')
    expect(inTable().getByText('CHUBB LIMITED').closest('button')).toBeNull()
    fireEvent.click(inTable().getByText('AAPL'))
    expect(screen.getByTestId('chart-modal').textContent).toContain('AAPL')
  })

  it('shows an error without crashing when the SEC load fails', async () => {
    mockFetch({ fail: { berkshire: 'SEC is down' } })
    render(<ManagerHoldings />)
    expect((await screen.findByRole('alert')).textContent).toContain('SEC is down')
  })
})

describe('disclosed investor view', () => {
  async function open() {
    const calls = mockFetch()
    render(<ManagerHoldings />)
    fireEvent.click(await screen.findByRole('tab', { name: /Aswath Damodaran/ }))
    await screen.findByText('Owns all seven.')
    return calls
  }

  it('shows each statement with its source and how reliable it is', async () => {
    await open()
    expect(screen.getByRole('link', { name: 'Damodaran on X' }).getAttribute('href')).toBe('https://x.com/a/1')
    expect(screen.getByText('His own words')).toBeTruthy()
    expect(screen.getByText(/About 40 stocks/)).toBeTruthy()
    fireEvent.click(screen.getByText('Read this first'))
    expect(screen.getByText(/files no 13F/i)).toBeTruthy()
  })

  it('adds an entry with a source and reloads', async () => {
    const calls = await open()
    fireEvent.click(screen.getByText('Add'))
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'brk-b' } })
    fireEvent.change(screen.getByLabelText('Source link'), { target: { value: 'https://example.com/p' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some(c => c[1] === 'POST')).toBe(true))
    await waitFor(() => expect(calls.filter(c => c[0].startsWith('/api/managers/damodaran')).length).toBeGreaterThan(2))
  })

  it('shows the server message when an entry is rejected', async () => {
    mockFetch({ post: async () => ({ ok: false, status: 400, json: async () => ({ detail: 'asOf must be YYYY-MM or YYYY-MM-DD' }) }) })
    render(<ManagerHoldings />)
    fireEvent.click(await screen.findByRole('tab', { name: /Aswath Damodaran/ }))
    await screen.findByText('Owns all seven.')
    fireEvent.click(screen.getByText('Add'))
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect((await screen.findByRole('alert')).textContent).toContain('asOf must be')
  })

  it('removes an entry', async () => {
    const calls = await open()
    fireEvent.click(screen.getByLabelText('Remove AAPL'))
    await waitFor(() => expect(calls.some(c => c[1] === 'DELETE' && c[0].endsWith('/disclosures/1'))).toBe(true))
  })
})
