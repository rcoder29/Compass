import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { NAV_GROUPS, navItems, flattenNav, Sidebar } from './App'

const ids = () => NAV_GROUPS.flatMap(g => navItems(g).map(i => i.id))

describe('sidebar structure', () => {
  it('has the eleven groups in workflow order', () => {
    expect(NAV_GROUPS.map(g => g.label)).toEqual(['My Money', 'Markets', 'Economy', 'Sectors & Themes', 'Find Ideas', 'Research', 'Fixed Income',
      'Event-Driven', 'Trading', 'Planning', 'AI Assistant'])
  })

  it('lists every view exactly once, and every item has a label', () => {
    expect(ids()).toHaveLength(109)
    expect(new Set(ids()).size).toBe(109)
    NAV_GROUPS.forEach(g => navItems(g).forEach(i => expect(i.label, i.id).toBeTruthy()))
  })

  it('group ids are unique and every group has an icon and at least three views', () => {
    expect(new Set(NAV_GROUPS.map(g => g.id)).size).toBe(NAV_GROUPS.length)
    NAV_GROUPS.forEach(g => { expect(g.icon, g.id).toBeTruthy(); expect(navItems(g).length, g.id).toBeGreaterThanOrEqual(3) })
  })

  it('every heading introduces at least one view and none are doubled up', () => {
    NAV_GROUPS.forEach(g => g.items.forEach((item, k) => {
      if (!item.heading) return
      expect(g.items[k + 1]?.id, `${g.id} › ${item.heading}`).toBeTruthy()
    }))
  })

  it('keeps related views together', () => {
    const group = id => NAV_GROUPS.find(g => navItems(g).some(i => i.id === id)).label
    expect(group('watchlist')).toBe('My Money'); expect(group('customnews')).toBe('My Money'); expect(group('portfolio')).toBe('My Money')
    expect(group('shortinterest')).toBe('Find Ideas'); expect(group('hundredbaggers')).toBe('Find Ideas'); expect(group('tradeideas')).toBe('Find Ideas')
    expect(group('tearsheet')).toBe('Research'); expect(group('corporatebonds')).toBe('Fixed Income')
    expect(group('mergeroverview')).toBe('Event-Driven'); expect(group('spacoverview')).toBe('Event-Driven')
    expect(group('optionstracker')).toBe('Trading'); expect(group('journal')).toBe('Trading')
    expect(group('fire')).toBe('Planning'); expect(group('taxadvisor')).toBe('Planning'); expect(group('taxlots')).toBe('Planning')
    expect(group('themeai')).toBe('Sectors & Themes'); expect(group('sectorboard')).toBe('Sectors & Themes')
  })
})

describe('flattenNav (⌘K index and recents)', () => {
  const flat = flattenNav(NAV_GROUPS)
  const find = id => flat.find(i => i.id === id)

  it('skips headings and includes every view once', () => {
    expect(flat).toHaveLength(109)
    expect(flat.some(i => i.heading || !i.id)).toBe(false)
  })

  it('names the sub-section so duplicate labels can be told apart', () => {
    expect(find('mergeroverview').group).toBe('Event-Driven › Merger Arb')
    expect(find('spacoverview').group).toBe('Event-Driven › SPACs')
    expect(find('spacportfolio').group).toBe('Event-Driven › SPACs')           // same label as Portfolio in My Money
    expect(find('portfolio').group).toBe('My Money › Portfolio')
    expect(find('themeai').group).toBe('Sectors & Themes › Themes')
    expect(find('econregime').group).toBe('Economy')                           // groups without headings keep just their name
  })
})

describe('Sidebar', () => {
  const renderSidebar = (activeTab = 'home', extra = {}) => render(<Sidebar activeTab={activeTab} onSelect={vi.fn()} pinnedTabs={[]} onTogglePin={vi.fn()} {...extra} />)

  it('starts with every group collapsed except the one holding the active view', () => {
    renderSidebar('themeai')
    expect(screen.getByRole('button', { name: /Sectors & Themes/ })).toBeInTheDocument()
    expect(screen.getByText('Artificial Intelligence')).toBeInTheDocument()       // its group is open
    expect(screen.queryByText('Tear Sheet')).toBeNull()                           // Research is closed
  })

  it('shows sub-headings inside an open group, as captions rather than links', () => {
    renderSidebar('themeai')
    expect(screen.getByText('Sectors', { selector: 'div' })).toBeInTheDocument()
    expect(screen.getByText('Themes', { selector: 'div' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Themes' })).toBeNull()
  })

  it('expands a group on click and selects a view', () => {
    const onSelect = vi.fn()
    renderSidebar('home', { onSelect })
    expect(screen.queryByText('Tear Sheet')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /^Research/ }))
    expect(screen.getByText('Analyze a company', { selector: 'div' })).toBeInTheDocument()
    expect(screen.getByText('Compare & test', { selector: 'div' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Tear Sheet' }))
    expect(onSelect).toHaveBeenCalledWith('tearsheet')
  })

  it('opens the right group for a view that moved (Short Interest is under Find Ideas)', () => {
    renderSidebar('shortinterest')
    const open = screen.getByText('Market-driven ideas', { selector: 'div' }).parentElement
    expect(within(open).getByRole('button', { name: 'Short Interest' })).toBeInTheDocument()
  })

  it('lists pins by label wherever the view now lives', () => {
    renderSidebar('home', { pinnedTabs: ['shortinterest', 'tearsheet', 'sectors-gone'] })
    const pinned = screen.getByText('Pinned').parentElement
    expect(within(pinned).getByText('Short Interest')).toBeInTheDocument(); expect(within(pinned).getByText('Tear Sheet')).toBeInTheDocument()
    expect(within(pinned).queryByText('sectors-gone')).toBeNull()                  // an unknown id is skipped, not shown raw
  })

  it('unpinning from the pinned list calls back', () => {
    const onTogglePin = vi.fn()
    renderSidebar('home', { pinnedTabs: ['tearsheet'], onTogglePin })
    fireEvent.click(screen.getByTitle('Unpin'))
    expect(onTogglePin).toHaveBeenCalledWith('tearsheet')
  })
})
