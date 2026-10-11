import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, renderHook } from '@testing-library/react'
import { fmtPct, fmtNum, fmtValue, heat, niceTicks, trimPoints, useApi, TimeChart, Sparkline, Segmented, signedClass } from './MacroKit'

afterEach(() => { vi.restoreAllMocks() })

describe('formatters', () => {
  it('fmtPct takes fractions, signs gains, drops decimals for big numbers, dashes missing', () => {
    expect(fmtPct(0.153)).toBe('+15.3%')
    expect(fmtPct(-0.05)).toBe('-5.0%')
    expect(fmtPct(0.153, { signed: false })).toBe('15.3%')
    expect(fmtPct(1.2345)).toBe('+123%')
    expect(fmtPct(34.298)).toBe('+3,430%')
    expect(fmtPct(0.0123, { digits: 2 })).toBe('+1.23%')
    for (const v of [null, undefined, NaN]) expect(fmtPct(v)).toBe('—')
  })

  it('fmtNum scales decimals to magnitude', () => {
    expect(fmtNum(1.2345)).toBe('1.23')
    expect(fmtNum(123.456)).toBe('123.5')
    expect(fmtNum(12345.6)).toBe('12,346')
    expect(fmtNum(null)).toBe('—')
    expect(fmtNum(198, 0)).toBe('198')
    expect(fmtNum(2.345, 1)).toBe('2.3')
    expect(fmtNum(12345.6, 2)).toBe('12,345.60')
  })

  it('fmtValue attaches the indicator unit', () => {
    expect(fmtValue(4.25, '%')).toBe('4.25%')
    expect(fmtValue(1.05, 'pts')).toBe('1.05 pts')
    expect(fmtValue(198, 'K')).toBe('198K')
    expect(fmtValue(18.3, 'index')).toBe('18.30 index')
    expect(fmtValue(2.5, '$B')).toBe('$2.50B')
    expect(fmtValue(undefined, '%')).toBe('—')
  })

  it('heat shades by sign and saturates', () => {
    expect(heat(0.1, 0.2).backgroundColor).toMatch(/^rgba\(16,185,129,/)
    expect(heat(-0.1, 0.2).backgroundColor).toMatch(/^rgba\(239,68,68,/)
    expect(heat(5, 0.2).backgroundColor).toContain('0.550')
    expect(heat(null, 0.2)).toEqual({})
  })

  it('signedClass', () => {
    expect(signedClass(1)).toContain('emerald'); expect(signedClass(-1)).toContain('red'); expect(signedClass(null)).toContain('gray-500')
  })
})

describe('chart helpers', () => {
  it('niceTicks gives round steps inside the range', () => {
    const t = niceTicks(0, 10, 5)
    expect(t[0]).toBe(0); expect(t[t.length - 1]).toBe(10); expect(t).toEqual([0, 2, 4, 6, 8, 10])
    expect(niceTicks(5, 5)).toEqual([5])
  })

  it('trimPoints keeps the last N years, or everything for 0', () => {
    const pts = [['2000-01-01', 1], ['2015-06-30', 2], ['2024-06-30', 3], ['2026-06-30', 4]]
    expect(trimPoints(pts, 5).map(p => p[1])).toEqual([3, 4])
    expect(trimPoints(pts, 0)).toHaveLength(4)
    expect(trimPoints(null, 5)).toEqual([])
  })

  it('Sparkline draws a line and tolerates tiny input', () => {
    const { container, rerender } = render(<Sparkline values={[1, 3, 2, 5]} />)
    expect(container.querySelector('polyline')).toBeInTheDocument()
    rerender(<Sparkline values={[1]} />)
    expect(container.querySelector('polyline')).toBeNull()
  })

  it('TimeChart plots series, shades recession bands and shows a tooltip on hover', () => {
    const points = [['2020-01-01', 1], ['2021-01-01', 2], ['2022-01-01', 3]]
    const { container } = render(<TimeChart series={[{ name: 'X', color: '#fff', points }]} bands={[{ start: '2020-06-01', end: '2020-12-01' }]}
                                            lines={[{ y: 2, label: 'warn' }]} format={v => `v${v}`} label="test chart" />)
    expect(screen.getByRole('img', { name: 'test chart' })).toBeInTheDocument()
    expect(container.querySelector('polyline')).toBeInTheDocument()
    expect(container.querySelectorAll('rect').length).toBe(1)
    expect(screen.getByText('warn')).toBeInTheDocument()
    const svg = screen.getByRole('img', { name: 'test chart' })
    svg.getBoundingClientRect = () => ({ left: 0, width: 900, top: 0, height: 260 })
    fireEvent.mouseMove(svg, { clientX: 880 })
    expect(screen.getByTestId('chart-tip')).toHaveTextContent('2022-01-01')
    expect(screen.getByTestId('chart-tip')).toHaveTextContent('v3')
    fireEvent.mouseLeave(svg)
    expect(screen.queryByTestId('chart-tip')).toBeNull()
  })

  it('TimeChart with no data says so', () => {
    render(<TimeChart series={[{ name: 'X', color: '#fff', points: [] }]} />)
    expect(screen.getByText(/no data/i)).toBeInTheDocument()
  })

  it('Segmented marks the active option and reports clicks', () => {
    const onChange = vi.fn()
    render(<Segmented label="Pick" options={[['a', 'A'], ['b', 'B']]} value="a" onChange={onChange} />)
    expect(screen.getByRole('button', { name: 'A' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'B' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })
})

describe('useApi', () => {
  it('loads data, surfaces server error text, and ignores superseded responses', async () => {
    let resolveSlow
    global.fetch = vi.fn(url => {
      if (url === '/slow') return new Promise(r => { resolveSlow = () => r({ ok: true, json: async () => ({ v: 'slow' }) }) })
      if (url === '/bad') return Promise.resolve({ ok: false, status: 502, json: async () => ({ detail: 'FRED down' }) })
      return Promise.resolve({ ok: true, json: async () => ({ v: 'fast' }) })
    })
    const { result, rerender } = renderHook(({ u }) => useApi(u), { initialProps: { u: '/slow' } })
    expect(result.current.loading).toBe(true)
    rerender({ u: '/fast' })
    await waitFor(() => expect(result.current.data).toEqual({ v: 'fast' }))
    resolveSlow()
    await new Promise(r => setTimeout(r, 10))
    expect(result.current.data).toEqual({ v: 'fast' })          // the slow, older response was dropped
    rerender({ u: '/bad' })
    await waitFor(() => expect(result.current.error).toBe('FRED down'))
    rerender({ u: null })
    await waitFor(() => expect(result.current).toMatchObject({ data: null, loading: false, error: null }))
  })
})
