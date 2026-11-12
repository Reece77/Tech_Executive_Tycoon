// M26: the Investments tab and the Rival page's own-money panel, rendered to static markup
// with the API's answers. A trade's regulatory risk never reaches the front end: only a
// "sensitive window" flag; the family office's manager shows as a revealed range.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { investingKeys, type Investments } from '../hooks/investing';
import { InvestmentsTab, PersonalInvestPanel } from './InvestmentsTab';

const SAVE = 's';

function render(node: ReactNode, data: Investments): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(investingKeys.investments(SAVE), data);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

const INV: Investments = {
  personal_cash_cents: 5_000_000_00,
  net_worth: {
    total_cents: 9_000_000_00,
    cash_cents: 5_000_000_00,
    angel_cents: 1_000_000_00,
    public_cents: 500_000_00,
    family_office_cents: 0,
    own_stake_cents: 2_500_000_00,
  },
  history: [
    { turn: 1, date_label: 'Feb 2010', total_cents: 8_000_000_00, own_stake_cents: 2_000_000_00 },
    { turn: 2, date_label: 'Mar 2010', total_cents: 9_000_000_00, own_stake_cents: 2_500_000_00 },
  ],
  stakes: [
    {
      id: 1,
      company_id: 41,
      company: 'Northwind',
      category_label: 'Fintech',
      status: 'open',
      stake_pct: 4.76,
      cost_cents: 500_000_00,
      worth_cents: 1_000_000_00,
      estimate_low_cents: 1_200_000_00,
      estimate_high_cents: 1_800_000_00,
      proceeds_cents: 0,
      backed: false,
      founder_known: false,
      since_label: 'Feb 2010',
      closed_label: null,
      cash_band: 'tight',
      funding: [
        {
          date_label: 'Jan 2010',
          raised_cents: 2_000_000_00,
          post_cents: 10_000_000_00,
          source: 'founded',
        },
      ],
      conflict: null,
    },
  ],
  open_rounds: [
    {
      company_id: 41,
      company: 'Northwind',
      category_label: 'Fintech',
      date_label: 'Feb 2010',
      raised_cents: 2_000_000_00,
      post_cents: 10_500_000_00,
      max_cents: 2_000_000_00,
      held_pct: 4.76,
    },
  ],
  network: [
    {
      person_id: 7,
      name: 'Ada Byron',
      role_label: 'Software engineer',
      source: 'former',
      known: true,
    },
  ],
  categories: [{ key: 'fintech', label: 'Fintech' }],
  holdings: [
    {
      company_id: 30,
      company: 'Dell',
      shares: 1000,
      price_cents: 500,
      worth_cents: 500_000,
      cost_cents: 450_000,
      own: false,
    },
  ],
  listed: [
    {
      company_id: 30,
      company: 'Dell',
      price_cents: 500,
      own: false,
      window_open: true,
      sensitive: true,
    },
  ],
  trades: [
    {
      id: 1,
      date_label: 'Mar 2010',
      company_id: 30,
      company: 'Dell',
      side: 'buy',
      shares: 1000,
      price_cents: 450,
      filed: false,
      sensitive: true,
      investigation: 'open',
    },
  ],
  family_office: null,
  family_office_form: {
    can_form: false,
    min_cents: 50_000_000_00,
    wealth_cents: 6_500_000_00,
    energy: 5,
    move_energy: 1,
    mandates: ['conservative', 'balanced', 'aggressive'],
  },
  index: [{ turn: 1, date_label: 'Feb 2010', level: 1.01 }],
  rules: {
    join_energy: 3,
    back_energy: 8,
    trade_energy: 1,
    round_min_cents: 10_000_00,
    min_cheque_cents: 250_000_00,
    seed_stake_low_pct: 20,
    seed_stake_high_pct: 40,
    seed_full_cents: 3_000_000_00,
    trade_cost_pct: 0.1,
  },
};

describe('InvestmentsTab', () => {
  it('shows net worth, stakes, open rounds, the network, holdings and trades', () => {
    const html = render(<InvestmentsTab saveId={SAVE} />, INV);
    expect(html).toContain('$9,000,000');
    expect(html).toContain('Northwind');
    expect(html).toContain('4.76%');
    expect(html).toContain('$1,200,000–$1,800,000 (est.)'); // M23c: the estimate beside the mark
    expect(html).toContain('round-invest-41');
    expect(html).toContain('Ada Byron, Software engineer (known)');
    expect(html).toContain('sensitive window');
    expect(html).toContain('under investigation');
    expect(html).toContain('Form a family office');
    expect(html.toLowerCase()).not.toContain('risk');
  });

  it('shows a formed family office with the revealed range only', () => {
    const html = render(<InvestmentsTab saveId={SAVE} />, {
      ...INV,
      family_office: {
        formed_label: 'Mar 2010',
        mandate: 'balanced',
        balance_cents: 1_000_000_00,
        manager_id: 9,
        manager_name: 'Grace Hopper',
        manager_skill_low: 11,
        manager_skill_high: 15,
        returns: [],
        trailing_year_pct: null,
        index_year_pct: null,
      },
    });
    expect(html).toContain('Grace Hopper');
    expect(html).toContain('finance 11–15');
  });
});

describe('PersonalInvestPanel', () => {
  it('offers Invest on a startup with an open round and Buy shares on a listed company', () => {
    expect(render(<PersonalInvestPanel saveId={SAVE} companyId={41} />, INV)).toContain('Invest');
    const listed = render(<PersonalInvestPanel saveId={SAVE} companyId={30} />, INV);
    expect(listed).toContain('Buy shares');
    expect(listed).toContain('sensitive window');
    expect(render(<PersonalInvestPanel saveId={SAVE} companyId={99} />, INV)).not.toContain(
      'personal-invest',
    );
  });
});
