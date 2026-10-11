import { useState, useMemo } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, Segmented, fmtPct, fmtNum, signedClass, heat } from './MacroKit'

const HEAT_SCALE = { '1D': 0.03, '1W': 0.05, '1M': 0.1, '3M': 0.2, '6M': 0.3, YTD: 0.4, '1Y': 0.5, '3Y': 1.0, '5Y': 1.5, '10Y': 3, LTD: 8 }
const ANNUAL = ['3Y', '5Y', '10Y', 'LTD']

export function cellValue(row, period, mode, annualised) {
  if (mode === 'excess') return row.excess?.[period] ?? null
  const r = row.returns?.[period]
  if (!r) return null
  return annualised && ANNUAL.includes(period) ? r.annualised : r.total
}

function LeaderBars({ rows, period, mode, annualised }) {
  const vals = rows.map(r => ({ r, v: cellValue(r, period, mode, annualised) })).filter(x => x.v != null).sort((a, b) => b.v - a.v)
  const max = Math.max(...vals.map(x => Math.abs(x.v)), 0.0001)
  return (
    <ul className="space-y-1" aria-label={`Sectors ranked by ${period} ${mode === 'excess' ? 'excess return' : 'return'}`}>
      {vals.map(({ r, v }) => (
        <li key={r.symbol} className="flex items-center gap-2 text-xs">
          <span className="w-36 truncate text-gray-300">{r.name}</span>
          <div className="flex-1 h-3 relative">
            <div className="absolute inset-y-0 left-1/2 w-px bg-gray-700" />
            <div className={`absolute h-full rounded-sm ${v >= 0 ? 'bg-emerald-500/70' : 'bg-red-500/70'}`}
                 style={v >= 0 ? { left: '50%', width: `${(v / max) * 50}%` } : { right: '50%', width: `${(-v / max) * 50}%` }} />
          </div>
          <span className={`w-16 text-right tabular-nums ${signedClass(v)}`}>{fmtPct(v)}</span>
        </li>
      ))}
    </ul>
  )
}

export default function SectorScoreboard({ onOpenHoldings }) {
  const { data, loading, error } = useApi('/api/sectors/scoreboard')
  const [view, setView] = useState('returns')
  const [mode, setMode] = useState('total')
  const [annualised, setAnnualised] = useState(false)
  const [sort, setSort] = useState({ key: 'YTD', dir: 'desc' })
  const [barPeriod, setBarPeriod] = useState('3M')

  const rows = useMemo(() => {
    if (!data) return []
    const val = r => {
      if (sort.key === 'name') return r.name
      if (view === 'risk') return r.risk?.[sort.key] ?? null
      if (view === 'calendar') return r.calendar?.[sort.key] ?? null
      return cellValue(r, sort.key, mode, annualised)
    }
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...data.sectors].sort((a, b) => {
      const x = val(a), y = val(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      return (x < y ? -1 : x > y ? 1 : 0) * dir
    })
  }, [data, sort, view, mode, annualised])

  const toggleSort = key => setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: key === 'name' ? 'asc' : 'desc' }))
  const mark = key => (sort.key === key ? (sort.dir === 'desc' ? ' ▼' : ' ▲') : '')
  const th = 'px-2 py-1.5 text-[11px] font-semibold text-gray-400 whitespace-nowrap cursor-pointer select-none hover:text-gray-200'
  const years = data ? Object.keys(data.benchmark.calendar) : []
  const RISK_COLS = [['volatility', 'Volatility', v => fmtPct(v, { signed: false })], ['maxDrawdown', 'Max drawdown', v => fmtPct(v, { signed: false })],
    ['returnPerRisk', 'Return / risk', v => fmtNum(v)], ['beta', 'Beta', v => fmtNum(v)], ['upCapture', 'Up capture', v => fmtNum(v)], ['downCapture', 'Down capture', v => fmtNum(v)]]

  const benchRows = data ? [data.benchmark, data.equalWeight].filter(Boolean) : []
  const benchCell = (b, p) => (mode === 'excess' ? null : cellValue(b, p, 'total', annualised))

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Sector Scoreboard">
        The eleven S&amp;P 500 sector ETFs against SPY over every horizon from one day to life-to-date, with risk measures and calendar-year results.
        Click a column to sort; click a sector to see its holdings.
      </PageHeader>
      {loading && <Loading>Loading sector price history…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Segmented label="View" options={[['returns', 'Returns'], ['risk', 'Risk'], ['calendar', 'Calendar years']]} value={view}
                       onChange={v => { setView(v); setSort({ key: v === 'returns' ? 'YTD' : v === 'risk' ? 'returnPerRisk' : years[years.length - 1], dir: 'desc' }) }} />
            {view === 'returns' && (
              <>
                <Segmented label="Measure" options={[['total', 'Total return'], ['excess', 'vs SPY']]} value={mode} onChange={setMode} />
                <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer"><input type="checkbox" checked={annualised} onChange={e => setAnnualised(e.target.checked)} disabled={mode === 'excess'} />Annualise 3Y+</label>
              </>
            )}
            <span className="ml-auto text-gray-500">as of {data.asOf}</span>
          </div>

          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-auto" data-testid="scoreboard-table">
            <table className="w-full text-xs border-separate border-spacing-0">
              <thead className="bg-gray-900">
                <tr>
                  <th className={`${th} text-left`} onClick={() => toggleSort('name')} aria-sort={sort.key === 'name' ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>Sector{mark('name')}</th>
                  {view === 'returns' && data.periods.map(p => (
                    <th key={p} className={`${th} text-right ${sort.key === p ? 'text-emerald-300' : ''}`} onClick={() => toggleSort(p)} aria-sort={sort.key === p ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      {p}{annualised && mode === 'total' && ANNUAL.includes(p) ? '/yr' : ''}{mark(p)}
                    </th>
                  ))}
                  {view === 'risk' && RISK_COLS.map(([k, label]) => <th key={k} className={`${th} text-right ${sort.key === k ? 'text-emerald-300' : ''}`} onClick={() => toggleSort(k)}>{label}{mark(k)}</th>)}
                  {view === 'calendar' && years.map(y => <th key={y} className={`${th} text-right ${sort.key === y ? 'text-emerald-300' : ''}`} onClick={() => toggleSort(y)}>{y === years[years.length - 1] ? `${y} YTD` : y}{mark(y)}</th>)}
                  <th className={th} />
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.symbol} className="hover:bg-gray-800/40">
                    <td className="px-2 py-1.5 whitespace-nowrap border-t border-gray-800/60"><span className="text-gray-100">{r.name}</span> <span className="text-gray-500">{r.symbol}</span></td>
                    {view === 'returns' && data.periods.map(p => {
                      const v = cellValue(r, p, mode, annualised)
                      return <td key={p} className={`px-2 py-1.5 text-right tabular-nums border-t border-gray-800/60 ${signedClass(v)}`} style={heat(v, annualised && ANNUAL.includes(p) && mode === 'total' ? 0.3 : HEAT_SCALE[p] * (mode === 'excess' ? 0.5 : 1))}>{fmtPct(v)}</td>
                    })}
                    {view === 'risk' && RISK_COLS.map(([k, , f]) => <td key={k} className="px-2 py-1.5 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{f(r.risk?.[k])}</td>)}
                    {view === 'calendar' && years.map(y => <td key={y} className={`px-2 py-1.5 text-right tabular-nums border-t border-gray-800/60 ${signedClass(r.calendar[y])}`} style={heat(r.calendar[y], 0.4)}>{fmtPct(r.calendar[y], { digits: 0 })}</td>)}
                    <td className="px-2 py-1.5 border-t border-gray-800/60"><button onClick={() => onOpenHoldings?.(r.symbol)} className="text-[11px] text-sky-400 hover:text-sky-300 whitespace-nowrap">Holdings →</button></td>
                  </tr>
                ))}
                {benchRows.map(b => (
                  <tr key={b.symbol} className="bg-gray-950/40">
                    <td className="px-2 py-1.5 whitespace-nowrap border-t border-gray-700 text-gray-300">{b.name}</td>
                    {view === 'returns' && data.periods.map(p => <td key={p} className={`px-2 py-1.5 text-right tabular-nums border-t border-gray-700 ${signedClass(benchCell(b, p))}`}>{mode === 'excess' ? '' : fmtPct(benchCell(b, p))}</td>)}
                    {view === 'risk' && RISK_COLS.map(([k, , f]) => <td key={k} className="px-2 py-1.5 text-right tabular-nums text-gray-400 border-t border-gray-700">{b.risk ? f(b.risk[k]) : ''}</td>)}
                    {view === 'calendar' && years.map(y => <td key={y} className={`px-2 py-1.5 text-right tabular-nums border-t border-gray-700 ${signedClass(b.calendar?.[y])}`}>{fmtPct(b.calendar?.[y], { digits: 0 })}</td>)}
                    <td className="border-t border-gray-700" />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {view === 'risk' && (
            <p className="text-[11px] text-gray-500">Volatility, return/risk, beta and capture use the trailing 3 years of monthly returns (a sector with a shorter life uses what it has). Max drawdown is the worst peak-to-trough decline over the same 3 years of daily prices. Return/risk is annualised return divided by volatility. Up/down capture: how much of SPY&apos;s gains and losses the sector participated in.</p>
          )}

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title="Leaders and laggards" right={<Segmented label="Bar period" options={['1W', '1M', '3M', '6M', 'YTD', '1Y'].map(p => [p, p])} value={barPeriod} onChange={setBarPeriod} />}>
              <LeaderBars rows={data.sectors} period={barPeriod} mode={mode} annualised={false} />
              <p className="text-[11px] text-gray-600 mt-2">{mode === 'excess' ? 'Excess return versus SPY.' : 'Total return.'} Switch the table to “vs SPY” to rank by relative performance.</p>
            </Card>
            <Card title="Relative strength vs SPY" right="change in sector ÷ SPY">
              <table className="w-full text-xs">
                <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1 font-medium">Sector</th>{['1M', '3M', '6M', '1Y'].map(p => <th key={p} className="text-right font-medium">{p}</th>)}<th className="text-right font-medium">Trend</th></tr></thead>
                <tbody>
                  {[...data.sectors].sort((a, b) => (b.rsChange['3M'] ?? -9) - (a.rsChange['3M'] ?? -9)).map(r => (
                    <tr key={r.symbol} className="border-t border-gray-800/70">
                      <td className="py-1 text-gray-200">{r.name}</td>
                      {['1M', '3M', '6M', '1Y'].map(p => <td key={p} className={`text-right tabular-nums ${signedClass(r.rsChange[p])}`}>{fmtPct(r.rsChange[p])}</td>)}
                      <td className="text-right text-[11px] text-gray-400">{r.trend.above200 == null ? '—' : r.trend.above200 ? (r.trend.ma50Above200 ? 'Uptrend' : 'Recovering') : (r.trend.ma50Above200 ? 'Pullback' : 'Downtrend')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[11px] text-gray-600 mt-2">Trend: price vs its 50- and 200-day averages.</p>
            </Card>
          </div>
          <Caveats title="Notes" items={data.notes} />
        </>
      )}
    </div>
  )
}
