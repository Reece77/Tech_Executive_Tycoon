import { describe, expect, it } from 'vitest';
import { GUIDES, whatNextHref } from './guides';
import { intersectKinds, kindChoices, tabKinds } from './inbox';
import { crumbs, hotkeyOf, isOpen, screenOf, SCREENS, sideGroups } from './nav';
import { matchOptions, type Option } from './palette';

// M29 (formulas.md 42.1, 42.4): the side bar, breadcrumbs, the palette's matching and the
// inbox tabs.

describe('side bar', () => {
  it('hides locked screens and empty groups', () => {
    const groups = sideGroups(new Set());
    const paths = groups.flatMap((g) => g.screens.map((s) => s.path));
    expect(paths).toContain('inbox');
    expect(paths).toContain('products/markets');
    expect(paths).not.toContain('products/fabs');
    expect(groups.map((g) => g.key)).not.toContain('chain');
    expect(groups.map((g) => g.key)).not.toContain('automation');
  });

  it('shows a screen once it unlocks, and everything while loading', () => {
    const chain = sideGroups(new Set(['fabs'])).find((g) => g.key === 'chain');
    expect(chain?.screens.map((s) => s.path)).toEqual(['products/fabs']);
    const all = sideGroups(null).flatMap((g) => g.screens);
    expect(all.length).toBe(SCREENS.filter((s) => s.side).length);
  });

  it('keeps hotkeys 1-9 and 0 on the first ten screens', () => {
    expect(hotkeyOf('inbox')).toBe('1');
    expect(hotkeyOf('saves')).toBe('0');
    expect(hotkeyOf('products/fabs')).toBeNull();
  });

  it('has a guide for every unlockable screen', () => {
    for (const s of SCREENS) if (s.unlock) expect(GUIDES[s.unlock]).toBeDefined();
    expect(isOpen(SCREENS[0], new Set())).toBe(true);
  });
});

describe('breadcrumbs', () => {
  it('names parents and the item', () => {
    const names = new Map([['people/7', 'Ana Ruiz']]);
    expect(crumbs('people/7', names)).toEqual([
      { label: 'People', path: 'people' },
      { label: 'Ana Ruiz', path: null },
    ]);
    expect(crumbs('products/fabs', names)).toEqual([
      { label: 'Products', path: 'products' },
      { label: 'Fabs', path: null },
    ]);
    expect(crumbs('inbox', names)).toEqual([{ label: 'Inbox', path: null }]);
    expect(screenOf('finance/captable')?.label).toBe('Cap table');
  });
});

describe('command palette', () => {
  const options: Option[] = [
    { key: 's', label: 'Fabs', detail: 'Screen', kind: 'screen', path: 'products/fabs' },
    { key: 'p', label: 'Ana Ruiz', detail: 'Software engineer', kind: 'person', path: 'people/7' },
    { key: 'r', label: 'Fabrikam', detail: 'Rival', kind: 'rival', path: 'competitors/3' },
  ];
  it('matches every word, screens and prefixes first', () => {
    expect(matchOptions(options, 'fab').map((o) => o.key)).toEqual(['s', 'r']);
    expect(matchOptions(options, 'ana engineer').map((o) => o.key)).toEqual(['p']);
    expect(matchOptions(options, '  ')).toEqual([]);
  });
});

describe('inbox tabs', () => {
  it('keeps the right kinds', () => {
    expect(tabKinds('digest')).toEqual(['digest']);
    expect(tabKinds('news')).toContain('market_news');
    expect(tabKinds('news')).toContain('unlock');
    expect(tabKinds('all')).toBeNull();
    expect(intersectKinds(null, ['a', 'b'], ['b', 'c'])).toEqual(['b']);
    expect(intersectKinds(null, null)).toBeNull();
    expect(kindChoices().find((c) => c.label === 'Finance')?.kinds).toContain('round_closed');
  });

  it('links What next items to their screens', () => {
    const item = { key: 'unlock', text: '', link_kind: 'guide', link_id: null, link_key: 'fabs' };
    expect(whatNextHref('s', item)).toBe('/game/s/guide/fabs');
    expect(whatNextHref('s', { ...item, link_kind: 'event', link_id: 4 })).toBe('/game/s/events/4');
    expect(whatNextHref('s', { ...item, link_kind: 'board' })).toBe('/game/s/finance/board');
  });
});
