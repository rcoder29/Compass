import { useState, useEffect, useMemo, useRef } from 'react'
import ChartModal from './ChartModal'

// ── Formatting ────────────────────────────────────────────────────────────────

const DASH = '—'

// v is a fraction (0.153 = 15.3%). Big multi-year gains drop the decimal and get thousands separators.
export function fmtRet(v, signed = true) {
  if (v == null || isNaN(v)) return DASH
  const pct = v * 100
  const body = Math.abs(pct) >= 1000 ? Math.round(pct).toLocaleString('en-US') : pct.toFixed(Math.abs(pct) >= 100 ? 0 : 1)
  return (signed && pct > 0 ? '+' : '') + body + '%'
}

// How big a move saturates the cell colour, per period (a 1D +5% is as notable as a 10Y +500%)
const HEAT_SCALE = { '1D': 0.04, '1W': 0.07, '1M': 0.12, '3M': 0.25, '6M': 0.35, YTD: 0.5, '1Y': 0.7, '3Y': 1.5, '5Y': 2.5, '10Y': 5, LTD: 10 }
const HEAT_SCALE_ANNUAL = 0.35

export function heatStyle(v, period, annualised) {
  if (v == null || isNaN(v)) return {}
  const max = annualised ? HEAT_SCALE_ANNUAL : (HEAT_SCALE[period] ?? 0.5)
  const a = Math.min(Math.abs(v) / max, 1) * 0.55
  return { backgroundColor: v >= 0 ? `rgba(16,185,129,${a.toFixed(3)})` : `rgba(239,68,68,${a.toFixed(3)})` }
}

const textTone = v => (v == null ? 'text-gray-500' : v >= 0 ? 'text-emerald-300' : 'text-red-300')

// The value shown for a period: cumulative, or annualised for the multi-year ones when that mode is on
export function periodValue(row, period, annualised, annualisedPeriods) {
  if (annualised && annualisedPeriods.includes(period)) return row.annualised?.[period] ?? null
  return row.returns?.[period] ?? null
}

// ── Stats over the rows currently shown (mirrors holdings_perf.summarize) ─────

export function summarizeRows(rows, benchmarkValue, period, annualised, annualisedPeriods) {
  const vals = rows.map(r => periodValue(r, period, annualised, annualisedPeriods)).filter(v => v != null)
  if (!vals.length) return { n: 0 }
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return {
    n: vals.length,
    mean: vals.reduce((a, b) => a + b, 0) / vals.length,
    median: sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2,
    positive: vals.filter(v => v > 0).length / vals.length,
    beating: benchmarkValue != null ? vals.filter(v => v > benchmarkValue).length / vals.length : null,
  }
}

function toCsv(rows, periods, annualised, annualisedPeriods, asOf) {
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`
  const head = ['Symbol', 'Name', 'Sector', 'Weight %', 'Price',
    ...periods.map(p => (annualised && annualisedPeriods.includes(p) ? `${p} annualised %` : `${p} %`))]
  const lines = [head.map(esc).join(',')]
  for (const r of rows) {
    lines.push([r.symbol, r.name, r.sector ?? '', r.weight ?? '', r.price ?? '',
      ...periods.map(p => { const v = periodValue(r, p, annualised, annualisedPeriods); return v == null ? '' : (v * 100).toFixed(2) })]
      .map((c, i) => (i < 3 ? esc(c) : c)).join(','))
  }
  lines.push('', esc(`Total returns (dividends reinvested) as of ${asOf}`))
  return lines.join('\n')
}

// ── Main component ────────────────────────────────────────────────────────────

const QUICK = [['SP500', 'S&P 500'], ['NASDAQ100', 'Nasdaq-100'], ['DOW30', 'Dow 30']]

export default function HoldingsPerformance() {
  const [presets, setPresets] = useState([])
  const [selected, setSelected] = useState('SP500')
  const [etfInput, setEtfInput] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sort, setSort] = useState({ key: 'YTD', dir: 'desc' })
  const [annualised, setAnnualised] = useState(false)
  const [sector, setSector] = useState('')
  const [query, setQuery] = useState('')
  const [chartRow, setChartRow] = useState(null)
  const requestId = useRef(0)

  useEffect(() => {
    fetch('/api/holdings-performance/universes').then(r => r.json()).then(j => setPresets(j.presets || [])).catch(() => {})
  }, [])

  async function load(universe) {
    const id = ++requestId.current
    setSelected(universe)
    setLoading(true)
    setError(null)
    setData(null)
    setSector('')
    setQuery('')
    setSort({ key: 'YTD', dir: 'desc' })
    try {
      const res = await fetch(`/api/holdings-performance?universe=${encodeURIComponent(universe)}`)
      const json = await res.json()
      if (id !== requestId.current) return                     // a newer selection superseded this one
      if (!res.ok) { setError(json.detail || 'Could not load holdings.'); return }
      setData(json)
    } catch (e) {
      if (id === requestId.current) setError(e.message)
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }

  useEffect(() => { load('SP500') }, [])                       // eslint-disable-line react-hooks/exhaustive-deps

  const periods = data?.periods || []
  const annPeriods = data?.annualisedPeriods || []
  const sectors = useMemo(() => [...new Set((data?.holdings || []).map(h => h.sector).filter(Boolean))].sort(), [data])
  const hasWeights = (data?.holdings || []).some(h => h.weight != null)

  const rows = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    const filtered = data.holdings.filter(h => (!sector || h.sector === sector)
      && (!q || h.symbol.toLowerCase().includes(q) || h.name.toLowerCase().includes(q)))
    const val = r => {
      if (sort.key === 'symbol') return r.symbol
      if (sort.key === 'name') return r.name.toLowerCase()
      if (sort.key === 'sector') return (r.sector || '').toLowerCase()
      if (sort.key === 'weight') return r.weight
      return periodValue(r, sort.key, annualised, annPeriods)
    }
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      const x = val(a), y = val(b)
      if (x == null && y == null) return 0
      if (x == null) return 1                                   // missing values always sink to the bottom
      if (y == null) return -1
      return (x < y ? -1 : x > y ? 1 : 0) * dir
    })
  }, [data, sector, query, sort, annualised, annPeriods])

  function toggleSort(key) {
    setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: ['symbol', 'name', 'sector'].includes(key) ? 'asc' : 'desc' }))
  }

  function exportCsv() {
    const blob = new Blob([toCsv(rows, periods, annualised, annPeriods, data.asOf)], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.universe.id}_performance_${data.asOf}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const bench = data?.benchmark
  const benchVal = p => (bench ? periodValue(bench, p, annualised, annPeriods) : null)
  const sectorEtfs = presets.filter(p => p.kind === 'sector-etf')
  const sortMark = key => (sort.key === key ? (sort.dir === 'desc' ? ' ▼' : ' ▲') : '')
  const ariaSort = key => (sort.key === key ? (sort.dir === 'desc' ? 'descending' : 'ascending') : 'none')

  const th = 'px-2 py-1.5 text-[11px] font-semibold text-gray-400 whitespace-nowrap cursor-pointer select-none hover:text-gray-200'
  const summaryRows = data ? [
    ['Average', s => s.mean, false],
    ['Median', s => s.median, false],
    ['% up', s => s.positive, true],
    [`% beating ${bench?.symbol ?? 'benchmark'}`, s => s.beating, true],
  ] : []
  const stats = useMemo(() => Object.fromEntries(periods.map(p => [p, summarizeRows(rows, benchVal(p), p, annualised, annPeriods)])),
    [rows, periods, annualised, annPeriods, bench]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Holdings Performance</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          How every holding of an index or ETF has performed over 1 day to life-to-date, ranked by year-to-date return.
          Total returns (dividends reinvested).
        </p>
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {QUICK.map(([id, label]) => (
            <button key={id} onClick={() => load(id)} disabled={loading}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-colors disabled:opacity-60 ${selected === id
                      ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300' : 'border-gray-700 text-gray-300 hover:border-gray-500'}`}>
              {label}
            </button>
          ))}
          <select aria-label="Sector ETF" value={sectorEtfs.some(p => p.id === selected) ? selected : ''} disabled={loading}
                  onChange={e => e.target.value && load(e.target.value)}
                  className="bg-gray-800 border border-gray-700 text-gray-200 text-xs px-2 py-1.5 rounded-lg">
            <option value="">Sector ETFs…</option>
            {sectorEtfs.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <form className="flex gap-1.5 ml-auto" onSubmit={e => { e.preventDefault(); if (etfInput.trim()) load(etfInput.trim().toUpperCase()) }}>
            <input value={etfInput} onChange={e => setEtfInput(e.target.value.toUpperCase())} aria-label="ETF or index ticker"
                   placeholder="Any ETF: SPY, QQQ, ARKK…"
                   className="w-52 bg-gray-800 border border-gray-700 text-gray-100 text-xs px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500 placeholder-gray-600" />
            <button type="submit" disabled={loading || !etfInput.trim()}
                    className="px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg">
              Show holdings
            </button>
          </form>
        </div>
        {error && <div role="alert" className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>}
        {loading && (
          <div className="text-xs text-gray-500 animate-pulse">
            Downloading price history for every holding — the first load of a full index takes 30–60 seconds, then it&apos;s cached.
          </div>
        )}
      </div>

      {data && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div>
              <span className="text-base font-semibold text-gray-100">{data.universe.name}</span>
              <span className="text-gray-500 ml-2">
                {data.universe.withData} holdings with data{data.missing.length > 0 && ` (${data.missing.length} without price history)`} · as of {data.asOf}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 ml-auto print:hidden">
              <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Filter holdings" placeholder="Filter…"
                     className="w-36 bg-gray-800 border border-gray-700 text-gray-100 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500 placeholder-gray-600" />
              {sectors.length > 0 && (
                <select aria-label="Sector" value={sector} onChange={e => setSector(e.target.value)}
                        className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
                  <option value="">All sectors</option>
                  {sectors.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              )}
              <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer">
                <input type="checkbox" checked={annualised} onChange={e => setAnnualised(e.target.checked)} />
                Annualise 3Y+
              </label>
              <button onClick={exportCsv} className="px-2.5 py-1.5 border border-gray-700 text-gray-300 rounded-lg hover:border-gray-500">Export CSV</button>
            </div>
          </div>

          {data.universe.note && (
            <div className={`text-xs rounded-lg px-3 py-2 border ${data.universe.partial
              ? 'text-amber-300 bg-amber-500/10 border-amber-500/30' : 'text-gray-400 bg-gray-800/60 border-gray-700'}`}>
              {data.universe.note}
            </div>
          )}

          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-auto max-h-[75vh]" data-testid="perf-table">
            <table className="w-full text-xs border-separate border-spacing-0">
              <thead className="sticky top-0 z-20 bg-gray-900">
                <tr>
                  <th className={`${th} text-left sticky left-0 z-30 bg-gray-900`} aria-sort={ariaSort('symbol')} onClick={() => toggleSort('symbol')}>
                    Symbol{sortMark('symbol')}
                  </th>
                  <th className={`${th} text-left`} aria-sort={ariaSort('name')} onClick={() => toggleSort('name')}>Name{sortMark('name')}</th>
                  {sectors.length > 0 && <th className={`${th} text-left`} aria-sort={ariaSort('sector')} onClick={() => toggleSort('sector')}>Sector{sortMark('sector')}</th>}
                  {hasWeights && <th className={`${th} text-right`} aria-sort={ariaSort('weight')} onClick={() => toggleSort('weight')}>Weight{sortMark('weight')}</th>}
                  {periods.map(p => (
                    <th key={p} className={`${th} text-right ${sort.key === p ? 'text-emerald-300' : ''}`} aria-sort={ariaSort(p)} onClick={() => toggleSort(p)}
                        title={annualised && annPeriods.includes(p) ? `${p} annualised` : p === 'LTD' ? 'Life to date: since the first trade' : undefined}>
                      {p}{annualised && annPeriods.includes(p) ? '/yr' : ''}{sortMark(p)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bench?.symbol && (
                  <tr className="bg-sky-500/10" data-testid="benchmark-row">
                    <td className="px-2 py-1.5 font-semibold text-sky-300 sticky left-0 bg-gray-900 border-b border-gray-800">{bench.symbol}</td>
                    <td className="px-2 py-1.5 text-sky-200 border-b border-gray-800" colSpan={1 + (sectors.length > 0 ? 1 : 0) + (hasWeights ? 1 : 0)}>Benchmark</td>
                    {periods.map(p => (
                      <td key={p} className={`px-2 py-1.5 text-right font-mono border-b border-gray-800 ${textTone(benchVal(p))}`}>{fmtRet(benchVal(p))}</td>
                    ))}
                  </tr>
                )}
                {summaryRows.map(([label, pick, isShare]) => (
                  <tr key={label} className="bg-gray-800/40" data-testid="summary-row">
                    <td className="px-2 py-1 text-gray-300 sticky left-0 bg-gray-900 border-b border-gray-800">{label}</td>
                    <td className="px-2 py-1 text-gray-500 border-b border-gray-800" colSpan={1 + (sectors.length > 0 ? 1 : 0) + (hasWeights ? 1 : 0)}>
                      {rows.length} shown
                    </td>
                    {periods.map(p => {
                      const v = pick(stats[p] || { n: 0 })
                      return (
                        <td key={p} className={`px-2 py-1 text-right font-mono border-b border-gray-800 ${isShare ? 'text-gray-300' : textTone(v)}`}>
                          {v == null ? DASH : isShare ? `${Math.round(v * 100)}%` : fmtRet(v)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                {rows.map(r => (
                  <tr key={r.symbol} className="hover:bg-gray-800/40" data-testid="holding-row">
                    <td className="px-2 py-1 sticky left-0 bg-gray-900 border-b border-gray-800/60">
                      <button onClick={() => setChartRow(r)} className="font-semibold text-emerald-300 hover:underline" aria-label={`Chart ${r.symbol}`}>{r.symbol}</button>
                    </td>
                    <td className="px-2 py-1 text-gray-300 border-b border-gray-800/60 max-w-[220px] truncate" title={r.name}>{r.name}</td>
                    {sectors.length > 0 && <td className="px-2 py-1 text-gray-500 border-b border-gray-800/60 whitespace-nowrap">{r.sector || DASH}</td>}
                    {hasWeights && <td className="px-2 py-1 text-right font-mono text-gray-400 border-b border-gray-800/60">{r.weight != null ? `${r.weight.toFixed(2)}%` : DASH}</td>}
                    {periods.map(p => {
                      const v = periodValue(r, p, annualised, annPeriods)
                      return (
                        <td key={p} style={heatStyle(v, p, annualised && annPeriods.includes(p))} data-period={p}
                            className={`px-2 py-1 text-right font-mono border-b border-gray-800/60 ${textTone(v)}`}
                            title={p === 'LTD' && r.ltdSince ? `Since ${r.ltdSince}` : undefined}>
                          {fmtRet(v)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={12} className="px-3 py-6 text-center text-gray-500">No holdings match the filter.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-gray-500 px-1">
            Returns use dividend-adjusted closes. 1W is 7 calendar days, 1M/3M/6M/1Y/3Y/5Y/10Y are calendar offsets from the latest close, YTD runs from the prior
            year-end close, and LTD from the first trade (hover a LTD cell for the date). A dash means the stock hadn&apos;t been listed that long.
            Annualised figures need at least 2.5 years of history (a year for LTD). Data: Yahoo Finance; constituents from Wikipedia (S&amp;P 500) and Nasdaq.
          </p>
        </>
      )}

      {chartRow && (
        <ChartModal symbol={chartRow.symbol}
                    quote={{ symbol: chartRow.symbol, name: chartRow.name, price: chartRow.price, changePercent: chartRow.returns['1D'] != null ? chartRow.returns['1D'] * 100 : null, change: null }}
                    onClose={() => setChartRow(null)} />
      )}
    </div>
  )
}
