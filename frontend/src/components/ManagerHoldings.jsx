import { useState, useMemo } from 'react'
import ChartModal from './ChartModal'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, TimeChart, Sparkline, fmtPct, fmtNum, signedClass, DASH } from './MacroKit'

export function fmtUsd(v) {
  if (v == null) return DASH
  const a = Math.abs(v)
  return a >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : a >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : a >= 1e6 ? `$${Math.round(v / 1e6)}M` : `$${Math.round(v / 1e3)}K`
}
export const fmtShares = v => (v == null ? DASH : Math.abs(v) >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : Math.abs(v) >= 1e3 ? `${Math.round(v / 1e3)}K` : String(Math.round(v)))
const fmtDate = d => (d ? new Date(d.length === 7 ? `${d}-01T00:00:00Z` : `${d}T00:00:00Z`).toLocaleDateString('en-US', { year: 'numeric', month: d.length === 7 ? 'short' : 'short', day: d.length === 7 ? undefined : 'numeric', timeZone: 'UTC' }) : DASH)

const STATUS = {
  new: { label: 'New', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/30' },
  added: { label: 'Added', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' },
  reduced: { label: 'Reduced', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
  unchanged: { label: 'Unchanged', cls: 'text-gray-400 bg-gray-800/50 border-gray-700' },
  unknown: { label: DASH, cls: 'text-gray-500 border-transparent' },
}
const ACTION = {
  owns: { label: 'Owns', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' },
  bought: { label: 'Bought', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/30' },
  added: { label: 'Added', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/30' },
  trimmed: { label: 'Trimmed', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
  sold: { label: 'Sold', cls: 'text-red-300 bg-red-500/10 border-red-500/30' },
  other: { label: 'Note', cls: 'text-gray-300 bg-gray-800/50 border-gray-700' },
}
const CONFIDENCE = { primary: 'His own words', secondary: 'Reported by others', user: 'Added by you' }

function Badge({ cls, children }) {
  return <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-medium whitespace-nowrap ${cls}`}>{children}</span>
}

export function toCsv(rows) {
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`
  const lines = [['Rank', 'Ticker', 'Name', 'Value', 'Weight %', 'Shares', 'Status', 'Share change %', 'Return since quarter end %'].map(esc).join(',')]
  rows.forEach(r => lines.push([r.rank, esc(r.ticker ?? ''), esc(r.name), r.value, (r.weight * 100).toFixed(2), r.shares, r.status,
    r.sharesChangePct == null ? '' : (r.sharesChangePct * 100).toFixed(1), r.retSinceQE == null ? '' : (r.retSinceQE * 100).toFixed(1)].join(',')))
  return lines.join('\n')
}

function Stat({ label, value, sub, cls = 'text-gray-100' }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl px-3 py-2.5">
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${cls}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function Names({ title, items, render }) {
  return (
    <div>
      <div className="text-[11px] font-semibold text-gray-400 mb-1">{title}</div>
      {items.length === 0 ? <div className="text-xs text-gray-600">None</div> : <ul className="space-y-0.5">{items.map(i => <li key={i.cusip} className="text-xs text-gray-300">{render(i)}</li>)}</ul>}
    </div>
  )
}

function Report({ d, onChart }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const { summary: s, filing: f, performance: perf } = d
  const rows = useMemo(() => d.positions.filter(r => (filter === 'all' || r.status === filter)
    && (!query.trim() || `${r.ticker ?? ''} ${r.name}`.toLowerCase().includes(query.trim().toLowerCase()))), [d, filter, query])
  const label = r => (r.ticker ? <><b className="text-gray-100">{r.ticker}</b> <span className="text-gray-500">{r.name}</span></> : <span className="text-gray-300">{r.name}</span>)
  const sinceQE = perf?.sinceQE, bench = perf?.benchmark?.sinceQE
  const series = d.history.series

  function exportCsv() {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv' }))
    a.download = `${d.manager.id}-13f-${f.period}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="space-y-4">
      <div className="text-xs text-gray-400">
        Quarter ended <b className="text-gray-200">{fmtDate(f.period)}</b>, filed <b className="text-gray-200">{fmtDate(f.filed)}</b> ({f.daysSinceFiled} days ago) ·{' '}
        <a className="text-sky-400 hover:underline" href={f.url} target="_blank" rel="noreferrer">SEC filing</a>
        {f.amendments.length > 0 && <> · {f.amendments.length} amendment{f.amendments.length === 1 ? '' : 's'} included</>}
        {' '}· next report due by <b className="text-gray-200">{fmtDate(f.nextExpected)}</b>
      </div>

      {f.stale && (
        <div role="status" className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
          This is the latest filing on record, and the next one is overdue (it was due {fmtDate(f.nextExpected)}). The manager may have stopped filing, so these holdings could be well out of date.
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Reported portfolio" value={fmtUsd(s.totalValue)} sub={s.valueChangePct == null ? null : `${fmtPct(s.valueChangePct)} vs prior quarter`} />
        <Stat label="Positions" value={s.positions} sub={`Top 5 = ${fmtPct(s.top5, { signed: false, digits: 0 })} · top 10 = ${fmtPct(s.top10, { signed: false, digits: 0 })}`} />
        <Stat label="Largest position" value={fmtPct(s.largestWeight, { signed: false, digits: 1 })} sub={d.positions[0] ? (d.positions[0].ticker || d.positions[0].name) : null} />
        <Stat label="Since quarter end" value={sinceQE ? fmtPct(sinceQE.return) : DASH} cls={signedClass(sinceQE?.return)}
          sub={sinceQE ? `S&P 500 ETF ${fmtPct(bench)} · ${fmtPct(sinceQE.coverage, { signed: false, digits: 0 })} of value priced` : 'No prices available'} />
      </div>

      <Card title="What changed last quarter" right={f.previousPeriod ? `vs ${fmtDate(f.previousPeriod)}` : null}>
        {!f.previousPeriod ? <div className="text-xs text-gray-500">Only one quarter on record, so there is nothing to compare.</div> : (
          <div className="grid md:grid-cols-4 gap-4">
            <Names title={`New (${s.counts.new})`} items={d.highlights.new} render={r => <>{label(r)} <span className="text-gray-500">{fmtPct(r.weight, { signed: false })}</span></>} />
            <Names title={`Added to (${s.counts.added})`} items={d.highlights.added} render={r => <>{label(r)} <span className="text-emerald-300">{fmtPct(r.sharesChangePct, { digits: 0 })}</span></>} />
            <Names title={`Reduced (${s.counts.reduced})`} items={d.highlights.reduced} render={r => <>{label(r)} <span className="text-amber-300">{fmtPct(r.sharesChangePct, { digits: 0 })}</span></>} />
            <Names title={`Sold out (${s.counts.exited})`} items={d.exited.slice(0, 8)} render={r => <>{label(r)} <span className="text-gray-500">was {fmtPct(r.prevWeight, { signed: false })}</span></>} />
          </div>
        )}
      </Card>

      <Card title="Holdings" right={`${rows.length} of ${d.positions.length}${d.otherPositions ? ` (+${d.otherPositions} smaller not shown)` : ''}`}>
        <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
          {['all', 'new', 'added', 'reduced', 'unchanged'].map(k => (
            <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
              className={`px-2.5 py-1 rounded-lg border ${filter === k ? 'border-sky-500/60 text-sky-300 bg-sky-500/10' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {k === 'all' ? 'All' : STATUS[k].label}
            </button>
          ))}
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a holding" aria-label="Find a holding"
            className="ml-auto bg-gray-900 border border-gray-700 rounded-lg px-2.5 py-1 text-gray-200 placeholder-gray-600 w-40" />
          <button onClick={exportCsv} className="px-2.5 py-1 rounded-lg border border-gray-700 text-gray-400 hover:border-gray-500">Export CSV</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] text-gray-400 border-b border-gray-800">
                <th className="px-2 py-1.5">#</th><th className="px-2 py-1.5">Holding</th><th className="px-2 py-1.5">Weight</th><th className="px-2 py-1.5">Value</th>
                <th className="px-2 py-1.5">Shares</th><th className="px-2 py-1.5">Last quarter</th><th className="px-2 py-1.5">Since quarter end</th>
                <th className="px-2 py-1.5" title="Shares held at each of the last quarters, oldest to newest">Shares, 6 quarters</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.cusip} className="border-b border-gray-800/60 hover:bg-gray-800/30">
                  <td className="px-2 py-1.5 text-gray-500 tabular-nums">{r.rank}</td>
                  <td className="px-2 py-1.5">
                    {r.ticker ? <button onClick={() => onChart(r)} className="text-left hover:underline">{label(r)}</button> : label(r)}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums">
                    <div className="flex items-center gap-2"><span className="w-12 text-right text-gray-200">{fmtPct(r.weight, { signed: false })}</span>
                      <div className="w-16 h-1.5 bg-gray-800 rounded-full"><div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.min(r.weight / (d.positions[0]?.weight || 1), 1) * 100}%` }} /></div></div>
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-gray-300">{fmtUsd(r.value)}</td>
                  <td className="px-2 py-1.5 tabular-nums text-gray-300">{fmtShares(r.shares)}</td>
                  <td className="px-2 py-1.5">
                    <Badge cls={STATUS[r.status].cls}>{STATUS[r.status].label}</Badge>
                    {r.sharesChangePct != null && r.status !== 'unchanged' && <span className={`ml-1.5 tabular-nums ${signedClass(r.sharesChangePct)}`}>{fmtPct(r.sharesChangePct, { digits: 0 })}</span>}
                  </td>
                  <td className={`px-2 py-1.5 tabular-nums ${signedClass(r.retSinceQE)}`}>{fmtPct(r.retSinceQE)}</td>
                  <td className="px-2 py-1.5"><Sparkline values={r.history} width={72} height={18} /></td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={8} className="px-2 py-6 text-center text-gray-500">No holdings match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      {series.length > 1 && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card title="Reported portfolio value"><TimeChart label="Reported portfolio value" height={160} series={[{ name: 'Value', color: '#38bdf8', points: series.map(p => [p.period, p.totalValue]) }]} format={fmtUsd} /></Card>
          <Card title="Share of portfolio in the top 5"><TimeChart label="Top 5 weight" height={160} series={[{ name: 'Top 5', color: '#f59e0b', points: series.map(p => [p.period, p.top5]) }]} format={v => fmtPct(v, { signed: false, digits: 0 })} /></Card>
        </div>
      )}
    </div>
  )
}

const BLANK = { symbol: '', action: 'owns', asOf: '', note: '', sourceTitle: '', sourceUrl: '' }

function Disclosed({ d, onChart, reload }) {
  const [form, setForm] = useState(BLANK)
  const [adding, setAdding] = useState(false)
  const [err, setErr] = useState(null)
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setErr(null)
    const body = { ...form, symbol: form.symbol || null, asOf: form.asOf || null, note: form.note || null, sourceTitle: form.sourceTitle || null, sourceUrl: form.sourceUrl || null }
    const r = await fetch(`/api/managers/${d.manager.id}/disclosures`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    if (!r.ok) { setErr((await r.json().catch(() => ({}))).detail || `Request failed (${r.status})`); return }
    setForm(BLANK); setAdding(false); reload()
  }
  async function remove(id) {
    await fetch(`/api/managers/${d.manager.id}/disclosures/${id}`, { method: 'DELETE' })
    reload()
  }
  const inp = 'bg-gray-900 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-200 placeholder-gray-600'

  return (
    <div className="space-y-4">
      <Card title="Positions stated publicly" right="Each row links to where it was said">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[11px] text-gray-400 border-b border-gray-800">
              <th className="px-2 py-1.5">Holding</th><th className="px-2 py-1.5">Said</th><th className="px-2 py-1.5">As of</th><th className="px-2 py-1.5">Price</th>
              <th className="px-2 py-1.5">1 year</th><th className="px-2 py-1.5">What was said</th><th className="px-2 py-1.5">Source</th><th />
            </tr></thead>
            <tbody>
              {d.positions.map(p => (
                <tr key={p.id} className="border-b border-gray-800/60 align-top hover:bg-gray-800/30">
                  <td className="px-2 py-1.5"><button onClick={() => onChart(p)} className="text-left hover:underline"><b className="text-gray-100">{p.symbol}</b> <span className="text-gray-500">{p.name}</span></button></td>
                  <td className="px-2 py-1.5"><Badge cls={(ACTION[p.action] || ACTION.other).cls}>{(ACTION[p.action] || ACTION.other).label}</Badge></td>
                  <td className="px-2 py-1.5 text-gray-300 whitespace-nowrap">{fmtDate(p.asOf)}</td>
                  <td className="px-2 py-1.5 tabular-nums text-gray-300">{p.price == null ? DASH : `$${fmtNum(p.price, 2)}`}</td>
                  <td className={`px-2 py-1.5 tabular-nums ${signedClass(p.ret1y)}`}>{fmtPct(p.ret1y)}</td>
                  <td className="px-2 py-1.5 text-gray-400 max-w-sm">{p.note}</td>
                  <td className="px-2 py-1.5 text-[11px]">
                    {p.sourceUrl ? <a className="text-sky-400 hover:underline" href={p.sourceUrl} target="_blank" rel="noreferrer">{p.sourceTitle || 'Source'}</a> : <span className="text-gray-600">No source</span>}
                    <div className="text-gray-600">{CONFIDENCE[p.confidence] || p.confidence}</div>
                  </td>
                  <td className="px-2 py-1.5"><button onClick={() => remove(p.id)} aria-label={`Remove ${p.symbol}`} className="text-gray-600 hover:text-red-400">✕</button></td>
                </tr>
              ))}
              {d.positions.length === 0 && <tr><td colSpan={8} className="px-2 py-6 text-center text-gray-500">Nothing logged yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      {d.approach.length > 0 && (
        <Card title="Stated approach">
          <ul className="space-y-2">{d.approach.map(a => (
            <li key={a.id} className="text-xs text-gray-300 flex gap-3 justify-between">
              <span>{a.note} <span className="text-gray-600">· {CONFIDENCE[a.confidence] || a.confidence}</span>
                {a.sourceUrl && <> · <a className="text-sky-400 hover:underline" href={a.sourceUrl} target="_blank" rel="noreferrer">{a.sourceTitle || 'Source'}</a></>}</span>
              <button onClick={() => remove(a.id)} aria-label="Remove this note" className="text-gray-600 hover:text-red-400 shrink-0">✕</button>
            </li>))}</ul>
        </Card>
      )}

      <Card title="Add something he has said" right={!adding && <button onClick={() => setAdding(true)} className="text-sky-400 hover:underline">Add</button>}>
        {!adding ? <div className="text-xs text-gray-500">Found a new post, interview or talk? Log the position with a link, so the record stays checkable.</div> : (
          <form onSubmit={submit} className="grid md:grid-cols-6 gap-2 text-xs">
            <input className={inp} placeholder="Ticker" aria-label="Ticker" value={form.symbol} onChange={set('symbol')} />
            <select className={inp} aria-label="What he said" value={form.action} onChange={set('action')}>
              {['owns', 'bought', 'added', 'trimmed', 'sold', 'approach', 'other'].map(a => <option key={a} value={a}>{a}</option>)}
            </select>
            <input className={inp} placeholder="As of (YYYY-MM or YYYY-MM-DD)" aria-label="As of" value={form.asOf} onChange={set('asOf')} />
            <input className={`${inp} md:col-span-3`} placeholder="What was said" aria-label="What was said" value={form.note} onChange={set('note')} />
            <input className={`${inp} md:col-span-2`} placeholder="Source title" aria-label="Source title" value={form.sourceTitle} onChange={set('sourceTitle')} />
            <input className={`${inp} md:col-span-3`} placeholder="Source link (https://…)" aria-label="Source link" value={form.sourceUrl} onChange={set('sourceUrl')} />
            <div className="flex gap-2"><button className="px-3 py-1.5 rounded-lg bg-sky-600 text-white hover:bg-sky-500" type="submit">Save</button>
              <button type="button" onClick={() => { setAdding(false); setErr(null) }} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400">Cancel</button></div>
            {err && <div className="md:col-span-6"><ErrorBox>{err}</ErrorBox></div>}
          </form>
        )}
      </Card>
    </div>
  )
}

export default function ManagerHoldings() {
  const list = useApi('/api/managers')
  const [id, setId] = useState('berkshire')
  const [rev, setRev] = useState(0)
  const [chartRow, setChartRow] = useState(null)
  const { data, loading, error } = useApi(`/api/managers/${id}?r=${rev}`)
  const managers = list.data?.managers || []
  const current = managers.find(m => m.id === id) || data?.manager

  return (
    <div className="p-4 space-y-4 max-w-6xl">
      <PageHeader title="Manager Holdings">Follow what well-known investors own. Institutions come from their quarterly SEC 13F filings; people who file nothing are logged from what they have said publicly, with a source for each entry.</PageHeader>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Investors">
        {(managers.length ? managers : [{ id: 'berkshire', name: 'Berkshire Hathaway' }, { id: 'damodaran', name: 'Aswath Damodaran' }]).map(m => (
          <button key={m.id} role="tab" aria-selected={m.id === id} onClick={() => setId(m.id)}
            className={`px-3 py-1.5 rounded-lg border text-xs ${m.id === id ? 'border-sky-500/60 text-sky-300 bg-sky-500/10' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
            {m.name}{m.kind === 'disclosed' && <span className="ml-1 text-[10px] text-gray-500">(public statements)</span>}
          </button>
        ))}
      </div>

      {current && <div className="text-xs text-gray-400"><b className="text-gray-200">{current.person}</b> · {current.blurb}</div>}

      <Caveats items={data?.manager?.kind === 'disclosed' ? [
        'He files no 13F, so there is no official record of his holdings. This page is only what he has said in public, and it is incomplete and dated.',
        'Entries are never inferred or estimated. If a position is not here, that does not mean he does not own it.',
        'The first group of entries was gathered from his own post on X and from a forum summary of his talks; each row says which. Anything you add is marked as yours.',
      ] : [
        'A 13F lists a manager\'s long US-listed positions as of the quarter end and is filed up to 45 days later, so it is always out of date. It shows nothing about short positions, cash, bonds or most non-US holdings.',
        'The filer is the institution, not the person: Berkshire\'s report covers its insurance and other businesses\' portfolios, not Warren Buffett personally.',
        'A manager can ask the SEC to keep a position confidential, so it can be missing here and appear months later in an amendment.',
        '"Since quarter end" weights the reported positions by their reported values and ignores anything bought or sold since, so it shows how the disclosed portfolio has done, not the manager\'s own return.',
      ]} />

      {loading && !data && <Loading>{id === 'damodaran' ? 'Loading…' : 'Reading SEC filings… the first load can take a few seconds.'}</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && data.manager.id === id && (data.manager.kind === 'disclosed'
        ? <Disclosed d={data} onChart={setChartRow} reload={() => setRev(r => r + 1)} />
        : <Report d={data} onChart={setChartRow} />)}

      {chartRow && <ChartModal symbol={chartRow.ticker || chartRow.symbol} quote={{ symbol: chartRow.ticker || chartRow.symbol, name: chartRow.name, price: chartRow.priceNow ?? chartRow.price ?? null, changePercent: null, change: null }} onClose={() => setChartRow(null)} />}
    </div>
  )
}
