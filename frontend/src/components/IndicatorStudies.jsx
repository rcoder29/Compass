import { useState, useEffect } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, fmtPct, signedClass, heat } from './MacroKit'

const HORIZON_LABEL = { 1: '1 month', 3: '3 months', 6: '6 months', 12: '12 months', 36: '3 years' }
const SECTOR_NAMES = { XLK: 'Technology', XLF: 'Financials', XLV: 'Health Care', XLY: 'Cons. Discretionary', XLP: 'Cons. Staples', XLE: 'Energy', XLI: 'Industrials', XLB: 'Materials', XLU: 'Utilities', XLRE: 'Real Estate', XLC: 'Comm. Services' }

function DistributionChart({ dist }) {
  const { edges, study, baseline } = dist
  const max = Math.max(...study, ...baseline, 1)
  const W = 560, H = 150, pad = 18, bw = (W - pad * 2) / study.length
  const label = (i) => (i === 0 ? `<${edges[1]}%` : i === study.length - 1 ? `>${edges[i]}%` : `${edges[i]}`)
  return (
    <svg viewBox={`0 0 ${W} ${H + 22}`} className="w-full" role="img" aria-label="Distribution of 12-month S&P 500 returns after the condition began versus any month">
      {study.map((v, i) => (
        <g key={i}>
          <rect x={pad + i * bw + 2} width={bw / 2 - 2} y={H - (baseline[i] / max) * (H - 10)} height={(baseline[i] / max) * (H - 10)} fill="#64748b" opacity="0.7" />
          <rect x={pad + i * bw + bw / 2} width={bw / 2 - 2} y={H - (v / max) * (H - 10)} height={(v / max) * (H - 10)} fill="#38bdf8" />
          <text x={pad + i * bw + bw / 2} y={H + 12} textAnchor="middle" fontSize="8" fill="#6b7280">{label(i)}</text>
        </g>
      ))}
      <line x1={pad} x2={W - pad} y1={H} y2={H} stroke="#374151" />
    </svg>
  )
}

function ResultView({ result }) {
  if (result.unavailable) {
    return <Card><p className="text-sm text-gray-300">{result.study.name}</p><p className="text-xs text-gray-500 mt-1">There isn&apos;t enough data to study this condition (it never occurred in the available history).</p></Card>
  }
  const { study, horizons } = result
  const h12 = horizons.find(h => h.months === 12)
  return (
    <div className="space-y-4">
      <Card title={study.name} right={result.currentlyActive ? <span className="text-amber-300 font-medium">Active now</span> : 'Not active now'}>
        <p className="text-xs text-gray-500">{study.condition}</p>
        {result.headline && <p className="text-sm text-gray-100 mt-3 leading-relaxed" data-testid="study-headline">{result.headline}</p>}
        <p className="text-[11px] text-gray-500 mt-2">
          {result.episodeCount} episode{result.episodeCount === 1 ? '' : 's'} ({result.monthsInState} months in the state) between {result.sampleStart} and {result.sampleEnd}.
          {result.thin && <span className="text-amber-300"> Very few episodes — treat as anecdotal.</span>}
        </p>
      </Card>

      <Card title="S&P 500 after the condition began vs any time" right="price return, episode start = 100% of weight">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[11px] text-gray-500">
                <th className="text-left py-1.5 font-medium">Next…</th>
                <th className="text-right font-medium">Avg return</th><th className="text-right font-medium">Median</th><th className="text-right font-medium">% higher</th>
                <th className="text-right font-medium">Worst</th><th className="text-right font-medium">Episodes</th>
                <th className="text-right font-medium text-gray-600 pl-4">Any-time avg</th><th className="text-right font-medium text-gray-600">Any-time % higher</th><th className="text-right font-medium">Difference</th>
              </tr>
            </thead>
            <tbody>
              {horizons.map(h => {
                const e = h.episodes, b = h.baseline
                const diff = e && b ? e.mean - b.mean : null
                return (
                  <tr key={h.months} className="border-t border-gray-800/70">
                    <td className="py-1.5 text-gray-200">{HORIZON_LABEL[h.months]}</td>
                    <td className={`text-right tabular-nums ${signedClass(e?.mean)}`}>{fmtPct(e?.mean)}</td>
                    <td className={`text-right tabular-nums ${signedClass(e?.median)}`}>{fmtPct(e?.median)}</td>
                    <td className="text-right tabular-nums text-gray-300">{e ? fmtPct(e.pctPositive, { signed: false, digits: 0 }) : '—'}</td>
                    <td className="text-right tabular-nums text-red-300/80">{fmtPct(e?.worst, { signed: false, digits: 0 })}</td>
                    <td className="text-right tabular-nums text-gray-400">{e?.n ?? 0}</td>
                    <td className="text-right tabular-nums text-gray-500 pl-4">{fmtPct(b?.mean)}</td>
                    <td className="text-right tabular-nums text-gray-500">{b ? fmtPct(b.pctPositive, { signed: false, digits: 0 }) : '—'}</td>
                    <td className="text-right tabular-nums rounded" style={heat(diff, 0.15)}><span className={signedClass(diff)}>{diff == null ? '—' : fmtPct(diff)}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="12-month outcomes" right={<span><span className="text-sky-400">■</span> after condition &nbsp;<span className="text-slate-400">■</span> any month</span>}>
          <DistributionChart dist={result.distribution12m} />
          <p className="text-[11px] text-gray-500">Share of outcomes in each return bucket (%). {h12?.episodes && `Worst episode: ${fmtPct(h12.episodes.worst)}, best: ${fmtPct(h12.episodes.best)}.`}</p>
        </Card>
        <Card title="Sectors vs S&P 500, next 12 months" right="since 1999 — few episodes">
          {result.sectors12m.length === 0 ? <p className="text-xs text-gray-500">No sector history overlaps these episodes (sector ETFs start in 1999).</p> : (
            <ul className="space-y-1.5 text-xs">
              {result.sectors12m.map(s => (
                <li key={s.symbol} className="flex items-center gap-2">
                  <span className="w-28 text-gray-300 truncate">{SECTOR_NAMES[s.symbol] || s.symbol}</span>
                  <div className="flex-1 h-2 relative bg-gray-800 rounded">
                    <div className={`absolute h-full rounded ${s.avgExcess >= 0 ? 'bg-emerald-500/70' : 'bg-red-500/70'}`}
                         style={s.avgExcess >= 0 ? { left: '50%', width: `${Math.min(Math.abs(s.avgExcess) / 0.25, 1) * 50}%` } : { right: '50%', width: `${Math.min(Math.abs(s.avgExcess) / 0.25, 1) * 50}%` }} />
                  </div>
                  <span className={`w-14 text-right tabular-nums ${signedClass(s.avgExcess)}`}>{fmtPct(s.avgExcess)}</span>
                  <span className="w-12 text-right text-gray-500">{s.n} ep{s.thin ? '*' : ''}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[11px] text-gray-600 mt-2">* fewer than 4 episodes. Average 12-month return minus SPY across the episodes.</p>
        </Card>
      </div>

      <Card title="Episode by episode" right="most recent 15">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1.5 font-medium">Began</th><th className="text-left font-medium">Lasted</th><th className="text-left font-medium">Entry</th>{[1, 3, 6, 12, 36].map(m => <th key={m} className="text-right font-medium">+{m}m</th>)}</tr></thead>
            <tbody>
              {[...result.episodes].reverse().map(ep => (
                <tr key={ep.start} className="border-t border-gray-800/70">
                  <td className="py-1.5 text-gray-200">{ep.start}</td><td className="text-gray-400">{ep.months} mo</td><td className="text-gray-500">{ep.entry}</td>
                  {[1, 3, 6, 12, 36].map(m => <td key={m} className={`text-right tabular-nums ${signedClass(ep.forward[m])}`} style={heat(ep.forward[m], 0.3)}>{fmtPct(ep.forward[m])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Caveats title="How to read this honestly" items={result.notes} />
    </div>
  )
}

export default function IndicatorStudies() {
  const list = useApi('/api/economy/studies')
  const [id, setId] = useState(null)
  useEffect(() => { if (!id && list.data?.studies?.length) setId(list.data.studies[0].id) }, [list.data, id])
  const result = useApi(id ? `/api/economy/studies/${id}` : null)
  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Indicator Studies">
        What has the stock market actually done after a macro condition appeared — an inverted yield curve, a jump in jobless claims, hot inflation?
        Each study measures S&amp;P 500 and sector returns over the following 1 month to 3 years, against what a random month would have delivered.
      </PageHeader>
      {list.loading && <Loading />}
      {list.error && <ErrorBox>{list.error}</ErrorBox>}
      {list.data && (
        <div className="grid lg:grid-cols-[280px_1fr] gap-4 items-start">
          <nav aria-label="Studies" className="bg-gray-900/60 border border-gray-800 rounded-xl p-2 lg:sticky lg:top-2 max-h-[80vh] overflow-auto">
            {list.data.studies.map(s => (
              <button key={s.id} onClick={() => setId(s.id)} aria-current={id === s.id ? 'true' : undefined}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${id === s.id ? 'bg-emerald-600/20 text-emerald-300' : 'text-gray-300 hover:bg-gray-800/60'}`}>
                <div className="font-medium">{s.name}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">{s.question}</div>
              </button>
            ))}
          </nav>
          <div>
            {result.loading && <Loading>Running the study…</Loading>}
            {result.error && <ErrorBox>{result.error}</ErrorBox>}
            {result.data && !result.loading && <ResultView result={result.data} />}
          </div>
        </div>
      )}
    </div>
  )
}
