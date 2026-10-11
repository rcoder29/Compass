import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor, act } from '@testing-library/react'
import HundredBaggers, { fmtCap, toCsv } from './HundredBaggers'

vi.mock('./ChartModal', () => ({ default: ({ symbol, onClose }) => <div data-testid="chart-modal">chart {symbol}<button onClick={onClose}>close chart</button></div> }))

const FACTORS = { size: 20, growth: 25, returns: 15, margins: 10, balance: 10, owners: 10, valuation: 10 }
const NAMES = { size: 'Room to grow (size)', growth: 'Growth', returns: 'Return on equity', margins: 'Margins & pricing power', balance: 'Balance sheet', owners: 'Owner-operators', valuation: 'Valuation vs growth' }
const traits = n => ['small', 'growth', 'returns', 'margins', 'balance', 'owners', 'valuation'].map((id, i) => ({ id, label: `Trait ${id}`, met: i < n }))
const row = (symbol, over = {}) => ({
  symbol, name: `${symbol} Corp`, sector: 'Technology', price: 10, marketCap: 1.5e9, revenue: 4e8, growthUsed: 0.3, roe: 0.3, grossMargin: 0.6, operatingMargin: 0.2,
  debtToEquity: 0.1, insiders: 0.2, score: 85, tier: 'Strong fit', capped: false, yearsTo100x: 17.5, capAt100x: 1.5e11, traits: traits(6), traitsMet: 6, flags: [],
  summary: `${symbol} makes widgets.`, factors: Object.fromEntries(Object.entries(FACTORS).map(([k, w]) => [k, { score: 80, weight: w, points: w * 0.8, note: `${k} note`, missing: false }])), ...over,
})
const ready = (rows, extra = {}) => ({
  status: 'ready', universe: { id: 'SP600', name: 'S&P SmallCap 600', size: rows.length }, rows: rows.map((r, i) => ({ ...r, rank: i + 1 })),
  counts: { scored: rows.length, tooBig: 2, noData: 1 }, tierCounts: { 'Strong fit': 1, Promising: 1, 'Partial fit': 1, 'Weak fit': 0 }, factorNames: NAMES, weights: FACTORS, ...extra,
})
const rows3 = () => [
  row('AAA'),
  row('BBB', { score: 62, tier: 'Promising', marketCap: 8e9, capAt100x: 8e11, sector: 'Health Care', growthUsed: 0.22, flags: ['Burning cash'], traitsMet: 4, traits: traits(4), insiders: 0.02 }),
  row('CCC', { score: 45, tier: 'Partial fit', marketCap: 25e9, sector: 'Industrials', growthUsed: 0.1, yearsTo100x: null, capped: true }),
]

function mock(handler) {
  global.fetch = vi.fn(async url => {
    const u = String(url)
    if (u.includes('/universes')) return { ok: true, json: async () => ({ universes: [{ id: 'SP600', name: 'S&P SmallCap 600', blurb: 'small caps' }, { id: 'SP400', name: 'S&P MidCap 400', blurb: 'mid caps' }] }) }
    const r = await handler(u)
    return r?.__error ? { ok: false, status: 502, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r }
  })
}
const order = () => screen.getAllByTestId('bagger-row').map(r => r.getAttribute('aria-label').replace(' details', ''))

beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:x'); URL.revokeObjectURL = vi.fn() })
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

describe('helpers', () => {
  it('formats market caps', () => {
    expect(fmtCap(5e8)).toBe('$500M'); expect(fmtCap(1.5e9)).toBe('$1.5B'); expect(fmtCap(2.5e10)).toBe('$25B'); expect(fmtCap(3e12)).toBe('$3.0T'); expect(fmtCap(null)).toBe('—')
  })
  it('exports CSV with quoted text and blank gaps', () => {
    const csv = toCsv([{ ...row('AAA'), rank: 1, name: 'A, "Inc"', debtToEquity: null, flags: ['x', 'y'] }])
    const lines = csv.split('\n')
    expect(lines[0]).toContain('"Symbol"') && expect(lines[1]).toContain('"A, ""Inc"""')
    expect(lines[1]).toContain('"x; y"'); expect(lines[1]).toContain('6/7')
  })
})

describe('HundredBaggers', () => {
  it('shows the scored table ranked by score with tiers, counts and the arithmetic', async () => {
    mock(() => ready(rows3()))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    expect(order()).toEqual(['AAA', 'BBB', 'CCC'])
    expect(screen.getByText('1 strong fit')).toBeInTheDocument()
    expect(screen.getByText(/2 left out as too large/)).toBeInTheDocument()
    expect(screen.getByText(/58%/)).toBeInTheDocument()
    expect(screen.getAllByText('Strong fit').length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('6 of 7 traits met')).toHaveLength(2)
    expect(screen.getByLabelText('4 of 7 traits met')).toBeInTheDocument()
  })

  it('shows a progress bar while the first scan runs and polls until ready', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mock(() => (++calls < 3 ? { status: 'running', universe: { id: 'SP600', name: 'S&P SmallCap 600', size: 600 }, progress: { done: calls * 100, total: 600 } } : ready(rows3())))
    render(<HundredBaggers />)
    expect(await screen.findByRole('status')).toHaveTextContent('100 / 600')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByRole('status')).toHaveTextContent('200 / 600')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByTestId('bagger-table')).toBeInTheDocument()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('filters by fit, size, sector, cautions and text; says when nothing matches', async () => {
    mock(() => ready(rows3()))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    fireEvent.change(screen.getByLabelText('Minimum fit'), { target: { value: 'promising' } })
    expect(order()).toEqual(['AAA', 'BBB'])
    fireEvent.change(screen.getByLabelText('Market cap'), { target: { value: String(5e9) } })
    expect(order()).toEqual(['AAA'])
    fireEvent.change(screen.getByLabelText('Market cap'), { target: { value: 'any' } })
    fireEvent.click(screen.getByLabelText(/Hide stocks with cautions/))
    expect(order()).toEqual(['AAA'])
    fireEvent.click(screen.getByLabelText(/Hide stocks with cautions/))
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: 'Health Care' } })
    expect(order()).toEqual(['BBB'])
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Filter stocks'), { target: { value: 'zzz' } })
    expect(screen.getByText(/No stocks match/)).toBeInTheDocument()
  })

  it('sorts by a column, toggles direction, and keeps missing values last', async () => {
    mock(() => ready(rows3()))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByRole('columnheader', { name: /^Mkt cap/ }))           // ascending first for size
    expect(order()).toEqual(['AAA', 'BBB', 'CCC'])
    fireEvent.click(screen.getByRole('columnheader', { name: /^Mkt cap/ }))
    expect(order()).toEqual(['CCC', 'BBB', 'AAA'])
    fireEvent.click(screen.getByRole('columnheader', { name: /^Yrs to 100x/ }))       // CCC has none
    expect(order()[2]).toBe('CCC')
    fireEvent.click(screen.getByRole('columnheader', { name: /^Yrs to 100x/ }))
    expect(order()[2]).toBe('CCC')
  })

  it('expands a row to the factor breakdown, traits, cautions and the 100x arithmetic', async () => {
    mock(() => ready(rows3()))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByLabelText('BBB details'))
    const d = within(screen.getByTestId('bagger-detail'))
    expect(d.getByText('Burning cash')).toBeInTheDocument()
    expect(d.getByText('growth note')).toBeInTheDocument()
    expect(d.getByText(/100x from \$8\.0B means a \$800B company/)).toBeInTheDocument()
    expect(d.getByText(/18 years/)).toBeInTheDocument()
    expect(d.getByText('Traits (4/7)')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('BBB details'))
    expect(screen.queryByTestId('bagger-detail')).toBeNull()
  })

  it('explains a cap and a no-growth company, and opens the chart', async () => {
    mock(() => ready(rows3()))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByLabelText('CCC details'))
    const d = within(screen.getByTestId('bagger-detail'))
    expect(d.getByText(/capped at 60/)).toBeInTheDocument()
    expect(d.getByText(/isn.t growing/)).toBeInTheDocument()
    fireEvent.click(d.getByText('Open chart'))
    expect(screen.getByTestId('chart-modal')).toHaveTextContent('chart CCC')
    fireEvent.click(screen.getByText('close chart'))
    expect(screen.queryByTestId('chart-modal')).toBeNull()
  })

  it('screens the watchlist by sending its tickers, and handles an empty watchlist', async () => {
    mock(() => ready(rows3()))
    const { unmount } = render(<HundredBaggers watchlist={['aapl', 'MSFT']} />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByRole('button', { name: 'My watchlist' }))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/hundred-baggers?symbols=aapl%2CMSFT'))
    unmount()
    mock(() => ready(rows3()))
    render(<HundredBaggers watchlist={[]} />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByRole('button', { name: 'My watchlist' }))
    expect(screen.getByText(/watchlist is empty/i)).toBeInTheDocument()
  })

  it('shows a partial-results banner when Yahoo refused some stocks', async () => {
    mock(() => ready(rows3(), { partial: { missing: 40, retryInSeconds: 200, note: '40 of 600 stocks couldn\'t be loaded (Yahoo is limiting requests).' } }))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    expect(screen.getByRole('note')).toHaveTextContent("40 of 600 stocks couldn't be loaded")
    expect(order()).toEqual(['AAA', 'BBB', 'CCC'])
  })

  it('switches universe and reports errors', async () => {
    mock(u => (u.includes('SP400') ? { __error: 'Wikipedia is down' } : ready(rows3())))
    render(<HundredBaggers />)
    await screen.findByTestId('bagger-table')
    fireEvent.click(screen.getByRole('button', { name: 'S&P MidCap 400' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wikipedia is down')
    expect(screen.queryByTestId('bagger-table')).toBeNull()
  })
})
