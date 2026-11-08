// M24: the top bar's stress meter, the founder's tabs and the legacy panel, rendered to static
// markup with the API's answers. The scandal risk never reaches the front end: only a word.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { founderKeys, type Founder } from '../hooks/founder';
import { FounderPanels, LegacyPanel } from './FounderPanels';
import { StressMeter } from './TopBar';

const SAVE = 's';

function render(node: ReactNode, seed?: (client: QueryClient) => void): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  seed?.(client);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

const STRESS: Founder['stress'] = {
  stress: 84,
  burnout: true,
  burnout_at: 80,
  recover_below: 40,
  energy_cut_pct: 30,
  burnouts: 1,
  causes: [{ turn: 3, date_label: 'Apr 2010', change: 16, cause: 'spent 100% of your energy' }],
};

const FOUNDER: Founder = {
  founder_name: 'Laura Wilson',
  stress: STRESS,
  persona: {
    traits: [
      { key: 'visionary', label: 'Visionary', value: 64, strong: true, effects: 'builders' },
      { key: 'ruthless', label: 'Ruthless', value: 20, strong: false, effects: '' },
      { key: 'beloved', label: 'Beloved', value: 26, strong: false, effects: '' },
      { key: 'reckless', label: 'Reckless', value: 20, strong: false, effects: '' },
    ],
    top: 'visionary',
    effect_at: 60,
    causes: [],
  },
  personal: {
    cash_cents: 250_000_000,
    endowment_cents: 0,
    income: { secondary: 250_000_000, dividend: 0, exit: 0, salary: 0 },
    gifts_cents: 0,
    grants_cents: 0,
    stake_shares: 900_000,
    stake_value_cents: 9_000_000_000,
    can_sell: true,
    entries: [],
  },
  foundation: null,
  foundation_form: {
    can_create: true,
    min_cents: 100_000_000,
    energy: 5,
    causes: ['education', 'climate', 'health', 'local'],
  },
  government: {
    regions: [
      {
        region: 'north_america',
        region_label: 'North America',
        influence: 13.2,
        monthly_cents: 50_000_000,
        spent_cents: 100_000_000,
        exposure: 'medium',
        antitrust_cut_pct: 5.3,
        scandals: 0,
      },
    ],
    scandals: [],
    energy: 5,
    max_monthly_cents: 1_000_000_000,
    region_options: [{ key: 'north_america', label: 'North America' }],
  },
  legacy: {
    total: 512,
    best_score: 420,
    best_company: 'Kestrel',
    giving: 30.1,
    persona: 62,
    grants_cents: 1_000_000_000,
  },
};

describe('founder', () => {
  it('shows stress and burnout on the top bar', () => {
    const html = render(<StressMeter stress={STRESS} />);
    expect(html).toContain('data-testid="stress"');
    expect(html).toContain('>84<');
    expect(html).toContain('burnout-flag');
    expect(html).toContain('spent 100% of your energy');
  });

  it("opens on the Personal tab with the founder's own cash and a sell form", () => {
    const html = render(<FounderPanels saveId={SAVE} />, (c) =>
      c.setQueryData(founderKeys.founder(SAVE), FOUNDER),
    );
    expect(html).toContain('founder-tabs');
    expect(html).toContain('Government affairs');
    expect(html).toContain('$2,500,000');
    expect(html).toContain('sell-shares');
    expect(html).not.toContain('risk');
  });

  it('shows the legacy with its parts', () => {
    const html = render(<LegacyPanel legacy={FOUNDER.legacy} />);
    expect(html).toContain('data-testid="legacy"');
    expect(html).toContain('512');
    expect(html).toContain('Kestrel');
    expect(render(<LegacyPanel legacy={null} />)).not.toContain('legacy-panel');
  });
});
