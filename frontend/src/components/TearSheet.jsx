import { useState, useEffect } from 'react'

// ── Formatters ────────────────────────────────────────────────────────────────

const DASH = '—'

export function fmtMoney(n, decimals = 2, sym = '$') {
  if (n == null || isNaN(n)) return DASH
  return sym + n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function fmtBig(n, sym = '$') {
  if (n == null || isNaN(n)) return DASH
  const a = Math.abs(n), sign = n < 0 ? '-' : ''
  if (a >= 1e12) return `${sign}${sym}${(a / 1e12).toFixed(2)}T`
  if (a >= 1e9)  return `${sign}${sym}${(a / 1e9).toFixed(2)}B`
  if (a >= 1e6)  return `${sign}${sym}${(a / 1e6).toFixed(1)}M`
  return `${sign}${sym}${a.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

// Inputs are decimal fractions (0.153 = 15.3%)
export function fmtPct(n, decimals = 1, signed = false) {
  if (n == null || isNaN(n)) return DASH
  const v = (n * 100).toFixed(decimals)
  return (signed && n > 0 ? '+' : '') + v + '%'
}

export function fmtX(n, decimals = 1) {
  if (n == null || isNaN(n)) return DASH
  return n.toFixed(decimals) + 'x'
}

const fmtNum = (n, d = 2) => (n == null || isNaN(n) ? DASH : n.toFixed(d))
const fmtInt = n => (n == null || isNaN(n) ? DASH : Math.round(n).toLocaleString('en-US'))

const posNeg = n => (n == null || isNaN(n) ? 'text-gray-400' : n >= 0 ? 'text-emerald-400' : 'text-red-400')

const TONE = {
  good:    { text: 'text-emerald-400', pill: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' },
  bad:     { text: 'text-red-400',     pill: 'bg-red-500/10 border-red-500/30 text-red-300' },
  neutral: { text: 'text-amber-400',   pill: 'bg-amber-500/10 border-amber-500/30 text-amber-300' },
}

const scoreColor = s => (s == null ? '#4b5563' : s >= 67 ? '#10b981' : s >= 40 ? '#f59e0b' : '#ef4444')

// ── Layout primitives ─────────────────────────────────────────────────────────

function Section({ id, title, subtitle, children }) {
  return (
    <section id={id} className="ts-card bg-gray-900/60 border border-gray-800 rounded-xl p-4 break-inside-avoid">
      <div className="mb-3">
        <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">{title}</h3>
        {subtitle && <p className="text-[11px] text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

function Stat({ label, value, sub, valueClass = 'text-gray-100' }) {
  return (
    <div className="bg-gray-800/50 rounded-lg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className={`text-sm font-semibold font-mono ${valueClass}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function Empty({ children }) {
  return <div className="text-xs text-gray-500 italic">{children}</div>
}

function Table({ head, rows, align = 'right' }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            {head.map((h, i) => (
              <th key={i} className={`py-1.5 px-2 font-medium whitespace-nowrap ${i === 0 ? 'text-left' : `text-${align}`}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="border-b border-gray-800/50 last:border-0">
              {r.map((cell, ci) => {
                const c = cell != null && typeof cell === 'object' && 'v' in cell ? cell : { v: cell }
                return (
                  <td key={ci} className={`py-1.5 px-2 font-mono whitespace-nowrap ${ci === 0 ? 'text-left text-gray-300 font-sans' : `text-${align} text-gray-200`} ${c.cls || ''}`}>
                    {c.v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Charts (plain SVG, same approach as PriceProjection / MonteCarlo) ─────────

function LineChart({ dates, lines, height = 190, yFormat = v => v.toFixed(0), baseline }) {
  const W = 600, H = height
  if (!dates || dates.length < 2) return <Empty>Not enough price history.</Empty>
  const vals = lines.flatMap(l => l.values.filter(v => v != null))
  if (!vals.length) return <Empty>Not enough price history.</Empty>
  const lo = Math.min(...vals), hi = Math.max(...vals)
  const pad = (hi - lo) * 0.06 || 1
  const min = lo - pad, span = hi - lo + pad * 2
  const x = i => (i / (dates.length - 1)) * W
  const y = v => H - 16 - ((v - min) / span) * (H - 22)
  const path = values => {
    let d = '', pen = false
    values.forEach((v, i) => {
      if (v == null) { pen = false; return }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)} `
      pen = true
    })
    return d
  }
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => min + span * f)
  const yearMarks = []
  dates.forEach((d, i) => {
    if (i > 0 && d.slice(0, 4) !== dates[i - 1].slice(0, 4)) yearMarks.push({ i, label: d.slice(0, 4) })
  })
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="line chart">
      {ticks.map(t => (
        <g key={t}>
          <line x1={0} x2={W} y1={y(t)} y2={y(t)} stroke="#1f2937" />
          <text x={2} y={y(t) - 2} fontSize="8" fill="#4b5563">{yFormat(t)}</text>
        </g>
      ))}
      {baseline != null && <line x1={0} x2={W} y1={y(baseline)} y2={y(baseline)} stroke="#6b7280" strokeDasharray="3 3" opacity="0.6" />}
      {yearMarks.map(m => (
        <text key={m.i} x={x(m.i)} y={H - 3} fontSize="9" fill="#6b7280" textAnchor="middle">{m.label}</text>
      ))}
      {lines.map(l => (
        <path key={l.label} d={path(l.values)} fill="none" stroke={l.color} strokeWidth={l.width || 1.6}
              strokeDasharray={l.dash} opacity={l.opacity ?? 1} />
      ))}
    </svg>
  )
}

function Legend({ items }) {
  return (
    <div className="flex flex-wrap gap-3 text-[10px] text-gray-400 mb-1">
      {items.map(i => (
        <span key={i.label} className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5" style={{ background: i.color }} />{i.label}
        </span>
      ))}
    </div>
  )
}

// Grouped vertical bars: one group per fiscal year, one bar per series
function GroupedBars({ groups, series, height = 150, sym = '$' }) {
  const W = 600, H = height
  const all = groups.flatMap(g => series.map(s => g[s.key])).filter(v => v != null)
  if (!all.length) return <Empty>No annual data.</Empty>
  const max = Math.max(...all, 0), min = Math.min(...all, 0)
  const span = max - min || 1
  const y = v => 8 + ((max - v) / span) * (H - 30)
  const zero = y(0)
  const gw = W / groups.length
  const bw = Math.min(36, (gw - 8) / series.length)
  const showValues = bw >= 24 // ten years of three bars each is too tight for value labels; the table has them
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="bar chart">
      <line x1={0} x2={W} y1={zero} y2={zero} stroke="#374151" />
      {groups.map((g, gi) => {
        const left = gi * gw + (gw - bw * series.length) / 2
        return (
          <g key={g.label}>
            {series.map((s, si) => {
              const v = g[s.key]
              if (v == null) return null
              const top = Math.min(y(v), zero), h = Math.max(Math.abs(y(v) - zero), 1)
              return (
                <g key={s.key}>
                  <rect x={left + si * bw} y={top} width={bw - 3} height={h} fill={s.color} rx="2" opacity="0.9" />
                  {showValues && (
                    <text x={left + si * bw + (bw - 3) / 2} y={v >= 0 ? top - 2 : top + h + 8} fontSize="8"
                          fill="#9ca3af" textAnchor="middle">{fmtBig(v, sym)}</text>
                  )}
                </g>
              )
            })}
            <text x={gi * gw + gw / 2} y={H - 4} fontSize="9" fill="#6b7280" textAnchor="middle">{g.label}</text>
          </g>
        )
      })}
    </svg>
  )
}

// Horizontal range with markers: used for the valuation "football field" and target range
function RangeStrip({ rows, price, min, max, height = 22 }) {
  const W = 600
  const x = v => ((v - min) / (max - min || 1)) * W
  const H = rows.length * height + 24
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }} role="img" aria-label="valuation range">
      {rows.map((r, i) => {
        const cy = 14 + i * height
        return (
          <g key={r.label}>
            <text x={0} y={cy - 5} fontSize="9" fill="#9ca3af">{r.label}</text>
            {r.low != null && r.high != null && (
              <rect x={x(r.low)} y={cy - 1} width={Math.max(x(r.high) - x(r.low), 2)} height={7} fill="#3b82f6" opacity="0.35" rx="2" />
            )}
            {r.value != null && (
              <>
                <circle cx={x(r.value)} cy={cy + 2.5} r="4.5" fill={r.color || '#60a5fa'} />
                <text x={Math.min(x(r.value) + 8, W - 40)} y={cy + 6} fontSize="9" fill="#e5e7eb">{fmtMoney(r.value)}</text>
              </>
            )}
          </g>
        )
      })}
      {price != null && (
        <g>
          <line x1={x(price)} x2={x(price)} y1={0} y2={H - 14} stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 3" />
          <text x={x(price)} y={H - 3} fontSize="9" fill="#f59e0b" textAnchor="middle">Price {fmtMoney(price)}</text>
        </g>
      )}
    </svg>
  )
}

function ScoreBar({ name, score }) {
  return (
    <div>
      <div className="flex justify-between text-[11px] mb-0.5">
        <span className="text-gray-400">{name}</span>
        <span className="font-mono" style={{ color: scoreColor(score) }}>{score == null ? DASH : score}</span>
      </div>
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score ?? 0}%`, background: scoreColor(score) }} />
      </div>
    </div>
  )
}

const REC_COLORS = { strongBuy: '#059669', buy: '#34d399', hold: '#fbbf24', sell: '#f87171', strongSell: '#b91c1c' }
const REC_LABELS = { strongBuy: 'Strong Buy', buy: 'Buy', hold: 'Hold', sell: 'Sell', strongSell: 'Strong Sell' }

function RecBar({ dist, label }) {
  if (!dist) return null
  const total = Object.values(dist).reduce((a, b) => a + b, 0)
  if (!total) return null
  return (
    <div className="mb-2">
      <div className="text-[10px] text-gray-500 mb-1">{label} · {total} analysts</div>
      <div className="flex h-5 rounded overflow-hidden text-[10px] font-semibold text-gray-900">
        {Object.keys(REC_COLORS).map(k => dist[k] > 0 && (
          <div key={k} style={{ width: `${(dist[k] / total) * 100}%`, background: REC_COLORS[k] }}
               className="flex items-center justify-center" title={`${REC_LABELS[k]}: ${dist[k]}`}>{dist[k]}</div>
        ))}
      </div>
    </div>
  )
}

// ── Sections ──────────────────────────────────────────────────────────────────

function VerdictSection({ d }) {
  const v = d.valuation.verdict
  const tone = TONE[v.tone] || TONE.neutral
  const fv = d.valuation.fairValues
  const price = d.snapshot.price
  const have = fv.filter(f => f.value != null)
  const all = [price, ...have.map(f => f.value), d.analysts.targetHigh, d.analysts.targetLow].filter(x => x != null)
  const min = Math.min(...all) * 0.9, max = Math.max(...all) * 1.05
  const rows = [
    ...have.map(f => ({ label: f.method, value: f.value })),
    ...(v.fairValue != null ? [{ label: 'Median fair value', value: v.fairValue, color: '#10b981' }] : []),
    ...(d.analysts.targetMean != null ? [{
      label: '12-mo analyst target (low–high)', value: d.analysts.targetMean, low: d.analysts.targetLow, high: d.analysts.targetHigh,
    }] : []),
  ]
  return (
    <Section id="ts-verdict" title="Is it cheap or expensive?" subtitle="Rules-based valuation verdict from four independent models">
      <div className="grid md:grid-cols-5 gap-4">
        <div className="md:col-span-2 space-y-3">
          <div className={`inline-block px-3 py-1.5 rounded-lg border text-sm font-bold ${tone.pill}`} data-testid="verdict-label">
            {v.label}
          </div>
          {v.fairValue != null ? (
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Fair value (median)" value={fmtMoney(v.fairValue)} sub={`${v.methodsUsed} models`} />
              <Stat label={v.premium >= 0 ? 'Premium to fair' : 'Discount to fair'} value={fmtPct(Math.abs(v.premium), 0)}
                    valueClass={tone.text} sub={`range ${fmtMoney(v.low, 0)}–${fmtMoney(v.high, 0)}`} />
            </div>
          ) : (
            <Empty>
              Only {v.methodsUsed} of 4 valuation models could run (usually because earnings or free cash flow are
              negative, or the ticker is a fund), which isn't enough for a verdict.
            </Empty>
          )}
          <div className="space-y-2 pt-1">
            {d.scorecard.pillars.map(p => <ScoreBar key={p.name} name={p.name} score={p.score} />)}
            <div className="flex justify-between text-xs pt-1 border-t border-gray-800">
              <span className="text-gray-300 font-semibold">Overall score</span>
              <span className="font-mono font-bold" style={{ color: scoreColor(d.scorecard.overall) }}>
                {d.scorecard.overall ?? DASH}<span className="text-gray-500 font-normal"> / 100</span>
              </span>
            </div>
          </div>
        </div>
        <div className="md:col-span-3">
          {rows.length ? <RangeStrip rows={rows} price={price} min={min} max={max} /> : <Empty>No fair-value models available.</Empty>}
          <div className="mt-2 space-y-1">
            {fv.map(f => (
              <div key={f.method} className="text-[11px] flex gap-2">
                <span className="text-gray-400 w-28 shrink-0">{f.method}</span>
                <span className="font-mono text-gray-200 w-16 shrink-0">{fmtMoney(f.value)}</span>
                <span className="text-gray-500">{f.basis}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Section>
  )
}

function FlagsSection({ flags }) {
  if (!flags.strengths.length && !flags.risks.length) return null
  const list = (items, cls, icon) => items.length
    ? items.map(t => <li key={t} className="flex gap-2"><span className={cls}>{icon}</span><span>{t}</span></li>)
    : <li className="text-gray-500 italic">None flagged</li>
  return (
    <Section id="ts-flags" title="Key takeaways" subtitle="Auto-generated from the numbers below">
      <div className="grid md:grid-cols-2 gap-4 text-xs text-gray-300">
        <div>
          <div className="text-emerald-400 font-semibold mb-1.5">Strengths</div>
          <ul className="space-y-1">{list(flags.strengths, 'text-emerald-400', '＋')}</ul>
        </div>
        <div>
          <div className="text-red-400 font-semibold mb-1.5">Risks to weigh</div>
          <ul className="space-y-1">{list(flags.risks, 'text-red-400', '−')}</ul>
        </div>
      </div>
    </Section>
  )
}

function BusinessSection({ d }) {
  const [open, setOpen] = useState(false)
  const p = d.profile
  const desc = p.description
  return (
    <Section id="ts-business" title="Business overview">
      {desc ? (
        <p className={`text-xs text-gray-300 leading-relaxed ${open ? '' : 'line-clamp-4'}`}>{desc}</p>
      ) : <Empty>No business description available.</Empty>}
      {desc && desc.length > 400 && (
        <button onClick={() => setOpen(o => !o)} className="text-[11px] text-emerald-400 mt-1 print:hidden">
          {open ? 'Show less' : 'Read more'}
        </button>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
        <Stat label="Sector" value={p.sector || DASH} />
        <Stat label="Industry" value={p.industry || DASH} />
        <Stat label="Employees" value={fmtInt(p.employees)} />
        <Stat label="Exchange" value={p.exchange || DASH} sub={p.country} />
      </div>
    </Section>
  )
}

function PerformanceSection({ d }) {
  const perf = d.performance
  const s = perf.series
  const snap = d.snapshot
  return (
    <Section id="ts-performance" title="Past performance" subtitle="Price history vs. the S&P 500 (SPY), dividends included">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <Table
            head={['Period', d.symbol, 'S&P 500', 'vs. S&P']}
            rows={perf.returns.map(r => [
              r.period,
              { v: fmtPct(r.stock, 1, true), cls: posNeg(r.stock) },
              { v: fmtPct(r.spy, 1, true), cls: posNeg(r.spy) },
              { v: fmtPct(r.relative, 1, true), cls: posNeg(r.relative) },
            ])}
          />
          <div className="grid grid-cols-2 gap-2 mt-3">
            <Stat label="Max drawdown (5y)" value={fmtPct(perf.maxDrawdown5y, 0)} valueClass="text-red-400" />
            <Stat label="Volatility (1y, ann.)" value={fmtPct(perf.volatility1y, 0)} />
          </div>
          {snap.week52Low != null && snap.week52High != null && (
            <div className="mt-3">
              <div className="flex justify-between text-[10px] text-gray-500">
                <span>52w low {fmtMoney(snap.week52Low)}</span><span>52w high {fmtMoney(snap.week52High)}</span>
              </div>
              <div className="relative h-1.5 bg-gray-800 rounded-full mt-1">
                <div className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-amber-400 border border-gray-900"
                     style={{ left: `calc(${Math.min(Math.max((snap.rangePosition ?? 0) * 100, 0), 100)}% - 5px)` }} />
              </div>
            </div>
          )}
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">5-year growth of 100 — {d.symbol} vs. S&P 500</div>
          {s ? (
            <>
              <Legend items={[{ label: d.symbol, color: '#34d399' }, ...(s.spyRebased ? [{ label: 'S&P 500', color: '#9ca3af' }] : [])]} />
              <LineChart dates={s.dates} baseline={100} yFormat={v => v.toFixed(0)}
                         lines={[...(s.spyRebased ? [{ label: 'spy', values: s.spyRebased, color: '#9ca3af', width: 1.2 }] : []),
                                 { label: 'stock', values: s.stockRebased, color: '#34d399' }]} />
            </>
          ) : <Empty>No price history.</Empty>}
        </div>
      </div>
      {s && (
        <div className="mt-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">5-year price with 50- and 200-day moving averages</div>
          <Legend items={[{ label: 'Price', color: '#60a5fa' }, { label: '50-day MA', color: '#f59e0b' }, { label: '200-day MA', color: '#a78bfa' }]} />
          <LineChart dates={s.dates} yFormat={v => '$' + v.toFixed(0)}
                     lines={[{ label: 'ma200', values: s.ma200, color: '#a78bfa', width: 1.2 },
                             { label: 'ma50', values: s.ma50, color: '#f59e0b', width: 1.2 },
                             { label: 'close', values: s.close, color: '#60a5fa' }]} />
        </div>
      )}
    </Section>
  )
}

function FinancialsSection({ d }) {
  const f = d.financials
  const h = f.history
  const yr = r => 'FY' + r.fiscalYear.slice(0, 4)
  const sym = d.currencyNote ? d.currencyNote.financial + ' ' : '$'
  const money = n => fmtBig(n, sym)
  const subtitle = h.length
    ? `Last ${h.length} fiscal years, oldest to newest${h.length < 10 ? ' (all the annual history available for this ticker)' : ''} · source: SEC filings + Yahoo Finance`
    : 'Last fiscal years, oldest to newest'
  return (
    <Section id="ts-financials" title="Financial track record" subtitle={subtitle}>
      {d.currencyNote && (
        <div className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1 mb-3">
          {d.symbol} reports in {d.currencyNote.financial} but trades in {d.currencyNote.trading}, so statement figures below are in {d.currencyNote.financial}
          and the per-share valuation models (P/E, PEG, DCF) are skipped to avoid comparing unlike currencies.
        </div>
      )}
      {d.bankNote && (
        <div className="text-[11px] text-gray-400 bg-gray-800/60 border border-gray-700 rounded px-2 py-1 mb-3">
          Free cash flow and gross profit aren't meaningful for banks (deposits, lending and trading run through operating cash flow), so they're left blank.
        </div>
      )}
      {h.length ? (
        <>
          <GroupedBars
            groups={h.map(r => ({ label: yr(r), revenue: r.revenue, netIncome: r.netIncome, fcf: r.freeCashFlow }))}
            series={[{ key: 'revenue', color: '#3b82f6' }, { key: 'netIncome', color: '#10b981' }, { key: 'fcf', color: '#f59e0b' }]}
            sym={sym} />
          <Legend items={[{ label: 'Revenue', color: '#3b82f6' }, { label: 'Net income', color: '#10b981' }, { label: 'Free cash flow', color: '#f59e0b' }]} />
          <Table
            head={['', ...h.map(yr)]}
            rows={[
              ['Revenue', ...h.map(r => money(r.revenue))],
              ['  growth YoY', ...h.map(r => ({ v: fmtPct(r.revenueGrowth, 1, true), cls: posNeg(r.revenueGrowth) }))],
              ['Gross margin', ...h.map(r => fmtPct(r.grossMargin))],
              ['Operating margin', ...h.map(r => fmtPct(r.operatingMargin))],
              ['Net income', ...h.map(r => money(r.netIncome))],
              ['Net margin', ...h.map(r => fmtPct(r.netMargin))],
              ['Diluted EPS', ...h.map(r => fmtMoney(r.eps, 2, sym))],
              ['  growth YoY', ...h.map(r => ({ v: fmtPct(r.epsGrowth, 1, true), cls: posNeg(r.epsGrowth) }))],
              ['Free cash flow', ...h.map(r => money(r.freeCashFlow))],
              ['FCF margin', ...h.map(r => fmtPct(r.fcfMargin))],
            ]}
          />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
            <Stat label={`Revenue CAGR (${h.length - 1}y)`} value={fmtPct(f.revenueCagr, 1, true)} valueClass={posNeg(f.revenueCagr)} />
            <Stat label={`EPS CAGR (${h.length - 1}y)`} value={fmtPct(f.epsCagr, 1, true)} valueClass={posNeg(f.epsCagr)} />
            <Stat label="Revenue growth (TTM)" value={fmtPct(f.ttm.revenueGrowth, 1, true)} valueClass={posNeg(f.ttm.revenueGrowth)} />
            <Stat label="Earnings growth (TTM)" value={fmtPct(f.ttm.earningsGrowth, 1, true)} valueClass={posNeg(f.ttm.earningsGrowth)} />
          </div>
        </>
      ) : <Empty>No annual financial statements available (common for ETFs and funds).</Empty>}
    </Section>
  )
}

function BalanceSheetSection({ b }) {
  const nd = b.netDebt
  return (
    <Section id="ts-balance" title="Balance sheet & returns on capital">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Stat label="Cash" value={fmtBig(b.cash)} />
        <Stat label="Total debt" value={fmtBig(b.debt)} />
        <Stat label={nd != null && nd < 0 ? 'Net cash' : 'Net debt'} value={fmtBig(nd != null ? Math.abs(nd) : null)}
              valueClass={nd != null && nd < 0 ? 'text-emerald-400' : 'text-gray-100'} />
        <Stat label="Net debt / EBITDA" value={fmtX(b.netDebtToEbitda)} />
        <Stat label="Debt / equity" value={b.debtToEquity != null ? fmtNum(b.debtToEquity, 0) + '%' : DASH} />
        <Stat label="Current ratio" value={fmtNum(b.currentRatio)} />
        <Stat label="Interest coverage" value={fmtX(b.interestCoverage)} />
        <Stat label="Payout ratio" value={fmtPct(b.payoutRatio, 0)} />
        <Stat label="Return on equity" value={fmtPct(b.roe)} />
        <Stat label="Return on assets" value={fmtPct(b.roa)} />
      </div>
    </Section>
  )
}

function ValuationSection({ d }) {
  const v = d.valuation
  const m = v.multiples
  const pes = v.historicalPE
  const maxPe = Math.max(...pes.map(p => p.pe), m.trailingPE || 0, 1)
  return (
    <Section id="ts-valuation" title="Valuation multiples" subtitle="How much you pay per dollar of earnings, sales and cash flow">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <Stat label="P/E (trailing)" value={fmtX(m.trailingPE)} />
        <Stat label="P/E (forward)" value={fmtX(m.forwardPE)} />
        <Stat label="PEG" value={fmtNum(m.peg)} />
        <Stat label="Price / sales" value={fmtX(m.priceToSales)} />
        <Stat label="Price / book" value={fmtX(m.priceToBook)} />
        <Stat label="EV / EBITDA" value={fmtX(m.evToEbitda)} />
        <Stat label="EV / revenue" value={fmtX(m.evToRevenue)} />
        <Stat label="FCF yield" value={fmtPct(m.fcfYield)} />
        <Stat label="Dividend yield" value={fmtPct(m.dividendYield)} />
        <Stat label="Earnings yield (fwd)" value={fmtPct(m.earningsYieldForward)}
              sub={v.tenYearYield != null ? `10-yr Treasury ${fmtPct(v.tenYearYield, 2)}` : undefined}
              valueClass={v.earningsYieldVsBond != null ? posNeg(v.earningsYieldVsBond) : 'text-gray-100'} />
      </div>
      {v.earningsYieldVsBond != null && (
        <p className="text-[11px] text-gray-400 mt-2">
          Forward earnings yield is{' '}
          <span className={posNeg(v.earningsYieldVsBond)}>{fmtPct(Math.abs(v.earningsYieldVsBond), 1)} {v.earningsYieldVsBond >= 0 ? 'above' : 'below'}</span>{' '}
          the risk-free 10-year Treasury — {v.earningsYieldVsBond >= 0
            ? 'stocks are paying you a premium for taking equity risk.'
            : 'you are accepting less earnings yield than a government bond pays, betting on growth to close the gap.'}
        </p>
      )}
      <div className="mt-4">
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">
          P/E at each fiscal year-end vs. today{v.historicalPEMedian != null && <> · median {fmtX(v.historicalPEMedian)}</>}
        </div>
        {pes.length ? (
          <div className="space-y-1">
            {[...pes.map(p => ({ label: 'FY' + p.fiscalYear.slice(0, 4), pe: p.pe, color: '#3b82f6' })),
              ...(m.trailingPE ? [{ label: 'Today', pe: m.trailingPE, color: '#f59e0b' }] : [])].map(p => (
              <div key={p.label} className="flex items-center gap-2 text-[11px]">
                <span className="w-12 text-gray-400">{p.label}</span>
                <div className="flex-1 h-3 bg-gray-800 rounded">
                  <div className="h-full rounded" style={{ width: `${(p.pe / maxPe) * 100}%`, background: p.color }} />
                </div>
                <span className="w-12 text-right font-mono text-gray-200">{fmtX(p.pe)}</span>
              </div>
            ))}
          </div>
        ) : <Empty>Not enough positive-EPS fiscal years to chart historical P/E.</Empty>}
      </div>
    </Section>
  )
}

function ProjectedReturnsSection({ d }) {
  const v = d.valuation
  return (
    <Section id="ts-returns" title="Projected earnings & returns"
             subtitle="What the stock could return if consensus earnings are delivered — and what happens if the multiple moves">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">12-month scenarios (next fiscal-year consensus EPS)</div>
          {v.scenarios12m.length ? (
            <Table
              head={['Case', 'EPS', 'P/E', 'Price', 'Total return']}
              rows={v.scenarios12m.map(s => [
                s.scenario, fmtMoney(s.eps), fmtX(s.peMultiple), fmtMoney(s.price),
                { v: fmtPct(s.totalReturn, 1, true), cls: posNeg(s.totalReturn) },
              ])} />
          ) : <Empty>Needs current-year and next-year consensus EPS estimates.</Empty>}
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            5-year annualised return (EPS compounding at {fmtPct(d.estimates.growthUsed, 1)})
          </div>
          {v.fiveYearReturns.length ? (
            <Table
              head={['If the P/E…', 'Exit P/E', 'Price in 5y', 'Annual return']}
              rows={v.fiveYearReturns.map(s => [
                s.scenario, fmtX(s.exitPe), fmtMoney(s.endPrice),
                { v: fmtPct(s.annualisedReturn, 1, true), cls: posNeg(s.annualisedReturn) },
              ])} />
          ) : <Empty>Needs positive trailing EPS and a growth estimate.</Empty>}
          <p className="text-[10px] text-gray-500 mt-2">
            Compare these to the ~{v.tenYearYield != null ? fmtPct(v.tenYearYield, 1) : '4–5%'} a 10-year Treasury pays with no equity risk.
          </p>
        </div>
      </div>
    </Section>
  )
}

function EstimatesSection({ d }) {
  const e = d.estimates
  const t = d.earningsTrack
  return (
    <Section id="ts-estimates" title="Consensus estimates & earnings record">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">EPS estimates</div>
          {e.eps.length ? (
            <Table head={['Period', 'Avg', 'Low–High', 'Year ago', 'Growth', '# est']}
                   rows={e.eps.map(r => [r.label, fmtMoney(r.avg), `${fmtNum(r.low)}–${fmtNum(r.high)}`, fmtMoney(r.yearAgo),
                     { v: fmtPct(r.growth, 1, true), cls: posNeg(r.growth) }, r.analysts ?? DASH])} />
          ) : <Empty>No EPS estimates.</Empty>}
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1 mt-3">Revenue estimates</div>
          {e.revenue.length ? (
            <Table head={['Period', 'Avg', 'Year ago', 'Growth']}
                   rows={e.revenue.map(r => [r.label, fmtBig(r.avg), fmtBig(r.yearAgo), { v: fmtPct(r.growth, 1, true), cls: posNeg(r.growth) }])} />
          ) : <Empty>No revenue estimates.</Empty>}
          {e.revisions.length > 0 && (
            <>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1 mt-3">EPS estimate revisions (are analysts raising or cutting?)</div>
              <Table head={['Period', 'Current', '30 days', '90 days']}
                     rows={e.revisions.map(r => [r.label, fmtMoney(r.current),
                       { v: fmtPct(r.change30d, 1, true), cls: posNeg(r.change30d) }, { v: fmtPct(r.change90d, 1, true), cls: posNeg(r.change90d) }])} />
            </>
          )}
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            Last {t.total || 'few'} quarters: actual vs. estimated EPS
            {t.total > 0 && <> · beat {t.beats}/{t.total}{t.avgSurprisePct != null && <>, avg surprise {fmtPct(t.avgSurprisePct, 1, true)}</>}</>}
          </div>
          {t.quarters.length ? (
            <Table head={['Quarter', 'Actual', 'Estimate', 'Surprise']}
                   rows={t.quarters.map(q => [q.quarter, fmtMoney(q.epsActual), fmtMoney(q.epsEstimate),
                     { v: fmtPct(q.surprisePct, 1, true), cls: posNeg(q.surprisePct) }])} />
          ) : <Empty>No earnings history.</Empty>}
          {d.snapshot.nextEarnings && (
            <p className="text-[11px] text-gray-400 mt-2">Next earnings report: <span className="text-gray-200 font-mono">{d.snapshot.nextEarnings}</span></p>
          )}
        </div>
      </div>
    </Section>
  )
}

function AnalystsSection({ d }) {
  const a = d.analysts
  const price = d.snapshot.price
  const have = [a.targetLow, a.targetHigh, a.targetMean, price].filter(x => x != null)
  const min = have.length ? Math.min(...have) * 0.92 : 0, max = have.length ? Math.max(...have) * 1.06 : 1
  const REC = { strong_buy: 'Strong Buy', buy: 'Buy', hold: 'Hold', underperform: 'Underperform', sell: 'Sell', strong_sell: 'Strong Sell' }
  return (
    <Section id="ts-analysts" title="Analyst ratings & price targets">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <Stat label="Consensus" value={REC[a.recommendation] || (a.recommendation ? a.recommendation : DASH)}
                  sub={a.recommendationMean != null ? `${a.recommendationMean.toFixed(2)} / 5 (1 = strong buy)` : undefined} />
            <Stat label="Mean target" value={fmtMoney(a.targetMean)} />
            <Stat label="Implied upside" value={fmtPct(a.upsideToMean, 1, true)} valueClass={posNeg(a.upsideToMean)} />
          </div>
          <RecBar dist={a.distribution} label="Ratings now" />
          <RecBar dist={a.distribution3mAgo} label="Ratings 3 months ago" />
          {a.targetLow != null && a.targetHigh != null && (
            <RangeStrip price={price} min={min} max={max} height={26}
                        rows={[{ label: `Target range ${fmtMoney(a.targetLow, 0)} – ${fmtMoney(a.targetHigh, 0)} (dot = mean)`, value: a.targetMean, low: a.targetLow, high: a.targetHigh }]} />
          )}
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Recent rating & target changes</div>
          {a.recentChanges.length ? (
            <Table head={['Date', 'Firm', 'Rating', 'Target']}
                   rows={a.recentChanges.map(c => [
                     c.date, c.firm,
                     c.from && c.from !== c.to ? `${c.from} → ${c.to}` : c.to,
                     c.target != null ? `${fmtMoney(c.target, 0)}${c.priorTarget ? ` (was ${fmtMoney(c.priorTarget, 0)})` : ''}` : DASH,
                   ])} align="left" />
          ) : <Empty>No recent analyst actions.</Empty>}
        </div>
      </div>
    </Section>
  )
}

function OwnershipSection({ o }) {
  const ins = o.insiderActivity
  return (
    <Section id="ts-ownership" title="Ownership, insiders & short interest">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Stat label="Held by institutions" value={fmtPct(o.institutionsPct, 1)} />
        <Stat label="Held by insiders" value={fmtPct(o.insidersPct, 1)} />
        <Stat label="Short % of float" value={fmtPct(o.shortPercentOfFloat, 1)} valueClass={o.shortPercentOfFloat > 0.1 ? 'text-red-400' : 'text-gray-100'} />
        <Stat label="Days to cover" value={fmtNum(o.shortRatio, 1)} />
      </div>
      {ins ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
          <Stat label="Insider buys (6m)" value={fmtInt(ins.boughtShares6m)} sub={`${fmtInt(ins.buyTransactions6m)} transactions`} valueClass="text-emerald-400" />
          <Stat label="Insider sells (6m)" value={fmtInt(ins.soldShares6m)} sub={`${fmtInt(ins.sellTransactions6m)} transactions`} valueClass="text-red-400" />
          <Stat label="Net shares (6m)" value={fmtInt(ins.netShares6m)} valueClass={posNeg(ins.netShares6m)} />
        </div>
      ) : null}
    </Section>
  )
}

// ── Share: download PDF / email ───────────────────────────────────────────────

const EMAIL_KEY = 'tearsheet:lastRecipients'

function readSavedRecipients() {
  try { return localStorage.getItem(EMAIL_KEY) || '' } catch { return '' }
}
function saveRecipients(v) {
  try { localStorage.setItem(EMAIL_KEY, v) } catch { /* private mode etc. — convenience only */ }
}

// FastAPI returns {detail: "..."} for our errors but {detail: [{msg}...]} for validation (422)
async function errorText(res, fallback) {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch { /* not JSON */ }
  return fallback
}

function filenameFrom(res, fallback) {
  const m = /filename="?([^";]+)"?/.exec(res.headers?.get?.('content-disposition') || '')
  return m ? m[1] : fallback
}

function SharePanel({ symbol }) {
  const [emailOpen, setEmailOpen] = useState(false)
  const [configured, setConfigured] = useState(null)   // null = still checking
  const [to, setTo] = useState(readSavedRecipients)
  const [note, setNote] = useState('')
  const [pdfBusy, setPdfBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [msg, setMsg] = useState(null)                 // {kind: 'ok' | 'err', text}

  useEffect(() => {
    let live = true
    fetch('/api/tear-sheet-share/status')
      .then(r => r.json())
      .then(j => { if (live) setConfigured(!!j.emailConfigured) })
      .catch(() => { if (live) setConfigured(false) })
    return () => { live = false }
  }, [])

  async function downloadPdf() {
    setPdfBusy(true)
    setMsg(null)
    try {
      const res = await fetch(`/api/tear-sheet/${encodeURIComponent(symbol)}/pdf`)
      if (!res.ok) { setMsg({ kind: 'err', text: await errorText(res, 'Could not build the PDF.') }); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filenameFrom(res, `${symbol}_TearSheet.pdf`)
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setMsg({ kind: 'err', text: e.message })
    } finally {
      setPdfBusy(false)
    }
  }

  async function sendEmail() {
    if (!to.trim()) { setMsg({ kind: 'err', text: 'Enter at least one email address.' }); return }
    setSending(true)
    setMsg(null)
    try {
      const res = await fetch(`/api/tear-sheet/${encodeURIComponent(symbol)}/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: to.trim(), note }),
      })
      if (!res.ok) { setMsg({ kind: 'err', text: await errorText(res, 'Could not send the email.') }); return }
      const json = await res.json()
      saveRecipients(to.trim())
      setMsg({ kind: 'ok', text: `Sent to ${json.sent.join(', ')} with ${json.filename} attached.` })
    } catch (e) {
      setMsg({ kind: 'err', text: e.message })
    } finally {
      setSending(false)
    }
  }

  const btn = 'text-[11px] border rounded px-2.5 py-1 transition-colors disabled:opacity-50'
  return (
    <div className="mt-3 print:hidden">
      <div className="flex flex-wrap gap-2">
        <button onClick={downloadPdf} disabled={pdfBusy}
                className={`${btn} border-emerald-600 text-emerald-300 hover:bg-emerald-600/20`}>
          {pdfBusy ? 'Building PDF…' : 'Download PDF'}
        </button>
        <button onClick={() => { setEmailOpen(o => !o); setMsg(null) }} aria-expanded={emailOpen}
                className={`${btn} border-sky-600 text-sky-300 hover:bg-sky-600/20`}>
          Email…
        </button>
        <button onClick={() => window.print()} className={`${btn} border-gray-700 text-gray-400 hover:text-gray-200`}>
          Print
        </button>
      </div>

      {emailOpen && (
        <div className="mt-3 bg-gray-800/50 border border-gray-700 rounded-lg p-3 space-y-2" data-testid="email-panel">
          {configured === false ? (
            <div className="text-xs text-gray-300 space-y-1.5">
              <div className="text-amber-300 font-semibold">Email isn't set up yet</div>
              <p>Add your SMTP settings to <code className="text-gray-100">backend/.env</code> and restart the backend. For Gmail, create an
                 app password (Google Account → Security → 2-Step Verification → App passwords) and use it as the password:</p>
              <pre className="bg-gray-900 rounded p-2 text-[11px] text-gray-200 overflow-x-auto">{`SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password`}</pre>
              <p className="text-gray-500">Optional: <code>SMTP_FROM</code> to change the sender, <code>EMAIL_ALLOWED_RECIPIENTS</code> to restrict who can receive mail.</p>
            </div>
          ) : (
            <>
              <label className="block text-[11px] text-gray-400">
                To <span className="text-gray-600">(separate several addresses with commas)</span>
                <input value={to} onChange={e => setTo(e.target.value)} aria-label="Recipients" placeholder="friend@example.com"
                       onKeyDown={e => e.key === 'Enter' && !sending && sendEmail()}
                       className="mt-1 w-full bg-gray-900 border border-gray-700 text-gray-100 text-sm px-2.5 py-1.5 rounded
                                  focus:outline-none focus:border-sky-500 placeholder-gray-600" />
              </label>
              <label className="block text-[11px] text-gray-400">
                Message <span className="text-gray-600">(optional)</span>
                <textarea value={note} onChange={e => setNote(e.target.value)} aria-label="Message" rows={2} maxLength={1000}
                          placeholder="Add a note to go above the summary…"
                          className="mt-1 w-full bg-gray-900 border border-gray-700 text-gray-100 text-sm px-2.5 py-1.5 rounded
                                     focus:outline-none focus:border-sky-500 placeholder-gray-600 resize-y" />
              </label>
              <div className="flex items-center gap-3">
                <button onClick={sendEmail} disabled={sending || configured === null}
                        className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded">
                  {sending ? 'Sending…' : `Send ${symbol} tear sheet`}
                </button>
                <span className="text-[10px] text-gray-500">Sends a short summary with the full PDF attached.</span>
              </div>
            </>
          )}
        </div>
      )}

      {msg && (
        <div role={msg.kind === 'err' ? 'alert' : 'status'}
             className={`mt-2 text-xs rounded px-3 py-2 border ${msg.kind === 'ok'
               ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
               : 'text-red-400 bg-red-500/10 border-red-500/20'}`}>
          {msg.text}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

const QUICK = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'JPM']

export default function TearSheet({ initialSymbol }) {
  const [symbolInput, setSymbolInput] = useState(initialSymbol || '')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function load(raw) {
    const sym = (raw ?? symbolInput).trim().toUpperCase()
    if (!sym) return
    setSymbolInput(sym)
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const res = await fetch(`/api/tear-sheet/${encodeURIComponent(sym)}`)
      const json = await res.json()
      if (json.error) setError(json.error)
      else setData(json)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (initialSymbol) load(initialSymbol) }, [initialSymbol]) // eslint-disable-line react-hooks/exhaustive-deps

  const snap = data?.snapshot
  const isFund = data && data.profile.quoteType && !['EQUITY'].includes(data.profile.quoteType)
  const tone = data ? (TONE[data.valuation.verdict.tone] || TONE.neutral) : null

  return (
    <div className="ts-root p-4 space-y-4 max-w-5xl mx-auto">
      <style>{`@media print {
        .ts-root, .ts-root * { color: #111 !important; border-color: #ccc !important; }
        .ts-root .ts-card { background: #fff !important; }
        .ts-root .bg-gray-800, .ts-root .bg-gray-800\\/50 { background: #f3f4f6 !important; }
      }`}</style>

      <div className="print:hidden">
        <h2 className="text-lg font-semibold text-gray-100">Company Tear Sheet</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Everything an investor needs on one page: business, past performance, financial track record, valuation,
          projected earnings and returns, analyst ratings, and a cheap-or-expensive verdict.
        </p>
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 print:hidden">
        <div className="flex gap-2">
          <input
            value={symbolInput}
            onChange={e => setSymbolInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && load()}
            placeholder="Enter a ticker, e.g. AAPL"
            aria-label="Ticker symbol"
            className="flex-1 bg-gray-800 border border-gray-700 text-gray-100 text-sm px-3 py-2 rounded-lg
                       focus:outline-none focus:border-emerald-500 placeholder-gray-600"
          />
          <button onClick={() => load()} disabled={loading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500
                             text-white text-sm font-medium rounded-lg transition-colors">
            {loading ? 'Building…' : 'Build tear sheet'}
          </button>
        </div>
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {QUICK.map(s => (
            <button key={s} onClick={() => load(s)}
                    className="px-2 py-0.5 text-[11px] bg-gray-800 hover:bg-gray-700 text-gray-400 rounded border border-gray-700">{s}</button>
          ))}
        </div>
        {error && (
          <div role="alert" className="mt-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
        )}
      </div>

      {loading && <div className="text-xs text-gray-500 animate-pulse">Gathering financials, estimates and analyst data — usually 5–15 seconds the first time…</div>}

      {data && snap && (
        <>
          <div className="ts-card bg-gray-900/60 border border-gray-800 rounded-xl p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-gray-100">{data.symbol}</span>
                  <span className="text-sm text-gray-400">{data.profile.name}</span>
                </div>
                <div className="text-[11px] text-gray-500 mt-0.5">
                  {[data.profile.sector, data.profile.industry, data.profile.exchange].filter(Boolean).join(' · ')} · as of {data.asOf}
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-mono text-gray-100">{fmtMoney(snap.price)}</div>
                {snap.changePct != null && <div className={`text-xs font-mono ${posNeg(snap.changePct)}`}>{snap.changePct >= 0 ? '+' : ''}{snap.changePct.toFixed(2)}% today</div>}
                <div className={`inline-block mt-1 px-2 py-0.5 rounded border text-[11px] font-semibold ${tone.pill}`}>{data.valuation.verdict.label}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
              <Stat label="Market cap" value={fmtBig(snap.marketCap)} />
              <Stat label="Enterprise value" value={fmtBig(snap.enterpriseValue)} />
              <Stat label="P/E (trailing)" value={fmtX(data.valuation.multiples.trailingPE)} />
              <Stat label="Beta" value={fmtNum(snap.beta)} />
              <Stat label="Dividend yield" value={fmtPct(data.valuation.multiples.dividendYield)} />
            </div>
            <SharePanel key={data.symbol} symbol={data.symbol} />
          </div>

          {isFund && (
            <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
              {data.symbol} is not an operating company (classified as {data.profile.quoteType}) — financial statements,
              earnings estimates and the valuation verdict don't apply. Price performance and risk below still do.
            </div>
          )}

          <VerdictSection d={data} />
          <FlagsSection flags={data.flags} />
          <BusinessSection d={data} />
          <PerformanceSection d={data} />
          <FinancialsSection d={data} />
          <BalanceSheetSection b={data.balanceSheet} />
          <ValuationSection d={data} />
          <ProjectedReturnsSection d={data} />
          <EstimatesSection d={data} />
          <AnalystsSection d={data} />
          <OwnershipSection o={data.ownership} />

          <p className="text-[10px] text-gray-500 leading-relaxed px-1">{data.methodologyNote} Data: Yahoo Finance via yfinance; may be delayed or incomplete.</p>
        </>
      )}
    </div>
  )
}
