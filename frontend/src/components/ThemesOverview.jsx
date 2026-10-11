import { usePolledApi, PageHeader, Loading, ErrorBox, Caveats, Card, fmtPct, signedClass, DASH } from './MacroKit'
import { RETURN_COLS, RetCell, MiniSeries, ScanProgress, PartialNote, Disclaimer } from './ThemeKit'

const NAV = { ai: 'themeai', robotics: 'themerobotics', quantum: 'themequantum', space: 'themespace' }

export default function ThemesOverview({ onNavigate }) {
  const { data, error } = usePolledApi('/api/themes')
  if (error) return <div className="p-4 max-w-[1500px] mx-auto"><ErrorBox>{error}</ErrorBox></div>
  if (!data) return <div className="p-4"><Loading>Loading themes…</Loading></div>
  if (data.status === 'running') return <div className="p-4 max-w-[1500px] mx-auto space-y-4"><PageHeader title="Themes">Reading fundamentals for the themed companies.</PageHeader><ScanProgress data={data} /></div>

  const themes = data.themes
  const best = key => [...themes].filter(t => t.returns[key] != null).sort((a, b) => b.returns[key] - a.returns[key])[0]
  const bestYear = best('1Y'), worstQuarter = [...themes].filter(t => t.returns['3M'] != null).sort((a, b) => a.returns['3M'] - b.returns['3M'])[0]

  return (
    <div className="p-4 space-y-4 max-w-[1500px] mx-auto">
      <PageHeader title="Themes Overview">
        Thematic investing groups companies by a long-term force reshaping the economy instead of by sector. Each theme has its own page with the leaders, the suppliers that benefit,
        speculative names, how they have performed, and where analysts and the numbers suggest it could go. Start here to compare them.
      </PageHeader>
      <PartialNote partial={data.partial} />

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
        {themes.map(t => (
          <button key={t.id} onClick={() => onNavigate?.(NAV[t.id])} aria-label={`${t.name} theme`} className="text-left bg-gray-900/60 border border-gray-800 hover:border-gray-600 rounded-xl p-4 space-y-3" style={{ borderTop: `3px solid ${t.color}` }}>
            <div>
              <div className="text-sm font-semibold text-gray-100">{t.name}</div>
              <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{t.tagline}</div>
            </div>
            <MiniSeries series={t.series} color={t.color} width={220} height={44} />
            <div className="grid grid-cols-3 gap-2 text-center">
              {['3M', '1Y', '3Y'].map(p => (
                <div key={p}><div className={`text-base font-semibold tabular-nums ${signedClass(t.returns[p])}`}>{fmtPct(t.returns[p], { digits: 0 })}</div><div className="text-[10px] text-gray-500">{p} · SPY {fmtPct(data.benchmark?.[p], { digits: 0 })}</div></div>
              ))}
            </div>
            <div className="text-[11px] text-gray-400 flex justify-between">
              <span>Analyst upside <span className={signedClass(t.outlook.analystUpsideMedian)}>{fmtPct(t.outlook.analystUpsideMedian, { digits: 0 })}</span></span>
              <span>{t.members} companies</span>
            </div>
            <div className="text-[11px]"><span className="text-gray-500">Strongest setups: </span><span className="text-gray-300">{t.top.map(x => x.symbol).join(', ') || DASH}</span></div>
          </button>
        ))}
      </div>

      <Card title="Side by side" right={`equal-weight basket averages · as of ${data.asOf}`}>
        <div className="overflow-x-auto" data-testid="themes-table">
          <table className="w-full text-xs border-separate border-spacing-0">
            <thead>
              <tr className="text-[11px] text-gray-400"><th className="text-left px-2 py-1.5 font-semibold">Theme</th>{RETURN_COLS.map(p => <th key={p} className="text-right px-2 font-semibold">{p}</th>)}
                <th className="text-right px-2 font-semibold">Analyst upside</th><th className="text-right px-2 font-semibold">Revenue growth</th><th className="text-right px-2 font-semibold">Profitable</th></tr>
            </thead>
            <tbody>
              {themes.map(t => (
                <tr key={t.id} className="hover:bg-gray-800/40 cursor-pointer" onClick={() => onNavigate?.(NAV[t.id])}>
                  <td className="px-2 py-2 border-t border-gray-800/60"><span className="inline-block w-2 h-2 rounded-sm mr-2" style={{ background: t.color }} /><span className="text-gray-100">{t.name}</span></td>
                  {RETURN_COLS.map(p => <RetCell key={p} v={t.returns[p]} col={p} />)}
                  <td className={`px-2 py-2 text-right tabular-nums border-t border-gray-800/60 ${signedClass(t.outlook.analystUpsideMedian)}`}>{fmtPct(t.outlook.analystUpsideMedian, { digits: 0 })}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{fmtPct(t.outlook.growthMedian, { signed: false, digits: 0 })}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-gray-300 border-t border-gray-800/60">{t.outlook.profitableShare == null ? DASH : fmtPct(t.outlook.profitableShare, { signed: false, digits: 0 })}</td>
                </tr>
              ))}
              <tr className="bg-gray-950/40">
                <td className="px-2 py-2 border-t border-gray-700 text-gray-300">S&amp;P 500 (SPY)</td>
                {RETURN_COLS.map(p => <td key={p} className={`px-2 py-2 text-right tabular-nums border-t border-gray-700 ${signedClass(data.benchmark?.[p])}`}>{fmtPct(data.benchmark?.[p], { digits: 0 })}</td>)}
                <td colSpan={3} className="border-t border-gray-700" />
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-gray-500 mt-3">
          {bestYear && <>Over the past year {bestYear.name} has led ({fmtPct(bestYear.returns['1Y'], { digits: 0 })}). </>}
          {worstQuarter && worstQuarter.returns['3M'] < 0 && <>{worstQuarter.name} has lagged most recently ({fmtPct(worstQuarter.returns['3M'], { digits: 0 })} over 3 months). </>}
          Themes move in waves: the best 3-year performers are often the most crowded and the most prone to sharp pullbacks.
        </p>
      </Card>

      <Card title="Where the leaders are, right now">
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4 text-xs">
          {themes.map(t => (
            <div key={t.id}>
              <div className="font-medium mb-1.5" style={{ color: t.color }}>{t.short}</div>
              <div className="text-[11px] text-gray-500">Best 3-month</div><div className="text-emerald-300 mb-1.5">{t.leaders3M.join(', ') || DASH}</div>
              <div className="text-[11px] text-gray-500">Weakest 3-month</div><div className="text-red-300 mb-1.5">{[...t.laggards3M].reverse().join(', ') || DASH}</div>
              <div className="text-[11px] text-gray-500">Mix</div><div className="text-gray-400">{t.roleCounts.core} core · {t.roleCounts.enabler} suppliers · {t.roleCounts.adjacent} other · {t.roleCounts.emerging} speculative</div>
            </div>
          ))}
        </div>
      </Card>

      <Caveats title={`How to use the themes section (editorial view, ${data.editorialDate})`} items={[
        'Each theme page is organised the same way: performance of an equal-weight basket against SPY, the outlook (analyst targets and growth for the near term, drivers and risks for the long term), the value chain showing who else benefits, a sortable company table with a transparent setup score, candidates to research and theme ETFs.',
        'A theme is a story, and stories get crowded. Use the setup score and the risk column together: the highest scores are often small, unprofitable companies that can lose most of their value.',
        'The framing and commentary are written by hand and dated. The numbers (returns, targets, growth, valuation) are live from Yahoo Finance and cached for 15 minutes to a day.',
      ]} />
      <Disclaimer />
    </div>
  )
}
