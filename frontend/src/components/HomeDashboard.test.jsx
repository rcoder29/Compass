import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import HomeDashboard from './HomeDashboard'

afterEach(() => { vi.restoreAllMocks() })

const SUMMARY = { portfolio: { totalValue: 123456.78, dayPnl: 250, dayPnlPct: 0.2, totalPnl: 9000, totalPnlPct: 8, positionCount: 12, topDayMovers: [] },
                  market: { indices: [{ symbol: 'SPY', price: 700, '1d': 0.5 }], vix: { price: 16, label: 'Elevated', '1d': 1 } } }
const REGIME = { date: '2026-10-09', errors: {}, changes: null, themes: null, shorts: null, sectors: null,
                 regime: { phase: { id: 'mid', name: 'Mid-cycle expansion' }, quadrant: { id: 'goldilocks', name: 'Goldilocks' }, growth: 'Growth above its norm and improving',
                           riskScore: 3, riskBand: 'Low', flashing: [], watching: [], curveInverted: false } }

function mock({ regime }) {
  global.fetch = vi.fn(async url => {
    const u = String(url)
    if (u.includes('/api/home/regime')) return regime === 'fail' ? { ok: false, status: 502, json: async () => ({ detail: 'FRED down' }) } : { ok: true, json: async () => REGIME }
    return { ok: true, json: async () => SUMMARY }
  })
}
const props = { watchlist: [], quotes: {}, alerts: [], earnings: [], portfolioSymbols: [], navIndex: {}, recentTabs: [], onNavigate: vi.fn(), onOpenChangelog: vi.fn() }

describe('HomeDashboard', () => {
  it('shows the market regime card alongside the portfolio and market cards', async () => {
    mock({})
    render(<HomeDashboard {...props} />)
    expect(await screen.findByText('Mid-cycle expansion')).toBeInTheDocument()
    expect(screen.getByLabelText('Market regime')).toBeInTheDocument()
    expect(await screen.findByText('$123,456.78')).toBeInTheDocument()
    expect(screen.getByText('Portfolio Movers')).toBeInTheDocument()
  })

  it('a failing regime build does not hide the rest of Home', async () => {
    mock({ regime: 'fail' })
    render(<HomeDashboard {...props} />)
    expect(await screen.findByText('FRED down')).toBeInTheDocument()
    expect(await screen.findByText('$123,456.78')).toBeInTheDocument()
    expect(screen.getByText('Portfolio Movers')).toBeInTheDocument()
  })
})
