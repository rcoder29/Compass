import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import fs from 'fs'
import UserGuide from './UserGuide'
import { CHANGELOG_BLOCKS } from '../data/changelog'

describe('UserGuide', () => {
  it('renders the main heading', () => {
    render(<UserGuide />)
    expect(screen.getByText('Stock Monitor — User Guide')).toBeInTheDocument()
  })

  it('renders all 6 top-level nav group names in TOC', () => {
    render(<UserGuide />)
    // These appear in TOC and as section headings — use getAllByText
    expect(screen.getAllByText('Getting Started').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Markets').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Watchlist').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Portfolio').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Research').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Trading').length).toBeGreaterThan(0)
  })

  it('renders Changelog section', () => {
    render(<UserGuide />)
    expect(screen.getAllByText('Changelog').length).toBeGreaterThan(0)
  })

  it('Markets section covers correct items in nav table', () => {
    render(<UserGuide />)
    // Nav table row for Markets should mention these
    const content = document.body.textContent
    expect(content).toContain('Analyst Picks')
    expect(content).toContain('Index Heatmap')
    expect(content).toContain('Sector Rotation')
    expect(content).toContain('Sector Momentum')
  })

  it('Watchlist section mentions Smart Alerts', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Smart Alerts')
  })

  it('search filters sections', () => {
    render(<UserGuide />)
    const input = screen.getByPlaceholderText('Search the guide…')
    fireEvent.change(input, { target: { value: 'heatmap' } })
    // Should show match count indicator
    // anchored to the indicator's real format ("3 sections match") so guide prose that happens to contain both words can't collide
    expect(screen.getByText(/^\d+ sections? match$/i)).toBeInTheDocument()
  })

  it('search with no matches shows no results message', () => {
    render(<UserGuide />)
    const input = screen.getByPlaceholderText('Search the guide…')
    fireEvent.change(input, { target: { value: 'xyzzy_impossible_match' } })
    expect(screen.getByText(/No results for/i)).toBeInTheDocument()
  })

  it('changelog mentions navigation restructure', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Navigation Restructure')
  })

  it('changelog mentions dynamic ETF search', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Dynamic')
  })

  it('Index Heatmap section is documented', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Index / ETF Heatmap')
  })

  it('Analyst Picks section is documented', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Analyst Picks')
  })

  it('Sector Rotation docs appear in Markets section', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Sector Rotation')
    expect(document.body.textContent).toContain('Sector Momentum')
  })

  it('Smart Alerts docs mention condition types', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('Volume Spike')
    expect(document.body.textContent).toContain('Golden Cross')
  })

  it('DCF section present under Research', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('DCF Valuation')
  })

  it('AI Chat section present', () => {
    render(<UserGuide />)
    expect(document.body.textContent).toContain('AI Chat')
  })
})

// The jump links ("Open feature →") passed `onNavigate` to blocks without Section ever receiving it, so
// the whole guide threw a ReferenceError the moment it rendered.
describe('UserGuide navigation links', () => {
  it('renders with an onNavigate handler (this used to throw ReferenceError)', () => {
    expect(() => render(<UserGuide onNavigate={() => {}} />)).not.toThrow()
    expect(screen.getByText('Stock Monitor — User Guide')).toBeInTheDocument()
  })

  it('offers an "Open feature" button on changelog entries and navigates to that tab', () => {
    const onNavigate = vi.fn()
    render(<UserGuide onNavigate={onNavigate} />)
    const buttons = screen.getAllByText('Open feature →')
    expect(buttons.length).toBeGreaterThan(10)
    const entry = CHANGELOG_BLOCKS.find(b => b.type === 'h3' && b.tabId === 'tearsheet')
    expect(entry).toBeTruthy()
    const heading = screen.getAllByText(entry.text, { exact: false })[0].closest('h3')
    fireEvent.click(heading.querySelector('button'))
    expect(onNavigate).toHaveBeenCalledWith('tearsheet')
  })

  it('offers one labelled button per feature for multi-feature entries', () => {
    const onNavigate = vi.fn()
    render(<UserGuide onNavigate={onNavigate} />)
    const entry = CHANGELOG_BLOCKS.find(b => b.type === 'h3' && b.tabIds?.length > 1)
    expect(entry).toBeTruthy()
    const heading = screen.getAllByText(entry.text, { exact: false })[0].closest('h3')
    const buttons = [...heading.querySelectorAll('button')]
    expect(buttons.map(b => b.textContent)).toEqual(entry.tabIds.map(t => `${t.label} →`))
    fireEvent.click(buttons[1])
    expect(onNavigate).toHaveBeenCalledWith(entry.tabIds[1].id)
  })

  it('shows no jump buttons when the guide is opened without a navigation handler', () => {
    render(<UserGuide />)
    expect(screen.queryByText('Open feature →')).not.toBeInTheDocument()
  })
})

// Documentation that drifts from the app is worse than none: keep the guide and the changelog links
// honest against the real sidebar.
describe('UserGuide stays in sync with the app', () => {
  const app = fs.readFileSync('src/App.jsx', 'utf8')
  const nav = app.slice(app.indexOf('const NAV_GROUPS'), app.indexOf('\n]\n', app.indexOf('const NAV_GROUPS')))
  const navItems = [...nav.matchAll(/\{ id: '(\w+)',\s*label: '([^']+)'/g)].map(m => ({ id: m[1], label: m[2] }))

  it('finds the sidebar items to compare against', () => {
    expect(navItems.length).toBeGreaterThan(80)
  })

  it('documents every sidebar view somewhere in the guide', () => {
    render(<UserGuide />)
    const text = document.body.textContent.toLowerCase()
    const missing = navItems.filter(i => !text.includes(i.label.toLowerCase())).map(i => i.label)
    expect(missing).toEqual([])
  })

  it('only links changelog entries to tabs that exist', () => {
    // every route App.jsx can render (sidebar items plus tabs outside the groups, like Home)
    const ids = new Set([...app.matchAll(/activeTab === '(\w+)'/g)].map(m => m[1]))
    expect(ids.size).toBeGreaterThan(80)
    const linked = CHANGELOG_BLOCKS.filter(b => b.type === 'h3').flatMap(b => [b.tabId, ...(b.tabIds || []).map(t => t.id)]).filter(Boolean)
    expect(linked.length).toBeGreaterThan(30)
    expect(linked.filter(id => !ids.has(id))).toEqual([])
  })
})

