// Recent items (M29, 42.4): the last screens, people, products and rivals visited in a save,
// kept in this browser only (UI state, like saved table views' last choice).

export interface Recent {
  label: string;
  path: string; // under /game/<save>/
  kind: string;
}

const MAX_RECENT = 8;
const storageKey = (saveId: string) => `tst.recent.${saveId}`;

export function readRecent(saveId: string): Recent[] {
  try {
    const raw = window.localStorage.getItem(storageKey(saveId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as Recent[]).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

/** Put an item first, without duplicates; returns the new list. */
export function pushRecent(saveId: string, item: Recent): Recent[] {
  const next = [item, ...readRecent(saveId).filter((r) => r.path !== item.path)].slice(
    0,
    MAX_RECENT,
  );
  try {
    window.localStorage.setItem(storageKey(saveId), JSON.stringify(next));
  } catch {
    // storage full or blocked: recent items are a convenience
  }
  return next;
}
