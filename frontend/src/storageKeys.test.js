import { describe, it, expect, vi, afterEach } from 'vitest'
import { migrateStorage, RENAMED_KEYS, KEYS } from './storageKeys'

function fakeStorage(initial = {}) {
  const data = { ...initial }
  return {
    data,
    getItem: k => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v) },
    removeItem: k => { delete data[k] },
  }
}

afterEach(() => { vi.unstubAllGlobals() })

describe('migrateStorage', () => {
  it('moves every branded key to its new name and removes the old one', () => {
    const s = fakeStorage({ 'sm-theme': 'light', 'sm-pinned-tabs': '["market"]', 'sm-recent-tabs': '["home"]', 'stockmonitor-watchlist': '["AAPL"]', 'stockmonitor-portfolio': '[{"s":1}]' })
    expect(migrateStorage(s)).toBe(5)
    expect(s.data).toEqual({ 'compass-theme': 'light', 'compass-pinned-tabs': '["market"]', 'compass-recent-tabs': '["home"]', 'compass-watchlist': '["AAPL"]', 'compass-portfolio': '[{"s":1}]' })
  })

  it('is idempotent: a second run changes nothing', () => {
    const s = fakeStorage({ 'sm-theme': 'light' })
    migrateStorage(s)
    const after = { ...s.data }
    expect(migrateStorage(s)).toBe(0)
    expect(s.data).toEqual(after)
  })

  it('a value already under the new key wins, and the old key is still cleaned up', () => {
    const s = fakeStorage({ 'sm-theme': 'light', 'compass-theme': 'dark' })
    expect(migrateStorage(s)).toBe(0)
    expect(s.data).toEqual({ 'compass-theme': 'dark' })
  })

  it('leaves unrelated keys alone, including unbranded ones the app uses', () => {
    const s = fakeStorage({ tax_lots: '[]', wheel_positions: '[]', 'drawings:AAPL': '{}', other: 'x' })
    expect(migrateStorage(s)).toBe(0)
    expect(s.data).toEqual({ tax_lots: '[]', wheel_positions: '[]', 'drawings:AAPL': '{}', other: 'x' })
  })

  it('keeps an empty string value (it is data, not missing)', () => {
    const s = fakeStorage({ 'sm-pinned-tabs': '' })
    migrateStorage(s)
    expect(s.data).toEqual({ 'compass-pinned-tabs': '' })
  })

  it('never throws if storage is unavailable', () => {
    const blocked = { getItem() { throw new Error('denied') }, setItem() {}, removeItem() {} }
    expect(migrateStorage(blocked)).toBe(0)
  })

  it('defaults to the browser\'s localStorage, where the app then finds the new names', () => {
    const s = fakeStorage({ 'sm-pinned-tabs': '["themeai"]' })
    vi.stubGlobal('localStorage', s)
    expect(migrateStorage()).toBe(1)
    expect(s.getItem(KEYS.pinnedTabs)).toBe('["themeai"]')
    expect(s.getItem('sm-pinned-tabs')).toBeNull()
  })

  it('maps each old name to a distinct new compass-* key', () => {
    const olds = RENAMED_KEYS.map(r => r[0]), news = RENAMED_KEYS.map(r => r[1])
    expect(new Set(news).size).toBe(news.length)
    expect(news.every(k => k.startsWith('compass-'))).toBe(true)
    expect(olds.every(k => k.startsWith('sm-') || k.startsWith('stockmonitor-'))).toBe(true)
    expect(Object.values(KEYS).sort()).toEqual([...news].sort())
  })
})
