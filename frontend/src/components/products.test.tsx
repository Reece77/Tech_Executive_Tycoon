// M3b shared components: ScoreBar, SegmentTable, MarketTable, and the product display helpers.
// Static markup, as in shared.test. Example values follow docs/formulas.md 11.14.
import { MantineProvider } from '@mantine/core';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { MarketProduct, MarketSegment, ProductSegment } from '../hooks/api';
import {
  formatFlow,
  formatPercent,
  formatSignedPercent,
  lifecycleText,
  paceText,
  weightsText,
} from '../lib/products';
import { MarketTable, segmentSummary } from './MarketTable';
import { barColors, ScoreBar } from './ScoreBar';
import { SegmentTable } from './SegmentTable';

const wrap = (node: ReactNode) =>
  renderToStaticMarkup(
    <MantineProvider>
      <MemoryRouter>{node}</MemoryRouter>
    </MantineProvider>,
  );

const SMB_WEIGHTS = { quality: 0.25, price: 0.35, brand: 0.15, features: 0.25 };

function segment(over: Partial<ProductSegment> = {}): ProductSegment {
  return {
    segment: 'smb',
    label: 'SMB',
    reach: 'self_serve',
    price_cents: 4000,
    price_score: 62.5,
    customers: 2900.4,
    appeal: 43.38,
    share_of_served: 0.0242,
    churn_rate: 0.0458,
    mrr_cents: 11_601_600,
    note: null,
    new_last_month: 41.5,
    churned_last_month: 90.2,
    counts_users: false,
    ...over,
  };
}

function marketProduct(over: Partial<MarketProduct>): MarketProduct {
  return {
    product_id: 1,
    name: 'Sales Cloud',
    company_id: 2,
    company_name: 'Salesforce',
    is_player: false,
    status: 'live',
    quality: 70,
    feature_score: 80,
    brand: 80,
    price_cents: 6500,
    price_score: 38.46,
    appeal: 62.96,
    customers: 60000,
    share_of_served: 0.5,
    churn_rate: 0.0341,
    mrr_cents: 390_000_000,
    ...over,
  };
}

const SMB_MARKET: MarketSegment = {
  segment: 'smb',
  label: 'SMB',
  reach: 'self_serve',
  addressable: 400000,
  served: 100041.5,
  unserved: 299958.5,
  reference_price_cents: 5000,
  weights: SMB_WEIGHTS,
  counts_users: false,
  player_sells: true,
  products: [
    marketProduct({}),
    marketProduct({
      product_id: 3,
      name: 'Zoho CRM',
      company_name: 'Zoho',
      quality: 55,
      feature_score: 60,
      brand: 40,
      price_cents: 2500,
      price_score: 100,
      appeal: 69.75,
      customers: 40000,
      share_of_served: 0.4,
    }),
    marketProduct({
      product_id: 13,
      name: 'Pipeline',
      company_name: 'Kestrel Systems',
      is_player: true,
      quality: 40,
      feature_score: 40,
      brand: 10,
      price_cents: 4000,
      price_score: 62.5,
      appeal: 43.38,
      customers: 41.5,
      share_of_served: 0.0004,
    }),
  ],
};

describe('product display helpers', () => {
  it('formats API fractions and flows without computing them', () => {
    expect(formatPercent(0.0242)).toBe('2.4%');
    expect(formatSignedPercent(0.068)).toBe('+6.8%');
    expect(formatSignedPercent(-0.17)).toBe('−17.0%');
    expect(formatSignedPercent(0)).toBe('0.0%');
    expect(formatFlow(262.4, '+')).toBe('+262');
    expect(formatFlow(2.54, '+')).toBe('+2.5');
    expect(formatFlow(0.7, '-')).toBe('−0.7');
    expect(formatFlow(0, '+')).toBe('0');
  });

  it('labels lifecycle and pace', () => {
    expect(lifecycleText({ status: 'live', lifecycle_label: 'Growth' })).toBe('Live · growth');
    expect(lifecycleText({ status: 'live', lifecycle_label: 'Live' })).toBe('Live');
    expect(lifecycleText({ status: 'in_development', lifecycle_label: 'In development' })).toBe(
      'In development',
    );
    expect(paceText('steady', 7)).toBe('Steady');
    expect(paceText('slow', 0)).toBe('No team');
  });

  it('words the appeal weights', () => {
    expect(weightsText(SMB_WEIGHTS)).toBe('quality 25%, price 35%, brand 15% and features 25%');
  });
});

describe('ScoreBar', () => {
  it('colors the player accent and competitors in greys', () => {
    const items = [{ mine: false }, { mine: true }, { mine: false }];
    expect(barColors(items)).toEqual(['#D5DBE3', 'var(--tst-accent)', '#6B7686']);
  });

  it('draws one bar per product with its text', () => {
    const html = wrap(
      <ScoreBar
        label="Price"
        items={[
          { key: '13', name: 'Pipeline', value: 62.5, text: '$40 · 63', mine: true },
          { key: '1', name: 'Sales Cloud', value: 38.46, text: '$65 · 38', mine: false },
        ]}
      />,
    );
    expect(html).toContain('data-testid="score-price"');
    expect(html).toContain('width:62.5%');
    expect(html).toContain('>$40 · 63<');
    expect(html).toContain('aria-label="Sales Cloud: $65 · 38"');
  });

  it('clamps a bar to its track', () => {
    const html = wrap(
      <ScoreBar
        label="Brand"
        items={[{ key: 'x', name: 'X', value: 140, text: '140', mine: false }]}
      />,
    );
    expect(html).toContain('width:100%');
  });
});

describe('SegmentTable', () => {
  const price = { prices: { smb: '40' }, editing: null, onChange: () => undefined };

  it('shows last month’s numbers for a selling product', () => {
    const html = wrap(<SegmentTable segments={[segment()]} price={price} selling />);
    expect(html).toContain('>2,900<');
    expect(html).toContain('>2.4%<');
    expect(html).toContain('>+42<'); // 10 or more: whole numbers
    expect(html).toContain('>−90<');
    expect(html).toContain('>4.6%<');
    expect(html).toContain('>$116,016<');
    expect(html).toContain('aria-label="SMB price"');
    expect(html).toContain('value="40"');
  });

  it('shows the capacity note and the editing marker', () => {
    const note = 'Sales capacity limited new customers in Mid-market';
    const mid = segment({ segment: 'mid_market', label: 'Mid-market', reach: 'sales', note });
    const html = wrap(
      <SegmentTable segments={[segment(), mid]} price={{ ...price, editing: 'smb' }} selling />,
    );
    expect(html).toContain(note);
    expect(html).toContain('Editing: preview below');
    expect(html).toContain('data-selected="true"');
  });

  it('shows prices set or missing in development', () => {
    const html = wrap(
      <SegmentTable
        segments={[
          segment(),
          segment({
            segment: 'mid_market',
            label: 'Mid-market',
            reach: 'sales',
            price_cents: null,
          }),
        ]}
        price={price}
        selling={false}
      />,
    );
    expect(html).toContain('Price set');
    expect(html).toContain('Price missing');
    expect(html).toContain('Needs salespeople');
    expect(html).not.toContain('Share of buyers');
  });
});

describe('MarketTable', () => {
  it('sorts by appeal and marks the player', () => {
    const html = wrap(<MarketTable segment={SMB_MARKET} productHref={(id) => `/p/${id}`} />);
    const zoho = html.indexOf('Zoho CRM');
    const sales = html.indexOf('Sales Cloud');
    const mine = html.indexOf('Pipeline');
    expect(zoho).toBeGreaterThan(-1);
    expect(zoho).toBeLessThan(sales);
    expect(sales).toBeLessThan(mine);
    expect(html).toContain('Kestrel Systems (you)');
    expect(html).toContain('href="/p/13"');
    expect(html).toContain('data-mine="true"');
    expect(html).toContain('>69.8<');
  });

  it('summarizes the segment', () => {
    expect(segmentSummary(SMB_MARKET)).toBe(
      '400,000 businesses · 100,042 use a product, 299,959 do not yet · typical price $50',
    );
    expect(
      segmentSummary({ ...SMB_MARKET, reach: 'sales', player_sells: false, counts_users: true }),
    ).toContain('users · ');
    expect(segmentSummary({ ...SMB_MARKET, reach: 'sales', player_sells: false })).toMatch(
      /sales-led · you do not sell here$/,
    );
  });
});
