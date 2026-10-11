import { useState } from 'react'
import { useApi, PageHeader, Loading, ErrorBox, Caveats, Card, TimeChart, fmtPct, fmtNum } from './MacroKit'

function StatsRow({ label, s, color }) {
  return (
    <tr className="border-t border-gray-800/70">
      <td className="py-1.5 text-gray-200"><span style={{ color }}>■</span> {label}</td>
      <td className="text-right tabular-nums">{fmtPct(s.cagr)}</td><td className="text-right tabular-nums">{fmtPct(s.volatility, { signed: false })}</td>
      <td className="text-right tabular-nums">{fmtNum(s.sharpe)}</td><td className="text-right tabular-nums text-red-300">{fmtPct(s.maxDrawdown, { signed: false })}</td>
      <td className="text-right tabular-nums">{fmtPct(s.worstMonth)}</td><td className="text-right tabular-nums">{fmtPct(s.totalReturn, { digits: 0 })}</td>
    </tr>
  )
}

export default function SectorBacktest() {
  const [topN, setTopN] = useState(3)
  const [cost, setCost] = useState(10)
  const [defensive, setDefensive] = useState(true)
  const { data, loading, error } = useApi(`/api/sectors/backtest?top_n=${topN}&cost_bps=${cost}&defensive=${defensive}`)
  const series = data ? [
    { name: 'Rotation strategy', color: '#34d399', points: data.curve.map(c => [c.date, c.strategy]) },
    { name: 'SPY', color: '#94a3b8', points: data.curve.map(c => [c.date, c.spy]) },
    { name: 'Equal-weight sectors', color: '#fbbf24', points: data.curve.map(c => [c.date, c.equalWeight]), dashed: true },
  ] : []
  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Sector Backtest">
        What would a simple, rule-based rotation have done? Each month-end it buys the top-ranked sectors by momentum, trend and risk (using only data known at that time)
        and holds them for the next month, optionally retreating to defensive sectors when SPY is below its 10-month average.
      </PageHeader>
      <Card>
        <div className="flex flex-wrap items-end gap-6 text-xs">
          <label className="flex flex-col gap-1 text-gray-400">Sectors held
            <select value={topN} onChange={e => setTopN(Number(e.target.value))} aria-label="Sectors held" className="bg-gray-800 border border-gray-700 text-gray-100 px-2 py-1.5 rounded-lg">
              {[1, 2, 3, 4, 5, 6].map(n => <option key={n} value={n}>Top {n}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-gray-400">Trading cost per side
            <select value={cost} onChange={e => setCost(Number(e.target.value))} aria-label="Trading cost" className="bg-gray-800 border border-gray-700 text-gray-100 px-2 py-1.5 rounded-lg">
              {[0, 5, 10, 25, 50].map(n => <option key={n} value={n}>{n} bps</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-gray-300 cursor-pointer pb-1.5"><input type="checkbox" checked={defensive} onChange={e => setDefensive(e.target.checked)} />Defensive switch (Staples, Utilities, Health Care when SPY &lt; 10-mo average)</label>
        </div>
      </Card>
      {loading && <Loading>Running the backtest…</Loading>}
      {error && <ErrorBox>{error}</ErrorBox>}
      {data && (
        <>
          <Card title="Growth of $1" right={`${data.start} to ${data.end} · ${data.months} months`}>
            <TimeChart series={series} height={300} format={v => `$${fmtNum(v)}`} label="Growth of one dollar" />
            <div className="flex flex-wrap gap-4 text-[11px] mt-1">{series.map(s => <span key={s.name} style={{ color: s.color }}>— {s.name}</span>)}</div>
          </Card>
          <div className="grid lg:grid-cols-[1fr_320px] gap-4">
            <Card title="Results">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-[11px] text-gray-500"><th className="text-left py-1.5 font-medium" /><th className="text-right font-medium">CAGR</th><th className="text-right font-medium">Volatility</th><th className="text-right font-medium">Return/risk</th><th className="text-right font-medium">Max drawdown</th><th className="text-right font-medium">Worst month</th><th className="text-right font-medium">Total</th></tr></thead>
                  <tbody>
                    <StatsRow label="Rotation strategy" s={data.strategy} color="#34d399" />
                    <StatsRow label="SPY" s={data.spy} color="#94a3b8" />
                    <StatsRow label="Equal-weight sectors" s={data.equalWeight} color="#fbbf24" />
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Beat SPY in {fmtPct(data.monthsBeatingSpy, { signed: false, digits: 0 })} of months · annual turnover {fmtNum(data.annualTurnover, 1)}× · risk-off in {data.riskOffMonths} months.
              </p>
            </Card>
            <Card title="Holdings for next month" right="signal as of the last month-end">
              <div className="flex flex-wrap gap-2">{data.latestHoldings.map(s => <span key={s} className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs">{s}</span>)}</div>
              <p className="text-[11px] text-gray-500 mt-3">Try changing the settings: if the result flips from a win to a loss with small changes, the “edge” is probably not robust.</p>
            </Card>
          </div>
          <Caveats title="Read before trusting any of this" items={data.notes} />
        </>
      )}
    </div>
  )
}
