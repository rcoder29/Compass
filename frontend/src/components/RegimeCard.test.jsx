import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import RegimeCard from './RegimeCard'

afterEach(() => { vi.restoreAllMocks() })

const summary = (over = {}) => ({
  date: '2026-10-09', errors: {},
  regime: { asOf: '2026-08-01', phase: { id: 'late', name: 'Late cycle' }, quadrant: { id: 'slowdown', name: 'Slowdown' }, growth: 'Growth above its norm and weakening', inflation: 'x',
            riskScore: 31.4, riskBand: 'Moderate', flashing: ['Sahm rule'], watching: [], curveInverted: true },
  changes: { since: '2026-10-08', phaseFrom: 'Mid-cycle expansion', phaseTo: 'Late cycle', riskFrom: 20, riskTo: 31.4 },
  sectors: { asOf: '2026-10-09', spy3m: 0.04, top: [{ symbol: 'XLK', name: 'Technology', ret3m: 0.12, excess3m: 0.08 }, { symbol: 'XLE', name: 'Energy', ret3m: 0.1, excess3m: 0.06 }],
             bottom: [{ symbol: 'XLU', name: 'Utilities', ret3m: -0.03, excess3m: -0.07 }, { symbol: 'XLP', name: 'Staples', ret3m: -0.01, excess3m: -0.05 }] },
  themes: { asOf: '2026-10-09', spy3m: 0.05, top: [{ id: 'ai', name: 'Artificial Intelligence', short: 'AI', ret3m: 0.15, vsSpy: 0.10 }], bottom: [{ id: 'space', name: 'Space Exploration', short: 'Space', ret3m: -0.12, vsSpy: -0.17 }] },
  shorts: { settlement: '2026-09-15', count: 100, above30: 49, hardToBorrow: 8, creditConfirms: 7, biggestIncreases: [],
            top: [{ symbol: 'WOLF', name: 'Wolfspeed', siPctFloat: 0.83, fee: 1.2, displacement: 'confirmed', displacementLabel: 'Credit confirms' }, { symbol: 'GRPN', name: 'Groupon', siPctFloat: 0.71, fee: null, displacement: 'none', displacementLabel: 'No bond read' }] },
  ...over,
})
function mock(handler) {
  global.fetch = vi.fn(async url => {
    const r = await handler(String(url))
    return r?.__error ? { ok: false, status: 502, json: async () => ({ detail: r.__error }) } : { ok: true, json: async () => r }
  })
}

describe('RegimeCard', () => {
  it('shows the phase, quadrant, recession risk, warning chips and what changed', async () => {
    mock(() => summary())
    render(<RegimeCard />)
    expect(await screen.findByText('Late cycle')).toBeInTheDocument()
    expect(screen.getByText(/Slowdown: growth above its norm and weakening/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Recession risk 31 of 100, Moderate' })).toBeInTheDocument()
    expect(screen.getByText('Yield curve inverted')).toBeInTheDocument(); expect(screen.getByText('Sahm rule flashing')).toBeInTheDocument()
    expect(screen.getByTestId('phase-change')).toHaveTextContent('Phase changed: Mid-cycle expansion → Late cycle')
    expect(screen.getByTestId('risk-change')).toHaveTextContent('Risk 20 → 31 since 2026-10-08')
  })

  it('lists sector and theme leaders and laggards against SPY, and the most shorted names', async () => {
    mock(() => summary())
    render(<RegimeCard />)
    await screen.findByText('Late cycle')
    const sectors = screen.getByText('Sectors vs SPY, 3 months').closest('div').parentElement
    expect(within(sectors).getByText('Technology').parentElement).toHaveTextContent('+8.0%')
    expect(within(sectors).getByText('Utilities').parentElement).toHaveTextContent('−7.0%')
    const themes = screen.getByText('Themes vs SPY, 3 months').closest('div').parentElement
    expect(within(themes).getByText('Artificial Intelligence').parentElement).toHaveTextContent('+10.0%')
    const shorts = within(screen.getByTestId('regime-shorts'))
    expect(shorts.getByText('WOLF').parentElement).toHaveTextContent('83% of float · 1.2% fee')
    expect(shorts.getByText('GRPN').parentElement).not.toHaveTextContent('fee')            // no borrow quote: nothing invented
    expect(shorts.getByText(/Bonds confirm the shorts on 7/)).toBeInTheDocument()
  })

  it('leaves out change chips when nothing changed', async () => {
    mock(() => summary({ changes: null }))
    render(<RegimeCard />)
    await screen.findByText('Late cycle')
    expect(screen.queryByTestId('phase-change')).toBeNull(); expect(screen.queryByTestId('risk-change')).toBeNull()
  })

  it('explains the cache-only parts instead of leaving gaps', async () => {
    mock(() => summary({ themes: null, shorts: null }))
    render(<RegimeCard />)
    expect(await screen.findByText('Shown once you have opened Themes.')).toBeInTheDocument()
    expect(screen.getByText('Shown once you have opened Short Interest.')).toBeInTheDocument()
    expect(screen.getByText('Technology')).toBeInTheDocument()
  })

  it('works with only the sectors (no economic data)', async () => {
    mock(() => summary({ regime: null, changes: null, themes: null, shorts: null }))
    render(<RegimeCard />)
    expect(await screen.findByText('Technology')).toBeInTheDocument()
    expect(screen.queryByText('Late cycle')).toBeNull()
  })

  it('says so when nothing at all could be loaded, and shows server errors', async () => {
    mock(() => summary({ regime: null, changes: null, sectors: null, themes: null, shorts: null }))
    const { unmount } = render(<RegimeCard />)
    expect(await screen.findByText(/summary isn't available right now/)).toBeInTheDocument()
    unmount()
    mock(() => ({ __error: 'FRED unreachable' }))
    render(<RegimeCard />)
    expect(await screen.findByRole('alert')).toHaveTextContent('FRED unreachable')
  })

  it('navigates from the headers', async () => {
    mock(() => summary())
    const onNavigate = vi.fn()
    render(<RegimeCard onNavigate={onNavigate} />)
    await screen.findByText('Late cycle')
    fireEvent.click(screen.getByText('Regime dashboard →')); expect(onNavigate).toHaveBeenLastCalledWith('econregime')
    fireEvent.click(screen.getByText('Scoreboard →')); expect(onNavigate).toHaveBeenLastCalledWith('sectorboard')
    fireEvent.click(screen.getByText('All themes →')); expect(onNavigate).toHaveBeenLastCalledWith('themesoverview')
    fireEvent.click(screen.getByText('Short interest →')); expect(onNavigate).toHaveBeenLastCalledWith('shortinterest')
  })

  it('requests the home regime endpoint once', async () => {
    mock(() => summary())
    render(<RegimeCard />)
    await screen.findByText('Late cycle')
    expect(global.fetch).toHaveBeenCalledTimes(1); expect(global.fetch).toHaveBeenCalledWith('/api/home/regime')
  })
})
