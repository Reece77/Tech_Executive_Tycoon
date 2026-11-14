// M28: World news and a chain company's page, rendered to static markup with the API's
// answers. The screens show what the API sends: links to each company, a cost band (never a
// cost position), and estimated ranges for a private company.
import { MantineProvider } from '@mantine/core';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { WorldCompany, WorldNews } from '../hooks/world';
import { WorldNewsBody } from '../screens/WorldNewsScreen';
import { WorldCompanyPanel } from './WorldCompanyPanel';

function render(node: ReactNode): string {
  return renderToStaticMarkup(
    <MantineProvider>
      <MemoryRouter>{node}</MemoryRouter>
    </MantineProvider>,
  );
}

const ALB = { company_id: 47, name: 'Albemarle' };

const NEWS: WorldNews = {
  started: true,
  items: [
    {
      news_id: 3,
      turn: 203,
      date_label: 'Dec 2026',
      kind: 'capacity',
      kind_label: 'New capacity',
      message: 'Albemarle will add 16,976 t a year of Lithium carbonate capacity',
      company: ALB,
      other: null,
      region: { key: 'north_america', label: 'North America' },
      good: { key: 'lithium_carbonate', label: 'Lithium carbonate' },
    },
  ],
  companies: [ALB],
  regions: [{ key: 'north_america', label: 'North America' }],
  goods: [{ key: 'lithium_carbonate', label: 'Lithium carbonate' }],
  kinds: [{ key: 'capacity', label: 'New capacity' }],
};

const COMPANY: WorldCompany = {
  kind: 'chain',
  country_label: 'United States',
  owner: null,
  subsidiaries: [],
  mandate: null,
  executives: [{ role: 'CEO', name: 'Kyle Lee', since_label: 'Jan 2026' }],
  facilities: [
    {
      facility_id: 8,
      good: 'lithium_carbonate',
      good_label: 'Lithium carbonate',
      country: 'us',
      country_label: 'United States',
      region: 'north_america',
      capacity_year: 202_500,
      unit: 't',
      status: 'live',
      cost_band: 'middle',
      ready_label: null,
    },
  ],
  financials: {
    listed: false,
    revenue_year_cents: null,
    ebitda_year_cents: null,
    revenue_range: { low_cents: 200_000_000_000, high_cents: 300_000_000_000 },
    ebitda_range: { low_cents: 40_000_000_000, high_cents: 60_000_000_000 },
  },
  deals: [],
  offtakes: [],
  news: NEWS.items,
};

describe('World news', () => {
  it('lists the items with links to their companies and the filters', () => {
    const html = render(
      <WorldNewsBody saveId="s" n={NEWS} params={new URLSearchParams()} onSet={() => {}} />,
    );
    expect(html).toContain('World news');
    expect(html).toContain('New capacity');
    expect(html).toContain('/game/s/competitors/47');
    expect(html).toContain('news-filter-good');
  });

  it('says when the world has not started', () => {
    const html = render(
      <WorldNewsBody
        saveId="s"
        n={{ ...NEWS, started: false, items: [] }}
        params={new URLSearchParams()}
        onSet={() => {}}
      />,
    );
    expect(html).toContain('from January 2026');
  });
});

describe('A chain company page', () => {
  it('shows its facilities, executives and estimated ranges', () => {
    const html = render(<WorldCompanyPanel saveId="s" companyId={47} w={COMPANY} />);
    expect(html).toContain('A chain company in United States');
    expect(html).toContain('CEO Kyle Lee');
    expect(html).toContain('202,500 t');
    expect(html).toContain('Middle');
    expect(html).toContain('estimated: private');
    expect(html).toContain('/game/s/competitors/world-news?company=47');
  });
});
