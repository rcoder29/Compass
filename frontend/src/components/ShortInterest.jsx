import { useState, useMemo } from 'react'
import ChartModal from './ChartModal'
import { usePolledApi, PageHeader, Loading, ErrorBox, Caveats, Card, fmtPct, fmtNum, signedClass, DASH } from './MacroKit'

const DISPLACEMENT = {
  equity_leads: { label: 'Equity ahead of credit', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/30' },
  partial: { label: 'Partly confirmed', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
  confirmed: { label: 'Credit confirms', cls: 'text-red-300 bg-red-500/10 border-red-500/30' },
  none: { label: 'No bond read', cls: 'text-gray-400 bg-gray-800/50 border-gray-700' },
}
const BORROW_CLS = { easy: 'text-emerald-300', warm: 'text-sky-300', hard: 'text-amber-300', extreme: 'text-red-300' }
const CAPS = [[100, '$100M+'], [300, '$300M+'], [1000, '$1B+'], [5000, '$5B+']]

export function fmtCap(v) {
  if (v == null) return DASH
  return v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e10 ? `$${Math.round(v / 1e9)}B` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`
}
export const fmtShares = v => (v == null ? DASH : v >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${Math.round(v / 1e3)}K` : String(Math.round(v)))
export const fmtAvail = b => (b?.available == null ? DASH : b.available === 0 ? 'none' : `${b.availableCapped ? '>' : ''}${fmtShares(b.available)}`)

const SORTS = {
  siPctFloat: r => r.siPctFloat, sharesShort: r => r.sharesShort, changePct: r => r.changePct, daysToCover: r => r.daysToCover,
  fee: r => r.borrow?.fee, spreadBps: r => r.spreadBps, displacementScore: r => r.displacementScore, marketCap: r => r.marketCap, change52w: r => r.change52w,
}

export function toCsv(rows) {
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`
  const head = ['Rank', 'Symbol', 'Name', 'Sector', 'Short % of float', 'Shares short', 'Change vs prior %', 'Days to cover', 'Borrow fee %', 'Rebate %', 'Shares available',
    'Market cap', 'Bond issuer', 'Bonds', 'Avg coupon %', 'Avg YTM %', 'Spread bps', 'Spread source', 'Implied interest rate %', 'Interest cover', 'Displacement']
  const lines = [head.map(esc).join(',')]
  rows.forEach(r => lines.push([r.rank, r.symbol, r.name, r.sector ?? '', (r.siPctFloat * 100).toFixed(1), r.sharesShort, r.changePct ?? '', r.daysToCover ?? '',
    r.borrow?.fee ?? '', r.borrow?.rebate ?? '', r.borrow?.available ?? '', r.marketCap ?? '', r.bonds?.issuer ?? '', r.bonds?.count ?? '', r.bonds?.avgCoupon ?? '', r.bonds?.avgYtm ?? '',
    r.spreadBps ?? '', r.spreadBps == null ? '' : (r.spreadIsProxy ? 'proxy' : 'bonds'), r.interestPaid?.impliedRate ?? '', r.interestPaid?.coverage ?? '', r.displacement.label]
    .map((c, i) => ([1, 2, 3, 12, 17, 20].includes(i) ? esc(c) : c)).join(',')))
  return lines.join('\n')
}

function Bar({ value, max = 1, cls = 'bg-red-500' }) {
  return <div className="w-20 h-1.5 bg-gray-800 rounded-full"><div className={`h-full rounded-full ${cls}`} style={{ width: `${Math.min(value / max, 1) * 100}%` }} /></div>
}

function DebtCell({ r }) {
  if (r.bonds) {
    const b = r.bonds
    return (
      <div>
        <div className="text-gray-100 tabular-nums">{b.avgYtm == null ? DASH : `${fmtNum(b.avgYtm, 1)}%`} <span className="text-gray-500">yield</span></div>
        <div className="text-[11px] text-gray-500 tabular-nums">{fmtNum(b.avgCoupon, 2)}% coupon · {r.spreadBps == null ? DASH : `+${r.spreadBps} bps`} · {b.count} bond{b.count === 1 ? '' : 's'} {b.grade}</div>
      </div>
    )
  }
  const ip = r.interestPaid
  if (ip?.impliedRate != null) {
    return (
      <div>
        <div className="text-gray-300 tabular-nums">~{fmtNum(ip.impliedRate, 1)}% <span className="text-gray-500">paid on debt</span></div>
        <div className="text-[11px] text-gray-500 tabular-nums">{r.spreadBps != null ? `proxy · ${r.spreadBps >= 0 ? '+' : ''}${r.spreadBps} bps` : 'low rate or small debt: no credit read'}{ip.coverage != null ? ` · cover ${fmtNum(ip.coverage, 1)}x` : ''}</div>
      </div>
    )
  }
  return <span className="text-gray-600">{DASH}</span>
}

function Detail({ r, onChart }) {
  const d = r.displacement, ip = r.interestPaid, b = r.borrow
  return (
    <div className="grid lg:grid-cols-3 gap-4 px-4 py-3 bg-gray-950/40 text-xs" data-testid="si-detail">
      <div className="space-y-3">
        <div className={`rounded-lg border px-3 py-2 ${DISPLACEMENT[d.key].cls}`}><div className="font-medium">{d.label}</div><p className="mt-1 text-gray-300">{d.text}</p></div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2"><span className="w-28 text-gray-500">Equity pessimism</span><Bar value={r.equityPercentile} max={100} cls="bg-red-500" /><span className="tabular-nums text-gray-300">{r.equityPercentile}</span></div>
          <div className="flex items-center gap-2"><span className="w-28 text-gray-500">Credit stress</span>{r.creditPercentile == null ? <span className="text-gray-600">no read</span> : <><Bar value={r.creditPercentile} max={100} cls="bg-amber-500" /><span className="tabular-nums text-gray-300">{r.creditPercentile}</span></>}</div>
          <p className="text-[11px] text-gray-600">Percentile within this list: short interest vs spread to Treasuries. A big gap means the two markets disagree.</p>
        </div>
      </div>
      <div className="space-y-3">
        <div>
          <div className="text-gray-300 font-medium mb-1">Borrowing the stock</div>
          {b ? <ul className="text-gray-400 space-y-0.5"><li>Fee: <span className={BORROW_CLS[b.band?.key]}>{b.fee == null ? DASH : `${fmtNum(b.fee, 2)}% a year`}</span> {b.band && <span className="text-gray-500">({b.band.label})</span>}</li>
            <li>Rebate: {b.rebate == null ? DASH : `${fmtNum(b.rebate, 2)}%`}</li><li>Shares available: {fmtAvail(b)}</li></ul> : <p className="text-gray-500">Not listed in Interactive Brokers&apos; stock-loan table.</p>}
        </div>
        <div>
          <div className="text-gray-300 font-medium mb-1">Interest actually paid</div>
          {ip ? <ul className="text-gray-400 space-y-0.5"><li>Interest expense: {ip.interestExpense == null ? DASH : fmtCap(ip.interestExpense)} on {ip.totalDebt == null ? DASH : fmtCap(ip.totalDebt)} of debt</li>
            <li>Implied rate: {ip.impliedRate == null ? DASH : `${fmtNum(ip.impliedRate, 2)}%`}</li><li>Interest cover (EBIT / interest): {ip.coverage == null ? DASH : `${fmtNum(ip.coverage, 1)}x`}</li>
            <li>Net debt: {ip.netDebt == null ? DASH : fmtCap(ip.netDebt)}</li></ul> : <p className="text-gray-500">No debt or interest figures available.</p>}
        </div>
      </div>
      <div className="space-y-3">
        <div className="text-gray-300 font-medium">Bonds{r.bonds ? ` (matched to “${r.bonds.issuer}”)` : ''}</div>
        {r.bonds ? (
          <table className="w-full"><thead><tr className="text-[11px] text-gray-500"><th className="text-left font-medium">Maturity</th><th className="text-right font-medium">Coupon</th><th className="text-right font-medium">Price</th><th className="text-right font-medium">Yield</th><th className="text-right font-medium">Spread</th></tr></thead>
            <tbody>{r.bonds.top.map(t => <tr key={`${t.maturity}-${t.coupon}`} className="border-t border-gray-800/70 tabular-nums"><td className="py-1 text-gray-300">{t.maturity.slice(0, 7)}</td><td className="text-right text-gray-300">{fmtNum(t.coupon, 2)}%</td><td className="text-right text-gray-300">{fmtNum(t.price, 1)}</td><td className="text-right text-gray-300">{fmtNum(t.ytm, 2)}%</td><td className="text-right text-gray-300">{t.spreadBps == null ? DASH : `+${t.spreadBps}`}</td></tr>)}</tbody></table>
        ) : <p className="text-gray-500">None of the company&apos;s bonds are held by the large corporate-bond funds the page reads, so there is no market price to show{r.spreadIsProxy ? '; the implied rate above is a lagging proxy' : ''}.</p>}
        <button onClick={() => onChart(r)} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Open chart</button>
      </div>
    </div>
  )
}

export default function ShortInterest() {
  const [minCap, setMinCap] = useState(300)
  const { data, error } = usePolledApi(`/api/short-interest?limit=100&min_cap=${minCap}`)
  const [sort, setSort] = useState({ key: 'siPctFloat', dir: 'desc' })
  const [filter, setFilter] = useState('all')
  const [sector, setSector] = useState('')
  const [query, setQuery] = useState('')
  const [hardOnly, setHardOnly] = useState(false)
  const [open, setOpen] = useState(null)
  const [chartRow, setChartRow] = useState(null)
  const ready = data?.status === 'ready'

  const sectors = useMemo(() => (ready ? [...new Set(data.rows.map(r => r.sector).filter(Boolean))].sort() : []), [data, ready])
  const rows = useMemo(() => {
    if (!ready) return []
    const f = SORTS[sort.key], dir = sort.dir === 'asc' ? 1 : -1, q = query.trim().toLowerCase()
    return data.rows.filter(r => (filter === 'all' || r.displacement.key === filter) && (!sector || r.sector === sector) && (!hardOnly || (r.borrow?.fee ?? 0) >= 5)
      && (!q || r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)))
      .sort((a, b) => { const x = f(a), y = f(b); if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x < y ? -1 : x > y ? 1 : 0) * dir })
  }, [data, ready, sort, filter, sector, query, hardOnly])

  const toggleSort = key => setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' }))
  const mark = key => (sort.key === key ? (sort.dir === 'desc' ? ' ▼' : ' ▲') : '')
  const th = 'px-2 py-1.5 text-[11px] font-semibold text-gray-400 whitespace-nowrap cursor-pointer select-none hover:text-gray-200'
  const s = ready ? data.summary : null

  function exportCsv() {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv' }))
    a.download = `short-interest-${data.settlement}.csv`
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href)
  }

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Short Interest Monitor">
        The 100 most heavily shorted US stocks, ranked by short interest as a share of the float, with what it costs to borrow them and what the same companies&apos; bonds are saying.
        When shorts pile in but lenders stay calm, the equity market is more pessimistic than the credit market: that gap is the displacement.
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="flex items-center gap-2 text-gray-400">Market cap
          <select aria-label="Minimum market cap" value={minCap} onChange={e => { setMinCap(Number(e.target.value)); setOpen(null) }} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg">
            {CAPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        {ready && <span className="text-gray-500 ml-auto">Short interest settled {data.settlement} · borrow data {data.borrowAsOf ?? 'unavailable'}</span>}
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}
      {!data && !error && <Loading>Loading short interest…</Loading>}
      {data?.status === 'running' && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4" role="status">
          <div className="flex justify-between text-xs text-gray-400 mb-2"><span>Step {data.stage} of {data.stages}: {data.stageLabel}…</span><span className="tabular-nums">{data.progress.done} / {data.progress.total}</span></div>
          <div className="h-2 bg-gray-800 rounded-full"><div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${(data.progress.done / Math.max(data.progress.total, 1)) * 100}%` }} /></div>
          <p className="text-[11px] text-gray-500 mt-2">The first load pulls float data, debt statements and corporate-bond fund holdings, and can take a few minutes; after that it is cached.</p>
        </div>
      )}
      {ready && data.partial && <div role="note" className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">{data.partial.note}</div>}
      {ready && data.notes.filter(n => !data.partial || !data.partial.note.includes(n)).map(n => <div key={n} role="note" className="text-xs text-gray-400 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2">{n}</div>)}

      {ready && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <SummaryStat label="Median short interest" value={fmtPct(s.medianSi, { signed: false, digits: 0 })} hint="of float, in this list" />
            <SummaryStat label="30%+ of float" value={s.above30} hint="names" />
            <SummaryStat label="Hard to borrow" value={s.hardToBorrow} hint={`of ${s.withBorrow} with a quote (fee 5%+)`} />
            <SummaryStat label="Most expensive" value={s.mostExpensive[0] ? s.mostExpensive[0].symbol : DASH} hint={s.mostExpensive[0] ? `${fmtNum(s.mostExpensive[0].fee, 1)}% a year` : ''} />
            <SummaryStat label="Biggest increase" value={s.biggestIncreases[0] ? s.biggestIncreases[0].symbol : DASH} hint={s.biggestIncreases[0] ? `${fmtPct(s.biggestIncreases[0].changePct / 100, { digits: 0 })} vs prior period` : ''} />
            <SummaryStat label="Bond read" value={`${s.withBonds + s.withProxy}`} hint={`${s.withBonds} bonds · ${s.withProxy} proxy`} />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs" role="group" aria-label="Displacement filter">
            {[['all', `All ${s.count}`], ...Object.entries(DISPLACEMENT).map(([k, v]) => [k, `${v.label} ${s.displacement[k]}`])].map(([k, label]) => (
              <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
                      className={`px-3 py-1.5 rounded-full border ${filter === k ? (k === 'all' ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300' : DISPLACEMENT[k].cls) : 'border-gray-700 text-gray-400 hover:text-gray-200'}`}>{label}</button>
            ))}
            <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Filter stocks" placeholder="Filter…" className="w-32 bg-gray-800 border border-gray-700 text-gray-100 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500 placeholder-gray-600 ml-2" />
            {sectors.length > 0 && <select aria-label="Sector" value={sector} onChange={e => setSector(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-200 px-2 py-1.5 rounded-lg"><option value="">All sectors</option>{sectors.map(x => <option key={x} value={x}>{x}</option>)}</select>}
            <label className="flex items-center gap-1.5 text-gray-400 cursor-pointer"><input type="checkbox" checked={hardOnly} onChange={e => setHardOnly(e.target.checked)} />Borrow fee 5%+</label>
            <span className="text-gray-500 ml-auto">{rows.length} shown</span>
            <button onClick={exportCsv} className="px-2.5 py-1.5 border border-gray-700 text-gray-300 rounded-lg hover:border-gray-500">Export CSV</button>
          </div>

          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-auto max-h-[75vh]" data-testid="si-table">
            <table className="w-full text-xs border-separate border-spacing-0">
              <thead className="sticky top-0 z-10 bg-gray-900">
                <tr>
                  <th className={`${th} text-left`}>#</th><th className={`${th} text-left`}>Stock</th>
                  <th className={`${th} text-left ${sort.key === 'siPctFloat' ? 'text-emerald-300' : ''}`} onClick={() => toggleSort('siPctFloat')}>Short % of float{mark('siPctFloat')}</th>
                  <th className={`${th} text-right`} onClick={() => toggleSort('sharesShort')}>Shares short{mark('sharesShort')}</th>
                  <th className={`${th} text-right`} onClick={() => toggleSort('changePct')}>vs prior{mark('changePct')}</th>
                  <th className={`${th} text-right`} onClick={() => toggleSort('daysToCover')}>Days to cover{mark('daysToCover')}</th>
                  <th className={`${th} text-right`} onClick={() => toggleSort('fee')}>Borrow fee{mark('fee')}</th>
                  <th className={`${th} text-left`} onClick={() => toggleSort('spreadBps')}>Company bonds / debt cost{mark('spreadBps')}</th>
                  <th className={`${th} text-left`} onClick={() => toggleSort('displacementScore')}>Equity vs credit{mark('displacementScore')}</th>
                  <th className={`${th} text-right`} onClick={() => toggleSort('marketCap')}>Mkt cap{mark('marketCap')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={10} className="text-center text-gray-500 py-8">No stocks match those filters.</td></tr>}
                {rows.map(r => (
                  <Row key={r.symbol} r={r} open={open === r.symbol} onToggle={() => setOpen(open === r.symbol ? null : r.symbol)} onChart={setChartRow} />
                ))}
              </tbody>
            </table>
          </div>
          <Caveats title="Sources, timing and limits" items={[
            `Short interest is FINRA's bi-monthly report (settlement ${data.settlement}); it is published about a week after the settlement date, so it is always somewhat stale. Short % of float = shares sold short / float from Yahoo Finance. Days to cover = shares short / average daily volume.`,
            'Borrow fee, rebate and availability come from Interactive Brokers\' public stock-loan table: one broker\'s indicative rates, not a market-wide quote. The hardest-to-borrow stocks are often missing from it.',
            `Bond figures come from the latest SEC N-PORT filings of ${data.bondFunds.join(', ')} (price = market value / par, a quarterly snapshot with no accrued-interest adjustment) and are matched to companies by name. Only issuers those funds hold appear; the “paid on debt” proxy (interest expense / total debt from the latest annual statement) lags and can be distorted by one-off items.`,
            'The displacement read compares short interest with the spread over Treasuries: under 400 bps lenders see little default risk, 400-700 is wide, 700+ is distressed. It organises questions and is not a trading signal: heavily shorted stocks can be squeezed, and a tight spread can widen quickly.',
          ]} />
        </>
      )}
      {chartRow && <ChartModal symbol={chartRow.symbol} quote={{ symbol: chartRow.symbol, name: chartRow.name, price: chartRow.price, changePercent: null, change: null }} onClose={() => setChartRow(null)} />}
    </div>
  )
}

function SummaryStat({ label, value, hint }) {
  return <div className="bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2"><div className="text-[11px] text-gray-500">{label}</div><div className="text-lg font-semibold tabular-nums text-gray-100">{value}</div><div className="text-[11px] text-gray-600">{hint}</div></div>
}

function Row({ r, open, onToggle, onChart }) {
  const fee = r.borrow?.fee
  return (
    <>
      <tr onClick={onToggle} onKeyDown={e => e.key === 'Enter' && onToggle()} tabIndex={0} aria-expanded={open} aria-label={`${r.symbol} details`} data-testid="si-row" className={`cursor-pointer hover:bg-gray-800/40 ${open ? 'bg-sky-500/5' : ''}`}>
        <td className="px-2 py-2 text-gray-500 tabular-nums border-t border-gray-800/60">{r.rank}</td>
        <td className="px-2 py-2 border-t border-gray-800/60 min-w-[170px]"><span className="text-gray-100 font-medium">{r.symbol}</span> <span className="text-gray-400">{r.name}</span><div className="text-[11px] text-gray-600">{r.sector}</div></td>
        <td className="px-2 py-2 border-t border-gray-800/60"><div className="flex items-center gap-2"><Bar value={r.siPctFloat} max={0.6} /><span className="tabular-nums text-gray-100 font-semibold w-12 text-right">{fmtPct(r.siPctFloat, { signed: false, digits: 1 })}</span></div></td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{fmtShares(r.sharesShort)}</td>
        <td className={`px-2 py-2 text-right tabular-nums border-t border-gray-800/60 ${signedClass(r.changePct)}`}>{r.changePct == null ? DASH : `${r.changePct >= 0 ? '+' : ''}${fmtNum(r.changePct, 0)}%`}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{r.daysToCover == null ? DASH : fmtNum(r.daysToCover, 1)}</td>
        <td className="px-2 py-2 text-right border-t border-gray-800/60">{fee == null ? <span className="text-gray-600">{DASH}</span> : <><span className={`tabular-nums font-medium ${BORROW_CLS[r.borrow.band?.key]}`}>{fmtNum(fee, 1)}%</span><div className="text-[11px] text-gray-600">{fmtAvail(r.borrow)} avail</div></>}</td>
        <td className="px-2 py-2 border-t border-gray-800/60 min-w-[190px]"><DebtCell r={r} /></td>
        <td className="px-2 py-2 border-t border-gray-800/60"><span className={`px-2 py-0.5 rounded-full border text-[11px] whitespace-nowrap ${DISPLACEMENT[r.displacement.key].cls}`} title={r.displacement.text}>{r.displacement.label}</span></td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{fmtCap(r.marketCap)}</td>
      </tr>
      {open && <tr><td colSpan={10} className="border-t border-gray-800/60"><Detail r={r} onChart={onChart} /></td></tr>}
    </>
  )
}
