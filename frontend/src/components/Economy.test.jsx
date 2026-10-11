import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import EconomyIndicators from './EconomyIndicators'
import EconomyRegime, { momentum } from './EconomyRegime'
import IndicatorStudies from './IndicatorStudies'

afterEach(() => { vi.restoreAllMocks() })

const ind = (id, over = {}) => ({
  id, name: id.toUpperCase() + ' name', category: 'labor', unit: '%', freq: 'M', lead: 'coincident', horizon: 'short', hib: false,
  date: '2026-08-01', value: 4.3, previous: 4.2, change3m: 0.1, change1y: -0.2, percentile: 31, zscore10y: -0.4, historyStart: '1948-01-01',
  trend: 'rising', signal: 'neutral', reason: 'Little changed', stale: false, spark: [4, 4.1, 4.2, 4.3], ...over,
})
const catalog = () => ({
  asOf: '2026-08-01', overall: { supportive: 1, neutral: 1, cautionary: 1 }, missing: [],
  categories: [
    { id: 'labor', name: 'Labor', counts: { supportive: 1, neutral: 0, cautionary: 1 }, indicators: [ind('unrate', { signal: 'cautionary', reason: 'Rising, and lower has been better for stocks' }), ind('payrolls', { unit: 'K', value: 150, signal: 'supportive' })] },
    { id: 'rates', name: 'Rates', counts: { supportive: 0, neutral: 1, cautionary: 0 }, indicators: [ind('dgs10', { category: 'rates', lead: 'leading', name: '10-Year Treasury yield' })] },
  ],
})
const detail = () => ({
  meta: { id: 'unrate', fred: 'UNRATE', name: 'Unemployment rate', category: 'labor', unit: '%', transform: 'level', freq: 'M', hib: false, lead: 'lagging', horizon: 'long',
          what: 'Share of the labor force without a job.', why: 'Rises as recessions begin.', read: 'A 0.5-point rise in six months is a warning.', band: null, warnAbove: 6, warnBelow: null },
  summary: ind('unrate', { signal: 'cautionary', reason: 'Rising' }),
  points: [['2000-01-01', 4], ['2010-01-01', 9.8], ['2020-04-01', 14.7], ['2026-08-01', 4.3]],
  recessions: [{ start: '2008-01-01', end: '2009-06-01' }],
  stats: { allTime: { min: 2.5, median: 5.6, max: 14.7, minDate: '1953-05-01', maxDate: '2020-04-01' }, tenYear: null, observations: 900 }, related: [],
})

function mockFetch(routes) {
  global.fetch = vi.fn(async url => {
    const key = Object.keys(routes).find(k => String(url).startsWith(k))
    const r = key ? routes[key] : { __status: 404, detail: 'nope' }
    if (r.__status) return { ok: false, status: r.__status, json: async () => ({ detail: r.detail }) }
    return { ok: true, json: async () => (typeof r === 'function' ? r(url) : r) }
  })
}

describe('EconomyIndicators', () => {
  it('lists indicators by category with values, signal and overall counts', async () => {
    mockFetch({ '/api/economy/indicators': catalog() })
    render(<EconomyIndicators />)
    const labor = await screen.findByRole('region', { name: 'Labor' })
    expect(within(labor).getByText('UNRATE name')).toBeInTheDocument()
    expect(within(labor).getByText('Cautionary')).toBeInTheDocument()
    expect(within(labor).getByText('150K')).toBeInTheDocument()
    expect(screen.getByTestId('overall-counts')).toHaveTextContent('1Supportive')
    expect(screen.getByRole('region', { name: 'Rates' })).toBeInTheDocument()
  })

  it('filters by signal, category and search text, and says when nothing matches', async () => {
    mockFetch({ '/api/economy/indicators': catalog() })
    render(<EconomyIndicators />)
    await screen.findByRole('region', { name: 'Labor' })
    fireEvent.change(screen.getByLabelText('Signal'), { target: { value: 'supportive' } })
    expect(screen.getByText('PAYROLLS name')).toBeInTheDocument()
    expect(screen.queryByText('UNRATE name')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Rates' })).toBeNull()
    fireEvent.change(screen.getByLabelText('Signal'), { target: { value: 'all' } })
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'rates' } })
    expect(screen.queryByRole('region', { name: 'Labor' })).toBeNull()
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'all' } })
    fireEvent.change(screen.getByLabelText('Search indicators'), { target: { value: 'zzzz' } })
    expect(screen.getByText(/no indicators match/i)).toBeInTheDocument()
  })

  it('opens the detail panel with chart, explanation and stats; closes it again', async () => {
    mockFetch({ '/api/economy/indicators': catalog(), '/api/economy/indicator/unrate': detail() })
    render(<EconomyIndicators />)
    fireEvent.click(await screen.findByLabelText('UNRATE name details'))
    expect(await screen.findByText('Share of the labor force without a job.')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Unemployment rate history' })).toBeInTheDocument()
    expect(screen.getByText('Rises as recessions begin.')).toBeInTheDocument()
    expect(screen.getByText('31th')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Close detail'))
    expect(screen.queryByText('Share of the labor force without a job.')).toBeNull()
  })

  it('shows an error from the server', async () => {
    mockFetch({ '/api/economy/indicators': { __status: 502, detail: 'FRED is unreachable' } })
    render(<EconomyIndicators />)
    expect(await screen.findByRole('alert')).toHaveTextContent('FRED is unreachable')
  })
})

const history = Array.from({ length: 24 }, (_, i) => ({
  date: `${2024 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}-01`, growth: 0.1 + i * 0.01, inflation: 0.3 - i * 0.005,
  risk: 10 + i, phase: i < 12 ? 'mid' : 'late', quadrant: 'goldilocks',
}))
const regime = () => ({
  asOf: '2026-08-01',
  growth: { level: 0.17, momentum: 0.07, label: 'Growth above its historical norm and improving', components: [] },
  inflation: { level: 0.08, momentum: -0.09, label: 'Inflation near its historical norm and weakening', components: [] },
  quadrant: { id: 'goldilocks', name: 'Goldilocks', description: 'Growth is picking up while inflation is easing.', growthDirection: 'up', inflationDirection: 'down' },
  recession: {
    score: 26.4, band: 'Moderate', curve: { invertedNow: false, value: 1.05, lastInverted: '2025-08', monthsInvertedLast24: 6 },
    components: [
      { id: 'curve10_3m', name: '10Y-3M Treasury spread', unit: 'pts', value: 1.0, date: '2026-08-01', weight: 20, stress: 0, rule: 'Inverted = full stress', status: 'calm' },
      { id: 'payrolls', name: 'Payrolls', unit: 'K', value: 50, date: '2026-08-01', weight: 8, stress: 0.33, rule: 'No stress above 100K', status: 'watch' },
      { id: 'sahm', name: 'Sahm rule', unit: 'pts', value: 0.6, date: '2026-08-01', weight: 15, stress: 1, rule: 'Full stress at 0.50', status: 'high' },
    ],
  },
  phase: { id: 'mid', name: 'Mid-cycle expansion', description: 'Growth is above trend and still improving.' },
  trackRecord: [{ start: '2008-01', end: '2009-06', peak: 84, firstWarning: '2007-12', monthsFromStart: -1 }, { start: '2020-03', end: '2020-04', peak: 90, firstWarning: '2020-03', monthsFromStart: 0 }],
  keyIndicators: [ind('curve10_3m', { name: '10Y-3M spread', unit: 'pts', value: 1.05, signal: 'supportive' })],
  history, method: 'Rule-based and transparent.',
})

describe('EconomyRegime', () => {
  it('renders phase, quadrant, recession gauge, drivers and track record', async () => {
    mockFetch({ '/api/economy/regime': regime() })
    render(<EconomyRegime onNavigate={vi.fn()} />)
    expect(await screen.findByText('Mid-cycle expansion')).toBeInTheDocument()
    expect(screen.getAllByText('Goldilocks').length).toBeGreaterThan(0)
    expect(screen.getByRole('img', { name: 'Recession risk 26 of 100, Moderate' })).toBeInTheDocument()
    const drivers = screen.getByText('What is driving recession risk').closest('section')
    expect(within(drivers).getByText('Flashing')).toBeInTheDocument()
    expect(within(drivers).getByText('Watch')).toBeInTheDocument()
    expect(within(drivers).getByText('Calm')).toBeInTheDocument()
    expect(screen.getByText('1 mo early')).toBeInTheDocument()
    expect(screen.getByText('on time')).toBeInTheDocument()
    expect(screen.getByText(/last inverted 2025-08/)).toBeInTheDocument()
  })

  it('navigates from the key tiles and the follow-up buttons', async () => {
    mockFetch({ '/api/economy/regime': regime() })
    const onNavigate = vi.fn()
    render(<EconomyRegime onNavigate={onNavigate} />)
    fireEvent.click(await screen.findByText('10Y-3M spread'))
    expect(onNavigate).toHaveBeenCalledWith('econindicators')
    fireEvent.click(screen.getByText(/Indicator Studies →/))
    expect(onNavigate).toHaveBeenCalledWith('econstudies')
    fireEvent.click(screen.getByText(/Sector Cycle Fit →/))
    expect(onNavigate).toHaveBeenCalledWith('sectorcycle')
  })

  it('momentum is the change over the lag', () => {
    const m = momentum([{ date: 'a', x: 1 }, { date: 'b', x: 2 }, { date: 'c', x: 4 }, { date: 'd', x: 7 }], 'x', 2)
    expect(m).toEqual([{ date: 'c', v: 3 }, { date: 'd', v: 5 }])
  })

  it('shows the error', async () => {
    mockFetch({ '/api/economy/regime': { __status: 502, detail: 'no FRED' } })
    render(<EconomyRegime />)
    expect(await screen.findByRole('alert')).toHaveTextContent('no FRED')
  })
})

const study = (over = {}) => ({
  study: { id: 'curve-inverted', name: 'Yield curve inverted', condition: 'The 10-year yield is below the 3-month yield.', question: 'q', indicators: ['curve10_3m'], lagMonths: 0 },
  episodeCount: 5, monthsInState: 58, sampleStart: '1982-01', sampleEnd: '2026-08', currentlyActive: false, thin: false,
  headline: 'In the 12 months after yield curve inverted began, the S&P 500 averaged +6.6% versus +11.1% for any 12-month period.',
  horizons: [1, 3, 6, 12, 36].map(m => ({ months: m, episodes: { n: 5, mean: 0.066, median: 0.05, pctPositive: 0.8, best: 0.3, worst: -0.2 }, allMonths: null, baseline: { n: 400, mean: 0.111, median: 0.1, pctPositive: 0.8, best: 0.5, worst: -0.4 } })),
  episodes: [{ start: '2006-06', end: '2007-05', months: 12, entry: '2006-06', forward: { 1: 0.02, 3: 0.05, 6: 0.1, 12: 0.15, 36: null } }],
  distribution12m: { edges: [-60, -40, -30, -20, -10, 0, 10, 20, 30, 40, 60, 100], study: [0, 0, 0, 10, 10, 30, 30, 10, 10, 0, 0], baseline: [1, 2, 3, 5, 9, 15, 25, 20, 10, 6, 3] },
  sectors12m: [{ symbol: 'XLK', n: 2, avgExcess: 0.05, pctBeating: 1, thin: true }, { symbol: 'XLE', n: 5, avgExcess: -0.04, pctBeating: 0.4, thin: false }],
  notes: ['5 independent episodes with a full 12-month window.'], ...over,
})

describe('IndicatorStudies', () => {
  const routes = (extra = {}) => ({
    '/api/economy/studies/curve-inverted': study(), '/api/economy/studies/sahm': extra.sahm ?? study({ study: { id: 'sahm', name: 'Sahm Rule triggered', condition: 'c', question: 'q', indicators: [] }, thin: true }),
    '/api/economy/studies/never': { unavailable: true, study: { id: 'never', name: 'Never happened', condition: 'c', question: 'q', indicators: [] } },
    '/api/economy/studies': { studies: [{ id: 'curve-inverted', name: 'Yield curve inverted', question: 'How has the market done?', condition: 'c', indicators: [] }, { id: 'sahm', name: 'Sahm Rule triggered', question: 'q2', condition: 'c', indicators: [] }, { id: 'never', name: 'Never happened', question: 'q3', condition: 'c', indicators: [] }] },
  })

  it('loads the first study by default with headline, table, sector bars and notes', async () => {
    mockFetch(routes())
    render(<IndicatorStudies />)
    expect(await screen.findByTestId('study-headline')).toHaveTextContent('averaged +6.6%')
    expect(screen.getByText('12 months')).toBeInTheDocument()
    expect(screen.getByText('Technology')).toBeInTheDocument()
    expect(screen.getByText(/5 episodes \(58 months in the state\)/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Distribution of 12-month/ })).toBeInTheDocument()
    expect(screen.getByText('5 independent episodes with a full 12-month window.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Yield curve inverted/ })).toHaveAttribute('aria-current', 'true')
  })

  it('switches study, flags thin samples, and handles a never-occurring condition', async () => {
    mockFetch(routes())
    render(<IndicatorStudies />)
    await screen.findByTestId('study-headline')
    fireEvent.click(screen.getByRole('button', { name: /Sahm Rule triggered/ }))
    expect(await screen.findByText(/Very few episodes/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Never happened/ }))
    expect(await screen.findByText(/never occurred in the available history/)).toBeInTheDocument()
  })

  it('shows the error when a study fails', async () => {
    mockFetch({ ...routes(), '/api/economy/studies/curve-inverted': { __status: 502, detail: 'prices unavailable' } })
    render(<IndicatorStudies />)
    expect(await screen.findByRole('alert')).toHaveTextContent('prices unavailable')
    await waitFor(() => expect(screen.queryByText('Running the study…')).toBeNull())
  })
})
