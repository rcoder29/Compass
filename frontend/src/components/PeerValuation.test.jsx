import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, act, fireEvent, waitFor } from '@testing-library/react'
import PeerValuationBody, { PeerComparison, Scatter, fmtMetric, fmtPrem } from './PeerValuation'

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

const metric = (key, label, group, unit, value, median, over = {}) => ({
  key, label, group, unit, value, peers: 8, median, p25: median * 0.8, p75: median * 1.2, premium: group === 'valuation' && value != null ? value / median - 1 : null,
  expensiveness: group === 'valuation' ? 12.5 : null, cheaperThan: 7, quality: group === 'quality' ? 87.5 : null, betterThan: 7, impliedPrice: null, ...over,
})
const payload = (over = {}) => ({
  status: 'ready', symbol: 'ACME', name: 'Acme', scope: 'industry', scopeLabel: 'Software', peerCount: 8, partial: null,
  headline: 'ACME trades at a 27% discount to the peer median (median across 5 multiples). At peer-median multiples it would be about $140.00 (+40% from $100.00).',
  verdict: { key: 'discount_strong', label: 'Cheaper than peers despite stronger fundamentals', tone: 'good', text: 'It trades below most peers while its growth, margins and returns are better than most.' },
  expensiveRank: 12.5, qualityRank: 87.5, medianPremium: -0.27, premiumCount: 5,
  metrics: [metric('forwardPE', 'P/E (forward)', 'valuation', 'x', 16, 22), metric('priceToBook', 'Price / book', 'valuation', 'x', 4, 6, { median: null, p25: null, p75: null, premium: null, expensiveness: null, peers: 2 }),
            metric('fcfYield', 'FCF yield', 'valuation', '%', 0.058, 0.04, { premium: null, expensiveness: 20 }),
            metric('revenueGrowth', 'Revenue growth', 'quality', '%', 0.29, 0.18), metric('operatingMargin', 'Operating margin', 'quality', '%', 0.29, 0.2)],
  peerImplied: { low: 110, mid: 140, high: 175, vsPrice: 0.4, price: 100, metrics: ['forwardPE', 'evToEbitda'] },
  scatter: { xLabel: 'Revenue growth', yLabel: 'P/E (forward)', yKey: 'forwardPE', points: [{ symbol: 'ACME', x: 0.29, y: 16, isSubject: true }, { symbol: 'P1', x: 0.2, y: 20, isSubject: false }, { symbol: 'P2', x: 0.1, y: 25, isSubject: false }] },
  subject: { symbol: 'ACME', name: 'Acme', marketCap: 12e9, forwardPE: 16, evToEbitda: 13, priceToSales: 3.5, revenueGrowth: 0.29, operatingMargin: 0.29 },
  peers: [{ symbol: 'P1', name: 'Peer One', marketCap: 20e9, forwardPE: 20, evToEbitda: 15, priceToSales: 5, revenueGrowth: 0.2, operatingMargin: 0.25 },
          { symbol: 'P2', name: 'Peer Two', marketCap: 9e9, forwardPE: null, evToEbitda: null, priceToSales: 6, revenueGrowth: 0.1, operatingMargin: 0.1 }],
  note: "Peers are the companies closest in size within Yahoo's industry 'Software'.", ...over,
})
function mock(handler) {
  global.fetch = vi.fn(async url => {
    const r = await handler(String(url))
    return r?.__error ? { ok: false, status: 502, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r }
  })
}

describe('helpers', () => {
  it('formats multiples, percentages and premiums', () => {
    expect(fmtMetric(16.04, 'x')).toBe('16.0x'); expect(fmtMetric(0.058, '%')).toBe('5.8%'); expect(fmtMetric(null, 'x')).toBe('—')
    expect(fmtPrem(0.274)).toBe('+27%'); expect(fmtPrem(-0.274)).toBe('−27%'); expect(fmtPrem(null)).toBe('—')
  })
})

describe('PeerComparison', () => {
  it('shows the verdict, the rank bars, the metric table and the implied price', () => {
    render(<PeerComparison d={payload()} />)
    expect(screen.getByText('Cheaper than peers despite stronger fundamentals')).toBeInTheDocument()
    expect(screen.getByText(/27% discount to the peer median/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'How expensive vs peers: 13 out of 100' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'How strong vs peers: 88 out of 100' })).toBeInTheDocument()
    const fwd = screen.getByText('P/E (forward)').closest('tr')
    expect(fwd).toHaveTextContent('16.0x'); expect(fwd).toHaveTextContent('22.0x'); expect(fwd).toHaveTextContent('−27%'); expect(fwd).toHaveTextContent('pricier than 13% of 8')
    expect(screen.getByText('Revenue growth').closest('tr')).toHaveTextContent('better than 88% of 8')
    expect(screen.getByText('Price / book').closest('tr')).toHaveTextContent('not enough peers')
    const imp = within(screen.getByTestId('peer-implied'))
    expect(imp.getByText('$140.00')).toBeInTheDocument(); expect(imp.getByText('+40%')).toBeInTheDocument(); expect(imp.getByText(/\$110.00 – \$175.00/)).toBeInTheDocument()
    expect(imp.getByText(/ignores differences in growth, risk and accounting/)).toBeInTheDocument()
  })

  it('warns when the implied price is far from the market price', () => {
    const { rerender } = render(<PeerComparison d={payload()} />)
    expect(screen.queryByText(/more than three times above or below/)).toBeNull()
    rerender(<PeerComparison d={payload({ peerImplied: { low: 300, mid: 900, high: 1500, vsPrice: 8, price: 100, metrics: ['forwardPE'], farFromPrice: true } })} />)
    expect(screen.getByText(/more than three times above or below the market price/)).toBeInTheDocument()
  })

  it('lists the stock first (highlighted) then its peers, with blanks for missing values', () => {
    render(<PeerComparison d={payload()} />)
    const rows = within(screen.getByTestId('peer-table')).getAllByRole('row').slice(1)
    expect(rows.map(r => r.cells[0].textContent.split(' ')[0])).toEqual(['ACME', 'P1', 'P2'])
    expect(rows[0].className).toMatch(/amber/); expect(rows[2]).toHaveTextContent('—')
    expect(rows[1]).toHaveTextContent('$20.0B')
  })

  it('draws the growth-vs-multiple scatter with the subject highlighted', () => {
    render(<PeerComparison d={payload()} />)
    expect(screen.getByRole('img', { name: 'P/E (forward) against revenue growth for ACME and its peers' })).toBeInTheDocument()
    expect(screen.getByText('Is a premium explained by growth? P/E (forward) vs revenue growth')).toBeInTheDocument()
  })

  it('omits the optional blocks and shows partial-data and scope notes', () => {
    render(<PeerComparison d={payload({ peerImplied: null, scatter: null, partial: { note: '3 of 40 candidate peers couldn\'t be loaded.' } })} />)
    expect(screen.queryByTestId('peer-implied')).toBeNull()
    expect(screen.queryByText(/Is a premium explained by growth/)).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent('3 of 40 candidate peers')
    expect(screen.getByText(/closest in size within Yahoo's industry 'Software'/)).toBeInTheDocument()
  })

  it('colours the read by tone', () => {
    const { rerender, container } = render(<PeerComparison d={payload()} />)
    expect(container.querySelector('.text-emerald-300')).toBeInTheDocument()
    rerender(<PeerComparison d={payload({ verdict: { key: 'premium_unearned', label: 'Expensive and weaker than peers', tone: 'bad', text: 't' } })} />)
    expect(screen.getByText('Expensive and weaker than peers').parentElement.className).toMatch(/red/)
  })

  it('Scatter handles a single flat series', () => {
    render(<Scatter symbol="ACME" data={{ xLabel: 'Revenue growth', yLabel: 'FCF yield', yKey: 'fcfYield', points: [{ symbol: 'ACME', x: 0.1, y: 0.04, isSubject: true }, { symbol: 'P1', x: 0.1, y: 0.04, isSubject: false }] }} />)
    expect(screen.getByRole('img', { name: /FCF yield against revenue growth/ })).toBeInTheDocument()
  })
})

describe('PeerValuationBody', () => {
  it('loads the comparison for the symbol', async () => {
    mock(() => payload())
    render(<PeerValuationBody symbol="acme" />)
    expect(await screen.findByTestId('peer-comparison')).toBeInTheDocument()
    expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/acme/peers')
  })

  it('shows progress while peers load, then the comparison', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mock(() => (++calls < 2 ? { status: 'running', progress: { done: 12, total: 40 }, error: null } : payload()))
    render(<PeerValuationBody symbol="ACME" />)
    expect(await screen.findByRole('status')).toHaveTextContent('12 / 40')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(await screen.findByTestId('peer-comparison')).toBeInTheDocument()
  })

  it('explains when a comparison is unavailable', async () => {
    mock(() => ({ status: 'unavailable', reason: 'Only 2 comparable companies could be found (at least 4 are needed).' }))
    render(<PeerValuationBody symbol="ACME" />)
    expect(await screen.findByText(/Only 2 comparable companies/)).toBeInTheDocument()
  })

  it('offers a retry when the lookup failed temporarily, and asks again', async () => {
    let calls = 0
    mock(() => (++calls < 2 ? { status: 'unavailable', transient: true, reason: 'Yahoo Finance is limiting requests right now.' } : payload()))
    render(<PeerValuationBody symbol="ACME" />)
    expect(await screen.findByText(/limiting requests right now/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByTestId('peer-comparison')).toBeInTheDocument()
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/tear-sheet/ACME/peers?retry=1'))
  })

  it('does not offer a retry for a permanent reason', async () => {
    mock(() => ({ status: 'unavailable', reason: 'Peer comparison applies to individual companies, not funds.' }))
    render(<PeerValuationBody symbol="SPY" />)
    expect(await screen.findByText(/not funds/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })

  it('shows server errors and survives a malformed payload', async () => {
    mock(() => ({ __error: 'Yahoo exploded' }))
    const { unmount } = render(<PeerValuationBody symbol="ACME" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Yahoo exploded')
    unmount()
    mock(() => ({ some: 'thing' }))
    render(<PeerValuationBody symbol="ACME" />)
    expect(await screen.findByText(/isn't available right now/)).toBeInTheDocument()
  })
})
