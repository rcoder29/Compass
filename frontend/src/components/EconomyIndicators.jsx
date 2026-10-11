import { useState, useMemo } from 'react'
import {
  useApi, PageHeader, Loading, ErrorBox, Caveats, Card, Segmented, Sparkline, TimeChart,
  fmtValue, fmtNum, signedClass, SIGNAL, RANGES, trimPoints,
} from './MacroKit'

const LEAD = { leading: 'Leads the cycle', coincident: 'Moves with the cycle', lagging: 'Lags the cycle' }
const HORIZON = { short: 'Short-term read', long: 'Long-term read', both: 'Short & long term' }
const TREND = { rising: '▲ Rising', falling: '▼ Falling', flat: '► Flat' }

export function SignalPill({ signal }) {
  const s = SIGNAL[signal] || SIGNAL.neutral
  return <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[11px] ${s.cls}`}><span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />{s.label}</span>
}

function PercentileBar({ value }) {
  return (
    <div className="flex items-center gap-2" title={`Higher than ${Math.round(value)}% of its history`}>
      <div className="relative w-20 h-1.5 bg-gray-800 rounded-full">
        <div className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-sky-400" style={{ left: `calc(${Math.min(Math.max(value, 0), 100)}% - 4px)` }} />
      </div>
      <span className="text-[11px] text-gray-400 w-7 text-right tabular-nums">{Math.round(value)}</span>
    </div>
  )
}

function changeText(v, unit) {
  if (v == null) return '—'
  const body = fmtValue(Math.abs(v), unit)
  return (v > 0 ? '+' : v < 0 ? '−' : '') + body
}

export function IndicatorDetail({ id, onClose }) {
  const { data, loading, error } = useApi(`/api/economy/indicator/${id}`)
  const [range, setRange] = useState(20)
  const points = useMemo(() => trimPoints(data?.points, range), [data, range])
  if (loading && !data) return <Card><Loading>Loading history…</Loading></Card>
  if (error) return <Card><ErrorBox>{error}</ErrorBox></Card>
  if (!data) return null
  const { meta, summary, stats } = data
  const lines = []
  if (meta.warnAbove != null) lines.push({ y: meta.warnAbove, label: `warning ${meta.warnAbove}` })
  if (meta.warnBelow != null) lines.push({ y: meta.warnBelow, label: `warning ${meta.warnBelow}` })
  if (meta.band) { lines.push({ y: meta.band[0], label: `comfort ${meta.band[0]}`, color: '#10b981' }); lines.push({ y: meta.band[1], label: `comfort ${meta.band[1]}`, color: '#10b981' }) }
  const first = points[0]?.[0]
  const bands = (data.recessions || []).filter(b => !first || b.end >= first)
  return (
    <Card className="border-sky-500/30" title={meta.name}
          right={<button onClick={onClose} className="text-gray-400 hover:text-gray-200" aria-label="Close detail">Close ✕</button>}>
      <div className="flex flex-wrap items-center gap-3 mb-3 text-xs">
        <span className="text-2xl font-semibold text-gray-100 tabular-nums">{fmtValue(summary.value, meta.unit)}</span>
        <span className="text-gray-500">as of {summary.date}</span>
        <SignalPill signal={summary.signal} />
        <span className="text-gray-400">{summary.reason}</span>
        <span className="ml-auto"><Segmented label="Chart range" options={RANGES.map(([l, y]) => [y, l])} value={range} onChange={setRange} /></span>
      </div>
      <TimeChart series={[{ name: meta.name, color: '#38bdf8', points }]} bands={bands} lines={lines} height={280}
                 format={v => fmtValue(v, meta.unit)} label={`${meta.name} history`} />
      <div className="text-[11px] text-gray-500 mt-1">Shaded areas are US recessions (NBER). Hover the chart for exact values.</div>
      <div className="grid md:grid-cols-3 gap-4 mt-4 text-xs">
        <div><div className="text-gray-300 font-medium mb-1">What it is</div><p className="text-gray-400">{meta.what}</p></div>
        <div><div className="text-gray-300 font-medium mb-1">Why it matters for markets</div><p className="text-gray-400">{meta.why}</p></div>
        <div><div className="text-gray-300 font-medium mb-1">How to read it</div><p className="text-gray-400">{meta.read}</p></div>
      </div>
      <div className="grid sm:grid-cols-4 gap-3 mt-4 text-xs">
        <Stat label="Percentile vs history" value={`${Math.round(summary.percentile)}th`} hint={`since ${summary.historyStart.slice(0, 4)}`} />
        <Stat label="10-yr z-score" value={summary.zscore10y == null ? '—' : fmtNum(summary.zscore10y)} hint="std devs from the 10-year average" />
        <Stat label="All-time range" value={`${fmtValue(stats.allTime.min, meta.unit)} to ${fmtValue(stats.allTime.max, meta.unit)}`} hint={`median ${fmtValue(stats.allTime.median, meta.unit)}`} />
        <Stat label="Type" value={LEAD[meta.lead] || meta.lead} hint={HORIZON[meta.horizon]} />
      </div>
    </Card>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="bg-gray-950/40 border border-gray-800 rounded-lg px-3 py-2">
      <div className="text-gray-500">{label}</div>
      <div className="text-gray-100 text-sm font-medium">{value}</div>
      {hint && <div className="text-[11px] text-gray-600">{hint}</div>}
    </div>
  )
}

export default function EconomyIndicators() {
  const { data, loading, error } = useApi('/api/economy/indicators')
  const [cat, setCat] = useState('all')
  const [signal, setSignal] = useState('all')
  const [lead, setLead] = useState('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)

  const rows = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.categories
      .filter(c => cat === 'all' || c.id === cat)
      .map(c => ({
        ...c,
        indicators: c.indicators.filter(i => (signal === 'all' || i.signal === signal) && (lead === 'all' || i.lead === lead)
          && (!q || i.name.toLowerCase().includes(q))),
      }))
      .filter(c => c.indicators.length)
  }, [data, cat, signal, lead, query])

  const total = data ? data.categories.reduce((n, c) => n + c.indicators.length, 0) : 0

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Economic Indicators">
        {total || 50}+ macro and micro indicators with decades of history. Each shows where it stands against its own past, where it is heading, and
        whether that has historically been supportive or cautionary for stocks. Click any row for the full history and what it means.
      </PageHeader>
      <Caveats items={[
        'Data comes from FRED (the St. Louis Fed) and is the current, revised history, not what was known at the time. Past relationships look cleaner than they were in real time.',
        '"Supportive / Cautionary" is a rule-based reading of conditions (a warning level, a comfort band, or whether the trend is moving in the direction that has historically been better for stocks). It is not a forecast.',
        'Percentile is the share of the indicator\'s whole history at or below today\'s reading. A high percentile is not automatically good: for unemployment it means rare weakness.',
      ]} />
      {loading && <Loading>Loading indicators from FRED…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-3 max-w-xl text-center text-xs" data-testid="overall-counts">
            {['supportive', 'neutral', 'cautionary'].map(k => (
              <div key={k} className={`rounded-lg border px-3 py-2 ${SIGNAL[k].cls}`}><div className="text-xl font-semibold tabular-nums">{data.overall[k]}</div>{SIGNAL[k].label}</div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select aria-label="Category" value={cat} onChange={e => setCat(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
              <option value="all">All categories</option>
              {data.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select aria-label="Signal" value={signal} onChange={e => setSignal(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
              <option value="all">Any signal</option>
              {Object.entries(SIGNAL).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <select aria-label="Timing" value={lead} onChange={e => setLead(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
              <option value="all">Leading, coincident &amp; lagging</option>
              {Object.entries(LEAD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Search indicators" placeholder="Search…"
                   className="w-44 bg-gray-800 border border-gray-700 text-gray-100 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500 placeholder-gray-600" />
            <span className="text-gray-500 ml-auto">as of {data.asOf}</span>
          </div>

          {selected && <IndicatorDetail key={selected} id={selected} onClose={() => setSelected(null)} />}

          {rows.length === 0 && <div className="text-xs text-gray-500 py-6 text-center">No indicators match those filters.</div>}
          {rows.map(c => (
            <section key={c.id} className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-x-auto" aria-label={c.name}>
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800">
                <h3 className="text-sm font-semibold text-gray-200">{c.name}</h3>
                <div className="flex gap-3 text-[11px]">
                  <span className="text-emerald-300">{c.counts.supportive} supportive</span>
                  <span className="text-gray-400">{c.counts.neutral} neutral</span>
                  <span className="text-amber-300">{c.counts.cautionary} cautionary</span>
                </div>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[11px] text-gray-500">
                    <th className="text-left px-4 py-1.5 font-medium">Indicator</th>
                    <th className="text-right px-2 font-medium">Latest</th>
                    <th className="text-right px-2 font-medium">3 mo</th>
                    <th className="text-right px-2 font-medium">1 yr</th>
                    <th className="text-left px-2 font-medium">Percentile</th>
                    <th className="text-left px-2 font-medium">Trend</th>
                    <th className="text-left px-2 font-medium">2-yr</th>
                    <th className="text-left px-2 font-medium">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {c.indicators.map(i => (
                    <tr key={i.id} onClick={() => setSelected(i.id)} tabIndex={0} onKeyDown={e => e.key === 'Enter' && setSelected(i.id)}
                        aria-label={`${i.name} details`}
                        className={`border-t border-gray-800/70 cursor-pointer hover:bg-gray-800/40 ${selected === i.id ? 'bg-sky-500/5' : ''}`}>
                      <td className="px-4 py-2">
                        <div className="text-gray-100">{i.name}{i.stale && <span className="ml-2 text-[10px] text-amber-400" title="This series hasn't updated recently">stale</span>}</div>
                        <div className="text-[11px] text-gray-500">{LEAD[i.lead]} · {HORIZON[i.horizon]}</div>
                      </td>
                      <td className="text-right px-2 tabular-nums text-gray-100">{fmtValue(i.value, i.unit)}<div className="text-[10px] text-gray-600">{i.date.slice(0, 7)}</div></td>
                      <td className={`text-right px-2 tabular-nums ${signedClass(i.change3m)}`}>{changeText(i.change3m, i.unit)}</td>
                      <td className={`text-right px-2 tabular-nums ${signedClass(i.change1y)}`}>{changeText(i.change1y, i.unit)}</td>
                      <td className="px-2"><PercentileBar value={i.percentile} /></td>
                      <td className="px-2 text-gray-300 whitespace-nowrap">{TREND[i.trend]}</td>
                      <td className="px-2"><Sparkline values={i.spark} color={i.signal === 'cautionary' ? '#fbbf24' : i.signal === 'supportive' ? '#34d399' : '#94a3b8'} /></td>
                      <td className="px-2"><SignalPill signal={i.signal} /><div className="text-[10px] text-gray-500 mt-0.5 max-w-[200px]">{i.reason}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </>
      )}
    </div>
  )
}
