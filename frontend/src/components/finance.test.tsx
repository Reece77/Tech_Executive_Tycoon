// M4b shared finance components, rendered to static markup with API-shaped fixtures. The
// numbers follow docs/formulas.md 14.10 (Kestrel's SAFE, seed and Series A).
import { MantineProvider } from '@mantine/core';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { CapTable as CapTableData, RoundPreview, StatementPeriod } from '../hooks/api';
import {
  capRowId,
  confidenceColor,
  formatFraction,
  formatPointChange,
  formatShares,
  formatThousands,
  pnlLines,
  seatsText,
  sparkPoints,
} from '../lib/finance';
import { financeTab, kindLabel, kindsFor } from '../lib/inbox';
import { CapTable } from './CapTable';
import { KindBadge } from './KindBadge';
import { BoardMemberCard } from './BoardMemberCard';
import { DilutionPreview } from './DilutionPreview';
import { StatementTable } from './StatementTable';

const line = (account: string, label: string, amount_cents: number) => ({
  account,
  label,
  amount_cents,
});

function period(label: string, turn: number, revenue: number, net: number): StatementPeriod {
  const hosting = 1_800_000;
  const salaries = 17_500_000;
  const opex = salaries;
  return {
    label,
    first_turn: turn,
    last_turn: turn,
    complete: true,
    profit_and_loss: {
      revenue: [line('4000_subscriptions', 'Subscriptions', revenue)],
      total_revenue_cents: revenue,
      cost_of_revenue: [line('6300_compute', 'Hosting', hosting)],
      total_cost_of_revenue_cents: hosting,
      gross_margin_cents: revenue - hosting,
      operating_expenses: [line('6000_salaries', 'Salaries', salaries)],
      total_operating_expenses_cents: opex,
      operating_result_cents: net,
      interest_cents: 0,
      tax_cents: 0,
      net_result_cents: net,
    },
    cash_flow: {
      operating_cents: net,
      investing_cents: 0,
      financing_cents: 0,
      change_in_cash_cents: net,
      burn_cents: Math.max(0, -net),
    },
    balance_sheet: {
      assets: [line('1000_cash', 'Cash', 412_000_000)],
      total_assets_cents: 412_000_000,
      liabilities: [],
      total_liabilities_cents: 0,
      paid_in_equity: [],
      accumulated_result_cents: 0,
      total_liabilities_and_equity_cents: 412_000_000,
    },
  };
}

const wrap = (node: ReactNode) => renderToStaticMarkup(<MantineProvider>{node}</MantineProvider>);

describe('finance formatting', () => {
  it.each([
    [-6_050_000, '−60.5'],
    [20_000_000, '200.0'],
    [0, '0.0'],
    [-4_000, '0.0'], // rounds to zero: no minus sign
    [412_000_000, '4,120.0'],
  ])('%i cents in $k is %s', (cents, text) => {
    expect(formatThousands(cents)).toBe(text);
  });

  it('formats shares, fractions and point changes', () => {
    expect(formatShares(22_633_308)).toBe('22,633,308');
    expect(formatFraction(0.39764)).toBe('39.76%');
    expect(formatPointChange(0.5505, 0.3976)).toBe('−15.29');
    expect(formatPointChange(0.0511, 0.1)).toBe('+4.89');
    expect(formatPointChange(0, 0.2146, true)).toBe('new');
  });

  it('colours confidence by band and lists seats', () => {
    expect(confidenceColor(22)).toBe('var(--tst-warn)');
    expect(confidenceColor(30)).toBe('var(--tst-tier-4)');
    expect(confidenceColor(62)).toBe('var(--tst-accent)');
    expect(seatsText({ common: 2, investor: 2, independent: 0 })).toBe('2 common · 2 investor');
    expect(sparkPoints([70, 58]).split(' ')).toHaveLength(2);
  });
});

describe('StatementTable', () => {
  const periods = [
    period('Feb 2013', 37, 25_200_000, -5_140_000),
    period('Mar 2013', 38, 26_800_000, -4_800_000),
  ];

  it('builds the P&L lines with costs negative and totals marked', () => {
    const lines = pnlLines(periods);
    expect(lines.map((l) => l.id)).toEqual([
      'revenue',
      '6300_compute',
      'gross',
      '6000_salaries',
      'opex',
      'net',
    ]);
    expect(lines.find((l) => l.id === 'opex')?.values).toEqual([-17_500_000, -17_500_000]);
    expect(lines.filter((l) => l.total).map((l) => l.id)).toEqual(['gross', 'opex', 'net']);
  });

  it('shows a disposal below the operating result (M16)', () => {
    const withLoss = periods.map((p, i) => ({
      ...p,
      profit_and_loss: {
        ...p.profit_and_loss,
        other_gains:
          i === 1 ? [line('4930_gain_on_disposal', 'Gain or loss on disposal', -900)] : [],
      },
    }));
    const lines = pnlLines(withLoss);
    expect(lines.map((l) => l.id).slice(-2)).toEqual(['4930_gain_on_disposal', 'net']);
    expect(lines.find((l) => l.id === '4930_gain_on_disposal')?.values).toEqual([0, -900]);
  });

  it('renders periods side by side with negatives in orange', () => {
    const html = renderToStaticMarkup(<StatementTable periods={periods} />);
    expect(html).toContain('Feb 2013');
    expect(html).toContain('Mar 2013');
    expect(html).toContain('Hosting (cost of revenue)');
    expect(html).toContain('−48.0'); // March's net result
    expect(html).toContain('var(--tst-warn)');
    expect(html).toContain('tst-subtotal');
  });
});

const KESTREL_CAP: CapTableData = {
  fd_shares: 22_633_308,
  share_price_dollars: '1.02950',
  holders: [
    { holder: 'Jordan Hale', holder_kind: 'person', share_class: 'common', shares: 9_000_000, fraction: 0.3976, is_founder: true, person_id: 1, firm: null },
    { holder: 'Andreessen Horowitz', holder_kind: 'firm', share_class: 'preferred_a', shares: 4_856_933, fraction: 0.2146, is_founder: false, person_id: null, firm: 'a16z' },
    { holder: 'Option pool (unallocated)', holder_kind: 'pool', share_class: 'option_pool', shares: 2_263_331, fraction: 0.1, is_founder: false, person_id: null, firm: null },
    { holder: 'Employee options', holder_kind: 'options', share_class: 'option_pool', shares: 1_200_000, fraction: 0.053, is_founder: false, person_id: null, firm: null },
  ],
  granted_options: 1_200_000,
  vested_options: 412_500,
  unallocated_options: 2_263_331,
  pool_left_bp: 1000,
  grants: [],
  vesting_months: 48,
  cliff_months: 12,
  founder_shares: 9_000_000,
  founder_fraction: 0.3976,
  last_round_label: 'Series A',
  last_round_date_label: 'Aug 2012',
  post_money_cents: 2_330_000_000,
  ownership_history: [],
}; // prettier-ignore

describe('CapTable', () => {
  it('lists holders with classes, a founder marker, bars by kind and a total', () => {
    const html = renderToStaticMarkup(<CapTable cap={KESTREL_CAP} />);
    expect(html).toContain('Jordan Hale (you)');
    expect(html).toContain('Series A preferred');
    expect(html).toContain('Unallocated');
    expect(html).toContain('Options granted');
    expect(html).toContain('39.76%');
    expect(html).toContain('22,633,308'); // the total row
    expect(html).toContain('100.00%');
    expect(html).toContain('data-color="var(--tst-accent)"'); // the founder's bar
    expect(html).toContain('data-color="var(--tst-good)"'); // granted options
  });

  it('gives converted SAFEs from two rounds different row ids', () => {
    // Playtest: SAFEs converted at the Series A and again at the B gave two equal React keys.
    const safe = { holder: 'SAFE holders', holder_kind: 'group', share_class: 'safe_conversion' };
    const rows = [...KESTREL_CAP.holders, safe, safe];
    const ids = rows.map((r, i) => capRowId(r, i));
    expect(new Set(ids).size).toBe(rows.length);
  });
});

const PREVIEW: RoundPreview = {
  sheet_id: 7,
  firm_name: 'Andreessen Horowitz',
  pre_money_cents: 1_830_000_000,
  amount_cents: 500_000_000,
  post_money_cents: 2_330_000_000,
  share_price_dollars: '1.02950',
  pool_top_up: 1_428_548,
  safe_conversion: 0,
  new_shares: 4_856_933,
  fd_before: 16_347_827,
  fd_after: 22_633_308,
  fees_cents: 2_500_000,
  down_round: false,
  lines: [
    { holder: 'Jordan Hale', share_class: 'common', shares_before: 9_000_000, shares_after: 9_000_000, fraction_before: 0.5505, fraction_after: 0.3976, holder_kind: 'person', is_founder: true, new: false },
    { holder: 'Option pool (unallocated)', share_class: 'option_pool', shares_before: 834_783, shares_after: 2_263_331, fraction_before: 0.0511, fraction_after: 0.1, holder_kind: 'pool', is_founder: false, new: false },
    { holder: 'Andreessen Horowitz', share_class: 'preferred_a', shares_before: 0, shares_after: 4_856_933, fraction_before: 0, fraction_after: 0.2146, holder_kind: 'firm', is_founder: false, new: true },
  ],
  board_after: { common: 2, investor: 2, independent: 0 },
  founder_keeps_tie: true,
  energy_cost: 5,
  series_label: 'Series A',
  nominee_required: true,
  nominee_choices: [
    { person_id: 3, name: 'Priya Shah', role_label: 'Software engineer', level: 'senior', default: true },
    { person_id: 2, name: 'Tom Okafor', role_label: 'Designer', level: 'mid', default: false },
  ],
}; // prettier-ignore

describe('DilutionPreview', () => {
  it('shows each holder now, after and the change, the pool, board and fees', () => {
    const html = wrap(<DilutionPreview preview={PREVIEW} onAccept={() => {}} />);
    expect(html).toContain('Accept Andreessen Horowitz&#x27;s term sheet?');
    expect(html).toContain('4,856,933 new Series A shares at $1.02950');
    expect(html).toContain('55.05%');
    expect(html).toContain('39.76%');
    expect(html).toContain('−15.29');
    expect(html).toContain('+4.89');
    expect(html).toContain('>new<');
    expect(html).toContain('1,428,548 new options');
    expect(html).toContain('2 common · 2 investor (you keep control on a tie)');
    expect(html).toContain('$25,000');
    expect(html).toContain('Accept · 5 energy');
    expect(html).not.toContain('Down round');
  });

  it('asks for the board nominee with the most senior preselected (M4c)', () => {
    const html = wrap(<DilutionPreview preview={PREVIEW} onAccept={() => {}} />);
    expect(html).toContain('Your board nominee');
    expect(html).toContain('Priya Shah · Software engineer, senior (most senior)');
    const none = wrap(<DilutionPreview preview={{ ...PREVIEW, nominee_choices: [] }} />);
    expect(none).toContain('no employees to nominate');
    const seed = wrap(<DilutionPreview preview={{ ...PREVIEW, nominee_required: false }} />);
    expect(seed).not.toContain('Your board nominee');
  });

  it('warns on a down round and can be read-only', () => {
    const html = wrap(
      <DilutionPreview preview={{ ...PREVIEW, down_round: true, founder_keeps_tie: false }} />,
    );
    expect(html).toContain('Down round');
    expect(html).toContain('investors can outvote you');
    expect(html).not.toContain('Accept ·');
  });
});

describe('Finance inbox kind', () => {
  it.each([
    ['safe_filled', 'fundraising'],
    ['bridge_offered', 'fundraising'],
    ['board_warning', 'board'],
    ['round_closed', 'captable'],
    ['bankrupt', 'statements'],
  ])('%s is a Finance message opening %s', (kind, tab) => {
    expect(kindLabel(kind)).toBe('Finance');
    expect(financeTab(kind)).toBe(tab);
    expect(wrap(<KindBadge kind={kind} />)).toContain('>Finance<');
  });

  it('filters Finance messages in the API', () => {
    expect(kindsFor('finance')).toContain('term_sheets_arrived');
    expect(kindsFor('finance')).not.toContain('offer_accepted');
  });
});

describe('BoardMemberCard', () => {
  it('shows name, firm, seat, since, confidence and trend (M4c)', () => {
    const html = wrap(
      <BoardMemberCard
        director={{
          seat_id: 2,
          kind: 'investor',
          person_id: 900,
          name: 'Dana Wills',
          firm: 'a16z',
          firm_name: 'Andreessen Horowitz',
          confidence: 61.4,
          label: 'watchful',
          months_below: 0,
          seated_label: 'Mar 2012',
          is_founder: false,
          vacant: false,
          is_employee: false,
          history: [70, 66, 61.4],
        }}
      />,
    );
    expect(html).toContain('Dana Wills');
    expect(html).toContain('Investor seat · Andreessen Horowitz');
    expect(html).toContain('Mar 2012');
    expect(html).toContain('>61<');
    expect(html).toContain('Last 3 month ends: 70 → 61');
  });
});
