import { useState } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, Segmented, fmtPct, heat } from './MacroKit'
import { PHASE_COLOR } from './EconomyRegime'

const GROUP_NAMES = {
  phase: { early: 'Early recovery', mid: 'Mid-cycle', late: 'Late cycle', slowdown: 'Slowdown', recession: 'Recession risk' },
  quadrant: { goldilocks: 'Goldilocks', overheating: 'Overheating', slowdown: 'Slowdown', stagflation: 'Stagflation' },
}
const ORDER = { phase: ['early', 'mid', 'late', 'slowdown', 'recession'], quadrant: ['goldilocks', 'overheating', 'slowdown', 'stagflation'] }

export default function SectorCycleFit() {
  const [group, setGroup] = useState('phase')
  const { data, loading, error } = useApi(`/api/sectors/cycle-fit?group=${group}`)
  const cols = data ? ORDER[group].filter(g => data.groups.includes(g)) : []
  const current = data?.current?.[group]

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Sector Cycle Fit">
        How each sector has behaved against the S&amp;P 500 in each stage of the business cycle, using the regime labels from the Economy section since 1999.
        Green means the sector has beaten SPY on average in that stage; red, lagged.
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Grouping" options={[['phase', 'By cycle phase'], ['quadrant', 'By growth / inflation']]} value={group} onChange={setGroup} />
        {current && <span className="text-xs text-gray-400 ml-auto">Right now: <span className="font-medium" style={{ color: group === 'phase' ? PHASE_COLOR[current] : '#e5e7eb' }}>{GROUP_NAMES[group][current]}</span></span>}
      </div>
      {loading && <Loading>Computing sector behaviour by regime…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <>
          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-auto" data-testid="cyclefit-table">
            <table className="w-full text-xs border-separate border-spacing-0">
              <thead className="bg-gray-900">
                <tr>
                  <th className="text-left px-3 py-2 text-[11px] text-gray-400 font-semibold">Sector</th>
                  {cols.map(g => (
                    <th key={g} className={`px-3 py-2 text-[11px] font-semibold text-right ${g === current ? 'text-emerald-300' : 'text-gray-400'}`}>
                      {GROUP_NAMES[group][g]}{g === current && ' ●'}
                      <div className="font-normal text-gray-600">{data.samples[g]} months</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.sectors.map(s => (
                  <tr key={s.symbol}>
                    <td className="px-3 py-1.5 border-t border-gray-800/60 text-gray-200 whitespace-nowrap">{s.name} <span className="text-gray-500">{s.symbol}</span></td>
                    {cols.map(g => {
                      const c = s.cells[g]
                      return (
                        <td key={g} className={`px-3 py-1.5 text-right tabular-nums border-t border-gray-800/60 ${c ? (c.avgMonthlyExcess >= 0 ? 'text-emerald-200' : 'text-red-200') : 'text-gray-600'}`}
                            style={c ? heat(c.avgMonthlyExcess, 0.012) : {}} title={c ? `${c.months} months across ${c.episodes} stretches; beat SPY in ${Math.round(c.hitRate * 100)}% of them` : 'No history'}>
                          {c ? <>{fmtPct(c.avgMonthlyExcess, { digits: 2 })}<span className="text-[10px] text-gray-500 ml-1">{c.months < 24 ? `(${c.months}m)` : ''}</span></> : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Card title="How to read this">
            <ul className="text-xs text-gray-400 space-y-1.5 list-disc pl-5">
              <li>Each cell is the sector&apos;s average <em>monthly</em> return minus SPY&apos;s in months labelled with that stage. +0.50% a month is roughly +6% a year ahead of the market while the stage lasts.</li>
              <li>Hover a cell for the number of months, how many separate stretches they came from, and the share of months the sector beat SPY. Cells with fewer than 24 months show the count.</li>
              <li>The Screener uses the current phase&apos;s column as its “Cycle fit” factor (only cells with at least 6 months of evidence).</li>
            </ul>
          </Card>
          <Caveats title="Be careful with this" items={[data.note, 'Averages hide a lot of variation: a sector can lead in a stage on average because of one episode (for example Energy in 2021-22 or Technology in 1999-2000). Look at hit rates before leaning on a cell.']} />
        </>
      )}
    </div>
  )
}
