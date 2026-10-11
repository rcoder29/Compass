import { useState } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, Segmented } from './MacroKit'

const QUAD = {
  leading: { color: '#34d399', tint: 'rgba(16,185,129,0.10)' },
  weakening: { color: '#fbbf24', tint: 'rgba(245,158,11,0.10)' },
  lagging: { color: '#f87171', tint: 'rgba(239,68,68,0.10)' },
  improving: { color: '#38bdf8', tint: 'rgba(56,189,248,0.10)' },
}
const ORDER = ['leading', 'improving', 'weakening', 'lagging']

export default function SectorRotation() {
  const { data, loading, error } = useApi('/api/sectors/rotation')
  const [trail, setTrail] = useState(8)
  const [focus, setFocus] = useState(null)

  const pts = data ? data.sectors.flatMap(s => s.trail) : []
  const dx = pts.length ? Math.max(2, ...pts.map(p => Math.abs(p.ratio - 100))) * 1.12 : 5
  const dy = pts.length ? Math.max(1, ...pts.map(p => Math.abs(p.momentum - 100))) * 1.12 : 3
  const W = 640, H = 460, P = 36
  const sx = v => P + ((v - (100 - dx)) / (2 * dx)) * (W - 2 * P)
  const sy = v => H - P - ((v - (100 - dy)) / (2 * dy)) * (H - 2 * P)

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Rotation Map">
        A relative-rotation view of the sectors against SPY. Horizontally: is the sector stronger or weaker than SPY&apos;s trend (RS-Ratio)?
        Vertically: is that relative strength speeding up or slowing (RS-Momentum)? Sectors tend to travel clockwise: Improving → Leading → Weakening → Lagging.
      </PageHeader>
      {loading && <Loading>Loading weekly history…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <div className="grid xl:grid-cols-[1fr_340px] gap-4 items-start">
          <Card title="Relative rotation" right={<Segmented label="Trail length" options={[[0, 'No trail'], [4, '4 wks'], [8, '8 wks']]} value={trail} onChange={setTrail} />}>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Relative rotation graph of the eleven sectors">
              <rect x={sx(100)} y={P} width={W - P - sx(100)} height={sy(100) - P} fill={QUAD.leading.tint} />
              <rect x={sx(100)} y={sy(100)} width={W - P - sx(100)} height={H - P - sy(100)} fill={QUAD.weakening.tint} />
              <rect x={P} y={sy(100)} width={sx(100) - P} height={H - P - sy(100)} fill={QUAD.lagging.tint} />
              <rect x={P} y={P} width={sx(100) - P} height={sy(100) - P} fill={QUAD.improving.tint} />
              <text x={W - P - 6} y={P + 14} textAnchor="end" fontSize="12" fill={QUAD.leading.color} opacity="0.9">LEADING</text>
              <text x={W - P - 6} y={H - P - 6} textAnchor="end" fontSize="12" fill={QUAD.weakening.color} opacity="0.9">WEAKENING</text>
              <text x={P + 6} y={H - P - 6} fontSize="12" fill={QUAD.lagging.color} opacity="0.9">LAGGING</text>
              <text x={P + 6} y={P + 14} fontSize="12" fill={QUAD.improving.color} opacity="0.9">IMPROVING</text>
              <line x1={sx(100)} x2={sx(100)} y1={P} y2={H - P} stroke="#475569" /><line x1={P} x2={W - P} y1={sy(100)} y2={sy(100)} stroke="#475569" />
              <text x={W / 2} y={H - 8} textAnchor="middle" fontSize="10" fill="#6b7280">RS-Ratio → stronger than SPY</text>
              <text x={10} y={H / 2} fontSize="10" fill="#6b7280" textAnchor="middle" transform={`rotate(-90 10 ${H / 2})`}>RS-Momentum → gaining</text>
              {data.sectors.map(s => {
                const c = QUAD[s.quadrant].color
                const faded = focus && focus !== s.symbol
                const t = trail ? s.trail.slice(-(trail + 1)) : [s.trail[s.trail.length - 1]]
                const cur = s.trail[s.trail.length - 1]
                return (
                  <g key={s.symbol} opacity={faded ? 0.18 : 1} onMouseEnter={() => setFocus(s.symbol)} onMouseLeave={() => setFocus(null)}>
                    {t.length > 1 && <polyline fill="none" stroke={c} strokeWidth="1.4" strokeOpacity="0.7" points={t.map(p => `${sx(p.ratio).toFixed(1)},${sy(p.momentum).toFixed(1)}`).join(' ')} />}
                    {t.slice(0, -1).map((p, i) => <circle key={i} cx={sx(p.ratio)} cy={sy(p.momentum)} r="2" fill={c} opacity="0.55" />)}
                    <circle cx={sx(cur.ratio)} cy={sy(cur.momentum)} r="6" fill={c} stroke="#0f172a" strokeWidth="1.5"><title>{`${s.name}: RS-Ratio ${cur.ratio}, RS-Momentum ${cur.momentum}`}</title></circle>
                    <text x={sx(cur.ratio) + 9} y={sy(cur.momentum) + 4} fontSize="11" fill="#e5e7eb" fontWeight="600">{s.symbol}</text>
                  </g>
                )
              })}
            </svg>
          </Card>
          <div className="space-y-4">
            {ORDER.map(q => {
              const members = data.sectors.filter(s => s.quadrant === q)
              return (
                <Card key={q} title={<span style={{ color: QUAD[q].color }}>{members[0]?.quadrantName || q[0].toUpperCase() + q.slice(1)}</span>} right={`${members.length} sector${members.length === 1 ? '' : 's'}`}>
                  <p className="text-[11px] text-gray-500 mb-2">{({ leading: 'Outperforming and still gaining strength', weakening: 'Outperforming, but momentum is fading', lagging: 'Underperforming and still losing ground', improving: 'Underperforming, but momentum is turning up' })[q]}</p>
                  {members.length === 0 ? <div className="text-xs text-gray-600">None right now.</div> : (
                    <ul className="space-y-1">
                      {members.map(s => (
                        <li key={s.symbol} className="flex items-center justify-between text-xs" onMouseEnter={() => setFocus(s.symbol)} onMouseLeave={() => setFocus(null)}>
                          <span className="text-gray-200">{s.name} <span className="text-gray-500">{s.symbol}</span></span>
                          <span className="text-gray-500 tabular-nums">{s.ratio.toFixed(1)} / {s.momentum.toFixed(1)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              )
            })}
          </div>
        </div>
      )}
      {data && <Caveats title="How this is calculated" items={[data.note, 'Positions are weekly and the trail shows the last 8 weeks. Rotations are not guaranteed to complete, and a sector can sit in one quadrant for months.', `As of ${data.asOf}. Not investment advice.`]} />}
    </div>
  )
}
