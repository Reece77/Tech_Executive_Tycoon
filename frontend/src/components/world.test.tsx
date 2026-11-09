// M22: the World screen and a product's export-controls panel, rendered to static markup with
// the API's answers. Only announced rules arrive; the screen shows what the API sends.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { World } from '../hooks/geopolitics';
import { WorldBody } from '../screens/WorldScreen';
import { ExportPanel } from './ExportPanel';

const SAVE = 's';

function render(node: ReactNode, data: World): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(['saves', SAVE, 'world'], data);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

const RULE: World['rules'][number] = {
  key: 'us_oct_2022',
  title: 'US advanced computing and semiconductor rules',
  actor: 'us',
  actor_label: 'United States',
  goods: ['Advanced AI chips'],
  destinations: ['China'],
  regime: 'licence',
  approval: 0.25,
  quota: null,
  threshold: 60,
  status: 'in_force',
  month: 'Oct 2022',
  announced: 'Oct 2022',
  end: null,
  suspended_until: null,
  effect: 'applies',
  tag: 'V',
  source: 'dossier 5',
  seeded: false,
};

const WORLD: World = {
  turn: 153,
  tension: 75,
  tension_history: [
    { turn: 152, label: 'Sep 2022', value: 68, shock: 'none' },
    { turn: 153, label: 'Oct 2022', value: 75, shock: 'none' },
  ],
  countries: [],
  rules: [RULE],
  licences: [],
  variants: [],
  listings: [],
  products: [
    {
      product_id: 7,
      product: 'Accel',
      company_id: 1,
      regions: [{ region: 'east_asia', blocked: 0.55, variant: 0 }],
      licensable: ['china'],
      restricted: ['china'],
      variant_possible: true,
      has_variant: false,
      tariff_cents: 0,
    },
  ],
  supply: [],
  sites: [],
  tariffs: [],
};

describe('World', () => {
  it('shows the rules in force, the tension and the exposure', () => {
    const html = render(<WorldBody saveId={SAVE} w={WORLD} />, WORLD);
    expect(html).toContain('US advanced computing and semiconductor rules');
    expect(html).toContain('US-China tension 75/100');
    expect(html).toContain('east_asia: 55% closed');
    expect(html).toContain('Request licence (china)');
    expect(html).toContain('Launch compliant variant');
    expect(html).toContain('licence (25% base)');
  });

  it('says so when nothing touches the group', () => {
    const quiet = { ...WORLD, products: [], rules: [] };
    const html = render(<WorldBody saveId={SAVE} w={quiet} />, quiet);
    expect(html).toContain('No export control touches the group.');
  });

  it('shows a product its controls, and nothing for an untouched product', () => {
    expect(render(<ExportPanel saveId={SAVE} productId={7} />, WORLD)).toContain('Export controls');
    expect(render(<ExportPanel saveId={SAVE} productId={8} />, WORLD)).not.toContain(
      'Export controls',
    );
  });
});
