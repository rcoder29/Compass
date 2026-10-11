import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import SectorScoreboard, { cellValue } from './SectorScoreboard'
import SectorRotation from './SectorRotation'
import SectorScreener, { weightsParam } from './SectorScreener'
import SectorCycleFit from './SectorCycleFit'
import SectorBacktest from './SectorBacktest'

afterEach(() => { vi.restoreAllMocks() })

function mockFetch(routes) {
  global.fetch = vi.fn(async url => {
    const key = Object.keys(routes).sort((a, b) => b.length - a.length).find(k => String(url).startsWith(k))
    const r = key ? routes[key] : { __status: 404, detail: 'nope' }
    if (r.__status) return { ok: false, status: r.__status, json: async () => ({ detail: r.detail }) }
    return { ok: true, json: async () => (typeof r === 'function' ? r(String(url)) : r) }
  })
}

const PERIODS = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y', '10Y', 'LTD']
const rets = (ytd, over = {}) => Object.fromEntries(PERIODS.map(p => [p, { total: p === 'YTD' ? ytd : 0.01, annualised: ['3Y', '5Y', '10Y', 'LTD'].includes(p) ? 0.1 : null, ...(over[p] || {}) }]))
const sector = (symbol, name, ytd, over = {}) => ({
  symbol, name, inception: '1998-12-22', price: 100, returns: rets(ytd, over.returns),
  excess: Object.fromEntries(PERIODS.map(p => [p, p === 'YTD' ? ytd - 0.15 : 0.0])),
  risk: { windowYears: 3, volatility: 0.2, maxDrawdown: -0.25, returnPerRisk: ytd * 5, beta: 1.1, upCapture: 1.2, downCapture: 0.9, short: false },
  trend: { above50: true, above200: true, ma50Above200: true, pctFrom200: 0.1 }, rsChange: { '1M': 0.01, '3M': ytd / 10, '6M': 0.02, '1Y': 0.03 },
  calendar: { 2025: ytd / 2, 2026: ytd }, ...over.extra,
})
const scoreboard = () => ({
  asOf: '2026-10-09', periods: PERIODS,
  sectors: [sector('XLK', 'Technology', 0.38), sector('XLE', 'Energy', 0.48), sector('XLU', 'Utilities', -0.01), sector('XLC', 'Communication Services', -0.05, { returns: { '10Y': { total: null, annualised: null } } })],
  benchmark: { symbol: 'SPY', name: 'S&P 500 (SPY)', returns: rets(0.15), risk: { volatility: 0.12, maxDrawdown: -0.18, returnPerRisk: 1.9, beta: 1, upCapture: 1, downCapture: 1 }, calendar: { 2025: 0.17, 2026: 0.15 } },
  equalWeight: { symbol: 'RSP', name: 'S&P 500 Equal Weight (RSP)', returns: rets(0.08), calendar: { 2025: 0.1, 2026: 0.08 } },
  notes: ['Returns are total returns.'],
})
const names = () => within(screen.getByTestId('scoreboard-table')).getAllByRole('row').slice(1).map(r => r.cells[0].textContent)

describe('SectorScoreboard', () => {
  it('sorts by YTD descending by default and lists the benchmarks beneath', async () => {
    mockFetch({ '/api/sectors/scoreboard': scoreboard() })
    render(<SectorScoreboard />)
    await screen.findByTestId('scoreboard-table')
    expect(names().map(n => n.split(' ')[0])).toEqual(['Energy', 'Technology', 'Utilities', 'Communication', 'S&P', 'S&P'])
    expect(screen.getByText('+48.0%')).toBeInTheDocument()
  })

  it('re-sorts when a header is clicked, with missing values always last', async () => {
    mockFetch({ '/api/sectors/scoreboard': scoreboard() })
    render(<SectorScoreboard />)
    await screen.findByTestId('scoreboard-table')
    const board = within(screen.getByTestId('scoreboard-table'))
    fireEvent.click(board.getByRole('columnheader', { name: /^10Y/ }))          // XLC has no 10Y
    const order = names().slice(0, 4).map(n => n.split(' ')[0])
    expect(order[3]).toBe('Communication')
    fireEvent.click(board.getByRole('columnheader', { name: /^Sector/ }))
    expect(names()[0]).toMatch(/^Communication/)
  })

  it('switches to the risk and calendar-year views', async () => {
    mockFetch({ '/api/sectors/scoreboard': scoreboard() })
    render(<SectorScoreboard />)
    await screen.findByTestId('scoreboard-table')
    fireEvent.click(screen.getByRole('button', { name: 'Risk' }))
    expect(screen.getByRole('columnheader', { name: /Max drawdown/ })).toBeInTheDocument()
    expect(screen.getAllByText('-25.0%').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Calendar years' }))
    expect(screen.getByRole('columnheader', { name: /2026 YTD/ })).toBeInTheDocument()
  })

  it('shows excess returns versus SPY and annualises on request', async () => {
    mockFetch({ '/api/sectors/scoreboard': scoreboard() })
    render(<SectorScoreboard />)
    await screen.findByTestId('scoreboard-table')
    fireEvent.click(screen.getByRole('button', { name: 'vs SPY' }))
    expect(screen.getByLabelText(/Annualise/)).toBeDisabled()
    expect(screen.getByText('+23.0%')).toBeInTheDocument()                       // XLK 38% - 15%
    fireEvent.click(screen.getByRole('button', { name: 'Total return' }))
    fireEvent.click(screen.getByLabelText(/Annualise/))
    expect(screen.getByRole('columnheader', { name: /^3Y\/yr/ })).toBeInTheDocument()
  })

  it('opens the holdings of a sector', async () => {
    mockFetch({ '/api/sectors/scoreboard': scoreboard() })
    const onOpen = vi.fn()
    render(<SectorScoreboard onOpenHoldings={onOpen} />)
    await screen.findByTestId('scoreboard-table')
    fireEvent.click(screen.getAllByText('Holdings →')[0])
    expect(onOpen).toHaveBeenCalledWith('XLE')
  })

  it('cellValue picks total, annualised or excess', () => {
    const r = sector('XLK', 'Technology', 0.38)
    expect(cellValue(r, 'YTD', 'total', false)).toBe(0.38)
    expect(cellValue(r, '3Y', 'total', true)).toBe(0.1)
    expect(cellValue(r, '3Y', 'total', false)).toBe(0.01)
    expect(cellValue(r, 'YTD', 'excess', false)).toBeCloseTo(0.23)
    expect(cellValue({ returns: {} }, 'YTD', 'total', false)).toBeNull()
  })

  it('shows the error', async () => {
    mockFetch({ '/api/sectors/scoreboard': { __status: 502, detail: 'no prices' } })
    render(<SectorScoreboard />)
    expect(await screen.findByRole('alert')).toHaveTextContent('no prices')
  })
})

const trail = (r, m) => Array.from({ length: 8 }, (_, i) => ({ date: `2026-0${(i % 9) + 1}-05`, ratio: r - (7 - i) * 0.3, momentum: m - (7 - i) * 0.1 }))
const rotation = () => ({
  asOf: '2026-10-09', note: 'Weekly. RS-Ratio compares a sector.',
  sectors: [
    { symbol: 'XLK', name: 'Technology', trail: trail(110, 102), ratio: 110, momentum: 102, quadrant: 'leading', quadrantName: 'Leading', quadrantText: '' },
    { symbol: 'XLU', name: 'Utilities', trail: trail(86, 96), ratio: 86, momentum: 96, quadrant: 'lagging', quadrantName: 'Lagging', quadrantText: '' },
    { symbol: 'XLC', name: 'Communication Services', trail: trail(91, 101), ratio: 91, momentum: 101, quadrant: 'improving', quadrantName: 'Improving', quadrantText: '' },
  ],
})

describe('SectorRotation', () => {
  it('plots every sector and groups them by quadrant', async () => {
    mockFetch({ '/api/sectors/rotation': rotation() })
    const { container } = render(<SectorRotation />)
    const map = await screen.findByRole('img', { name: /Relative rotation graph/ })
    expect(within(map).getByText('XLK')).toBeInTheDocument()
    expect(container.querySelectorAll('polyline').length).toBe(3)
    const leading = screen.getByText('Leading', { selector: 'span' }).closest('section')
    expect(within(leading).getByText(/Technology/)).toBeInTheDocument()
    expect(within(screen.getByText('Weakening', { selector: 'span' }).closest('section')).getByText('None right now.')).toBeInTheDocument()
  })

  it('hides trails when asked', async () => {
    mockFetch({ '/api/sectors/rotation': rotation() })
    const { container } = render(<SectorRotation />)
    await screen.findByRole('img', { name: /Relative rotation graph/ })
    fireEvent.click(screen.getByRole('button', { name: 'No trail' }))
    expect(container.querySelectorAll('polyline').length).toBe(0)
  })
})

const screener = (horizon = 'intermediate', withCycle = true) => ({
  asOf: '2026-10-09', horizon, horizonInfo: { name: horizon[0].toUpperCase() + horizon.slice(1), span: '3-12 months', blurb: 'Trend persistence plus where we are in the cycle.' },
  weights: withCycle ? { momentum: 30, trend: 15, cycle: 25 } : { momentum: 30, trend: 15 }, defaultWeights: { momentum: 30, trend: 15, cycle: 25 },
  factorNames: { momentum: 'Price momentum', trend: 'Trend', cycle: 'Cycle fit' }, cyclePhase: withCycle ? 'Mid-cycle expansion' : null,
  sectors: [
    { symbol: 'XLK', name: 'Technology', rank: 1, score: 88.2, tier: 'Overweight', why: 'Strongest on price momentum (+12.8% vs SPY)', missing: [],
      factors: { momentum: { rank: 100, raw: 0.128, weight: 50, contribution: 50 }, trend: { rank: 80, raw: 1.2, weight: 25, contribution: 20 }, cycle: { rank: 70, raw: 0.01, weight: 25, contribution: 18.2 } } },
    { symbol: 'XLU', name: 'Utilities', rank: 2, score: 11.5, tier: 'Underweight', why: 'Nothing stands out; best factor is trend (+0.1)', missing: ['cycle'],
      factors: { momentum: { rank: 0, raw: -0.13, weight: 67, contribution: 0 }, trend: { rank: 30, raw: 0.1, weight: 33, contribution: 11.5 } } },
  ],
  notes: ['Valuation is not included.'],
})

describe('SectorScreener', () => {
  it('ranks sectors with tier, score and the reason', async () => {
    mockFetch({ '/api/sectors/screener': screener() })
    render(<SectorScreener />)
    const table = await screen.findByTestId('screener-table')
    expect(within(table).getByText('Technology')).toBeInTheDocument()
    expect(within(table).getByText('88')).toBeInTheDocument()
    expect(within(table).getByText('Overweight')).toBeInTheDocument()
    expect(within(table).getByText('Strongest on price momentum (+12.8% vs SPY)')).toBeInTheDocument()
    expect(screen.getByText(/Current cycle phase: Mid-cycle expansion/)).toBeInTheDocument()
  })

  it('expands a sector to show each factor and re-balanced weights', async () => {
    mockFetch({ '/api/sectors/screener': screener() })
    render(<SectorScreener />)
    fireEvent.click(await screen.findByRole('button', { name: /Utilities/ }))
    expect(screen.getByText(/Not enough history for: Cycle fit/)).toBeInTheDocument()
    expect(screen.getByText('67%')).toBeInTheDocument()
  })

  it('requests the chosen horizon', async () => {
    mockFetch({ '/api/sectors/screener': url => screener(new URL(url, 'http://x').searchParams.get('horizon')) })
    render(<SectorScreener />)
    await screen.findByTestId('screener-table')
    fireEvent.click(screen.getByRole('button', { name: /Strategic/ }))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('horizon=strategic')))
    expect(screen.getByRole('button', { name: /Strategic/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('refetches with custom weights when a slider moves and Reset restores the defaults', async () => {
    mockFetch({ '/api/sectors/screener': screener() })
    render(<SectorScreener />)
    await screen.findByTestId('screener-table')
    fireEvent.change(screen.getByLabelText('Price momentum weight'), { target: { value: '60' } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/weights=.*momentum.*60/)))
    fireEvent.click(await screen.findByText('Reset'))
    expect(screen.queryByText('Reset')).toBeNull()
  })

  it('disables the cycle slider when economic data is unavailable', async () => {
    mockFetch({ '/api/sectors/screener': screener('intermediate', false) })
    render(<SectorScreener />)
    await screen.findByTestId('screener-table')
    expect(screen.getByLabelText('Cycle fit weight')).toBeDisabled()
    expect(screen.getByText(/Needs economic data/)).toBeInTheDocument()
  })

  it('weightsParam is empty unless the weights differ from the defaults', () => {
    expect(weightsParam({ a: 30, b: 20 }, { a: 30, b: 20 })).toBe('')
    expect(weightsParam({ a: 30, b: 25 }, { a: 30, b: 20 })).toMatch(/^&weights=/)
    expect(weightsParam({ a: 30, b: 0 }, { a: 30 })).toBe('')
  })
})

const cycle = () => ({
  group: 'phase', groups: ['early', 'mid', 'late', 'slowdown', 'recession'], samples: { early: 134, mid: 170, late: 105, slowdown: 161, recession: 82 },
  current: { phase: 'mid', quadrant: 'goldilocks', asOf: '2026-08-01' }, note: 'Sector history starts in 1999, so each cell rests on few distinct episodes.',
  sectors: [
    { symbol: 'XLK', name: 'Technology', cells: { early: { avgMonthlyExcess: -0.004, months: 84, episodes: 26, hitRate: 0.45 }, mid: { avgMonthlyExcess: 0.01, months: 74, episodes: 21, hitRate: 0.6 } } },
    { symbol: 'XLRE', name: 'Real Estate', cells: { recession: { avgMonthlyExcess: -0.0191, months: 6, episodes: 2, hitRate: 0.17 } } },
  ],
})

describe('SectorCycleFit', () => {
  it('shows the sector × phase matrix, marks the current phase and flags thin cells', async () => {
    mockFetch({ '/api/sectors/cycle-fit': cycle() })
    render(<SectorCycleFit />)
    const table = await screen.findByTestId('cyclefit-table')
    expect(within(table).getByText('Technology')).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: /Mid-cycle ●/ })).toBeInTheDocument()
    expect(within(table).getByText('+1.00%')).toBeInTheDocument()
    expect(within(table).getByText('(6m)')).toBeInTheDocument()
    expect(within(table).getAllByText('—').length).toBeGreaterThan(0)
    expect(screen.getByText(/Right now:/)).toHaveTextContent('Mid-cycle')
  })

  it('switches grouping to the growth/inflation quadrants', async () => {
    mockFetch({ '/api/sectors/cycle-fit?group=quadrant': { ...cycle(), group: 'quadrant', groups: ['goldilocks', 'stagflation'], samples: { goldilocks: 100, stagflation: 50 } }, '/api/sectors/cycle-fit': cycle() })
    render(<SectorCycleFit />)
    await screen.findByTestId('cyclefit-table')
    fireEvent.click(screen.getByRole('button', { name: 'By growth / inflation' }))
    expect(await screen.findByRole('columnheader', { name: /Goldilocks ●/ })).toBeInTheDocument()
  })

  it('shows an error when economic data is down', async () => {
    mockFetch({ '/api/sectors/cycle-fit': { __status: 502, detail: 'Could not build cycle-fit' } })
    render(<SectorCycleFit />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not build')
  })
})

const stats = (cagr, dd) => ({ cagr, volatility: 0.13, sharpe: 0.7, maxDrawdown: dd, totalReturn: 9.2, bestMonth: 0.1, worstMonth: -0.12, positiveMonths: 0.62 })
const backtest = () => ({
  params: { topN: 3, costBps: 10, defensiveSwitch: true, start: '2000-01-01' }, start: '2000-02-29', end: '2026-09-30', months: 320,
  strategy: stats(0.0914, -0.3515), spy: stats(0.0847, -0.5078), equalWeight: stats(0.0874, -0.4913), annualTurnover: 3.02, riskOffMonths: 81, monthsBeatingSpy: 0.512,
  curve: [{ date: '2000-02-29', strategy: 1, spy: 1, equalWeight: 1, holdings: ['XLK'] }, { date: '2010-02-28', strategy: 2, spy: 1.5, equalWeight: 1.7, holdings: ['XLK'] }, { date: '2026-09-30', strategy: 9, spy: 7, equalWeight: 7.5, holdings: ['XLK', 'XLF', 'XLE'] }],
  latestHoldings: ['XLK', 'XLF', 'XLE'], notes: ['Hypothetical, rule-based.'],
})

describe('SectorBacktest', () => {
  it('shows results for the strategy against SPY and equal weight', async () => {
    mockFetch({ '/api/sectors/backtest': backtest() })
    render(<SectorBacktest />)
    expect(await screen.findByRole('img', { name: 'Growth of one dollar' })).toBeInTheDocument()
    expect(screen.getByText('+9.1%')).toBeInTheDocument()
    expect(screen.getByText('+8.5%')).toBeInTheDocument()
    expect(screen.getByText(/Beat SPY in 51% of months/)).toBeInTheDocument()
    expect(screen.getByText(/annual turnover 3.0×/)).toBeInTheDocument()
    expect(screen.getByText('XLE')).toBeInTheDocument()
  })

  it('reruns with the chosen settings', async () => {
    mockFetch({ '/api/sectors/backtest': backtest() })
    render(<SectorBacktest />)
    await screen.findByRole('img', { name: 'Growth of one dollar' })
    fireEvent.change(screen.getByLabelText('Sectors held'), { target: { value: '2' } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/sectors/backtest?top_n=2&cost_bps=10&defensive=true'))
    fireEvent.change(screen.getByLabelText('Trading cost'), { target: { value: '50' } })
    fireEvent.click(screen.getByLabelText(/Defensive switch/))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/sectors/backtest?top_n=2&cost_bps=50&defensive=false'))
  })

  it('shows the error', async () => {
    mockFetch({ '/api/sectors/backtest': { __status: 502, detail: 'No price history' } })
    render(<SectorBacktest />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No price history')
  })
})
