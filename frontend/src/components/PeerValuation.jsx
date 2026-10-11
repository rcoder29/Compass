import { useState } from 'react'
import { usePolledApi } from './MacroKit'

// Body of the Tear Sheet's "Versus peers" section (the page wraps it in its own Section). Loads separately from the sheet.

const DASH = '—'
const TONE = { good: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', bad: 'text-red-300 bg-red-500/10 border-red-500/30', neutral: 'text-amber-300 bg-amber-500/10 border-amber-500/30' }

export const fmtMetric = (v, unit) => (v == null ? DASH : unit === 'x' ? `${v.toFixed(1)}x` : `${(v * 100).toFixed(1)}%`)
export const fmtPrem = v => (v == null ? DASH : `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(0)}%`)
const money = v => (v == null ? DASH : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
const bigCap = v => (v == null ? DASH : v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`)

function RankBar({ label, value, hint, color }) {
  return (
    <div>
      <div className="flex justify-between text-[11px] text-gray-400 mb-1"><span>{label}</span><span className="font-mono text-gray-200">{value == null ? DASH : Math.round(value)}</span></div>
      <div className="relative h-2 bg-gray-800 rounded" role="img" aria-label={`${label}: ${value == null ? 'no data' : Math.round(value)} out of 100`}>
        <div className="absolute inset-y-0 left-1/2 w-px bg-gray-600" />
        {value != null && <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-gray-950" style={{ left: `calc(${value}% - 6px)`, background: color }} />}
      </div>
      <div className="text-[10px] text-gray-600 mt-1">{hint}</div>
    </div>
  )
}

export function Scatter({ data, symbol }) {
  const pts = data.points
  const W = 520, H = 220, P = { l: 44, r: 12, t: 10, b: 30 }
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys, 0), y1 = Math.max(...ys)
  const sx = v => P.l + ((v - x0) / (x1 - x0 || 1)) * (W - P.l - P.r)
  const sy = v => H - P.b - ((v - y0) / (y1 - y0 || 1)) * (H - P.t - P.b)
  const fy = v => (data.yKey === 'fcfYield' ? `${(v * 100).toFixed(0)}%` : `${v.toFixed(0)}x`)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`${data.yLabel} against ${data.xLabel.toLowerCase()} for ${symbol} and its peers`}>
      {[0, 0.5, 1].map(t => { const v = y0 + t * (y1 - y0); return <g key={t}><line x1={P.l} x2={W - P.r} y1={sy(v)} y2={sy(v)} stroke="#1f2937" /><text x={P.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="9" fill="#6b7280">{fy(v)}</text></g> })}
      {[0, 0.5, 1].map(t => { const v = x0 + t * (x1 - x0); return <text key={t} x={sx(v)} y={H - 12} textAnchor="middle" fontSize="9" fill="#6b7280">{`${(v * 100).toFixed(0)}%`}</text> })}
      <text x={W / 2} y={H - 1} textAnchor="middle" fontSize="9" fill="#6b7280">{data.xLabel} →</text>
      <text x={10} y={H / 2} fontSize="9" fill="#6b7280" textAnchor="middle" transform={`rotate(-90 10 ${H / 2})`}>{data.yLabel} →</text>
      {pts.filter(p => !p.isSubject).map(p => (
        <g key={p.symbol}><circle cx={sx(p.x)} cy={sy(p.y)} r="4" fill="#64748b" opacity="0.8"><title>{`${p.symbol}: ${fy(p.y)}, growth ${(p.x * 100).toFixed(0)}%`}</title></circle>
          <text x={sx(p.x) + 6} y={sy(p.y) + 3} fontSize="8" fill="#6b7280">{p.symbol}</text></g>
      ))}
      {pts.filter(p => p.isSubject).map(p => (
        <g key={p.symbol}><circle cx={sx(p.x)} cy={sy(p.y)} r="6" fill="#f59e0b" stroke="#0f172a" strokeWidth="1.5"><title>{`${p.symbol}: ${fy(p.y)}, growth ${(p.x * 100).toFixed(0)}%`}</title></circle>
          <text x={sx(p.x) + 9} y={sy(p.y) + 3} fontSize="10" fontWeight="700" fill="#fbbf24">{p.symbol}</text></g>
      ))}
    </svg>
  )
}

export function PeerComparison({ d }) {
  const v = d.verdict
  const valuation = d.metrics.filter(m => m.group === 'valuation'), quality = d.metrics.filter(m => m.group === 'quality')
  const imp = d.peerImplied
  const row = m => {
    const hasPeers = m.median != null
    const rel = m.premium
    return (
      <tr key={m.key} className="border-t border-gray-800/70">
        <td className="py-1.5 text-gray-300">{m.label}</td>
        <td className="text-right font-mono text-gray-100">{fmtMetric(m.value, m.unit)}</td>
        <td className="text-right font-mono text-gray-400">{fmtMetric(m.median, m.unit)}</td>
        <td className="text-right font-mono text-gray-600 hidden md:table-cell">{hasPeers ? `${fmtMetric(m.p25, m.unit)} – ${fmtMetric(m.p75, m.unit)}` : DASH}</td>
        <td className={`text-right font-mono ${rel == null ? 'text-gray-600' : rel > 0.05 ? 'text-red-400' : rel < -0.05 ? 'text-emerald-400' : 'text-gray-300'}`}>{m.group === 'valuation' ? fmtPrem(rel) : DASH}</td>
        <td className="text-right text-gray-500">{!hasPeers ? 'not enough peers' : m.group === 'valuation' ? `pricier than ${Math.round(m.expensiveness)}% of ${m.peers}` : `better than ${Math.round(m.quality)}% of ${m.peers}`}</td>
      </tr>
    )
  }
  return (
    <div className="space-y-4" data-testid="peer-comparison">
      <div className={`rounded-lg border px-3 py-2 ${TONE[v.tone] || TONE.neutral}`}>
        <div className="text-sm font-semibold">{v.label}</div>
        <p className="text-[12px] mt-0.5 text-gray-300">{v.text}</p>
        <p className="text-[11px] mt-1 text-gray-400">{d.headline}</p>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <RankBar label="How expensive vs peers" value={d.expensiveRank} color="#f87171" hint="0 = cheaper than every peer, 100 = pricier than every peer (average over the multiples below)" />
        <RankBar label="How strong vs peers" value={d.qualityRank} color="#34d399" hint="0 = weaker than every peer, 100 = better than every peer (growth, margin, return on equity)" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead><tr className="text-[10px] uppercase tracking-wider text-gray-500"><th className="text-left py-1 font-medium">Metric</th><th className="text-right font-medium">This stock</th><th className="text-right font-medium">Peer median</th><th className="text-right font-medium hidden md:table-cell">Peer range (25-75th)</th><th className="text-right font-medium">vs median</th><th className="text-right font-medium">Rank</th></tr></thead>
          <tbody>{valuation.map(row)}<tr><td colSpan={6} className="pt-3 pb-1 text-[10px] uppercase tracking-wider text-gray-500">Fundamentals</td></tr>{quality.map(row)}</tbody>
        </table>
      </div>
      {imp && (
        <div className="bg-gray-800/50 rounded-lg px-3 py-2 text-[12px]" data-testid="peer-implied">
          <span className="text-gray-400">At peer multiples the stock would trade near </span><span className="font-mono text-gray-100 font-semibold">{money(imp.mid)}</span>
          <span className="text-gray-400"> (middle half of peers: {money(imp.low)} – {money(imp.high)}), </span>
          <span className={`font-mono font-semibold ${imp.vsPrice >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtPrem(imp.vsPrice)}</span><span className="text-gray-400"> from {money(imp.price)}.</span>
          {imp.farFromPrice && <p role="note" className="text-[11px] text-amber-300 mt-1">This is more than three times above or below the market price, which usually means the peers are not a like-for-like match (different size, business mix or accounting). Do not read it as a target.</p>}
          <p className="text-[10px] text-gray-500 mt-1">Median of the implied prices from {imp.metrics.length} multiples. It ignores differences in growth, risk and accounting between companies, so use it as a reference point, not a target.</p>
        </div>
      )}
      {d.scatter && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Is a premium explained by growth? {d.scatter.yLabel} vs {d.scatter.xLabel.toLowerCase()}</div>
          <Scatter data={d.scatter} symbol={d.symbol} />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]" data-testid="peer-table">
          <thead><tr className="text-[10px] uppercase tracking-wider text-gray-500"><th className="text-left py-1 font-medium">Company</th><th className="text-right font-medium">Mkt cap</th><th className="text-right font-medium">P/E (fwd)</th><th className="text-right font-medium">EV/EBITDA</th><th className="text-right font-medium">P/S</th><th className="text-right font-medium">Rev growth</th><th className="text-right font-medium">Op margin</th></tr></thead>
          <tbody>
            {[{ ...d.subject, isSubject: true }, ...d.peers].map(p => (
              <tr key={p.symbol} className={`border-t border-gray-800/70 ${p.isSubject ? 'bg-amber-500/5' : ''}`}>
                <td className="py-1.5"><span className={`font-mono ${p.isSubject ? 'text-amber-300 font-semibold' : 'text-gray-200'}`}>{p.symbol}</span> <span className="text-gray-500">{p.name}</span></td>
                <td className="text-right font-mono text-gray-300">{bigCap(p.marketCap)}</td><td className="text-right font-mono text-gray-300">{fmtMetric(p.forwardPE, 'x')}</td>
                <td className="text-right font-mono text-gray-300">{fmtMetric(p.evToEbitda, 'x')}</td><td className="text-right font-mono text-gray-300">{fmtMetric(p.priceToSales, 'x')}</td>
                <td className="text-right font-mono text-gray-300">{fmtMetric(p.revenueGrowth, '%')}</td><td className="text-right font-mono text-gray-300">{fmtMetric(p.operatingMargin, '%')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.partial && <p role="note" className="text-[11px] text-amber-300">{d.partial.note}</p>}
      <p className="text-[10px] text-gray-500">{d.note} Companies account differently and the best peers are rarely identical: treat this as a reference point. Financial companies skip EV/EBITDA, FCF yield and price/sales, and REITs skip P/E, because those measures mean something different there.</p>
    </div>
  )
}

export default function PeerValuationBody({ symbol }) {
  const [attempt, setAttempt] = useState(0)                     // bumping this changes the URL, which makes the hook ask again
  const { data, error } = usePolledApi(`/api/tear-sheet/${encodeURIComponent(symbol)}/peers${attempt ? `?retry=${attempt}` : ''}`)
  if (error) return <div role="alert" className="text-xs text-red-400">{error}</div>
  if (!data) return <div className="text-xs text-gray-500 animate-pulse">Finding comparable companies…</div>
  if (data.status === 'running') {
    return (
      <div role="status">
        <div className="flex justify-between text-[11px] text-gray-400 mb-1"><span>Loading peer companies…</span><span className="font-mono">{data.progress.done} / {data.progress.total}</span></div>
        <div className="h-1.5 bg-gray-800 rounded"><div className="h-full bg-emerald-500 rounded transition-all" style={{ width: `${(data.progress.done / Math.max(data.progress.total, 1)) * 100}%` }} /></div>
        <p className="text-[10px] text-gray-500 mt-1">The first look at an industry takes a moment; after that it is cached and shared by every company in it.</p>
      </div>
    )
  }
  if (data.status === 'unavailable') {
    return (
      <div className="text-xs text-gray-500 italic">{data.reason}
        {data.transient && <button onClick={() => setAttempt(a => a + 1)} className="ml-3 not-italic px-2.5 py-1 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500">Try again</button>}
      </div>
    )
  }
  if (data.status !== 'ready' || !data.verdict || !data.metrics) return <div className="text-xs text-gray-500 italic">Peer comparison isn't available right now.</div>
  return <PeerComparison d={data} />
}
