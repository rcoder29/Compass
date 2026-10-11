// Browser-storage keys that used to carry the app's old name (Stock Monitor, "sm-") and what they are called now.
// migrateStorage() moves the data across once, so the rename never loses a saved watchlist, pins or theme.
export const KEYS = {
  watchlist: 'compass-watchlist',        // legacy one-time import of a pre-database watchlist
  portfolio: 'compass-portfolio',        // legacy one-time import of a pre-database portfolio
  theme: 'compass-theme',
  recentTabs: 'compass-recent-tabs',
  pinnedTabs: 'compass-pinned-tabs',
}

export const RENAMED_KEYS = [
  ['stockmonitor-watchlist', KEYS.watchlist],
  ['stockmonitor-portfolio', KEYS.portfolio],
  ['sm-theme', KEYS.theme],
  ['sm-recent-tabs', KEYS.recentTabs],
  ['sm-pinned-tabs', KEYS.pinnedTabs],
]

/**
 * Copy each old key's value to its new key, then remove the old one. A value already stored under the new key always
 * wins (it is newer), and the old key is still removed. Safe to run on every load; never throws (storage can be
 * blocked in private windows). Returns how many keys it moved.
 */
export function migrateStorage(storage, renames = RENAMED_KEYS) {
  let moved = 0
  try {
    const store = storage ?? window.localStorage
    for (const [oldKey, newKey] of renames) {
      const value = store.getItem(oldKey)
      if (value === null) continue
      if (store.getItem(newKey) === null) { store.setItem(newKey, value); moved += 1 }
      store.removeItem(oldKey)
    }
  } catch { /* storage unavailable: nothing to migrate */ }
  return moved
}
