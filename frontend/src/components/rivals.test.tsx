// Component tests render to static markup: no DOM library is in ADR-0001's dependency list.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { kindLabel } from '../lib/inbox';
import { answerHref } from '../lib/nav';
import { MoveTag, ProductMarkets, StartupChip, StyleChip } from '../lib/rivals';

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

describe("Reece's playtest 3", () => {
  it("shows each rival product's market: category, segments and regions", () => {
    const html = renderToStaticMarkup(
      <ProductMarkets
        products={[
          {
            product_id: 7,
            name: 'Zoho CRM',
            category_label: 'B2B SaaS',
            segment_labels: ['SMB', 'Mid-market'],
            region_labels: ['North America', 'Europe'],
          },
        ]}
      />,
    );
    expect(html).toContain('Zoho CRM');
    expect(html).toContain('B2B SaaS · SMB, Mid-market · North America, Europe');
  });

  it('sends "Answer 1 event" to the event that needs answering', () => {
    expect(answerHref('s', [42, 43], 1)).toBe('/game/s/events/42');
    expect(answerHref('s', [], 2)).toBe('/game/s/org');
    expect(answerHref('s', [], 0)).toBe('/game/s/inbox');
  });
});
