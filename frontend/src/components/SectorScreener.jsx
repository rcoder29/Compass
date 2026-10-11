import { useState, useMemo } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, Segmented, fmtNum } from './MacroKit'

const HORIZONS = [['tactical', 'Tactical · 1-3 months'], ['intermediate', 'Intermediate · 3-12 months'], ['strategic', 'Strategic · 1-5+ years']]
const TIER_CLS = { Overweight: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', Neutral: 'text-gray-300 bg-gray-700/40 border-gray-600', Underweight: 'text-red-300 bg-red-500/10 border-red-500/30' }
const FACTOR_COLOR = { momentum: '#38bdf8', trend: '#34d399', rotation: '#a78bfa', risk: '#fbbf24', drawdown: '#fb923c', seasonality: '#f472b6', cycle: '#2dd4bf' }

export function weightsParam(weights, defaults) {
  const same = Object.keys({ ...weights, ...defaults }).every(k => (weights[k] || 0) === (defaults[k] || 0))
  return same ? '' : `&weights=${encodeURIComponent(JSON.stringify(weights))}`
}

function ScoreBar({ row }) {
  return (
    <div className="flex h-3 rounded overflow-hidden bg-gray-800 w-full" role="img" aria-label={`Score ${row.score} of 100`}>
      {Object.entries(row.factors).map(([f, v]) => <div key={f} style={{ width: `${v.contribution}%`, background: FACTOR_COLOR[f] }} title={`${f}: ${v.contribution} points`} />)}
    </div>
  )
}

export default function SectorScreener() {
  const [horizon, setHorizon] = useState('intermediate')
  const [custom, setCustom] = useState(null)        // {factor: weight} once the user moves a slider
  const [open, setOpen] = useState(null)
  const base = useApi(`/api/sectors/screener?horizon=${horizon}`)
  const defaults = base.data?.defaultWeights || {}
  const active = custom ?? base.data?.weights ?? {}
  const wp = custom ? weightsParam(custom, base.data?.weights || {}) : ''
  const tuned = useApi(wp ? `/api/sectors/screener?horizon=${horizon}${wp}` : null)
  const data = (wp && tuned.data) || base.data
  const loading = base.loading || (!!wp && tuned.loading)
  const error = base.error || tuned.error
  const names = data?.factorNames || {}
  const allFactors = useMemo(() => Object.keys(names), [names])

  const pickHorizon = h => { setHorizon(h); setCustom(null); setOpen(null) }
  const setWeight = (f, v) => setCustom({ ...(custom ?? base.data?.weights ?? {}), [f]: v })

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Sector Screener">
        Ranks the eleven sectors for the horizon you care about. Each factor is scored 0-100 by ranking the sectors against each other, then blended with weights suited to that horizon.
        You can change the weights; every score shows exactly what drove it.
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Horizon" options={HORIZONS} value={horizon} onChange={pickHorizon} />
        {data && <span className="text-xs text-gray-500">{data.horizonInfo.blurb}</span>}
        {data?.cyclePhase && <span className="text-xs text-teal-300 ml-auto">Current cycle phase: {data.cyclePhase}</span>}
      </div>
      {loading && !data && <Loading>Scoring sectors…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <div className="grid xl:grid-cols-[1fr_300px] gap-4 items-start">
          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-hidden" data-testid="screener-table">
            {data.sectors.map(r => (
              <div key={r.symbol} className="border-b border-gray-800/70 last:border-0">
                <button onClick={() => setOpen(open === r.symbol ? null : r.symbol)} aria-expanded={open === r.symbol} className="w-full text-left px-4 py-3 hover:bg-gray-800/40">
                  <div className="flex items-center gap-3">
                    <span className="w-6 text-gray-500 text-xs tabular-nums">{r.rank}</span>
                    <div className="w-44"><div className="text-sm text-gray-100">{r.name}</div><div className="text-[11px] text-gray-500">{r.symbol}</div></div>
                    <div className="w-12 text-right text-lg font-semibold tabular-nums text-gray-100">{Math.round(r.score)}</div>
                    <div className="flex-1 min-w-[80px]"><ScoreBar row={r} /></div>
                    <span className={`px-2 py-0.5 rounded-full border text-[11px] w-24 text-center ${TIER_CLS[r.tier]}`}>{r.tier}</span>
                  </div>
                  <div className="text-[11px] text-gray-500 mt-1 ml-9">{r.why}</div>
                </button>
                {open === r.symbol && (
                  <div className="px-4 pb-3 ml-9 text-xs">
                    <table className="w-full max-w-xl">
                      <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1 font-medium">Factor</th><th className="text-right font-medium">Rank (0-100)</th><th className="text-right font-medium">Weight</th><th className="text-right font-medium">Points</th></tr></thead>
                      <tbody>
                        {Object.entries(r.factors).map(([f, v]) => (
                          <tr key={f} className="border-t border-gray-800/70">
                            <td className="py-1 text-gray-300"><span className="inline-block w-2 h-2 rounded-sm mr-2" style={{ background: FACTOR_COLOR[f] }} />{names[f]}</td>
                            <td className="text-right tabular-nums text-gray-300">{Math.round(v.rank)}</td>
                            <td className="text-right tabular-nums text-gray-500">{fmtNum(v.weight, 0)}%</td>
                            <td className="text-right tabular-nums text-gray-200">{fmtNum(v.contribution, 1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {r.missing.length > 0 && <p className="text-[11px] text-amber-300/80 mt-1">Not enough history for: {r.missing.map(f => names[f]).join(', ')} (weights re-balanced).</p>}
                  </div>
                )}
              </div>
            ))}
          </div>

          <Card title="Factor weights" right={custom && <button onClick={() => setCustom(null)} className="text-sky-400 hover:text-sky-300">Reset</button>}>
            <ul className="space-y-3">
              {allFactors.map(f => {
                const v = active[f] ?? 0
                const unavailable = f === 'cycle' && !(f in (base.data?.weights || {})) && !custom
                return (
                  <li key={f}>
                    <label className="flex items-center justify-between text-xs text-gray-300">
                      <span><span className="inline-block w-2 h-2 rounded-sm mr-2" style={{ background: FACTOR_COLOR[f] }} />{names[f]}</span>
                      <span className="tabular-nums text-gray-400">{Math.round(v)}</span>
                    </label>
                    <input type="range" min="0" max="60" step="5" value={v} aria-label={`${names[f]} weight`} disabled={f === 'cycle' && !('cycle' in (base.data?.weights || {}))}
                           onChange={e => setWeight(f, Number(e.target.value))} className="w-full accent-emerald-500" />
                    {unavailable && <div className="text-[10px] text-gray-600">Needs economic data (FRED) — currently unavailable.</div>}
                  </li>
                )
              })}
            </ul>
            <p className="text-[11px] text-gray-600 mt-3">Weights are relative; they are re-scaled to 100. Default for {data.horizonInfo.name.toLowerCase()}: {Object.entries(defaults).map(([f, w]) => `${names[f]?.split(' ')[0]} ${w}`).join(', ')}.</p>
          </Card>
        </div>
      )}
      {data && <Caveats title="How to use this" items={data.notes} />}
    </div>
  )
}
