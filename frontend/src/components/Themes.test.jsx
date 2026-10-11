import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor, act } from '@testing-library/react'
import ThemePage from './ThemePage'
import ThemesOverview from './ThemesOverview'

vi.mock('./ChartModal', () => ({ default: ({ symbol, onClose }) => <div data-testid="chart-modal">chart {symbol}<button onClick={onClose}>close chart</button></div> }))
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

const RET = (over = {}) => ({ '1D': 0.01, '1W': 0.02, '1M': 0.05, '3M': 0.1, '6M': 0.2, YTD: 0.3, '1Y': 0.5, '3Y': 2, '5Y': 4, ...over })
const FACTORS = { exposure: 20, momentum: 20, analysts: 20, growth: 20, strength: 10, valuation: 10 }
const NAMES = { exposure: 'Theme exposure', momentum: 'Momentum vs SPY', analysts: 'Analyst upside', growth: 'Growth', strength: 'Financial strength', valuation: 'Valuation vs growth' }
const setup = (score, label = 'Stronger setup', over = {}) => ({
  score, rawScore: score, riskMultiplier: 1, risk: 'Moderate', label, capReason: null,
  factors: Object.fromEntries(Object.entries(FACTORS).map(([k, w]) => [k, { score: 80, weight: w, points: w * 0.8, missing: false, note: `${k} note` }])), ...over,
})
const member = (symbol, over = {}) => ({
  symbol, name: `${symbol} Inc`, layer: 'silicon', role: 'core', exposure: 3, why: `${symbol} is a reason.`, available: true, price: 50, marketCap: 200e9, size: 'Large cap', risk: 'Lower',
  returns: RET(), annualised: {}, excess: {}, upside: { mean: 0.25, high: 0.6, low: -0.1, count: 20, rating: 'Buy' }, growth: 0.3, revenueGrowth: 0.3, forwardPE: 30,
  operatingMargin: 0.2, profitable: true, off52wHigh: -0.1, setup: setup(80), bagger: { score: 72, tier: 'Strong fit' }, flags: [], ...over,
})
const members = () => [
  member('AAA'),
  member('BBB', { role: 'enabler', layer: 'foundry', setup: setup(60, 'Mixed'), returns: RET({ '1M': -0.05, '3M': -0.2 }), marketCap: 20e9, risk: 'Moderate', upside: null, growth: 0.1 }),
  member('CCC', { role: 'emerging', layer: 'silicon', setup: setup(55, 'Mixed', { riskMultiplier: 0.85, rawScore: 65, risk: 'Very high', capReason: 'Capped at Mixed: very high risk (small, unprofitable or cash-burning)' }),
                  marketCap: 1e9, risk: 'Very high', flags: ['Burning cash'], bagger: null }),
  member('GONE', { available: false, returns: {}, setup: setup(30, 'Weaker setup') }),
]
const theme = () => ({
  id: 'ai', name: 'Artificial Intelligence', short: 'AI', color: '#a78bfa', tagline: 'Models and the chips under them.', thesis: 'AI turns computing into something that does work.',
  whyNow: 'Capital budgets are committed.', watch: 'Most value so far went to infrastructure.',
  layers: [{ id: 'silicon', name: 'Chips & design', blurb: 'GPUs and memory' }, { id: 'foundry', name: 'Manufacturing', blurb: 'Fabs' }, { id: 'apps', name: 'Applications', blurb: 'Software' }],
  shortTerm: { catalysts: ['Capex updates'], risks: ['Spending guided down'] }, longTerm: { drivers: ['Falling compute cost'], risks: ['Overcapacity'] },
  members: members(), roleCounts: { core: 1, enabler: 1, adjacent: 0, emerging: 1 },
  basket: Object.fromEntries(['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y'].map(p => [p, { mean: 0.1, median: 0.1, n: 3, positive: 0.7, ...(p === '3Y' ? { annualised: 0.31 } : {}), ...(p === '5Y' ? { annualised: 0.4 } : {}) }])),
  benchmark: RET({ '1Y': 0.17 }), series: { points: [['2025-10-10', 100, 100], ['2026-04-10', 120, 108], ['2026-10-09', 142, 117]], maxDrawdown: -0.29, volatility: 0.46, benchMaxDrawdown: -0.1, members: 3, start: '2025-10-10' },
  outlook: { analystUpsideMedian: 0.18, analystUpsideCapWeighted: 0.22, analystNames: 29, buyShare: 0.93, growthMedian: 0.25, forwardPEMedian: 32, profitableShare: 0.7, record: { annualised3Y: 0.31, annualised5Y: 0.4 } },
  scenarios: { start: 10000, years: [1, 3, 5, 10], rows: [{ rate: 0.08, label: 'Market-like', values: { 1: 10800, 3: 12597, 5: 14693, 10: 21589 } }, { rate: 0.25, label: 'Exceptional', values: { 1: 12500, 3: 19531, 5: 30518, 10: 93132 } }] },
  top: ['AAA'], leaders3M: ['AAA'], laggards3M: ['BBB'], etfs: [{ symbol: 'SMH', name: 'VanEck Semiconductor ETF', returns: RET({ '3M': 0.15 }) }, { symbol: 'XXX', name: 'No data ETF' }],
  unavailable: ['GONE'], factorNames: NAMES, weights: FACTORS,
})
const detail = (over = {}) => ({ status: 'ready', asOf: '2026-10-09', partial: null, editorialDate: 'October 2026', periods: [], others: [{ id: 'robotics', name: 'Robotics & Automation' }, { id: 'space', name: 'Space Exploration' }], theme: theme(), ...over })

function mock(handler) {
  global.fetch = vi.fn(async url => {
    const r = await handler(String(url))
    return r?.__error ? { ok: false, status: 502, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r }
  })
}
const names = () => screen.getAllByTestId('member-row').map(r => r.getAttribute('aria-label').replace(' details', ''))

describe('ThemePage', () => {
  it('shows thesis, basket performance, outlook, value chain and the company table', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    expect(await screen.findByText('Artificial Intelligence')).toBeInTheDocument()
    expect(screen.getByText('AI turns computing into something that does work.')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /basket versus SPY/ })).toBeInTheDocument()
    expect(screen.getByText('Next 3-12 months')).toBeInTheDocument()
    expect(screen.getByText('Capex updates')).toBeInTheDocument()
    expect(screen.getByText('Overcapacity')).toBeInTheDocument()
    expect(screen.getByText(/\+22%/)).toBeInTheDocument()                                  // cap-weighted upside
    expect(screen.getByText(/93%/)).toBeInTheDocument()
    expect(screen.getByText('Chips & design')).toBeInTheDocument()
    expect(names()).toEqual(['AAA', 'BBB', 'CCC'])                                          // best setup first; unavailable excluded
    expect(screen.getByText(/No data from Yahoo for: GONE/)).toBeInTheDocument()
  })

  it('shows compounding scenarios beside the basket record and drawdown', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByText('What compounding would mean')
    expect(screen.getByText('$93,132')).toBeInTheDocument()
    expect(screen.getByText('$12,597')).toBeInTheDocument()
    expect(screen.getByText(/arithmetic, not a forecast/)).toBeInTheDocument()
    expect(screen.getByText(/31% a year over 3 years/)).toBeInTheDocument()
    expect(screen.getByText(/worst peak-to-trough fall of/)).toHaveTextContent('29%')
  })

  it('filters by role and re-sorts', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByTestId('member-table')
    fireEvent.click(screen.getByRole('tab', { name: /Picks & shovels/ }))
    expect(names()).toEqual(['BBB'])
    fireEvent.click(screen.getByRole('tab', { name: /Emerging & speculative/ }))
    expect(names()).toEqual(['CCC'])
    expect(screen.queryByRole('tab', { name: /Other beneficiaries/ })).toBeNull()          // groups with no companies get no tab
    fireEvent.click(screen.getByRole('tab', { name: 'All' }))
    fireEvent.click(screen.getByRole('columnheader', { name: /^Mkt cap/ }))
    expect(names()).toEqual(['AAA', 'BBB', 'CCC'])                                          // descending
    fireEvent.click(screen.getByRole('columnheader', { name: /^Mkt cap/ }))
    expect(names()).toEqual(['CCC', 'BBB', 'AAA'])
    fireEvent.click(screen.getByRole('columnheader', { name: /^3M/ }))                      // BBB is down, AAA/CCC up
    expect(names()[2]).toBe('BBB')
    fireEvent.click(screen.getByRole('columnheader', { name: /^Analyst upside/ }))          // BBB has none: always last
    expect(names()[2]).toBe('BBB')
    fireEvent.click(screen.getByRole('columnheader', { name: /^Analyst upside/ }))
    expect(names()[2]).toBe('BBB')
  })

  it('expands a row to the score breakdown, risk adjustment, analyst range and cautions; opens a chart', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByTestId('member-table')
    fireEvent.click(screen.getByLabelText('CCC details'))
    const d = within(screen.getByTestId('member-detail'))
    expect(d.getByText(/Risk adjustment ×0.85 for very high risk/)).toBeInTheDocument()
    expect(d.getByText(/Capped at Mixed: very high risk/)).toBeInTheDocument()
    expect(d.getByText('Burning cash')).toBeInTheDocument()
    expect(d.getByText('growth note')).toBeInTheDocument()
    fireEvent.click(d.getByText('Open chart'))
    expect(screen.getByTestId('chart-modal')).toHaveTextContent('chart CCC')
    fireEvent.click(screen.getByText('close chart'))
    fireEvent.click(screen.getByLabelText('AAA details'))
    const a = within(screen.getAllByTestId('member-detail').at(-1))
    expect(a.getByText(/20 analysts/)).toBeInTheDocument()
    expect(a.getByText('72')).toBeInTheDocument()                                          // 100-bagger traits
  })

  it('jumps to a company from the value chain and the candidate cards', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByTestId('member-table')
    fireEvent.click(screen.getByRole('tab', { name: /Emerging/ }))
    fireEvent.click(screen.getByTitle(/AAA Inc: AAA is a reason/))                         // value-chain chip
    expect(names()).toEqual(['AAA', 'BBB', 'CCC'])                                          // tab reset to All
    expect(screen.getByTestId('member-detail')).toBeInTheDocument()
    expect(screen.getByText('Candidates to research')).toBeInTheDocument()
  })

  it('lists theme ETFs and handles one with no data', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByText('Diversified ways in: theme ETFs')
    expect(screen.getByText('SMH')).toBeInTheDocument()
    expect(screen.getByText('No data')).toBeInTheDocument()
  })

  it('navigates to other themes and the overview', async () => {
    mock(() => detail())
    const onNavigate = vi.fn()
    render(<ThemePage themeId="ai" onNavigate={onNavigate} />)
    fireEvent.click(await screen.findByRole('button', { name: /Robotics & Automation →/ }))
    expect(onNavigate).toHaveBeenCalledWith('themerobotics')
    fireEvent.click(screen.getByRole('button', { name: /All themes →/ }))
    expect(onNavigate).toHaveBeenCalledWith('themesoverview')
  })

  it('shows scan progress, then the page once the scan finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mock(() => (++calls < 2 ? { status: 'running', progress: { done: 20, total: 79 }, error: null } : detail()))
    render(<ThemePage themeId="ai" />)
    expect(await screen.findByRole('status')).toHaveTextContent('20 / 79')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByText('What compounding would mean')).toBeInTheDocument()
  })

  it('shows a partial-data note, and errors', async () => {
    mock(() => detail({ partial: { missing: 30, retryInSeconds: 100, note: 'Fundamentals for 30 of 79 companies couldn\'t be loaded.' } }))
    const { unmount } = render(<ThemePage themeId="ai" />)
    expect(await screen.findByRole('note')).toHaveTextContent('30 of 79')
    unmount()
    mock(() => ({ __error: 'Couldn\'t build the themes' }))
    render(<ThemePage themeId="ai" />)
    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't build")
  })

  it('requests the theme it was given', async () => {
    mock(() => detail())
    render(<ThemePage themeId="quantum" />)
    await screen.findByText('Artificial Intelligence')
    expect(global.fetch).toHaveBeenCalledWith('/api/themes/quantum')
  })
})

const summary = (id, name, over = {}) => ({
  id, name, short: name.slice(0, 3), color: '#fff', tagline: `${name} tagline`, members: 20, series: { points: [['2025-10-10', 100, 100], ['2026-10-09', 130, 117]] },
  returns: RET(over.returns), benchmark: RET(), outlook: { analystUpsideMedian: 0.2, growthMedian: 0.25, profitableShare: 0.6, ...over.outlook },
  top: [{ symbol: 'NVDA', name: 'NVIDIA', score: 80 }, { symbol: 'MU', name: 'Micron', score: 75 }], leaders3M: ['AAA', 'BBB'], laggards3M: ['ZZZ', 'YYY'],
  roleCounts: { core: 6, enabler: 8, adjacent: 4, emerging: 7 },
})
const overview = () => ({
  status: 'ready', asOf: '2026-10-09', benchmark: RET({ '1Y': 0.17, '3M': 0.05 }), partial: null, editorialDate: 'October 2026', periods: [],
  themes: [summary('ai', 'Artificial Intelligence', { returns: { '1Y': 0.42, '3M': 0.1 } }), summary('robotics', 'Robotics & Automation', { returns: { '1Y': 0.07, '3M': -0.02 } }),
           summary('quantum', 'Quantum Computing', { returns: { '1Y': 0.16, '3M': -0.04 } }), summary('space', 'Space Exploration', { returns: { '1Y': 0.06, '3M': -0.12 } })],
})

const impact = () => ({
  intro: 'A way of thinking about the scenario.',
  sections: [
    { id: 'jobs', label: 'Jobs', type: 'lists', summary: 'Tasks change before jobs vanish.', columns: [
      { title: 'Most exposed', tone: 'bad', items: ['Routine screen work', 'Outsourced hours'] }, { title: 'More resilient', tone: 'good', items: ['Skilled trades', 'Trust roles'] },
      { title: 'What could be created', tone: 'new', items: ['AI auditors', 'New services'] }] },
    { id: 'markets', label: 'Markets', type: 'cards', items: [{ title: 'Scarce inputs reprice', text: 'Compute and power stay valuable.' }, { title: 'Demand is the loop', text: 'Output needs buyers with income.' }] },
    { id: 'winners', label: 'Who is best set up', type: 'ranked', items: [{ who: 'Owners of the scarce inputs', why: 'Compute, power, materials.' }, { who: 'Distribution and trust', why: 'Pricing power stays.' }] },
    { id: 'scenarios', label: 'Scenarios', type: 'scenarios', items: [
      { name: 'Broad abundance', text: 'Productivity lifts everyone.', favours: 'Infrastructure', hurts: 'Headcount services' }, { name: 'Concentrated gains', text: 'Owners win.', favours: 'Platforms', hurts: 'Workers' },
      { name: 'Slower than hoped', text: 'Plateau.', favours: 'Incumbents', hurts: 'Speculative names', positioning: 'Stay liquid.' }] },
  ],
})
const abundance = () => {
  const t = theme()
  t.id = 'abundance'; t.name = 'AI Abundance'; t.short = 'Abundance'; t.impact = impact()
  t.layers = [...t.layers, { id: 'disrupted', name: 'At risk of disruption', blurb: 'Sell routine human hours' }]
  t.members = [...members().filter(m => m.available), member('RISKY', { role: 'atrisk', layer: 'disrupted', setup: setup(50, 'Disruption risk') })]
  t.roleCounts = { core: 1, enabler: 1, adjacent: 0, emerging: 1, atrisk: 1 }
  return t
}

describe('AI Abundance theme', () => {
  it('shows the jobs, markets, winners and scenarios tabs', async () => {
    mock(() => detail({ theme: abundance() }))
    render(<ThemePage themeId="abundance" />)
    await screen.findByText('What it could mean')
    expect(screen.getByText('Tasks change before jobs vanish.')).toBeInTheDocument()
    expect(screen.getByText('Routine screen work')).toBeInTheDocument()
    expect(screen.getByText('Skilled trades')).toBeInTheDocument()
    expect(screen.getByText('AI auditors')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Markets' }))
    expect(screen.getByText('Scarce inputs reprice')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Who is best set up' }))
    expect(screen.getByText('Owners of the scarce inputs')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Scenarios' }))
    expect(screen.getByText('Broad abundance')).toBeInTheDocument()
    expect(screen.getByText('Headcount services')).toBeInTheDocument()
  })

  it('offers an at-risk tab, labels those names, and keeps them out of the candidates', async () => {
    mock(() => detail({ theme: abundance() }))
    render(<ThemePage themeId="abundance" />)
    await screen.findByTestId('member-table')
    fireEvent.click(screen.getByRole('tab', { name: /At risk of disruption/ }))
    expect(names()).toEqual(['RISKY'])
    expect(within(screen.getByTestId('member-table')).getByText('Disruption risk')).toBeInTheDocument()
    const candidates = screen.getByText('Candidates to research').closest('section')
    expect(within(candidates).queryByText(/RISKY/)).toBeNull()
    expect(screen.getByText(/red outline: at risk of disruption/)).toBeInTheDocument()
  })

  it('other themes have neither the impact section nor an at-risk tab', async () => {
    mock(() => detail())
    render(<ThemePage themeId="ai" />)
    await screen.findByTestId('member-table')
    expect(screen.queryByText('What it could mean')).toBeNull()
    expect(screen.queryByRole('tab', { name: /At risk/ })).toBeNull()
  })
})

const fund = (symbol, over = {}) => member(symbol, { kind: 'fund', marketCap: null, size: 'Fund', risk: 'Fund', upside: null, growth: null, bagger: null,
  setup: { score: null, rawScore: null, riskMultiplier: 1, risk: 'Fund', label: 'Fund', capReason: null, factors: {} }, ...over })
const dollar = () => {
  const t = theme()
  t.id = 'dollar'; t.name = 'Dollar Regime Shift'; t.short = 'Dollar'; t.impact = impact()
  t.impact.sections = [...t.impact.sections.slice(0, 1), { id: 'reality', label: 'Reality check', type: 'cards', items: [{ title: 'No ready substitute', text: 'Only the US has markets this deep.' }] }, t.impact.sections[3]]
  t.roleLabels = { core: ['Hard-asset hedges', 'Gold and miners'], enabler: ['Markets & resources that gain', 'Non-US markets'], adjacent: ['US multinationals', 'Earn abroad'], emerging: ['Speculative alternatives', 'Thin stores of value'], atrisk: ['Most exposed to the shift', 'Lose if dollar demand fades'] }
  t.layers = [{ id: 'silicon', name: 'Gold & hard assets', blurb: 'Stores of value' }, { id: 'foundry', name: 'Developed markets', blurb: 'Europe, Japan' }]
  t.members = [fund('GLD', { name: 'SPDR Gold Shares', role: 'core', why: 'Gold fund.' }), member('NEM', { role: 'core', layer: 'silicon', setup: setup(70) }), fund('VGK', { role: 'enabler', layer: 'foundry' }), fund('TLT', { role: 'atrisk', layer: 'foundry', why: 'Long Treasuries.' })]
  t.roleCounts = { core: 2, enabler: 1, adjacent: 0, emerging: 0, atrisk: 1 }
  return t
}

describe('Dollar Regime Shift theme', () => {
  it('uses theme-specific group names and keeps funds out of the candidates', async () => {
    mock(() => detail({ theme: dollar() }))
    render(<ThemePage themeId="dollar" />)
    await screen.findByTestId('member-table')
    expect(screen.getByRole('tab', { name: /Hard-asset hedges/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Markets & resources that gain/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Most exposed to the shift/ })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /Picks & shovels/ })).toBeNull()
    const candidates = screen.getByText('Candidates to research').closest('section')
    expect(within(candidates).getAllByText(/NEM/).length).toBeGreaterThan(0)
    expect(within(candidates).queryByText(/GLD/)).toBeNull()
  })

  it('shows funds as funds: no score, a Fund pill, and a short explanation when opened', async () => {
    mock(() => detail({ theme: dollar() }))
    render(<ThemePage themeId="dollar" />)
    await screen.findByTestId('member-table')
    const row = screen.getByLabelText('GLD details')
    expect(within(row).getByText('Fund', { selector: 'span' })).toBeInTheDocument()
    fireEvent.click(row)
    const d = within(screen.getByTestId('member-detail'))
    expect(d.getByText('Gold fund.')).toBeInTheDocument()
    expect(d.getByText(/no company fundamentals, analyst targets or setup score/)).toBeInTheDocument()
    fireEvent.click(d.getByText('Open chart'))
    expect(screen.getByTestId('chart-modal')).toHaveTextContent('chart GLD')
  })

  it('sorting by setup keeps fund rows (no score) at the bottom', async () => {
    mock(() => detail({ theme: dollar() }))
    render(<ThemePage themeId="dollar" />)
    await screen.findByTestId('member-table')
    expect(names()[0]).toBe('NEM')                                                          // the only scored name
    fireEvent.click(screen.getByRole('columnheader', { name: /^Setup/ }))                   // flip to ascending
    expect(names()[0]).toBe('NEM')                                                          // unscored funds still sink to the bottom
    expect(names().slice(1).sort()).toEqual(['GLD', 'TLT', 'VGK'])
  })

  it('renders the theme\'s own tabs (reality check) and the scenario positioning line', async () => {
    mock(() => detail({ theme: dollar() }))
    render(<ThemePage themeId="dollar" />)
    await screen.findByText('What it could mean')
    fireEvent.click(screen.getByRole('tab', { name: 'Reality check' }))
    expect(screen.getByText('No ready substitute')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Scenarios' }))
    expect(screen.getByText('Stay liquid.')).toBeInTheDocument()
  })
})

describe('ThemesOverview', () => {
  it('shows a card per theme, a side-by-side table including SPY, and the narrative', async () => {
    mock(() => overview())
    render(<ThemesOverview />)
    expect(await screen.findByLabelText('Artificial Intelligence theme')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /theme$/ })).toHaveLength(4)
    const table = within(screen.getByTestId('themes-table'))
    expect(table.getAllByRole('row')).toHaveLength(6)                                       // header + 4 themes + SPY
    expect(table.getByText(/S&P 500/)).toBeInTheDocument()
    expect(screen.getByText(/Over the past year Artificial Intelligence has led \(\+42%\)/)).toBeInTheDocument()
    expect(screen.getByText(/Space Exploration has lagged most recently \(-12%/)).toBeInTheDocument()
    expect(screen.getAllByText(/NVDA, MU/).length).toBeGreaterThan(0)
  })

  it('opens a theme from a card and from a table row', async () => {
    mock(() => overview())
    const onNavigate = vi.fn()
    render(<ThemesOverview onNavigate={onNavigate} />)
    fireEvent.click(await screen.findByLabelText('Quantum Computing theme'))
    expect(onNavigate).toHaveBeenCalledWith('themequantum')
    fireEvent.click(within(screen.getByTestId('themes-table')).getByText('Space Exploration'))
    expect(onNavigate).toHaveBeenCalledWith('themespace')
  })

  it('shows progress while scanning and errors', async () => {
    mock(() => ({ status: 'running', progress: { done: 5, total: 79 }, error: null }))
    const { unmount } = render(<ThemesOverview />)
    expect(await screen.findByRole('status')).toHaveTextContent('5 / 79')
    unmount()
    mock(() => ({ __error: 'Yahoo down' }))
    render(<ThemesOverview />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Yahoo down')
  })
})
