import { useState, useEffect } from 'react'

// Home dashboard → market regime card. Loads /api/home/regime on its own, so a slow or failing build never holds up the rest of Home.
// Themes and short interest appear once those pages have been opened (the backend reads them from cache and never starts a scan).

const PHASE_COLOR = { early: '#34d399', mid: '#38bdf8', late: '#fbbf24', slowdown: '#fb923c', recession: '#f87171' }
const BAND_CLS = { Low: 'text-emerald-300', Moderate: 'text-sky-300', Elevated: 'text-amber-300', High: 'text-red-300' }
const DISP_CLS = { equity_leads: 'bg-sky-400', partial: 'bg-amber-400', confirmed: 'bg-red-400', none: 'bg-gray-600' }
const pct = (v, d = 1) => (v == null ? '—' : `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(d)}%`)
const tone = v => (v == null ? 'text-gray-500' : v >= 0 ? 'text-emerald-400' : 'text-red-400')

function Block({ title, link, onLink, children }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-gray-500 text-[11px] uppercase tracking-widest">{title}</span>
        {onLink && <button onClick={onLink} className="text-[11px] text-emerald-500 hover:text-emerald-400">{link} →</button>}
      </div>
      {children}
    </div>
  )
}

function Rows({ rows, label, value }) {
  return (
    <ul className="space-y-0.5 text-xs">
      {rows.map(r => (
        <li key={label(r)} className="flex items-center justify-between gap-2">
          <span className="text-gray-300 truncate">{label(r)}</span>
          <span className={`tabular-nums ${tone(value(r))}`}>{pct(value(r))}</span>
        </li>
      ))}
    </ul>
  )
}

export default function RegimeCard({ onNavigate }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/api/home/regime')
      .then(async r => { const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.detail || `Request failed (${r.status})`); return j })
      .then(j => { if (!cancelled) setData(j) })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const g = data?.regime, s = data?.sectors, t = data?.themes, sh = data?.shorts, ch = data?.changes
  const go = id => () => onNavigate?.(id)

  return (
    <section aria-label="Market regime" className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-hidden" data-testid="regime-card">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-gray-500 text-xs uppercase tracking-widest">Market Regime</span>
        <button onClick={go('econregime')} className="text-xs text-emerald-500 hover:text-emerald-400 transition-colors">Regime dashboard →</button>
      </div>
      <div className="p-4">
        {loading && <div className="text-xs text-gray-500 animate-pulse">Reading the economy and sectors…</div>}
        {!loading && error && <div role="alert" className="text-xs text-red-400">{error}</div>}
        {!loading && !error && !g && !s && !t && !sh && <div className="text-xs text-gray-500">The regime summary isn&apos;t available right now (economic data or prices couldn&apos;t be loaded).</div>}
        {!loading && !error && (g || s || t || sh) && (
          <div className="space-y-4">
            {g && (
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                <div>
                  <div className="text-lg font-semibold" style={{ color: PHASE_COLOR[g.phase.id] }}>{g.phase.name}</div>
                  <div className="text-[11px] text-gray-500">{g.quadrant.name}: {g.growth ? g.growth.toLowerCase() : 'growth and inflation direction'}</div>
                </div>
                {g.riskScore != null && (
                  <div className="min-w-[150px]" role="img" aria-label={`Recession risk ${Math.round(g.riskScore)} of 100, ${g.riskBand}`}>
                    <div className="text-[11px] text-gray-500">Recession risk</div>
                    <div className="flex items-baseline gap-1.5"><span className={`text-xl font-semibold tabular-nums ${BAND_CLS[g.riskBand]}`}>{Math.round(g.riskScore)}</span><span className={`text-xs ${BAND_CLS[g.riskBand]}`}>{g.riskBand}</span></div>
                    <div className="relative h-1.5 bg-gray-800 rounded-full mt-1"><div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 opacity-50 w-full" /><div className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-white border border-gray-900" style={{ left: `calc(${Math.min(g.riskScore, 100)}% - 5px)` }} /></div>
                  </div>
                )}
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {g.curveInverted && <span className="px-2 py-0.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-300">Yield curve inverted</span>}
                  {g.flashing.map(n => <span key={n} className="px-2 py-0.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-300">{n} flashing</span>)}
                  {ch?.phaseTo && <span className="px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-300" data-testid="phase-change">Phase changed: {ch.phaseFrom} → {ch.phaseTo}</span>}
                  {ch?.riskTo != null && <span className="px-2 py-0.5 rounded-full border border-gray-600 bg-gray-800/60 text-gray-300" data-testid="risk-change">Risk {Math.round(ch.riskFrom)} → {Math.round(ch.riskTo)} since {ch.since}</span>}
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <Block title="Sectors vs SPY, 3 months" link="Scoreboard" onLink={go('sectorboard')}>
                {s ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div><div className="text-[10px] text-emerald-500 mb-0.5">Leading</div><Rows rows={s.top} label={r => r.name} value={r => r.excess3m} /></div>
                    <div><div className="text-[10px] text-red-400 mb-0.5">Lagging</div><Rows rows={s.bottom} label={r => r.name} value={r => r.excess3m} /></div>
                  </div>
                ) : <div className="text-xs text-gray-600">Not available.</div>}
              </Block>
              <Block title="Themes vs SPY, 3 months" link="All themes" onLink={go('themesoverview')}>
                {t ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div><div className="text-[10px] text-emerald-500 mb-0.5">Strongest</div><Rows rows={t.top} label={r => r.name} value={r => r.vsSpy} /></div>
                    <div><div className="text-[10px] text-red-400 mb-0.5">Weakest</div><Rows rows={t.bottom} label={r => r.name} value={r => r.vsSpy} /></div>
                  </div>
                ) : <div className="text-xs text-gray-600">Shown once you have opened Themes.</div>}
              </Block>
              <Block title="Most shorted" link="Short interest" onLink={go('shortinterest')}>
                {sh ? (
                  <ul className="space-y-0.5 text-xs" data-testid="regime-shorts">
                    {sh.top.slice(0, 4).map(r => (
                      <li key={r.symbol} className="flex items-center justify-between gap-2">
                        <span className="text-gray-200 font-medium flex items-center gap-1.5"><span className={`w-1.5 h-1.5 rounded-full ${DISP_CLS[r.displacement]}`} title={r.displacementLabel} />{r.symbol}</span>
                        <span className="text-gray-400 tabular-nums">{(r.siPctFloat * 100).toFixed(0)}% of float{r.fee != null ? ` · ${r.fee.toFixed(1)}% fee` : ''}</span>
                      </li>
                    ))}
                    {sh.creditConfirms ? <li className="text-[11px] text-gray-500 pt-0.5">Bonds confirm the shorts on {sh.creditConfirms}</li> : null}
                  </ul>
                ) : <div className="text-xs text-gray-600">Shown once you have opened Short Interest.</div>}
              </Block>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
