import { useState, useEffect, useRef, useMemo } from 'react'

// Shared building blocks for the Economy and Sectors pages: a fetch hook, formatters, a plain-SVG time-series
// chart with recession shading, sparklines and a few small presentational pieces.

// ── Data ──────────────────────────────────────────────────────────────────────

export function useApi(url) {
  const [state, setState] = useState({ data: null, loading: !!url, error: null })
  const req = useRef(0)
  useEffect(() => {
    if (!url) { setState({ data: null, loading: false, error: null }); return }
    const id = ++req.current
    setState(s => ({ data: s.data, loading: true, error: null }))
    fetch(url)
      .then(async r => {
        const j = await r.json().catch(() => ({}))
        if (id !== req.current) return
        if (!r.ok) setState({ data: null, loading: false, error: j.detail || `Request failed (${r.status})` })
        else setState({ data: j, loading: false, error: null })
      })
      .catch(e => { if (id === req.current) setState({ data: null, loading: false, error: e.message }) })
  }, [url])
  return state
}

// ── Formatting ────────────────────────────────────────────────────────────────

export const DASH = '—'

// v is a fraction (0.153 → +15.3%)
export function fmtPct(v, { signed = true, digits = 1 } = {}) {
  if (v == null || Number.isNaN(v)) return DASH
  const p = v * 100
  const body = Math.abs(p) >= 1000 ? Math.round(p).toLocaleString('en-US') : p.toFixed(Math.abs(p) >= 100 ? 0 : digits)
  return (signed && p > 0 ? '+' : '') + body + '%'
}

// With no `digits`, precision scales with magnitude (1.23, 123.5, 12,346); an explicit `digits` is always honoured.
export function fmtNum(v, digits) {
  if (v == null || Number.isNaN(v)) return DASH
  const abs = Math.abs(v)
  const d = digits != null ? digits : abs >= 1000 ? 0 : abs >= 100 ? 1 : 2
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

// An indicator reading with its unit: 4.2% / 198K / 1.05 pts / 18.3
export function fmtValue(v, unit) {
  if (v == null || Number.isNaN(v)) return DASH
  if (unit === '%') return `${fmtNum(v)}%`
  if (unit === 'pts') return `${fmtNum(v)} pts`
  if (unit === '$') return `$${fmtNum(v)}`
  if (unit === '$B') return `$${fmtNum(v)}B`
  if (unit === '$T') return `$${fmtNum(v)}T`
  if (unit === 'K') return `${fmtNum(v, 0)}K`
  if (unit === 'M') return `${fmtNum(v)}M`
  return `${fmtNum(v)}${unit ? ' ' + unit : ''}`
}

export const signedClass = v => (v == null ? 'text-gray-500' : v > 0 ? 'text-emerald-300' : v < 0 ? 'text-red-300' : 'text-gray-300')

// Cell colouring for a fraction, saturating at ±max
export function heat(v, max) {
  if (v == null || Number.isNaN(v)) return {}
  const a = Math.min(Math.abs(v) / max, 1) * 0.55
  return { backgroundColor: v >= 0 ? `rgba(16,185,129,${a.toFixed(3)})` : `rgba(239,68,68,${a.toFixed(3)})` }
}

export const SIGNAL = {
  supportive: { label: 'Supportive', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', dot: 'bg-emerald-400' },
  neutral: { label: 'Neutral', cls: 'text-gray-300 bg-gray-700/40 border-gray-600', dot: 'bg-gray-400' },
  cautionary: { label: 'Cautionary', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30', dot: 'bg-amber-400' },
}

// ── Small pieces ──────────────────────────────────────────────────────────────

export function PageHeader({ title, children }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
      {children && <p className="text-xs text-gray-500 mt-0.5 max-w-3xl">{children}</p>}
    </div>
  )
}

export function Loading({ children = 'Loading…' }) {
  return <div className="text-xs text-gray-500 animate-pulse py-6 text-center">{children}</div>
}

export function ErrorBox({ children }) {
  return <div role="alert" className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{children}</div>
}

export function Caveats({ items, title = 'Read this first' }) {
  if (!items?.length) return null
  return (
    <details className="text-xs text-gray-400 bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2">
      <summary className="cursor-pointer text-gray-300 select-none">{title}</summary>
      <ul className="list-disc pl-5 mt-2 space-y-1">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </details>
  )
}

export function Card({ title, right, children, className = '' }) {
  return (
    <section className={`bg-gray-900/60 border border-gray-800 rounded-xl p-4 ${className}`}>
      {(title || right) && (
        <div className="flex items-start justify-between gap-3 mb-3">
          {title && <h3 className="text-sm font-semibold text-gray-200">{title}</h3>}
          {right && <div className="text-[11px] text-gray-500">{right}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border border-gray-700 overflow-hidden">
      {options.map(([id, text]) => (
        <button key={id} onClick={() => onChange(id)} aria-pressed={value === id}
                className={`px-3 py-1.5 text-xs transition-colors ${value === id ? 'bg-emerald-600/20 text-emerald-300' : 'text-gray-400 hover:text-gray-200'}`}>
          {text}
        </button>
      ))}
    </div>
  )
}

// ── Charts ────────────────────────────────────────────────────────────────────

export function Sparkline({ values, width = 84, height = 22, color = '#94a3b8' }) {
  if (!values || values.length < 2) return <svg width={width} height={height} aria-hidden="true" />
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * (width - 2) + 1).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`)
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="shrink-0">
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1].split(',')[0]} cy={pts[pts.length - 1].split(',')[1]} r="1.8" fill={color} />
    </svg>
  )
}

const T = s => new Date(s + 'T00:00:00Z').getTime()

// Nice axis ticks between lo and hi
export function niceTicks(lo, hi, count = 5) {
  if (!(hi > lo)) return [lo]
  const raw = (hi - lo) / count
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || raw
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10))
  return out
}

/**
 * Time-series line chart.
 *  series: [{ name, color, points: [[date, value], ...], dashed? }]
 *  bands:  [{ start, end }]            shaded spans (NBER recessions)
 *  lines:  [{ y, label, color? }]       horizontal reference lines
 *  format: value → string for axis and tooltip
 */
export function TimeChart({ series, bands = [], lines = [], height = 260, format = v => fmtNum(v), label = 'Chart', zeroLine = false }) {
  const [hover, setHover] = useState(null)
  const ref = useRef(null)
  const W = 900, PAD = { l: 52, r: 12, t: 10, b: 24 }
  const all = useMemo(() => series.flatMap(s => s.points), [series])
  const geo = useMemo(() => {
    if (!all.length) return null
    const xs = all.map(p => T(p[0])), ys = all.map(p => p[1]).concat(lines.map(l => l.y))
    let lo = Math.min(...ys, zeroLine ? 0 : Infinity), hi = Math.max(...ys, zeroLine ? 0 : -Infinity)
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.06
    lo -= pad; hi += pad
    return { x0: Math.min(...xs), x1: Math.max(...xs), lo, hi }
  }, [all, lines, zeroLine])
  if (!geo) return <div className="text-xs text-gray-500 py-8 text-center">No data to chart.</div>
  const sx = t => PAD.l + ((t - geo.x0) / (geo.x1 - geo.x0 || 1)) * (W - PAD.l - PAD.r)
  const sy = v => PAD.t + (1 - (v - geo.lo) / (geo.hi - geo.lo)) * (height - PAD.t - PAD.b)
  const yTicks = niceTicks(geo.lo, geo.hi, 5)
  const years = []
  const y0 = new Date(geo.x0).getUTCFullYear(), y1 = new Date(geo.x1).getUTCFullYear()
  const stride = [1, 2, 5, 10, 20, 25, 50].find(st => (y1 - y0) / st <= 8) || 50
  for (let y = Math.ceil(y0 / stride) * stride; y <= y1; y += stride) years.push(y)

  const nearest = x => {
    const t = geo.x0 + ((x - PAD.l) / (W - PAD.l - PAD.r)) * (geo.x1 - geo.x0)
    const primary = series[0].points
    let lo = 0, hi = primary.length - 1
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (T(primary[mid][0]) < t) lo = mid; else hi = mid }
    const i = Math.abs(T(primary[lo][0]) - t) < Math.abs(T(primary[hi][0]) - t) ? lo : hi
    return primary[i][0]
  }
  const onMove = e => {
    const r = ref.current.getBoundingClientRect()
    setHover(nearest(((e.clientX - r.left) / r.width) * W))
  }
  const tipRows = hover ? series.map(s => {
    const p = s.points.find(pt => pt[0] === hover) || s.points.reduce((best, pt) => (Math.abs(T(pt[0]) - T(hover)) < Math.abs(T(best[0]) - T(hover)) ? pt : best), s.points[0])
    return { name: s.name, color: s.color, value: p[1], date: p[0] }
  }) : []

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${height}`} className="w-full h-auto select-none" role="img" aria-label={label}
           onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {bands.map((b, i) => {
          const a = Math.max(T(b.start), geo.x0), z = Math.min(T(b.end) + 30 * 864e5, geo.x1)
          return z > a ? <rect key={i} x={sx(a)} y={PAD.t} width={Math.max(sx(z) - sx(a), 1.5)} height={height - PAD.t - PAD.b} fill="rgba(148,163,184,0.16)" /> : null
        })}
        {yTicks.map(v => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(v)} y2={sy(v)} stroke="#1f2937" strokeWidth="1" />
            <text x={PAD.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="10" fill="#6b7280">{format(v)}</text>
          </g>
        ))}
        {years.map(y => {
          const x = sx(Date.UTC(y, 0, 1))
          return x >= PAD.l && x <= W - PAD.r ? <text key={y} x={x} y={height - 6} textAnchor="middle" fontSize="10" fill="#6b7280">{y}</text> : null
        })}
        {lines.map((l, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(l.y)} y2={sy(l.y)} stroke={l.color || '#f59e0b'} strokeWidth="1" strokeDasharray="4 3" opacity="0.8" />
            <text x={W - PAD.r - 2} y={sy(l.y) - 3} textAnchor="end" fontSize="10" fill={l.color || '#f59e0b'}>{l.label}</text>
          </g>
        ))}
        {zeroLine && geo.lo < 0 && geo.hi > 0 && <line x1={PAD.l} x2={W - PAD.r} y1={sy(0)} y2={sy(0)} stroke="#475569" strokeWidth="1" />}
        {series.map(s => (
          <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="1.6" strokeLinejoin="round" strokeDasharray={s.dashed ? '5 3' : undefined}
                    points={s.points.map(p => `${sx(T(p[0])).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(' ')} />
        ))}
        {hover && <line x1={sx(T(hover))} x2={sx(T(hover))} y1={PAD.t} y2={height - PAD.b} stroke="#64748b" strokeWidth="1" />}
        {hover && tipRows.map(r => <circle key={r.name} cx={sx(T(r.date))} cy={sy(r.value)} r="3" fill={r.color} />)}
      </svg>
      {hover && (
        <div className="absolute top-1 left-14 bg-gray-950/90 border border-gray-700 rounded-md px-2 py-1 text-[11px] pointer-events-none" data-testid="chart-tip">
          <div className="text-gray-400">{hover}</div>
          {tipRows.map(r => <div key={r.name} style={{ color: r.color }}>{series.length > 1 ? `${r.name}: ` : ''}{format(r.value)}</div>)}
        </div>
      )}
    </div>
  )
}

export const RANGES = [['5Y', 5], ['10Y', 10], ['20Y', 20], ['Max', 0]]

// Trim [date, value] points to the last `years` years (0 = all)
export function trimPoints(points, years) {
  if (!points?.length || !years) return points || []
  const last = new Date(points[points.length - 1][0] + 'T00:00:00Z')
  const cutoff = new Date(Date.UTC(last.getUTCFullYear() - years, last.getUTCMonth(), last.getUTCDate())).toISOString().slice(0, 10)
  return points.filter(p => p[0] >= cutoff)
}
