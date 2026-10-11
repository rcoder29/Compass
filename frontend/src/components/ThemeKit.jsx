import { Card, fmtPct, fmtNum, signedClass, heat, Sparkline } from './MacroKit'

export const RETURN_COLS = ['1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y']
export const ROLE_ORDER = ['core', 'enabler', 'adjacent', 'emerging']
export const ROLE_NAMES = { core: 'Core leaders', enabler: 'Picks & shovels', adjacent: 'Other beneficiaries', emerging: 'Emerging & speculative' }
export const ROLE_BLURB = {
  core: 'Pure plays and the clear leaders', enabler: 'Suppliers the theme cannot grow without',
  adjacent: 'Large companies that benefit without depending on the theme', emerging: 'Small, early or unproven: high potential, high risk of permanent loss',
}
export const SETUP_CLS = { 'Stronger setup': 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', Mixed: 'text-gray-300 bg-gray-700/40 border-gray-600', 'Weaker setup': 'text-amber-300 bg-amber-500/10 border-amber-500/30' }
export const RISK_CLS = { Lower: 'text-emerald-300', Moderate: 'text-sky-300', High: 'text-amber-300', 'Very high': 'text-red-300' }

// colour scale for a return in a given column (longer horizons saturate later)
export const HEAT = { '1M': 0.2, '3M': 0.35, '6M': 0.5, YTD: 0.6, '1Y': 0.9, '3Y': 2, '5Y': 3 }

export function RetCell({ v, col }) {
  return <td className={`px-2 py-1.5 text-right tabular-nums border-t border-gray-800/60 ${signedClass(v)}`} style={heat(v, HEAT[col] ?? 0.5)}>{fmtPct(v, { digits: 0 })}</td>
}

export function SetupPill({ setup }) {
  return <span className={`px-2 py-0.5 rounded-full border text-[11px] whitespace-nowrap ${SETUP_CLS[setup.label]}`} title={setup.capReason || undefined}>{setup.label}</span>
}

// A compact basket-vs-SPY line from a theme's series points ([date, basket, spy])
export function MiniSeries({ series, color, width = 150, height = 36 }) {
  if (!series?.points?.length) return null
  return <Sparkline values={series.points.map(p => p[1])} width={width} height={height} color={color} />
}

export function Stat({ label, value, hint, tone }) {
  return (
    <div className="bg-gray-950/40 border border-gray-800 rounded-lg px-3 py-2">
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${tone || 'text-gray-100'}`}>{value}</div>
      {hint && <div className="text-[11px] text-gray-600">{hint}</div>}
    </div>
  )
}

export function List({ title, items, tone = 'text-gray-400', marker = '•' }) {
  return (
    <div>
      <div className="text-gray-300 font-medium text-xs mb-1.5">{title}</div>
      <ul className="space-y-1.5 text-xs">{items.map(t => <li key={t} className={`flex gap-2 ${tone}`}><span className="shrink-0">{marker}</span><span>{t}</span></li>)}</ul>
    </div>
  )
}

export function ScanProgress({ data }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4" role="status">
      <div className="flex justify-between text-xs text-gray-400 mb-2"><span>Reading company fundamentals and analyst targets…</span><span className="tabular-nums">{data.progress.done} / {data.progress.total}</span></div>
      <div className="h-2 bg-gray-800 rounded-full"><div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${(data.progress.done / Math.max(data.progress.total, 1)) * 100}%` }} /></div>
      <p className="text-[11px] text-gray-500 mt-2">The first load takes about a minute and serves every theme page; after that the data is cached for a day.</p>
    </div>
  )
}

export function PartialNote({ partial }) {
  if (!partial) return null
  return <div role="note" className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">{partial.note}</div>
}

export const Disclaimer = () => (
  <p className="text-[11px] text-gray-600">Returns are price changes (dividends excluded for individual stocks). Analyst targets and growth figures are opinions and trailing data, not forecasts. The commentary is editorial, written by hand and dated; companies change, so check anything you act on. Not investment advice: thematic stocks are volatile and can lose most of their value.</p>
)

export { Card, fmtPct, fmtNum }
