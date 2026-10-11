import { useState, useMemo } from 'react'
import ChartModal from './ChartModal'
import { usePolledApi, PageHeader, Loading, ErrorBox, Caveats, Card, TimeChart, fmtPct, fmtNum, signedClass, DASH } from './MacroKit'
import { RETURN_COLS, ROLE_ORDER, roleName, roleBlurb, RISK_CLS, RetCell, SetupPill, Stat, List, ScanProgress, PartialNote, Disclaimer } from './ThemeKit'

function fmtCap(v) {
  if (v == null) return DASH
  return v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e10 ? `$${Math.round(v / 1e9)}B` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`
}

const SORTS = {
  setup: m => m.setup.score, '1M': m => m.returns['1M'], '3M': m => m.returns['3M'], '1Y': m => m.returns['1Y'], '3Y': m => m.returns['3Y'],
  upside: m => m.upside?.mean, growth: m => m.growth, marketCap: m => m.marketCap,
}

function Outlook({ t }) {
  const o = t.outlook
  const near = (
    <Card title="Next 3-12 months" right="analysts + editorial">
      <div className="grid grid-cols-3 gap-2 mb-3">
        <Stat label="Median analyst upside" value={fmtPct(o.analystUpsideMedian, { digits: 0 })} tone={signedClass(o.analystUpsideMedian)} hint={`${o.analystNames} names with 3+ analysts`} />
        <Stat label="Cap-weighted upside" value={fmtPct(o.analystUpsideCapWeighted, { digits: 0 })} tone={signedClass(o.analystUpsideCapWeighted)} hint="Leaders count for more" />
        <Stat label="Analysts at Buy" value={o.buyShare == null ? DASH : fmtPct(o.buyShare, { signed: false, digits: 0 })} hint="Of names covered" />
      </div>
      <p className="text-[11px] text-gray-500 mb-3">Upside is the gap between analysts&apos; 12-month price targets and today&apos;s price. Targets are opinions, are often wrong, and tend to be cut after prices fall.</p>
      <div className="grid md:grid-cols-2 gap-4">
        <List title="What could move it" items={t.shortTerm.catalysts} tone="text-emerald-200/80" marker="↑" />
        <List title="What could hurt" items={t.shortTerm.risks} tone="text-amber-200/80" marker="↓" />
      </div>
    </Card>
  )
  const far = (
    <Card title="The next 3-10 years" right="growth + editorial">
      <div className="grid grid-cols-3 gap-2 mb-3">
        <Stat label="Median revenue growth" value={fmtPct(o.growthMedian, { signed: false, digits: 0 })} hint="Blended multi-year and latest" />
        <Stat label="Profitable today" value={o.profitableShare == null ? DASH : fmtPct(o.profitableShare, { signed: false, digits: 0 })} hint="Of names with data" />
        <Stat label="Median forward P/E" value={o.forwardPEMedian == null ? DASH : fmtNum(o.forwardPEMedian, 0)} hint="Profitable names only" />
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <List title="What drives it" items={t.longTerm.drivers} tone="text-emerald-200/80" marker="↑" />
        <List title="What could go wrong" items={t.longTerm.risks} tone="text-amber-200/80" marker="↓" />
      </div>
    </Card>
  )
  return <div className="grid xl:grid-cols-2 gap-4">{near}{far}</div>
}

function Scenarios({ t }) {
  const sc = t.scenarios
  const rec = t.outlook.record
  return (
    <Card title="What compounding would mean" right="arithmetic, not a forecast">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1.5 font-medium">If the basket grew…</th>{sc.years.map(y => <th key={y} className="text-right font-medium">${sc.start.toLocaleString()} after {y} yr{y > 1 ? 's' : ''}</th>)}</tr></thead>
          <tbody>
            {sc.rows.map(r => (
              <tr key={r.rate} className="border-t border-gray-800/70">
                <td className="py-1.5 text-gray-200">{fmtPct(r.rate, { signed: false, digits: 0 })} a year <span className="text-gray-500">({r.label.toLowerCase()})</span></td>
                {sc.years.map(y => <td key={y} className="text-right tabular-nums text-gray-300">${r.values[y].toLocaleString()}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-gray-500 mt-3">
        For context, this basket&apos;s own record: {rec.annualised3Y == null ? 'three-year' : <>averaging <span className="text-gray-300">{fmtPct(rec.annualised3Y, { digits: 0 })} a year over 3 years</span></>}
        {rec.annualised5Y != null && <> and <span className="text-gray-300">{fmtPct(rec.annualised5Y, { digits: 0 })} a year over 5</span></>}
        {t.series && <>, with a worst peak-to-trough fall of <span className="text-red-300">{fmtPct(t.series.maxDrawdown, { signed: false, digits: 0 })}</span> in the past year (SPY: {fmtPct(t.series.benchMaxDrawdown, { signed: false, digits: 0 })})</>}.
        Past returns, especially of themes that have already run, do not repeat on schedule.
      </p>
    </Card>
  )
}

const TONE = { bad: ['text-red-200/80', '↓'], good: ['text-emerald-200/80', '↑'], new: ['text-sky-200/80', '+'] }

function ImpactSection({ sec }) {
  if (sec.type === 'lists') {
    return (
      <div className="space-y-3 text-xs">
        <p className="text-gray-300">{sec.summary}</p>
        <div className="grid md:grid-cols-3 gap-4">{sec.columns.map(c => <List key={c.title} title={c.title} items={c.items} tone={TONE[c.tone]?.[0]} marker={TONE[c.tone]?.[1]} />)}</div>
      </div>
    )
  }
  if (sec.type === 'cards') {
    return <ul className="grid md:grid-cols-2 gap-3 text-xs">{sec.items.map(m => <li key={m.title} className="bg-gray-950/40 border border-gray-800 rounded-lg p-3"><div className="text-gray-200 font-medium mb-1">{m.title}</div><p className="text-gray-400">{m.text}</p></li>)}</ul>
  }
  if (sec.type === 'ranked') {
    return (
      <ol className="space-y-2 text-xs">
        {sec.items.map((w, i) => <li key={w.who} className="flex gap-3 bg-gray-950/40 border border-gray-800 rounded-lg p-3"><span className="text-gray-500 tabular-nums">{i + 1}</span><div><div className="text-gray-200 font-medium">{w.who}</div><p className="text-gray-400 mt-0.5">{w.why}</p></div></li>)}
        <li className="text-[11px] text-gray-500 list-none">The companies and funds that fit each group are in the value chain and the table below, with live performance.</li>
      </ol>
    )
  }
  return (
    <div className="grid md:grid-cols-3 gap-3 text-xs">
      {sec.items.map(sc => (
        <div key={sc.name} className="bg-gray-950/40 border border-gray-800 rounded-lg p-3 space-y-2">
          <div className="text-gray-100 font-medium">{sc.name}</div>
          <p className="text-gray-400">{sc.text}</p>
          <p><span className="text-emerald-300">Favours: </span><span className="text-gray-400">{sc.favours}</span></p>
          <p><span className="text-red-300">Hurts: </span><span className="text-gray-400">{sc.hurts}</span></p>
          {sc.positioning && <p><span className="text-sky-300">Positioning: </span><span className="text-gray-400">{sc.positioning}</span></p>}
        </div>
      ))}
    </div>
  )
}

function Impact({ imp }) {
  const [tab, setTab] = useState(imp.sections[0].id)
  const sec = imp.sections.find(x => x.id === tab) ?? imp.sections[0]
  return (
    <Card title="What it could mean" right="editorial scenario map, not a forecast">
      <p className="text-xs text-gray-400 mb-3">{imp.intro}</p>
      <div className="flex flex-wrap gap-2 mb-3 text-xs" role="tablist" aria-label="Implications">
        {imp.sections.map(x => (
          <button key={x.id} role="tab" aria-selected={sec.id === x.id} onClick={() => setTab(x.id)}
                  className={`px-3 py-1.5 rounded-lg border ${sec.id === x.id ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300' : 'border-gray-700 text-gray-400 hover:text-gray-200'}`}>{x.label}</button>
        ))}
      </div>
      <ImpactSection sec={sec} />
    </Card>
  )
}

function ValueChain({ t, onPick }) {
  return (
    <Card title="The value chain: who else benefits" right="click a name to jump to it">
      <div className="space-y-3">
        {t.layers.map(l => {
          const names = t.members.filter(m => m.layer === l.id)
          return (
            <div key={l.id} className="grid md:grid-cols-[220px_1fr] gap-2 text-xs">
              <div><div className="text-gray-200 font-medium">{l.name}</div><div className="text-[11px] text-gray-500">{l.blurb}</div></div>
              <div className="flex flex-wrap gap-1.5">
                {names.map(m => (
                  <button key={m.symbol} onClick={() => onPick(m.symbol)} title={`${m.name}: ${m.why}`} disabled={!m.available}
                          className={`px-2 py-1 rounded-md border text-[11px] ${m.role === 'emerging' ? 'border-dashed border-gray-700' : m.role === 'atrisk' ? 'border-red-500/40' : 'border-gray-700'} hover:border-gray-500 disabled:opacity-40`}>
                    <span className="text-gray-100 font-medium">{m.symbol}</span>
                    <span className={`ml-1.5 tabular-nums ${signedClass(m.returns['3M'])}`}>{fmtPct(m.returns['3M'], { digits: 0 })}</span>
                  </button>
                ))}
                {names.length === 0 && <span className="text-gray-600">—</span>}
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-[11px] text-gray-600 mt-3">Dashed outline: emerging or speculative{t.roleCounts.atrisk > 0 && '; red outline: at risk of disruption'}. The number is the 3-month price change.</p>
    </Card>
  )
}

function Detail({ m, names, onChart }) {
  if (m.kind === 'fund') {
    return (
      <div className="grid lg:grid-cols-3 gap-4 px-4 py-3 bg-gray-950/40 text-xs" data-testid="member-detail">
        <div className="lg:col-span-2 space-y-2">
          <p className="text-gray-300">{m.why}</p>
          <p className="text-gray-500">A fund: it has live returns but no company fundamentals, analyst targets or setup score. Compare it by what it holds, its fees and the currency it is priced in.</p>
          <div className="flex gap-4 tabular-nums">{['1M', '3M', '1Y', '3Y', '5Y'].map(p => <span key={p}><span className="text-gray-600">{p} </span><span className={signedClass(m.returns[p])}>{fmtPct(m.returns[p], { digits: 0 })}</span></span>)}</div>
        </div>
        <div><button onClick={() => onChart(m)} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Open chart</button></div>
      </div>
    )
  }
  return (
    <div className="grid lg:grid-cols-3 gap-4 px-4 py-3 bg-gray-950/40 text-xs" data-testid="member-detail">
      <div className="lg:col-span-2 space-y-3">
        <p className="text-gray-300">{m.why}</p>
        <table className="w-full">
          <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1 font-medium">Part of the setup score</th><th className="text-left font-medium w-36">Score</th><th className="text-right font-medium">Points</th><th className="text-left pl-3 font-medium">Why</th></tr></thead>
          <tbody>
            {Object.entries(m.setup.factors).map(([k, f]) => (
              <tr key={k} className="border-t border-gray-800/70">
                <td className="py-1.5 text-gray-200">{names[k]}<span className="text-gray-600 ml-1">({f.weight})</span></td>
                <td><div className="h-1.5 bg-gray-800 rounded-full w-28"><div className={`h-full rounded-full ${f.missing ? 'bg-gray-600' : f.score >= 66 ? 'bg-emerald-500' : f.score >= 40 ? 'bg-sky-500' : 'bg-amber-500'}`} style={{ width: `${Math.max(f.score, 2)}%` }} /></div></td>
                <td className="text-right tabular-nums text-gray-300">{fmtNum(f.points, 1)}</td>
                <td className="pl-3 text-gray-500">{f.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {m.setup.riskMultiplier < 1 && <p className="text-amber-300">Risk adjustment ×{m.setup.riskMultiplier} for {m.setup.risk.toLowerCase()} risk (raw score {fmtNum(m.setup.rawScore, 1)}).</p>}
        {m.setup.capReason && <p className="text-amber-300">{m.setup.capReason}.</p>}
      </div>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Stat label="Analyst target" value={m.upside ? fmtPct(m.upside.mean, { digits: 0 }) : DASH} tone={signedClass(m.upside?.mean)} hint={m.upside ? `${m.upside.rating ?? ''} · ${m.upside.count} analysts` : 'Fewer than 3 analysts'} />
          <Stat label="Target range" value={m.upside?.low != null && m.upside?.high != null ? `${fmtPct(m.upside.low, { digits: 0 })} to ${fmtPct(m.upside.high, { digits: 0 })}` : DASH} hint="Lowest to highest" />
          <Stat label="From 52-wk high" value={fmtPct(m.off52wHigh, { digits: 0 })} tone={signedClass(m.off52wHigh)} />
          <Stat label="100-bagger traits" value={m.bagger ? Math.round(m.bagger.score) : DASH} hint={m.bagger?.tier} />
        </div>
        {m.flags.length > 0 && <div><div className="text-amber-300 font-medium mb-1">Cautions</div><ul className="list-disc pl-4 text-amber-200/80 space-y-0.5">{m.flags.map(f => <li key={f}>{f}</li>)}</ul></div>}
        <button onClick={() => onChart(m)} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Open chart</button>
      </div>
    </div>
  )
}

export default function ThemePage({ themeId, onNavigate }) {
  const { data, error } = usePolledApi(`/api/themes/${themeId}`)
  const [roleTab, setRoleTab] = useState('all')
  const [sort, setSort] = useState({ key: 'setup', dir: 'desc' })
  const [open, setOpen] = useState(null)
  const [chartRow, setChartRow] = useState(null)
  const ready = data?.status === 'ready'
  const t = ready ? data.theme : null

  const rows = useMemo(() => {
    if (!t) return []
    const f = SORTS[sort.key]
    const dir = sort.dir === 'asc' ? 1 : -1
    return t.members.filter(m => m.available && (roleTab === 'all' || m.role === roleTab)).sort((a, b) => {
      const x = f(a), y = f(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      return (x < y ? -1 : x > y ? 1 : 0) * dir
    })
  }, [t, roleTab, sort])

  const toggleSort = key => setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' }))
  const mark = key => (sort.key === key ? (sort.dir === 'desc' ? ' ▼' : ' ▲') : '')
  const jump = symbol => { setRoleTab('all'); setOpen(symbol); setTimeout(() => document.getElementById(`m-${symbol}`)?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }), 50) }
  const th = 'px-2 py-1.5 text-[11px] font-semibold text-gray-400 whitespace-nowrap cursor-pointer select-none hover:text-gray-200'

  if (error) return <div className="p-4 max-w-[1500px] mx-auto"><ErrorBox>{error}</ErrorBox></div>
  if (!data) return <div className="p-4"><Loading>Loading theme…</Loading></div>
  if (data.status === 'running') return <div className="p-4 max-w-[1500px] mx-auto space-y-4"><PageHeader title="Loading theme…">Reading fundamentals for the themed companies.</PageHeader><ScanProgress data={data} /></div>

  const chartSeries = t.series ? [
    { name: `${t.short} basket`, color: t.color, points: t.series.points.map(p => [p[0], p[1]]) },
    { name: 'SPY', color: '#94a3b8', points: t.series.points.map(p => [p[0], p[2]]) },
  ] : null
  const candidates = [...t.members].filter(m => m.available && m.role !== 'atrisk' && m.setup.score != null).sort((a, b) => b.setup.score - a.setup.score).slice(0, 6)
  const b = t.basket

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <div style={{ borderLeft: `3px solid ${t.color}` }} className="pl-3">
        <PageHeader title={t.name}>{t.tagline}</PageHeader>
        <p className="text-xs text-gray-400 mt-2 max-w-4xl">{t.thesis}</p>
        <p className="text-xs text-gray-500 mt-1 max-w-4xl"><span className="text-gray-400">Why now: </span>{t.whyNow}</p>
        <div className="flex flex-wrap gap-2 mt-3 text-[11px]">
          {data.others.map(o => <button key={o.id} onClick={() => onNavigate?.(`theme${o.id}`)} className="px-2.5 py-1 rounded-full border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500">{o.name} →</button>)}
          <button onClick={() => onNavigate?.('themesoverview')} className="px-2.5 py-1 rounded-full border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500">All themes →</button>
        </div>
      </div>
      <PartialNote partial={data.partial} />

      <Card title={`How the ${t.short} basket has performed`} right={`equal-weight average of ${t.members.filter(m => m.available).length} companies · as of ${data.asOf}`}>
        <div className="grid xl:grid-cols-[1fr_380px] gap-4">
          <div>
            {chartSeries ? <TimeChart series={chartSeries} height={240} format={v => fmtNum(v, 0)} label={`${t.name} basket versus SPY, rebased to 100`} /> : <div className="text-xs text-gray-500 py-8 text-center">No price history available.</div>}
            <div className="flex gap-4 text-[11px] mt-1"><span style={{ color: t.color }}>— {t.short} basket</span><span className="text-slate-400">— SPY</span><span className="text-gray-600 ml-auto">last 12 months, rebased to 100</span></div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1 font-medium" /><th className="text-right font-medium">Basket</th><th className="text-right font-medium">SPY</th><th className="text-right font-medium">Beat SPY</th></tr></thead>
              <tbody>
                {RETURN_COLS.map(p => {
                  const ex = b[p].mean != null && t.benchmark?.[p] != null ? b[p].mean - t.benchmark[p] : null
                  return (
                    <tr key={p} className="border-t border-gray-800/70">
                      <td className="py-1 text-gray-300">{p}</td>
                      <td className={`text-right tabular-nums ${signedClass(b[p].mean)}`}>{fmtPct(b[p].mean, { digits: 0 })}</td>
                      <td className="text-right tabular-nums text-gray-400">{fmtPct(t.benchmark?.[p], { digits: 0 })}</td>
                      <td className={`text-right tabular-nums ${signedClass(ex)}`}>{ex == null ? DASH : fmtPct(ex, { digits: 0 })}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {t.series && <p className="text-[11px] text-gray-500 mt-2">Past year: volatility {fmtPct(t.series.volatility, { signed: false, digits: 0 })}, worst fall {fmtPct(t.series.maxDrawdown, { signed: false, digits: 0 })} (SPY {fmtPct(t.series.benchMaxDrawdown, { signed: false, digits: 0 })}).</p>}
          </div>
        </div>
      </Card>

      <Outlook t={t} />
      {t.impact && <Impact imp={t.impact} />}
      <Scenarios t={t} />
      <ValueChain t={t} onPick={jump} />

      <Card title="Companies in the theme" right={`${rows.length} shown · click a row for the reasoning`}>
        <div className="flex flex-wrap gap-2 mb-3 text-xs" role="tablist" aria-label="Company group">
          {[['all', 'All'], ...ROLE_ORDER.filter(r => (t.roleCounts[r] || 0) > 0).map(r => [r, roleName(t, r)])].map(([id, label]) => (
            <button key={id} role="tab" aria-selected={roleTab === id} onClick={() => setRoleTab(id)} title={id === 'all' ? undefined : roleBlurb(t, id)}
                    className={`px-3 py-1.5 rounded-lg border ${roleTab === id ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300' : 'border-gray-700 text-gray-400 hover:text-gray-200'}`}>
              {label}{id !== 'all' && <span className="ml-1.5 text-gray-500">{t.roleCounts[id]}</span>}
            </button>
          ))}
        </div>
        <div className="overflow-auto" data-testid="member-table">
          <table className="w-full text-xs border-separate border-spacing-0">
            <thead>
              <tr>
                <th className={`${th} text-left`}>Company</th>
                <th className={`${th} text-right`} onClick={() => toggleSort('marketCap')}>Mkt cap{mark('marketCap')}</th>
                {['1M', '3M', '1Y', '3Y'].map(p => <th key={p} className={`${th} text-right ${sort.key === p ? 'text-emerald-300' : ''}`} onClick={() => toggleSort(p)}>{p}{mark(p)}</th>)}
                <th className={`${th} text-right`} onClick={() => toggleSort('upside')}>Analyst upside{mark('upside')}</th>
                <th className={`${th} text-right`} onClick={() => toggleSort('growth')}>Growth{mark('growth')}</th>
                <th className={`${th} text-left`}>Risk</th>
                <th className={`${th} text-left ${sort.key === 'setup' ? 'text-emerald-300' : ''}`} onClick={() => toggleSort('setup')}>Setup{mark('setup')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={11} className="text-center text-gray-500 py-6">No companies in this group.</td></tr>}
              {rows.map(m => (
                <MemberRow key={m.symbol} m={m} t={t} open={open === m.symbol} onToggle={() => setOpen(open === m.symbol ? null : m.symbol)} names={t.factorNames} onChart={setChartRow} />
              ))}
            </tbody>
          </table>
        </div>
        {t.unavailable.length > 0 && <p className="text-[11px] text-gray-600 mt-2">No data from Yahoo for: {t.unavailable.join(', ')} (delisted, renamed or not yet trading).</p>}
      </Card>

      <Card title="Candidates to research" right="highest setup scores in this theme">
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {candidates.map(m => (
            <button key={m.symbol} onClick={() => jump(m.symbol)} className="text-left bg-gray-950/40 border border-gray-800 hover:border-gray-600 rounded-lg p-3">
              <div className="flex items-center justify-between"><span className="text-sm font-semibold text-gray-100">{m.symbol} <span className="text-gray-500 font-normal text-xs">{m.name}</span></span><span className="tabular-nums text-gray-100 font-semibold">{Math.round(m.setup.score)}</span></div>
              <div className="flex items-center gap-2 mt-1"><SetupPill setup={m.setup} /><span className={`text-[11px] ${RISK_CLS[m.risk]}`}>{m.risk} risk</span><span className="text-[11px] text-gray-500">{roleName(t, m.role)}</span></div>
              <p className="text-[11px] text-gray-500 mt-2 line-clamp-2">{m.why}</p>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-gray-500 mt-3">A candidate list is where research starts, not a recommendation. High scores often come with high risk: a speculative name can top a factor ranking and still lose most of its value.</p>
      </Card>

      {t.etfs.length > 0 && (
        <Card title="Diversified ways in: theme ETFs" right="price change">
          <div className="grid sm:grid-cols-3 gap-3 text-xs">
            {t.etfs.map(e => (
              <div key={e.symbol} className="bg-gray-950/40 border border-gray-800 rounded-lg p-3">
                <div className="text-gray-100 font-medium">{e.symbol}</div><div className="text-[11px] text-gray-500 mb-2">{e.name}</div>
                {e.returns ? <div className="flex gap-3 tabular-nums">{['3M', '1Y', '3Y'].map(p => <span key={p}><span className="text-gray-600">{p} </span><span className={signedClass(e.returns[p])}>{fmtPct(e.returns[p], { digits: 0 })}</span></span>)}</div> : <span className="text-gray-600">No data</span>}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Caveats title={`What to keep in mind (editorial view, ${data.editorialDate})`} items={[t.watch, 'The setup score ranks names against each other on theme exposure, momentum, analyst upside, growth, financial strength and valuation, then marks down very risky names. It is a research aid, not a prediction.', 'Themes that have already run tend to be crowded: a good story and a good investment are different things.']} />
      <Disclaimer />
      {chartRow && <ChartModal symbol={chartRow.symbol} quote={{ symbol: chartRow.symbol, name: chartRow.name, price: chartRow.price, changePercent: chartRow.returns['1D'] != null ? chartRow.returns['1D'] * 100 : null, change: null }} onClose={() => setChartRow(null)} />}
    </div>
  )
}

function MemberRow({ m, t, open, onToggle, names, onChart }) {
  return (
    <>
      <tr id={`m-${m.symbol}`} onClick={onToggle} onKeyDown={e => e.key === 'Enter' && onToggle()} tabIndex={0} aria-expanded={open} aria-label={`${m.symbol} details`} data-testid="member-row"
          className={`cursor-pointer hover:bg-gray-800/40 ${open ? 'bg-sky-500/5' : ''}`}>
        <td className="px-2 py-2 border-t border-gray-800/60 min-w-[200px]">
          <span className="text-gray-100 font-medium">{m.symbol}</span> <span className="text-gray-400">{m.name}</span>
          <div className="text-[11px] text-gray-600">{roleName(t, m.role)}{m.flags.length > 0 && <span className="text-amber-400 ml-2" title={m.flags.join('; ')}>⚠ {m.flags.length}</span>}</div>
        </td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{m.kind === 'fund' ? 'Fund' : fmtCap(m.marketCap)}</td>
        {['1M', '3M', '1Y', '3Y'].map(p => <RetCell key={p} v={m.returns[p]} col={p} />)}
        <td className={`px-2 py-2 text-right tabular-nums border-t border-gray-800/60 ${signedClass(m.upside?.mean)}`}>{m.upside ? fmtPct(m.upside.mean, { digits: 0 }) : DASH}</td>
        <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{fmtPct(m.growth, { signed: false, digits: 0 })}</td>
        <td className={`px-2 py-2 border-t border-gray-800/60 whitespace-nowrap ${RISK_CLS[m.risk]}`}>{m.risk}</td>
        <td className="px-2 py-2 border-t border-gray-800/60"><div className="flex items-center gap-2"><span className="tabular-nums text-gray-100 font-semibold w-7 text-right">{m.setup.score == null ? DASH : Math.round(m.setup.score)}</span><SetupPill setup={m.setup} /></div></td>
      </tr>
      {open && <tr><td colSpan={11} className="border-t border-gray-800/60"><Detail m={m} names={names} onChart={onChart} /></td></tr>}
    </>
  )
}
