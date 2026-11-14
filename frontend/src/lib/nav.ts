// Navigation (M29, formulas.md 42.4): the grouped side bar, the command palette's screens and
// breadcrumbs. Which screens are open comes from the API (`/unlocks`); this file only lays
// them out. Keys 1-9 and 0 still jump to NAV_ITEMS in order.
export interface NavItem {
  path: string;
  label: string;
  arrivesIn: string | null; // null = live now
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: 'inbox', label: 'Inbox', arrivesIn: null },
  { path: 'overview', label: 'Overview', arrivesIn: null },
  { path: 'people', label: 'People', arrivesIn: null },
  { path: 'recruitment', label: 'Recruitment', arrivesIn: null },
  { path: 'org', label: 'Org', arrivesIn: null },
  { path: 'products', label: 'Products', arrivesIn: null },
  { path: 'finance', label: 'Finance', arrivesIn: null },
  { path: 'competitors', label: 'Competitors', arrivesIn: null },
  { path: 'history', label: 'History', arrivesIn: null },
  { path: 'saves', label: 'Saves', arrivesIn: null }, // M7b, key 0
];

export type NavGroup =
  'company' | 'people' | 'products' | 'markets' | 'chain' | 'finance' | 'world' | 'automation';

export const GROUPS: readonly { key: NavGroup; label: string }[] = [
  { key: 'company', label: 'Company' },
  { key: 'people', label: 'People' },
  { key: 'products', label: 'Products' },
  { key: 'markets', label: 'Markets' },
  { key: 'chain', label: 'Chain' },
  { key: 'finance', label: 'Finance' },
  { key: 'world', label: 'World' },
  { key: 'automation', label: 'Automation' }, // M27a adds its screen
];

export interface Screen {
  path: string; // under /game/<save>/
  label: string;
  group: NavGroup;
  unlock: string | null; // the /unlocks systems key; null = always shown
  side: boolean; // in the side bar (else palette and breadcrumbs only)
  parent?: string; // a parent screen's path, for breadcrumbs
}

export const SCREENS: readonly Screen[] = [
  { path: 'inbox', label: 'Inbox', group: 'company', unlock: null, side: true },
  { path: 'overview', label: 'Overview', group: 'company', unlock: null, side: true },
  { path: 'history', label: 'History', group: 'company', unlock: null, side: true },
  { path: 'saves', label: 'Saves', group: 'company', unlock: null, side: true },
  { path: 'settings', label: 'Settings', group: 'company', unlock: null, side: true },
  { path: 'people', label: 'People', group: 'people', unlock: null, side: true },
  { path: 'recruitment', label: 'Recruitment', group: 'people', unlock: null, side: true },
  { path: 'org', label: 'Org', group: 'people', unlock: null, side: true },
  {
    path: 'org/offices',
    label: 'Offices',
    group: 'people',
    unlock: 'offices',
    side: true,
    parent: 'org',
  },
  { path: 'products', label: 'Products', group: 'products', unlock: null, side: true },
  {
    path: 'products/research',
    label: 'Research',
    group: 'products',
    unlock: 'research',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/infrastructure',
    label: 'Infrastructure',
    group: 'products',
    unlock: 'infrastructure',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/hardware',
    label: 'Hardware',
    group: 'products',
    unlock: 'hardware',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/markets',
    label: 'Markets',
    group: 'markets',
    unlock: null,
    side: true,
    parent: 'products',
  },
  { path: 'competitors', label: 'Competitors', group: 'markets', unlock: null, side: true },
  {
    path: 'competitors/rankings',
    label: 'Rankings',
    group: 'markets',
    unlock: 'rankings',
    side: true,
    parent: 'competitors',
  },
  {
    path: 'products/exploration',
    label: 'Exploration',
    group: 'chain',
    unlock: 'exploration',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/mines',
    label: 'Mines',
    group: 'chain',
    unlock: 'mines',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/refineries',
    label: 'Refineries',
    group: 'chain',
    unlock: 'refineries',
    side: true,
    parent: 'products',
  },
  {
    path: 'products/fabs',
    label: 'Fabs',
    group: 'chain',
    unlock: 'fabs',
    side: true,
    parent: 'products',
  },
  { path: 'finance', label: 'Finance', group: 'finance', unlock: null, side: true },
  ...(
    [
      ['statements', 'Statements'],
      ['captable', 'Cap table'],
      ['fundraising', 'Fundraising'],
      ['debt', 'Debt'],
      ['board', 'Board'],
      ['divisions', 'Divisions'],
      ['deals', 'Deals'],
      ['stock', 'Stock'],
    ] as const
  ).map(([tab, label]) => ({
    path: `finance/${tab}`,
    label,
    group: 'finance' as const,
    unlock: null,
    side: false,
    parent: 'finance',
  })),
  {
    path: 'finance/group',
    label: 'Group',
    group: 'finance',
    unlock: 'group',
    side: true,
    parent: 'finance',
  },
  {
    path: 'competitors/world',
    label: 'World',
    group: 'world',
    unlock: 'world',
    side: true,
    parent: 'competitors',
  },
  {
    path: 'automation',
    label: 'Automation',
    group: 'automation',
    unlock: 'automation',
    side: true,
  }, // M27a
  ...(
    [
      ['timeline', 'Timeline'],
      ['charts', 'Charts'],
      ['storylines', 'Storylines'],
      ['fame', 'Hall of fame'],
    ] as const
  ).map(([tab, label]) => ({
    path: `history/${tab}`,
    label,
    group: 'company' as const,
    unlock: null,
    side: false,
    parent: 'history',
  })),
];

/** Whether a screen is open: always-shown ones, and those the API says are unlocked. */
export function isOpen(screen: Screen, unlocked: ReadonlySet<string> | null): boolean {
  return screen.unlock === null || unlocked === null || unlocked.has(screen.unlock);
}

/** The side bar's groups with their open screens; an empty group is left out. */
export function sideGroups(unlocked: ReadonlySet<string> | null) {
  return GROUPS.map((g) => ({
    ...g,
    screens: SCREENS.filter((s) => s.side && s.group === g.key && isOpen(s, unlocked)),
  })).filter((g) => g.screens.length > 0);
}

/** The hotkey (1-9, 0) of a side-bar screen, if it has one. */
export function hotkeyOf(path: string): string | null {
  const index = NAV_ITEMS.findIndex((n) => n.path === path);
  return index < 0 ? null : String((index + 1) % 10);
}

/** The screen a path shows: the longest catalogue path it starts with. */
export function screenOf(path: string): Screen | undefined {
  const clean = path.split('?')[0].replace(/\/+$/, '');
  return [...SCREENS]
    .filter((s) => clean === s.path || clean.startsWith(`${s.path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0];
}

export interface Crumb {
  label: string;
  path: string | null; // null: the page itself
}

/** Breadcrumbs for a path under /game/<save>/: its screen's parents, the screen, then a
 * named item (a person, product or rival) when the path goes deeper. */
export function crumbs(path: string, names: ReadonlyMap<string, string>): Crumb[] {
  const clean = path.split('?')[0].replace(/\/+$/, '');
  const screen = screenOf(clean);
  if (!screen) return [];
  const chain: Screen[] = [screen];
  for (let s = screen; s.parent;) {
    const parent = SCREENS.find((p) => p.path === s.parent);
    if (!parent) break;
    chain.unshift(parent);
    s = parent;
  }
  const out: Crumb[] = chain.map((s) => ({ label: s.label, path: s.path }));
  if (clean !== screen.path) {
    const name = names.get(clean);
    if (name) out.push({ label: name, path: clean });
  }
  out[out.length - 1] = { ...out[out.length - 1], path: null };
  return out;
}

/** Where the top bar's "Answer ... first" link goes (Reece's playtest 3): the first event
 * that needs answering, else the Org screen for proposals and pitches, else the inbox. */
export function answerHref(saveId: string, blockingEventIds: readonly number[], proposals: number) {
  if (blockingEventIds.length > 0) return `/game/${saveId}/events/${blockingEventIds[0]}`;
  return proposals > 0 ? `/game/${saveId}/org` : `/game/${saveId}/inbox`;
}
