// M36: the Family screen and the founder profile's Family tab, rendered to static markup with
// the API's answers. A child's potential reaches the front end only as a phrase.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { familyKeys, type Family, type FamilyMember } from '../hooks/family';
import { FamilyBody } from '../screens/FamilyScreen';
import { FamilyTab } from './FamilyTab';

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

function member(over: Partial<FamilyMember>): FamilyMember {
  return {
    person_id: 10,
    name: 'Ada Wilson',
    relation: 'child',
    age: 30,
    closeness: 72.4,
    school: 'elite',
    university: 'top',
    degree: 'engineering',
    mba: false,
    company_id: 1,
    company_name: 'Kestrel',
    role: 'software_engineer',
    level: 'senior',
    mentored: true,
    own_way: null,
    interests: ['ai'],
    skills: [
      {
        key: 'software_engineering',
        label: 'Software engineering',
        short_label: 'SWE',
        group: 'technical',
        range: { min: 12, max: 15 },
      },
      {
        key: 'leadership',
        label: 'Leadership',
        short_label: 'LEAD',
        group: 'management',
        range: { min: 9, max: 13 },
      },
    ],
    personality: [],
    potential: 'Could become very good',
    readiness: { band: 'ready', points: 7.5, fit: 13.2, years: 6, seats: 2, board: 1.5 },
    choices: [],
    can_join: false,
    ...over,
  };
}

const ADA = member({});
const BEN = member({
  person_id: 11,
  name: 'Ben Wilson',
  age: 18,
  closeness: 55,
  school: 'standard',
  university: null,
  degree: null,
  company_id: null,
  company_name: null,
  role: null,
  level: null,
  mentored: false,
  readiness: null,
  choices: [
    { stage: 'university', tier: 'standard', cost_cents: 12_000_000 },
    { stage: 'university', tier: 'top', cost_cents: 30_000_000 },
  ],
});

const FAMILY: Family = {
  exists: true,
  setting: 'children',
  head_id: 1,
  head_name: 'Laura Wilson',
  head_mode: 'founder',
  family_time: 10,
  max_time: 20,
  time_now: 10,
  energy_cost: 13,
  relationship: 68.6,
  married: true,
  partner: member({
    person_id: 9,
    name: 'Sam Wilson',
    relation: 'partner',
    age: 60,
    closeness: null,
    readiness: null,
    company_id: null,
    company_name: null,
    skills: [],
  }),
  children: [ADA, BEN],
  others: [member({ person_id: 12, name: 'Tom Wilson', relation: 'sibling', age: 58 })],
  heirs: [10],
  succession_open: 'health',
  step_back_open: false,
  adviser: {
    person_id: 2,
    name: 'Old Wilson',
    age: 77,
    retires_at: 80,
    opinions: [
      {
        turn: 300,
        date_label: 'Jan 2035',
        subject: 'proposal',
        subject_id: 4,
        title: 'Open a Tokyo office',
        stance: 'oppose',
        text: 'We never needed Tokyo.',
        overruled: false,
      },
    ],
  },
  estate: {
    region: 'north_america',
    rate: 0.4,
    exemption_cents: 1_361_000_000,
    used_exemption_cents: 0,
    shares: 4_000_000,
    share_price_cents: 200_000,
    shares_cents: 800_000_000_000,
    cash_cents: 10_000_000_000,
    other_cents: 0,
    estate_cents: 810_000_000_000,
    taxable_cents: 808_639_000_000,
    tax_cents: 323_455_600_000,
    shares_to_sell: 1_567_278,
    family_bp_now: 5_500,
    family_bp_after: 3_345,
    control_bp: 5_000,
    trust_shares: 0,
    gift_tax: true,
    lifetime_gifts_cents: 0,
    gift_tax_paid_cents: 0,
    estate_tax_paid_cents: 0,
  },
  dynasty: {
    generations: [
      {
        person_id: 1,
        name: 'Laura Wilson',
        from_label: 'Jan 2010',
        to_label: null,
        legacy: 410,
        how: null,
      },
    ],
    legacies: 410,
    family_value_cents: 800_000_000_000,
    value_points: 95,
    control_losses: 0,
    loss_points: 0,
    total: 505,
  },
  notes: [{ turn: 12, date_label: 'Jan 2011', kind: 'milestone', text: 'Ben turned 5.' }],
  trust_since: null,
};

const NONE: Family = {
  ...FAMILY,
  exists: false,
  setting: 'none',
  head_id: null,
  head_name: null,
  partner: null,
  relationship: null,
  children: [],
  others: [],
  heirs: [],
  succession_open: null,
  adviser: null,
  estate: null,
  dynasty: null,
  notes: [],
};

describe('family screen', () => {
  it('shows family time, the partner, children with ranges and readiness', () => {
    const html = render(<FamilyBody saveId={SAVE} family={FAMILY} />);
    expect(html).toContain('data-testid="family-screen"');
    expect(html).toMatch(/data-testid="family-time"[^>]*>10</);
    expect(html).toContain('data-testid="family-time-input"');
    expect(html).toContain('data-testid="family-time-save"');
    expect(html).toMatch(/data-testid="family-relationship"[^>]*>69</);
    expect(html.match(/data-testid="family-member"/g)).toHaveLength(2);
    expect(html).toContain('data-person-id="10"');
    expect(html).toMatch(/data-testid="member-skill-range"[^>]*>12-15</);
    expect(html).toMatch(/data-testid="readiness-band"[^>]*>Ready</);
    expect(html).toContain('explain-heir_readiness-10');
    expect(html).toContain('Could become very good');
    expect(html).toContain('Laura Wilson');
  });

  it('offers education, mentoring, the adviser and the dynasty', () => {
    const html = render(<FamilyBody saveId={SAVE} family={FAMILY} />);
    expect(html.match(/data-testid="educate-choice"/g)).toHaveLength(2);
    expect(html).toContain('data-stage="university"');
    expect(html).toContain('data-tier="top"');
    expect(html).toContain('$300,000');
    expect(html).toContain('data-testid="educate-degree"');
    expect(html.match(/data-testid="mentor-toggle"/g)).toHaveLength(1);
    expect(html).toContain('data-testid="adviser-panel"');
    expect(html).toContain('We never needed Tokyo.');
    expect(html).toMatch(/data-testid="dynasty-total"[^>]*>.*505/);
    expect(html).toContain('Ben turned 5.');
    expect(html).toContain('Tom Wilson');
  });

  it('says so when there is no family', () => {
    const html = render(<FamilyBody saveId={SAVE} family={NONE} />);
    expect(html).toContain('No family in this game (Family was set to none).');
    expect(html).not.toContain('family-member');
  });

  it('never shows a number for potential', () => {
    const html = render(<FamilyBody saveId={SAVE} family={FAMILY} />);
    expect(html).not.toMatch(/potential[^<]*\d/i);
  });
});

describe('founder family tab', () => {
  const seed = (f: Family) => (c: QueryClient) => c.setQueryData(familyKeys.family(SAVE), f);

  it('shows succession with the heirs and the open choice', () => {
    const html = render(<FamilyTab saveId={SAVE} />, seed(FAMILY));
    expect(html).toContain('data-testid="founder-family-tab"');
    expect(html).toContain('/game/s/people/family');
    expect(html).toContain('data-testid="succession-heir-select"');
    expect(html).toContain('Ada Wilson');
    expect(html).toContain('data-testid="succession-hand-over"');
    expect(html).toContain('data-testid="succession-ceo"');
    expect(html).toContain('data-testid="succession-open"');
  });

  it('shows the estate quote, planning forms and totals', () => {
    const html = render(<FamilyTab saveId={SAVE} />, seed(FAMILY));
    expect(html).toContain('data-testid="estate-quote"');
    expect(html).toContain('explain-estate_tax');
    expect(html).toContain('40%');
    expect(html).toContain('$3,234,556,000');
    expect(html).toContain('55.00% → 33.45%');
    expect(html).toContain('50.00%');
    expect(html).toContain('lose control');
    expect(html).toContain('data-testid="gift-shares"');
    expect(html).toContain('data-testid="fund-trust"');
    expect(html).toContain('data-testid="foundation-shares"');
    expect(html).toContain('none yet');
  });

  it('shows only a message without a family', () => {
    const html = render(<FamilyTab saveId={SAVE} />, seed(NONE));
    expect(html).toContain('No family in this game');
    expect(html).not.toContain('estate-quote');
  });
});
