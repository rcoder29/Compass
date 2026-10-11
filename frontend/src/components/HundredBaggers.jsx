import { useState, useEffect, useMemo, useRef } from 'react'
import ChartModal from './ChartModal'
import { PageHeader, Loading, ErrorBox, Caveats, Card, Segmented, fmtPct, fmtNum, DASH } from './MacroKit'

const TIER_CLS = {
  'Strong fit': 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', Promising: 'text-sky-300 bg-sky-500/10 border-sky-500/30',
  'Partial fit': 'text-gray-300 bg-gray-700/40 border-gray-600', 'Weak fit': 'text-gray-500 bg-gray-800/40 border-gray-700',
}
const CAPS = [['any', 'Any size'], [2e9, 'Under $2B'], [5e9, 'Under $5B'], [10e9, 'Under $10B'], [30e9, 'Under $30B']]

export function fmtCap(v) {
  if (v == null) return DASH
  return v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e10 ? `$${Math.round(v / 1e9)}B` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`
}

const COLS = [
  ['score', 'Score', r => r.score], ['marketCap', 'Mkt cap', r => r.marketCap], ['growthUsed', 'Growth', r => r.growthUsed],
  ['roe', 'ROE', r => r.roe], ['grossMargin', 'Gross margin', r => r.grossMargin], ['insiders', 'Insiders', r => r.insiders],
  ['debtToEquity', 'Debt/Equity', r => r.debtToEquity], ['yearsTo100x', 'Yrs to 100x*', r => r.yearsTo100x], ['traitsMet', 'Traits', r => r.traitsMet],
]

export function toCsv(rows) {
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`
  const head = ['Rank', 'Symbol', 'Name', 'Sector', 'Score', 'Tier', 'Market cap', 'Growth %', 'ROE %', 'Gross margin %', 'Insiders %', 'Debt/Equity', 'Years to 100x', 'Traits met', 'Flags']
  const pct = v => (v == null ? '' : (v * 100).toFixed(1))
  const lines = [head.map(esc).join(',')]
  rows.forEach(r => lines.push([r.rank, r.symbol, r.name, r.sector ?? '', r.score, r.tier, r.marketCap ?? '', pct(r.growthUsed), pct(r.roe), pct(r.grossMargin), pct(r.insiders),
    r.debtToEquity == null ? '' : r.debtToEquity.toFixed(2), r.yearsTo100x ?? '', `${r.traitsMet}/7`, r.flags.join('; ')].map((c, i) => (i === 1 || i === 2 || i === 3 || i === 5 || i === 14 ? esc(c) : c)).join(',')))
  return lines.join('\n')
}

function TraitDots({ traits }) {
  return (
    <span className="inline-flex gap-0.5" aria-label={`${traits.filter(t => t.met).length} of ${traits.length} traits met`}>
      {traits.map(t => <span key={t.id} title={`${t.met ? '✓' : '✗'} ${t.label}`} className={`w-1.5 h-3 rounded-sm ${t.met ? 'bg-emerald-400' : 'bg-gray-700'}`} />)}
    </span>
  )
}

function Detail({ row, names, onChart }) {
  return (
    <div className="grid lg:grid-cols-3 gap-4 text-xs px-4 py-3 bg-gray-950/40" data-testid="bagger-detail">
      <div className="lg:col-span-2 space-y-3">
        {row.summary && <p className="text-gray-400">{row.summary}{row.summary.length >= 320 ? '…' : ''}</p>}
        <table className="w-full">
          <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1 font-medium">Factor</th><th className="text-left font-medium w-40">Score</th><th className="text-right font-medium">Points</th><th className="text-left pl-3 font-medium">Why</th></tr></thead>
          <tbody>
            {Object.entries(row.factors).map(([k, f]) => (
              <tr key={k} className="border-t border-gray-800/70">
                <td className="py-1.5 text-gray-200">{names[k]}<span className="text-gray-600 ml-1">({f.weight})</span></td>
                <td><div className="h-1.5 bg-gray-800 rounded-full w-32"><div className={`h-full rounded-full ${f.missing ? 'bg-gray-600' : f.score >= 66 ? 'bg-emerald-500' : f.score >= 40 ? 'bg-sky-500' : 'bg-amber-500'}`} style={{ width: `${Math.max(f.score, 2)}%` }} /></div></td>
                <td className="text-right tabular-nums text-gray-300">{fmtNum(f.points, 1)}</td>
                <td className="pl-3 text-gray-500">{f.missing ? 'No data — scored as unknown. ' : ''}{f.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {row.capped && <p className="text-amber-300">Score capped at 60: never profitable in the years available.</p>}
      </div>
      <div className="space-y-3">
        <div>
          <div className="text-gray-300 font-medium mb-1">The math</div>
          <p className="text-gray-400">
            100x from {fmtCap(row.marketCap)} means a {fmtCap(row.capAt100x)} company.
            {row.yearsTo100x != null
              ? <> At its current growth ({fmtPct(row.growthUsed, { signed: false, digits: 0 })} a year) that takes <span className="text-gray-100">{fmtNum(row.yearsTo100x, 0)} years</span>, if growth never slowed — which it almost always does.</>
              : <> It isn&apos;t growing, so there is no path at the current pace.</>}
          </p>
        </div>
        <div>
          <div className="text-gray-300 font-medium mb-1">Traits ({row.traitsMet}/{row.traits.length})</div>
          <ul className="space-y-0.5">{row.traits.map(t => <li key={t.id} className={t.met ? 'text-emerald-300' : 'text-gray-600'}>{t.met ? '✓' : '✗'} {t.label}</li>)}</ul>
        </div>
        {row.flags.length > 0 && (
          <div><div className="text-amber-300 font-medium mb-1">Cautions</div><ul className="list-disc pl-4 text-amber-200/80 space-y-0.5">{row.flags.map(f => <li key={f}>{f}</li>)}</ul></div>
        )}
        <button onClick={() => onChart(row)} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Open chart</button>
      </div>
    </div>
  )
}

export default function HundredBaggers({ watchlist = [] }) {
  const [universe, setUniverse] = useState('SP600')
  const [universes, setUniverses] = useState([])
  const [state, setState] = useState({ data: null, error: null })
  const [tick, setTick] = useState(0)
  const [sort, setSort] = useState({ key: 'score', dir: 'desc' })
  const [minTier, setMinTier] = useState('all')
  const [maxCap, setMaxCap] = useState('any')
  const [sector, setSector] = useState('')
  const [query, setQuery] = useState('')
  const [hideFlagged, setHideFlagged] = useState(false)
  const [open, setOpen] = useState(null)
  const [chartRow, setChartRow] = useState(null)
  const req = useRef(0)

  useEffect(() => { fetch('/api/hundred-baggers/universes').then(r => r.json()).then(j => setUniverses(j.universes || [])).catch(() => {}) }, [])

  const symbols = universe === 'WATCHLIST' ? (watchlist || []).map(w => (typeof w === 'string' ? w : w.symbol)).filter(Boolean) : []
  const url = universe === 'WATCHLIST' ? (symbols.length ? `/api/hundred-baggers?symbols=${encodeURIComponent(symbols.join(','))}` : null) : `/api/hundred-baggers?universe=${universe}`

  useEffect(() => {
    if (!url) { setState({ data: null, error: null }); return undefined }
    const id = ++req.current
    let timer
    fetch(url).then(async r => {
      const j = await r.json().catch(() => ({}))
      if (id !== req.current) return
      if (!r.ok) { setState({ data: null, error: j.detail || `Request failed (${r.status})` }); return }
      setState({ data: j, error: null })
      if (j.status === 'running') timer = setTimeout(() => setTick(t => t + 1), 2000)
      else if (j.partial) timer = setTimeout(() => setTick(t => t + 1), Math.max(j.partial.retryInSeconds, 5) * 1000 + 2000)
    }).catch(e => { if (id === req.current) setState({ data: null, error: e.message }) })
    return () => clearTimeout(timer)
  }, [url, tick])

  const pick = u => { setUniverse(u); setState({ data: null, error: null }); setOpen(null); setSector(''); setQuery('') }
  const { data, error } = state
  const ready = data?.status === 'ready'
  const names = data?.factorNames || {}
  const sectors = useMemo(() => (ready ? [...new Set(data.rows.map(r => r.sector).filter(Boolean))].sort() : []), [data, ready])

  const rows = useMemo(() => {
    if (!ready) return []
    const q = query.trim().toLowerCase()
    const tierMin = { all: 0, promising: 55, strong: 70 }[minTier]
    const col = COLS.find(c => c[0] === sort.key)
    const dir = sort.dir === 'asc' ? 1 : -1
    return data.rows
      .filter(r => r.score >= tierMin && (maxCap === 'any' || (r.marketCap != null && r.marketCap < maxCap)) && (!sector || r.sector === sector)
        && (!hideFlagged || r.flags.length === 0) && (!q || r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)))
      .sort((a, b) => {
        const x = col ? col[2](a) : a.score, y = col ? col[2](b) : b.score
        if (x == null && y == null) return 0
        if (x == null) return 1
        if (y == null) return -1
        return (x < y ? -1 : x > y ? 1 : 0) * dir
      })
  }, [data, ready, query, minTier, maxCap, sector, hideFlagged, sort])

  const toggleSort = key => setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: key === 'debtToEquity' || key === 'yearsTo100x' || key === 'marketCap' ? 'asc' : 'desc' }))
  const mark = key => (sort.key === key ? (sort.dir === 'desc' ? ' ▼' : ' ▲') : '')

  function exportCsv() {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv' }))
    a.download = `100-bagger-screen-${data.universe.id.slice(0, 12)}.csv`
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href)
  }

  const timeline = [[10, 0.5849], [15, 0.3593], [20, 0.2589], [25, 0.2023], [30, 0.1659]]
  const th = 'px-2 py-1.5 text-[11px] font-semibold text-gray-400 whitespace-nowrap cursor-pointer select-none hover:text-gray-200'

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="100-Bagger Finder">
        Screens for stocks that share the traits of past 100x compounders: small to start with, growing fast, earning high returns on capital, run by owners,
        with a sound balance sheet and a price that hasn&apos;t already assumed perfection. It scores traits; it does not predict winners.
      </PageHeader>

      <Card title="The arithmetic of a 100-bagger">
        <div className="flex flex-wrap gap-x-8 gap-y-2 text-xs">
          {timeline.map(([y, c]) => <div key={y}><span className="text-lg font-semibold text-gray-100 tabular-nums">{fmtPct(c, { signed: false, digits: 0 })}</span><span className="text-gray-500"> a year for {y} years</span></div>)}
        </div>
        <p className="text-[11px] text-gray-500 mt-2">Growth that high, sustained that long, is rare, and the company has to still be small enough: a $50B company would need to become a $5T one. Most stocks that look like this never get there; many 100-baggers looked ordinary at the start.</p>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Universe" options={[...universes.map(u => [u.id, u.name]), ['WATCHLIST', 'My watchlist']]} value={universe} onChange={pick} />
        {universes.find(u => u.id === universe) && <span className="text-xs text-gray-500">{universes.find(u => u.id === universe).blurb}</span>}
      </div>

      {universe === 'WATCHLIST' && symbols.length === 0 && <div className="text-xs text-gray-500">Your watchlist is empty. Add tickers in the header to screen them here.</div>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {!data && !error && url && <Loading>Starting the scan…</Loading>}
      {data?.status === 'running' && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4" role="status">
          <div className="flex justify-between text-xs text-gray-400 mb-2"><span>Reading fundamentals for {data.universe.name}…</span><span className="tabular-nums">{data.progress.done} / {data.progress.total}</span></div>
          <div className="h-2 bg-gray-800 rounded-full"><div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${(data.progress.done / Math.max(data.progress.total, 1)) * 100}%` }} /></div>
          <p className="text-[11px] text-gray-500 mt-2">The first scan of a universe takes about a minute; after that the data is cached for a day.</p>
        </div>
      )}

      {ready && (
        <>
          {data.partial && <div role="note" className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">{data.partial.note}</div>}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {Object.entries(data.tierCounts).map(([t, n]) => <span key={t} className={`px-2.5 py-1 rounded-full border ${TIER_CLS[t]}`}>{n} {t.toLowerCase()}</span>)}
            <span className="text-gray-500 ml-2">{data.counts.scored} scored{data.counts.tooBig > 0 && ` · ${data.counts.tooBig} left out as too large for 100x`}{data.counts.noData > 0 && ` · ${data.counts.noData} without data`}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Filter stocks" placeholder="Filter…" className="w-36 bg-gray-800 border border-gray-700 text-gray-100 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500 placeholder-gray-600" />
            <select aria-label="Minimum fit" value={minTier} onChange={e => setMinTier(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
              <option value="all">Any fit</option><option value="promising">Promising or better (55+)</option><option value="strong">Strong fit (70+)</option>
            </select>
            <select aria-label="Market cap" value={maxCap} onChange={e => setMaxCap(e.target.value === 'any' ? 'any' : Number(e.target.value))} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
              {CAPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            {sectors.length > 0 && (
              <select aria-label="Sector" value={sector} onChange={e => setSector(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
                <option value="">All sectors</option>{sectors.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
            <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer"><input type="checkbox" checked={hideFlagged} onChange={e => setHideFlagged(e.target.checked)} />Hide stocks with cautions</label>
            <span className="text-gray-500 ml-auto">{rows.length} shown</span>
            <button onClick={exportCsv} className="px-2.5 py-1.5 border border-gray-700 text-gray-300 rounded-lg hover:border-gray-500">Export CSV</button>
          </div>

          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-auto max-h-[75vh]" data-testid="bagger-table">
            <table className="w-full text-xs border-separate border-spacing-0">
              <thead className="sticky top-0 z-10 bg-gray-900">
                <tr>
                  <th className={`${th} text-left`}>#</th><th className={`${th} text-left`}>Stock</th>
                  {COLS.map(([k, label]) => <th key={k} className={`${th} text-right ${sort.key === k ? 'text-emerald-300' : ''}`} onClick={() => toggleSort(k)} aria-sort={sort.key === k ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>{label}{mark(k)}</th>)}
                  <th className={`${th} text-left`}>Fit</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={COLS.length + 3} className="text-center text-gray-500 py-8">No stocks match those filters.</td></tr>}
                {rows.map(r => (
                  <FragmentRow key={r.symbol} r={r} isOpen={open === r.symbol} onToggle={() => setOpen(open === r.symbol ? null : r.symbol)} names={names} onChart={setChartRow} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-gray-500">* Years to 100x if growth continued at its current rate (revenue growth blended over several years and the latest year, capped at 50%). Traits (left to right): under $10B, growth 20%+, ROE 15%+, gross margin 40%+, low debt, insiders own 10%+, not priced for perfection. Click a row for the full breakdown.</p>
          <Caveats title="How the score works, and its limits" items={[
            'Seven traits are scored 0-100 on fixed thresholds and weighted: room to grow 20, growth 25, return on equity 15, margins 10, balance sheet 10, owner-operators 10, valuation vs growth 10. A company that has never been profitable is capped at 60.',
            'It is a screen for traits, not a forecast. Yahoo\'s figures can be stale or restated, and growth, ROE and margins can all be flattered by one good year.',
            'The S&P indexes only include profitable, established companies, so the true micro-cap 100-baggers of the future are mostly not in these lists. Use "My watchlist" to screen any ticker you find.',
            'Not investment advice. Concentrated small-cap bets can lose most of their value.',
          ]} />
        </>
      )}

      {chartRow && <ChartModal symbol={chartRow.symbol} quote={{ symbol: chartRow.symbol, name: chartRow.name, price: chartRow.price, changePercent: null, change: null }} onClose={() => setChartRow(null)} />}
    </div>
  )
}

function FragmentRow({ r, isOpen, onToggle, names, onChart }) {
  return (
    <>
      <tr onClick={onToggle} onKeyDown={e => e.key === 'Enter' && onToggle()} tabIndex={0} aria-expanded={isOpen} aria-label={`${r.symbol} details`} data-testid="bagger-row"
          className={`cursor-pointer hover:bg-gray-800/40 ${isOpen ? 'bg-sky-500/5' : ''}`}>
        <td className="px-2 py-2 text-gray-500 tabular-nums border-t border-gray-800/60">{r.rank}</td>
        <td className="px-2 py-2 border-t border-gray-800/60 min-w-[190px]">
          <span className="text-gray-100 font-medium">{r.symbol}</span> <span className="text-gray-400">{r.name}</span>
          <div className="text-[11px] text-gray-600">{r.sector}{r.flags.length > 0 && <span className="text-amber-400 ml-2" title={r.flags.join('; ')}>⚠ {r.flags.length}</span>}</div>
        </td>
        <td className="px-2 py-2 text-right border-t border-gray-800/60">
          <div className="inline-flex items-center gap-2"><div className="w-14 h-1.5 bg-gray-800 rounded-full"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${r.score}%` }} /></div><span className="tabular-nums text-gray-100 w-9 text-right font-semibold">{r.score.toFixed(0)}</span></div>
        </td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{fmtCap(r.marketCap)}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{fmtPct(r.growthUsed, { signed: false, digits: 0 })}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{fmtPct(r.roe, { signed: false, digits: 0 })}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{fmtPct(r.grossMargin, { signed: false, digits: 0 })}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{fmtPct(r.insiders, { signed: false, digits: 0 })}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{r.debtToEquity == null ? DASH : fmtNum(r.debtToEquity, 1)}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-200 border-t border-gray-800/60">{r.yearsTo100x == null ? DASH : fmtNum(r.yearsTo100x, 0)}</td>
        <td className="px-2 py-2 text-right border-t border-gray-800/60"><TraitDots traits={r.traits} /></td>
        <td className="px-2 py-2 border-t border-gray-800/60"><span className={`px-2 py-0.5 rounded-full border text-[11px] whitespace-nowrap ${TIER_CLS[r.tier]}`}>{r.tier}</span></td>
      </tr>
      {isOpen && <tr><td colSpan={COLS.length + 3} className="border-t border-gray-800/60"><Detail row={r} names={names} onChart={onChart} /></td></tr>}
    </>
  )
}
