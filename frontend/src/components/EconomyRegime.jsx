import { useMemo } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, TimeChart, Sparkline, fmtValue, fmtNum } from './MacroKit'
import { SignalPill } from './EconomyIndicators'

export const PHASE_COLOR = { early: '#34d399', mid: '#38bdf8', late: '#fbbf24', slowdown: '#fb923c', recession: '#f87171' }
const PHASE_ORDER = ['early', 'mid', 'late', 'slowdown', 'recession']
const PHASE_NAME = { early: 'Early recovery', mid: 'Mid-cycle', late: 'Late cycle', slowdown: 'Slowdown', recession: 'Recession risk' }
const BAND_CLS = { Low: 'text-emerald-300', Moderate: 'text-sky-300', Elevated: 'text-amber-300', High: 'text-red-300' }

export function momentum(history, key, lag = 3) {
  return history.map((h, i) => (i >= lag ? { date: h.date, v: h[key] - history[i - lag][key] } : null)).filter(Boolean)
}

function RiskGauge({ score, band }) {
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className={`text-4xl font-semibold tabular-nums ${BAND_CLS[band]}`}>{Math.round(score)}</span>
        <span className="text-gray-500 text-xs">/ 100</span>
        <span className={`text-sm font-medium ${BAND_CLS[band]}`}>{band}</span>
      </div>
      <div className="relative h-2.5 rounded-full mt-3 overflow-hidden flex" role="img" aria-label={`Recession risk ${Math.round(score)} of 100, ${band}`}>
        <div className="bg-emerald-500/40 w-[20%]" /><div className="bg-sky-500/40 w-[20%]" /><div className="bg-amber-500/40 w-[20%]" /><div className="bg-red-500/40 w-[40%]" />
        <div className="absolute top-0 h-full w-1 bg-white rounded" style={{ left: `calc(${Math.min(score, 100)}% - 2px)` }} />
      </div>
      <div className="flex text-[10px] text-gray-500 mt-1"><span className="w-[20%]">Low</span><span className="w-[20%]">Moderate</span><span className="w-[20%]">Elevated</span><span>High (55+ has marked recessions)</span></div>
    </div>
  )
}

function QuadrantPlot({ history, quadrant }) {
  const g = momentum(history, 'growth'), i = momentum(history, 'inflation')
  const n = Math.min(g.length, i.length)
  const trail = Array.from({ length: Math.min(12, n) }, (_, k) => ({ x: i[i.length - 1 - k].v, y: g[g.length - 1 - k].v })).reverse()
  const m = Math.max(0.15, ...trail.map(p => Math.max(Math.abs(p.x), Math.abs(p.y)))) * 1.15
  const px = x => 100 + (x / m) * 90, py = y => 100 - (y / m) * 90
  const cell = (id, label, tint, x, y) => (
    <g key={id}>
      <rect x={x} y={y} width="100" height="100" fill={tint} opacity={quadrant.id === id ? 0.28 : 0.1} />
      <text x={x + 50} y={y + (y === 0 ? 14 : 92)} textAnchor="middle" fontSize="9" fill={quadrant.id === id ? '#e5e7eb' : '#6b7280'} fontWeight={quadrant.id === id ? 700 : 400}>{label}</text>
    </g>
  )
  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[260px]" role="img" aria-label={`Growth versus inflation momentum: currently ${quadrant.name}`}>
      {cell('goldilocks', 'Goldilocks', '#34d399', 0, 0)}
      {cell('overheating', 'Overheating', '#fb923c', 100, 0)}
      {cell('slowdown', 'Slowdown', '#38bdf8', 0, 100)}
      {cell('stagflation', 'Stagflation', '#f87171', 100, 100)}
      <line x1="100" x2="100" y1="0" y2="200" stroke="#374151" /><line x1="0" x2="200" y1="100" y2="100" stroke="#374151" />
      <polyline fill="none" stroke="#e5e7eb" strokeOpacity="0.6" strokeWidth="1" points={trail.map(p => `${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`).join(' ')} />
      {trail.length > 0 && <circle cx={px(trail[trail.length - 1].x)} cy={py(trail[trail.length - 1].y)} r="4.5" fill="#fff" stroke="#0f172a" strokeWidth="1.5" />}
      <text x="100" y="199" textAnchor="middle" fontSize="7" fill="#6b7280">inflation momentum →</text>
      <text x="6" y="100" fontSize="7" fill="#6b7280" transform="rotate(-90 6 100)" textAnchor="middle" dy="-0">growth momentum →</text>
    </svg>
  )
}

function PhaseStrip({ history }) {
  if (!history.length) return null
  const runs = []
  for (const h of history) {
    const last = runs[runs.length - 1]
    if (last && last.phase === h.phase) last.n += 1
    else runs.push({ phase: h.phase, n: 1, from: h.date })
  }
  return (
    <div>
      <div className="flex h-5 rounded overflow-hidden" role="img" aria-label="Cycle phase over the last ten years">
        {runs.map((r, k) => <div key={k} style={{ width: `${(r.n / history.length) * 100}%`, background: PHASE_COLOR[r.phase] }} title={`${PHASE_NAME[r.phase]} from ${r.from.slice(0, 7)} (${r.n} mo)`} />)}
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1"><span>{history[0].date.slice(0, 4)}</span><span>{history[history.length - 1].date.slice(0, 7)}</span></div>
      <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
        {PHASE_ORDER.map(p => <span key={p} className="flex items-center gap-1.5 text-gray-400"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: PHASE_COLOR[p] }} />{PHASE_NAME[p]}</span>)}
      </div>
    </div>
  )
}

function StressBar({ stress }) {
  const cls = stress >= 0.66 ? 'bg-red-500' : stress >= 0.25 ? 'bg-amber-500' : 'bg-emerald-500'
  return <div className="w-24 h-1.5 bg-gray-800 rounded-full"><div className={`h-full rounded-full ${cls}`} style={{ width: `${Math.max(stress * 100, 3)}%` }} /></div>
}

export default function EconomyRegime({ onNavigate }) {
  const { data, loading, error } = useApi('/api/economy/regime')
  const hist = data?.history || []
  const growthLine = useMemo(() => hist.map(h => [h.date, h.growth]), [hist])
  const inflLine = useMemo(() => hist.map(h => [h.date, h.inflation]), [hist])
  const riskLine = useMemo(() => hist.filter(h => h.risk != null).map(h => [h.date, h.risk]), [hist])

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Regime Dashboard">
        Where the economy sits in the cycle, which way growth and inflation are moving, and how many recession warning signs are lit.
        Each reading is a transparent rule applied to the indicators on the Indicators page.
      </PageHeader>
      <Caveats items={[
        'Everything here summarises current conditions with fixed rules; it does not predict. Recession risk, in particular, has to be judged by its record, shown at the bottom of this page.',
        'Uses FRED\'s revised data. A real-time observer would have seen noisier and later readings than the history here suggests.',
        'Growth and inflation scores compare each reading with that indicator\'s own history up to that date, so a 1990s reading is not judged against 2020s data.',
      ]} />
      {loading && <Loading>Building the regime from FRED data…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <>
          <div className="grid lg:grid-cols-3 gap-4">
            <Card title="Cycle phase" right={`as of ${data.asOf.slice(0, 7)}`}>
              <div className="text-2xl font-semibold" style={{ color: PHASE_COLOR[data.phase.id] }}>{data.phase.name}</div>
              <p className="text-xs text-gray-400 mt-2">{data.phase.description}</p>
              <div className="mt-4"><PhaseStrip history={hist} /></div>
            </Card>
            <Card title="Growth &amp; inflation">
              <div className="flex gap-4 items-center">
                <QuadrantPlot history={hist} quadrant={data.quadrant} />
                <div className="text-xs space-y-2">
                  <div className="text-lg font-semibold text-gray-100">{data.quadrant.name}</div>
                  <p className="text-gray-400">{data.quadrant.description}</p>
                  <p className="text-gray-500">{data.growth.label}.</p>
                  <p className="text-gray-500">{data.inflation.label}.</p>
                </div>
              </div>
            </Card>
            <Card title="Recession risk">
              {data.recession ? (
                <>
                  <RiskGauge score={data.recession.score} band={data.recession.band} />
                  {data.recession.curve && (
                    <p className="text-xs text-gray-400 mt-4">
                      Yield curve (10Y − 3M): <span className="text-gray-100">{fmtNum(data.recession.curve.value)} pts</span>
                      {data.recession.curve.invertedNow ? ' — inverted now.' : data.recession.curve.lastInverted ? ` — last inverted ${data.recession.curve.lastInverted}.` : '.'}
                    </p>
                  )}
                </>
              ) : <div className="text-xs text-gray-500">Not enough data.</div>}
            </Card>
          </div>

          {data.keyIndicators?.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3" aria-label="Key indicators">
              {data.keyIndicators.map(k => (
                <button key={k.id} onClick={() => onNavigate?.('econindicators')} className="text-left bg-gray-900/60 border border-gray-800 hover:border-gray-600 rounded-lg px-3 py-2">
                  <div className="text-[11px] text-gray-500 truncate">{k.name}</div>
                  <div className="text-sm font-semibold text-gray-100 tabular-nums">{fmtValue(k.value, k.unit)}</div>
                  <div className="flex items-center justify-between mt-1"><Sparkline values={k.spark} width={56} height={16} /><SignalPill signal={k.signal} /></div>
                </button>
              ))}
            </div>
          )}

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title="Growth and inflation composites" right="0 = typical for its history; above 0 = stronger / hotter">
              <TimeChart series={[{ name: 'Growth', color: '#38bdf8', points: growthLine }, { name: 'Inflation', color: '#fb923c', points: inflLine }]}
                         height={220} zeroLine format={v => fmtNum(v)} label="Growth and inflation composites" />
              <div className="flex gap-4 text-[11px] mt-1"><span className="text-sky-300">— Growth</span><span className="text-orange-300">— Inflation</span></div>
            </Card>
            <Card title="Recession-risk score, last 10 years" right="55+ = recession phase">
              <TimeChart series={[{ name: 'Risk score', color: '#f87171', points: riskLine }]} lines={[{ y: 55, label: 'recession phase' }]} height={220} format={v => Math.round(v)} label="Recession risk score history" />
            </Card>
          </div>

          {data.recession && (
            <Card title="What is driving recession risk" right="weights sum to 100">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1.5 font-medium">Warning sign</th><th className="text-right font-medium">Latest</th><th className="text-left px-3 font-medium">Stress</th><th className="text-right font-medium">Weight</th><th className="text-left px-3 font-medium">Rule</th></tr></thead>
                  <tbody>
                    {data.recession.components.map(c => (
                      <tr key={c.id} className="border-t border-gray-800/70">
                        <td className="py-2 text-gray-100">{c.name}<div className="text-[10px] text-gray-600">{c.date.slice(0, 7)}</div></td>
                        <td className="text-right tabular-nums text-gray-200">{fmtValue(c.value, c.unit)}</td>
                        <td className="px-3"><div className="flex items-center gap-2"><StressBar stress={c.stress} /><span className={`text-[11px] ${c.status === 'high' ? 'text-red-300' : c.status === 'watch' ? 'text-amber-300' : 'text-emerald-300'}`}>{c.status === 'high' ? 'Flashing' : c.status === 'watch' ? 'Watch' : 'Calm'}</span></div></td>
                        <td className="text-right tabular-nums text-gray-400">{c.weight}</td>
                        <td className="px-3 text-gray-500">{c.rule}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title="How the score behaved around past recessions" right="since 1973, NBER dates">
              {data.trackRecord.length === 0 ? <div className="text-xs text-gray-500">Not enough history.</div> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1.5 font-medium">Recession</th><th className="text-right font-medium">Peak score</th><th className="text-right font-medium">First 40+</th><th className="text-right font-medium">vs start</th></tr></thead>
                  <tbody>
                    {data.trackRecord.map(t => (
                      <tr key={t.start} className="border-t border-gray-800/70">
                        <td className="py-1.5 text-gray-200">{t.start} to {t.end}</td>
                        <td className="text-right tabular-nums text-gray-200">{Math.round(t.peak)}</td>
                        <td className="text-right text-gray-300">{t.firstWarning ?? 'never'}</td>
                        <td className="text-right text-gray-400">{t.monthsFromStart == null ? '—' : t.monthsFromStart < 0 ? `${-t.monthsFromStart} mo early` : t.monthsFromStart === 0 ? 'on time' : `${t.monthsFromStart} mo late`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="text-[11px] text-gray-500 mt-2">The score has also lingered for months after recessions ended, and has crossed 40 without a recession (for example 2024). Treat it as a conditions gauge, not a timing tool.</p>
            </Card>
            <Card title="What this means for markets">
              <div className="text-xs text-gray-400 space-y-3">
                <p><span className="text-gray-200 font-medium">Short term (next few months): </span>{data.quadrant.description}</p>
                <p><span className="text-gray-200 font-medium">Longer term (a year or more): </span>{data.phase.description}</p>
                <p className="text-gray-500">Use the Indicator Studies page to see how stocks have actually behaved after similar conditions, and Cycle Fit to see which sectors have led in this phase.</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button onClick={() => onNavigate?.('econstudies')} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Indicator Studies →</button>
                  <button onClick={() => onNavigate?.('sectorcycle')} className="px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Sector Cycle Fit →</button>
                </div>
              </div>
            </Card>
          </div>
          <p className="text-[11px] text-gray-600">{data.method}</p>
        </>
      )}
    </div>
  )
}
