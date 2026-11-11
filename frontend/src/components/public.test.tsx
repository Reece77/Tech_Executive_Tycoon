// M13: the IPO panel, the pricing card, the Stock tab and the CEO seat, rendered to static
// markup with the API's answers seeded in the query cache (as the API would send them).
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import {
  keys,
  type Ceo,
  type Events,
  type GameEventOut,
  type Ipo,
  type PublicCompany,
  type Stock,
} from '../hooks/api';
import { openIpoEvent, pctText, scopeLabel } from '../lib/public';
import { StockBody, StockTab } from '../screens/finance/StockTab';
import { CeoSeat } from './CeoSeat';
import { IpoPanel } from './IpoPanel';

const SAVE = 's';

function render(node: ReactNode, p: PublicCompany, events?: Events): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(keys.public(SAVE), p);
  if (events) client.setQueryData(['saves', SAVE, 'events'], events);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

const CEO: Ceo = {
  seat_open: false,
  problem: 'A CEO can be appointed once the company is public.',
  person_id: null,
  name: null,
  since: null,
  scopes: [],
  all_scopes: ['cto', 'cro', 'cmo', 'coo', 'cfo', 'products'],
  decisions: [],
  candidates: [],
  appoint_energy: 10,
  override_energy: 6,
  chair_energy: 40,
};

const ELIGIBLE: PublicCompany = {
  stage: 3,
  eligible: true,
  problem: null,
  banks: [
    {
      key: 'goldman_sachs',
      name: 'Goldman Sachs',
      fee_pct: 7.000000000000001,
      reputation: 'a premium name: prices higher',
    },
    { key: 'morgan_stanley', name: 'Morgan Stanley', fee_pct: 6, reputation: 'a solid name' },
  ],
  hire_energy: 10,
  ipo: null,
  stock: null,
  ceo: CEO,
};

const PRICING: Ipo = {
  status: 'pricing',
  bank: 'Goldman Sachs',
  fee_pct: 7,
  hired: 'Jan 2010',
  steps: [
    { key: 'banks', label: 'Banks hired', state: 'done', detail: 'Goldman Sachs, Jan 2010' },
    { key: 'filing', label: 'S-1 filed', state: 'done', detail: 'filed on time' },
    { key: 'roadshow', label: 'Roadshow', state: 'done', detail: 'middle ambition, sell 15%' },
    { key: 'pricing', label: 'Pricing', state: 'now', detail: 'the book and the price' },
    { key: 'listing', label: 'Listing day', state: 'next', detail: 'the month after pricing' },
  ],
  ambition: 'middle',
  share_sold_pct: 15,
  dual_class: false,
  demand: 'weak',
  price_cents: 12_792,
  new_shares: 1_764_706,
  shares_after: 11_764_706,
  implied_cap_cents: 150_493_119_152,
  price_to_sales: 14.6,
  stake_pct_after: 59.499999405,
  stake_value_cents: 89_544_000_000,
  options: [
    {
      choice: 'range',
      label: 'Price at the suggestion',
      price_cents: 12_792,
      gross_cents: 22_574_119_152,
      net_cents: 20_993_930_811,
      first_day: 'likely to fall, about -11% (est.)',
      available: true,
      note: '',
    },
    {
      choice: 'raise',
      label: 'Raise 10%',
      price_cents: 14_071,
      gross_cents: 24_831_178_126,
      net_cents: 23_092_995_657,
      first_day: 'likely to fall, about -21% (est.)',
      available: false,
      note: 'only with strong demand',
    },
    {
      choice: 'cut',
      label: 'Cut 15%',
      price_cents: 10_873,
      gross_cents: 19_187_648_338,
      net_cents: 17_844_512_954,
      first_day: 'likely flat (est.)',
      available: true,
      note: '',
    },
    {
      choice: 'pull',
      label: 'Pull the IPO',
      price_cents: 0,
      gross_cents: 0,
      net_cents: -474_056_502,
      first_day: 'no listing; board confidence falls',
      available: true,
      note: 'fees of $4,740,565 are owed',
    },
  ],
  listed: null,
  first_day_pct: null,
  pulled: null,
};

const PRICING_EVENT: GameEventOut = {
  event_id: 6,
  turn: 4,
  date_label: 'May 2010',
  category: 'public',
  category_label: 'Public company',
  severity: 'critical',
  status: 'open',
  title: 'Pricing night: the book is weak',
  body: 'The book is weak.',
  choices: [
    { key: 'A', label: 'Price at $127.92 as suggested', effects: [], do_nothing: false },
    { key: 'B', label: 'Cut the price 15% to clear the book', effects: [], do_nothing: false },
    { key: 'C', label: 'Pull the IPO', effects: [], do_nothing: false },
  ],
  chosen: null,
  written_by: 'template',
  storyline: null,
  follow_up_note: null,
  person_ids: [],
  links: [],
};

const EVENTS: Events = {
  to_answer: 1,
  blocking_event_id: 6,
  blocking_event_ids: [6],
  blocking_proposal_ids: [],
  open: [PRICING_EVENT],
  recent: [],
  ai_spend_cents: 0,
  ai_budget_cents: 0,
};

const STOCK: Stock = {
  ticker: 'KEST',
  price_cents: 7_947,
  change_pct: -10.9,
  market_cap_cents: 93_494_118_582,
  shares: 11_764_706,
  listing_price_cents: 11_630,
  listed: 'May 2010',
  dual_class: false,
  stake_shares: 7_000_000,
  stake_pct: 59.5,
  stake_value_cents: 55_629_000_000,
  history: [
    { turn: 4, label: 'May 2010', price_cents: 9_996, market_cap_cents: 1, mark: 'listing' },
    { turn: 7, label: 'Aug 2010', price_cents: 8_916, market_cap_cents: 1, mark: '' },
    { turn: 8, label: 'Sep 2010', price_cents: 7_947, market_cap_cents: 1, mark: 'miss' },
  ],
  analysts: [
    { firm: 'Goldman Sachs Research', rating: 'hold', target_cents: 8_667 },
    { firm: 'J.P. Morgan Research', rating: 'buy', target_cents: 12_600 },
  ],
  buys: 1,
  holds: 1,
  sells: 0,
  average_target_cents: 10_634,
  guidance: [
    {
      quarter: 'Q3 2010',
      by_player: true,
      revenue_cents: 3_055_137_332,
      margin_pct: 50.19,
      actual_revenue_cents: 2_240_031_054,
      actual_margin_pct: 91.42,
      result: 'miss',
      price_before_cents: 8_916,
      price_after_cents: 7_947,
    },
  ],
  next_guidance: {
    quarter: 'Q4 2010',
    can_set: true,
    problem: null,
    consensus_revenue_cents: 2_444_109_866,
    consensus_margin_pct: 50.19,
    set_revenue_cents: null,
    set_margin_pct: null,
    band_pct: 50,
    energy: 4,
    hint: 'Guiding above the consensus makes a miss likelier.',
  },
  capital: {
    buyback_price_cents: 8_106,
    buyback_max_shares: 1_176_470,
    buyback_energy: 6,
    dividend_declared_cents: 0,
    dividend_energy: 4,
    shares_outstanding: 10_764_706,
    secondary_price_cents: 7_550,
    secondary_max_shares: 2_352_941,
    secondary_fee_pct: 3,
    secondary_energy: 10,
  },
  board_line: "Directors' patience follows the analysts' consensus.",
  drivers: [
    { label: 'Revenue growth', effect: 'weighs on', detail: '+7% over the year' },
    { label: 'Last earnings', effect: 'weighs on', detail: 'last quarter: miss' },
  ],
};

describe('public display helpers', () => {
  it('formats percentages and scope labels, and finds the open IPO event', () => {
    expect(pctText(7.000000000000001)).toBe('7%');
    expect(pctText(59.499999405)).toBe('59.5%');
    expect(scopeLabel('cto')).toBe('CTO');
    expect(scopeLabel('products')).toBe('Products');
    expect(openIpoEvent([{ ...PRICING_EVENT, category: 'market' }])).toBeUndefined();
    expect(openIpoEvent([PRICING_EVENT])?.event_id).toBe(6);
  });
});

describe('IPO panel (M13)', () => {
  it('offers the banks with fee and reputation, and Hire banks with its energy', () => {
    const html = render(<IpoPanel saveId={SAVE} />, ELIGIBLE);
    expect(html).toContain('data-testid="ipo-panel"');
    expect(html).toContain('data-testid="bank-option-goldman_sachs"');
    expect(html).toContain('fee 7%');
    expect(html).toContain('a premium name: prices higher');
    expect(html).toContain('Hire banks · 10 energy');
    expect(html).toContain('Eligible');
  });

  it('shows why a company cannot go public, with Hire banks disabled', () => {
    const html = render(<IpoPanel saveId={SAVE} />, {
      ...ELIGIBLE,
      eligible: false,
      problem: 'ARR must reach $100M',
    });
    expect(html).toContain('Not yet: ARR must reach $100M.');
    expect(html).toMatch(/<button[^>]*disabled[^>]*data-testid="hire-banks"/);
  });

  it('is hidden before the scale-up stage', () => {
    const html = render(<IpoPanel saveId={SAVE} />, { ...ELIGIBLE, stage: 2 });
    expect(html).not.toContain('ipo-panel');
  });

  it('at pricing: the progress strip, the book in words, the offering and the pricing card', () => {
    const html = render(
      <IpoPanel saveId={SAVE} />,
      { ...ELIGIBLE, eligible: false, ipo: PRICING },
      EVENTS,
    );
    expect(html).toMatch(/data-testid="ipo-step-pricing" data-state="now"/);
    expect(html).toContain('data-status="pricing"');
    expect(html).toContain('<strong>weak</strong>');
    expect(html).toContain('data-testid="pricing-card"');
    expect(html).toContain('$127.92');
    expect(html).toContain('raises $225.7M ($209.9M after fees)');
    expect(html).toContain('likely to fall, about -11% (est.)');
    expect(html).toMatch(/data-testid="price-option-raise" data-available="false"/);
    expect(html).toContain('costs $4,740,565');
    // the available options answer the pricing event's choices in order
    expect(html).toContain('price-choose-range');
    expect(html).toContain('price-choose-cut');
    expect(html).toContain('price-choose-pull');
    expect(html).not.toContain('price-choose-raise');
    // the offering
    expect(html).toContain('1,764,706 (15%)');
    expect(html).toContain('11,764,706');
    expect(html).toContain('$1.5B');
    expect(html).toContain('14.6× ARR');
    expect(html).toContain('59.5% · $895.4M');
    expect(html).not.toContain('hire-banks');
  });
});

describe('Stock tab (M13)', () => {
  it('says the company is not listed before the IPO', () => {
    const html = render(<StockTab saveId={SAVE} />, ELIGIBLE);
    expect(html).toContain('data-testid="not-listed"');
  });

  it('shows the price, the chart marks, guidance against results and the miss', () => {
    const html = render(<StockBody saveId={SAVE} stock={STOCK} />, ELIGIBLE);
    expect(html).toContain('>KEST<');
    expect(html).toMatch(/data-testid="stock-price">\$79\.47</);
    expect(html).toContain('−10.9% this month');
    expect(html).toContain('$934.9M');
    expect(html).toContain('at $116.30 (May 2010)');
    expect(html).toContain('59.5% · 7,000,000 shares · $556.3M');
    expect(html).toContain('miss in Sep 2010');
    expect(html).toContain('data-testid="guidance-row"');
    expect(html).toMatch(/data-testid="guidance-result" data-result="miss"/);
    expect(html).toContain('$89.16 → $79.47');
    expect(html).toContain('50.2% / 91.4%');
  });

  it('shows next quarter guidance, analysts, capital actions, the board and the drivers', () => {
    const html = render(<StockBody saveId={SAVE} stock={STOCK} />, ELIGIBLE);
    expect(html).toContain('Set Q4 2010 guidance');
    expect(html).toContain('$24.4M');
    expect(html).toContain('Set guidance · 4 energy');
    expect(html).toContain('Guiding above the consensus makes a miss likelier.');
    expect(html).toContain('data-testid="analysts-panel"');
    expect(html).toContain('Average target');
    expect(html).toContain('$106.34');
    expect(html).toContain('Buy back · 6 energy');
    expect(html).toContain('Declare · 4 energy');
    expect(html).toContain('Sell shares · 10 energy');
    expect(html).toContain('up to 2,352,941; fee 3%');
    expect(html).toContain('Directors&#x27; patience follows');
    expect(html).toContain('data-testid="price-drivers"');
    expect(html).toContain('last quarter: miss');
    expect(html).toContain('weighs on');
  });
});

describe('CEO seat (M13)', () => {
  it('is you until the IPO', () => {
    const html = render(<CeoSeat saveId={SAVE} authorityEnergy={2} />, ELIGIBLE);
    expect(html).toContain('data-testid="ceo-seat"');
    expect(html).toContain('(until the IPO)');
    expect(html).not.toContain('ceo-appoint');
  });

  it('offers candidates and Appoint CEO with its energy once public', () => {
    const html = render(<CeoSeat saveId={SAVE} authorityEnergy={2} />, {
      ...ELIGIBLE,
      stage: 4,
      ceo: {
        ...CEO,
        seat_open: true,
        problem: null,
        candidates: [
          { person_id: 3, name: 'Olivia Davis', role: 'Product manager', level: 'principal' },
        ],
      },
    });
    expect(html).toContain('data-testid="ceo-candidate-3"');
    expect(html).toContain('Olivia Davis');
    expect(html).toContain('Appoint CEO · 10 energy');
    expect(html).not.toContain('(until the IPO)');
  });

  it('with a CEO: you are Chair, the scopes, decisions with Override, and Dismiss', () => {
    const html = render(<CeoSeat saveId={SAVE} authorityEnergy={2} />, {
      ...ELIGIBLE,
      stage: 4,
      ceo: {
        ...CEO,
        seat_open: true,
        problem: null,
        person_id: 3,
        name: 'Olivia Davis',
        since: 'Jul 2010',
        scopes: ['cto', 'cro'],
        decisions: [
          {
            id: 5,
            turn: 7,
            label: 'Aug 2010',
            scope: 'cro',
            text: "raised Pipeline's Mid-market price to $550",
            mistake: false,
            can_override: true,
            overridden: false,
          },
          {
            id: 4,
            turn: 6,
            label: 'Jul 2010',
            scope: 'cmo',
            text: "set Pipeline's marketing to $1,174,246 a month",
            mistake: true,
            can_override: false,
            overridden: true,
          },
        ],
      },
    });
    expect(html).toContain('data-testid="ceo-name"');
    expect(html).toContain('since Jul 2010');
    expect(html).toContain('(energy 40 a month)');
    expect(html).toContain('each change 2 energy');
    expect(html).toContain('ceo-scope-products');
    expect(html).toContain('Aug 2010 · CRO: raised Pipeline&#x27;s Mid-market price to $550');
    expect(html).toContain('Override · 6');
    expect(html.match(/data-testid="ceo-override"/g)).toHaveLength(1);
    expect(html).toContain('data-testid="ceo-overridden"');
    expect(html).toContain('misstep');
    expect(html).toContain('Dismiss · 10');
  });
});
