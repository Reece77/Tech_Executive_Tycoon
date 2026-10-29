// Component tests render to static markup: no DOM library is in ADR-0001's dependency list.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { kindLabel } from '../lib/inbox';
import { MoveTag, StartupChip, StyleChip } from '../lib/rivals';

describe('rival chips (M5)', () => {
  it('shows the style label and the startup chip', () => {
    expect(renderToStaticMarkup(<StyleChip personality="premium" label="Premium" />)).toContain(
      '>Premium<',
    );
    expect(renderToStaticMarkup(<StartupChip />)).toContain('>Startup<');
    expect(renderToStaticMarkup(<MoveTag tag="Price" />)).toContain('>Price<');
  });

  it('labels rival inbox items as News', () => {
    expect(kindLabel('market_news')).toBe('News');
    expect(kindLabel('rival_approach')).toBe('News');
    expect(kindLabel('poach_accepted')).toBe('Notice');
  });
});
