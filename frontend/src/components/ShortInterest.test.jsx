import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor, act } from '@testing-library/react'
import ShortInterest, { fmtCap, fmtShares, fmtAvail, toCsv } from './ShortInterest'

vi.mock('./ChartModal', () => ({ default: ({ symbol, onClose }) => <div data-testid="chart-modal">chart {symbol}<button onClick={onClose}>close chart</button></div> }))
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:x'); URL.revokeObjectURL = vi.fn() })

const disp = key => ({
  equity_leads: { key, label: 'Equity ahead of credit', tone: 'info', text: '40% of the float is sold short, yet bond spreads are only about 120 bps: lenders see little default risk.' },
  partial: { key, label: 'Partly confirmed', tone: 'warn', text: '30% of the float is sold short; bond spreads are wide at about 520 bps.' },
  confirmed: { key, label: 'Credit confirms', tone: 'bad', text: '45% of the float is sold short, and bond spreads are around 900 bps over Treasuries.' },
  none: { key, label: 'No bond read', tone: 'none', text: '25% of the float is sold short, but no bond data was found.' },
}[key])
const row = (symbol, rank, over = {}) => ({
  rank, symbol, name: `${symbol} Corp`, sector: 'Consumer Cyclical', exchange: 'NYSE', price: 20, marketCap: 3e9, floatShares: 50e6, sharesShort: 22e6, prevShort: 20e6, changePct: 10, adv: 4e6,
  daysToCover: 5.5, siPctFloat: 0.44, change52w: -0.3, settlement: '2026-09-15',
  borrow: { fee: 16, rebate: -12.5, available: 250000, availableCapped: false, band: { label: 'Hard to borrow', key: 'hard' } },
  bonds: { issuer: `${symbol} CO`, matchType: 'exact', count: 2, avgCoupon: 5.25, avgYtm: 6.4, avgSpreadBps: 210, grade: 'IG', inDefault: false, nextMaturity: '2030-01-01', lastMaturity: '2034-01-01',
           top: [{ coupon: 5.5, maturity: '2034-01-01', price: 98.5, ytm: 6.2, spreadBps: 200, grades: ['IG'] }, { coupon: 4.0, maturity: '2030-01-01', price: 95, ytm: 6.8, spreadBps: 240, grades: ['IG'] }] },
  interestPaid: { interestExpense: 40e6, totalDebt: 500e6, impliedRate: 8, coverage: 2.5, netDebt: 450e6, proxySpreadBps: 380 },
  spreadBps: 210, spreadIsProxy: false, displacement: disp('equity_leads'), equityPercentile: 100, creditPercentile: 40, displacementScore: 60, ...over,
})
const rows4 = () => [
  row('AAA', 1),
  row('BBB', 2, { siPctFloat: 0.38, sharesShort: 9e6, changePct: -20, daysToCover: 2.1, marketCap: 800e6, sector: 'Technology', borrow: { fee: 0.4, rebate: 3.6, available: 10000000, availableCapped: true, band: { label: 'General collateral', key: 'easy' } },
                  bonds: { ...row('BBB', 2).bonds, avgCoupon: 9.0, avgYtm: 12.5, avgSpreadBps: 780, grade: 'HY' }, spreadBps: 780, displacement: disp('confirmed'), equityPercentile: 75, creditPercentile: 100, displacementScore: -25 }),
  row('CCC', 3, { siPctFloat: 0.3, bonds: null, interestPaid: { interestExpense: 10e6, totalDebt: 200e6, impliedRate: 5, coverage: 6, netDebt: -5e6, proxySpreadBps: 100 }, spreadBps: 520, spreadIsProxy: true, displacement: disp('partial'),
                  borrow: null, equityPercentile: 50, creditPercentile: 70, displacementScore: -20 }),
  row('DDD', 4, { siPctFloat: 0.25, borrow: null, bonds: null, interestPaid: null, spreadBps: null, spreadIsProxy: null, displacement: disp('none'), changePct: null, daysToCover: null, creditPercentile: null, displacementScore: null, equityPercentile: 25 }),
]
const ready = (rows = rows4(), over = {}) => ({
  status: 'ready', settlement: '2026-09-15', borrowAsOf: '2026-10-11 17:43:33', limit: 100, minCapM: 300, treasury10y: 4.1, rows, partial: null, notes: [], bondFunds: ['LQD', 'HYG'],
  summary: { count: rows.length, medianSi: 0.38, above30: 3, withBorrow: 2, hardToBorrow: 1, mostExpensive: [{ symbol: 'AAA', fee: 16 }], biggestIncreases: [{ symbol: 'AAA', changePct: 10 }], withBonds: 2, withProxy: 1,
             displacement: { equity_leads: 1, partial: 1, confirmed: 1, none: 1 } }, ...over,
})
function mock(handler) {
  global.fetch = vi.fn(async url => {
    const r = await handler(String(url))
    return r?.__error ? { ok: false, status: 502, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r }
  })
}
const order = () => screen.getAllByTestId('si-row').map(r => r.getAttribute('aria-label').replace(' details', ''))

describe('helpers', () => {
  it('formats caps, share counts and availability', () => {
    expect(fmtCap(5e8)).toBe('$500M'); expect(fmtCap(3e9)).toBe('$3.0B'); expect(fmtCap(2.5e10)).toBe('$25B'); expect(fmtCap(null)).toBe('—')
    expect(fmtShares(22e6)).toBe('22.0M'); expect(fmtShares(1.5e9)).toBe('1.50B'); expect(fmtShares(8500)).toBe('9K'); expect(fmtShares(null)).toBe('—')
    expect(fmtAvail({ available: 250000, availableCapped: false })).toBe('250K'); expect(fmtAvail({ available: 1e7, availableCapped: true })).toBe('>10.0M')
    expect(fmtAvail({ available: 0 })).toBe('none'); expect(fmtAvail(null)).toBe('—')
  })
  it('exports CSV with quoting and blanks', () => {
    const csv = toCsv([{ ...row('AAA', 1), name: 'A, "Inc"', borrow: null, bonds: null, spreadBps: null }])
    const [head, line] = csv.split('\n')
    expect(head).toContain('"Borrow fee %"'); expect(line).toContain('"A, ""Inc"""'); expect(line).toContain('44.0'); expect(line).toContain('"Equity ahead of credit"')
  })
})

describe('ShortInterest', () => {
  it('ranks stocks by short interest with borrow cost, bond read and the displacement badge', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    expect(order()).toEqual(['AAA', 'BBB', 'CCC', 'DDD'])
    const a = within(screen.getByLabelText('AAA details'))
    expect(a.getByText('44.0%')).toBeInTheDocument(); expect(a.getByText('16.0%')).toBeInTheDocument(); expect(a.getByText('Equity ahead of credit')).toBeInTheDocument()
    expect(a.getByText(/5.25% coupon/)).toBeInTheDocument(); expect(a.getByText(/\+210 bps/)).toBeInTheDocument()
    expect(screen.getByText(/Short interest settled 2026-09-15 · borrow data 2026-10-11 17:43:33/)).toBeInTheDocument()
    expect(within(screen.getByLabelText('CCC details')).getByText(/paid on debt/)).toBeInTheDocument()          // no bonds: the interest-paid proxy
    expect(within(screen.getByLabelText('DDD details')).getByText('No bond read')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^All 4/ }))
  })

  it('says when the interest paid is too low or too small to read as credit', async () => {
    const lowRate = row('LOW', 1, { bonds: null, spreadBps: null, spreadIsProxy: null, displacement: disp('none'), interestPaid: { interestExpense: 1e6, totalDebt: 800e6, impliedRate: 0.1, coverage: 5, netDebt: 10e6, proxySpreadBps: -390 } })
    mock(() => ready([lowRate]))
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    expect(within(screen.getByLabelText('LOW details')).getByText(/no credit read/)).toBeInTheDocument()
  })

  it('shows summary cards', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    expect(screen.getByText('Median short interest').parentElement).toHaveTextContent('38%')
    expect(screen.getByText('Hard to borrow').parentElement).toHaveTextContent('1')
    expect(screen.getByText('Most expensive').parentElement).toHaveTextContent('AAA')
    expect(screen.getByText('Biggest increase').parentElement).toHaveTextContent('+10%')
  })

  it('filters by displacement type, sector, text and hard-to-borrow', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.click(screen.getByRole('button', { name: /^Credit confirms/ }))
    expect(order()).toEqual(['BBB'])
    fireEvent.click(screen.getByRole('button', { name: /^All 4/ }))
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: 'Technology' } })
    expect(order()).toEqual(['BBB'])
    fireEvent.change(screen.getByLabelText('Sector'), { target: { value: '' } })
    fireEvent.click(screen.getByLabelText(/Borrow fee 5%/))
    expect(order()).toEqual(['AAA'])
    fireEvent.click(screen.getByLabelText(/Borrow fee 5%/))
    fireEvent.change(screen.getByLabelText('Filter stocks'), { target: { value: 'ddd' } })
    expect(order()).toEqual(['DDD'])
    fireEvent.change(screen.getByLabelText('Filter stocks'), { target: { value: 'zzz' } })
    expect(screen.getByText(/No stocks match/)).toBeInTheDocument()
  })

  it('sorts by borrow fee and spread, with missing values always last', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.click(screen.getByRole('columnheader', { name: /^Borrow fee/ }))
    expect(order().slice(0, 2)).toEqual(['AAA', 'BBB'])
    fireEvent.click(screen.getByRole('columnheader', { name: /^Borrow fee/ }))
    expect(order().slice(0, 2)).toEqual(['BBB', 'AAA'])
    expect(order().slice(2).sort()).toEqual(['CCC', 'DDD'])                                       // no quote: still last
    fireEvent.click(screen.getByRole('columnheader', { name: /^Company bonds/ }))
    expect(order()[0]).toBe('BBB'); expect(order()[3]).toBe('DDD')                                 // widest spread first; none last
    fireEvent.click(screen.getByRole('columnheader', { name: /^Equity vs credit/ }))
    expect(order()[0]).toBe('AAA')                                                                 // biggest equity-over-credit gap
  })

  it('opens the detail: why, percentiles, borrow, interest paid and the bond table', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.click(screen.getByLabelText('AAA details'))
    const d = within(screen.getByTestId('si-detail'))
    expect(d.getByText(/lenders see little default risk/)).toBeInTheDocument()
    expect(d.getByText(/16.00% a year/)).toBeInTheDocument(); expect(d.getByText(/Hard to borrow/)).toBeInTheDocument(); expect(d.getByText(/Rebate: -12.50%/)).toBeInTheDocument()
    expect(d.getByText(/Implied rate: 8.00%/)).toBeInTheDocument(); expect(d.getByText(/Interest cover \(EBIT \/ interest\): 2.5x/)).toBeInTheDocument()
    expect(d.getByText(/matched to “AAA CO”/)).toBeInTheDocument(); expect(d.getByText('2034-01')).toBeInTheDocument(); expect(d.getByText('6.20%')).toBeInTheDocument()
    fireEvent.click(d.getByText('Open chart'))
    expect(screen.getByTestId('chart-modal')).toHaveTextContent('chart AAA')
    fireEvent.click(screen.getByText('close chart'))
    fireEvent.click(screen.getByLabelText('AAA details'))
    expect(screen.queryByTestId('si-detail')).toBeNull()
  })

  it('explains the absence of bonds and of a borrow quote', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.click(screen.getByLabelText('CCC details'))
    const d = within(screen.getByTestId('si-detail'))
    expect(d.getByText(/Not listed in Interactive Brokers/)).toBeInTheDocument()
    expect(d.getByText(/None of the company's bonds are held by the large corporate-bond funds/)).toBeInTheDocument()
    expect(d.getByText(/lagging proxy/)).toBeInTheDocument()
  })

  it('refetches when the market-cap floor changes', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.change(screen.getByLabelText('Minimum market cap'), { target: { value: '1000' } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/short-interest?limit=100&min_cap=1000'))
  })

  it('shows stage progress, then the table when the stages finish', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mock(() => (++calls < 3 ? { status: 'running', stage: calls, stages: 3, stageLabel: calls === 1 ? 'Reading float and market caps' : 'Reading interest expense and debt', progress: { done: 40 * calls, total: 563 } } : ready()))
    render(<ShortInterest />)
    expect(await screen.findByRole('status')).toHaveTextContent('Step 1 of 3: Reading float and market caps')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByText(/Step 2 of 3: Reading interest expense and debt/)).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByTestId('si-table')).toBeInTheDocument()
  })

  it('shows partial-data notes and server notes, and errors', async () => {
    mock(() => ready(rows4(), { partial: { note: 'Bond holdings couldn\'t be loaded; showing the proxy.' }, notes: ['Bond holdings couldn\'t be loaded; showing the proxy.', 'Borrow rates are unavailable right now.'] }))
    const { unmount } = render(<ShortInterest />)
    await screen.findByTestId('si-table')
    expect(screen.getAllByRole('note')).toHaveLength(2)                                           // the partial note once, plus the extra server note
    unmount()
    mock(() => ({ __error: 'finra down' }))
    render(<ShortInterest />)
    expect(await screen.findByRole('alert')).toHaveTextContent('finra down')
  })

  it('exports the filtered rows as CSV', async () => {
    mock(() => ready())
    render(<ShortInterest />)
    await screen.findByTestId('si-table')
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(URL.createObjectURL).toHaveBeenCalled()
  })
})
