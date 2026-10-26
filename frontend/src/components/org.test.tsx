// M2b shared components: SpanBadge, OrgNode, PreviewDialog's body. Static markup, as in shared.test.
import { MantineProvider } from '@mantine/core';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { kindLabel, matchesFilter, pageRange } from '../lib/inbox';
import { policyText, signed } from '../lib/org';
import { KindBadge } from './KindBadge';
import { OrgNode } from './OrgNode';
import { RaiseFacts } from './PersonOrg';
import { PreviewBody } from './PreviewDialog';
import { SpanBadge } from './SpanBadge';

const wrap = (node: ReactNode) =>
  renderToStaticMarkup(
    <MantineProvider>
      <MemoryRouter>{node}</MemoryRouter>
    </MantineProvider>,
  );

describe('SpanBadge', () => {
  it('shows reports against span', () => {
    const html = renderToStaticMarkup(<SpanBadge reports={4} limit={8} over={false} />);
    expect(html).toContain('data-over="false"');
    expect(html).toContain('4 / 8 reports');
    expect(html).not.toContain('over span');
  });

  it('warns over span', () => {
    const html = renderToStaticMarkup(<SpanBadge reports={7} limit={6} over />);
    expect(html).toContain('data-over="true"');
    expect(html).toContain('7 / 6 reports · over span');
  });
});

describe('OrgNode', () => {
  it('shows kind, name, leader, inherited policy, headcount and span', () => {
    const html = wrap(
      <OrgNode
        kind="team"
        name="Platform"
        leaderName="Marcus Ode"
        leaderHref="/game/s/people/5"
        policy={null}
        effectivePolicy="office"
        headcount={8}
        span={{ reports: 7, limit: 6, over: true }}
        selected
      />,
    );
    expect(html).toContain('data-kind="team"');
    expect(html).toContain('>Team<');
    expect(html).toContain('>Platform<');
    expect(html).toContain('href="/game/s/people/5"');
    expect(html).toContain('Office (inherited)');
    expect(html).toContain('8 people');
    expect(html).toContain('over span');
    expect(html).toContain('aria-pressed="true"');
  });

  it('shows the product a unit works on (M3b)', () => {
    const node = (product: string | null) =>
      wrap(
        <OrgNode
          kind="team"
          name="Platform"
          leaderName={null}
          leaderHref={null}
          policy={null}
          effectivePolicy="office"
          headcount={3}
          span={null}
          product={product}
        />,
      );
    expect(node('Pipeline')).toContain('Works on Pipeline');
    expect(node(null)).not.toContain('Works on');
  });

  it('handles a leaderless unit and its own policy', () => {
    const html = wrap(
      <OrgNode
        kind="department"
        name="Eng"
        leaderName={null}
        leaderHref={null}
        policy="remote"
        effectivePolicy="remote"
        headcount={1}
        span={null}
      />,
    );
    expect(html).toContain('No leader');
    expect(html).toContain('>Remote<');
    expect(html).toContain('1 person');
    expect(html).not.toContain('span-badge');
  });
});

describe('PreviewBody', () => {
  it('lists the one-off morale changes and the energy', () => {
    const html = wrap(
      <PreviewBody
        preview={{
          allowed: true,
          problem: null,
          energy_cost: 1,
          morale_changes: [{ person_id: 3, name: 'Nadia Karim', change: -2 }],
        }}
      />,
    );
    expect(html).toContain('Costs 1 energy.');
    expect(html).toContain('Nadia Karim');
    expect(html).toContain('−2');
  });

  it('says when nobody is affected, or why a change is refused', () => {
    const none = wrap(
      <PreviewBody
        preview={{ allowed: true, problem: null, energy_cost: 2, morale_changes: [] }}
      />,
    );
    expect(none).toContain('preview-none');
    const refused = wrap(
      <PreviewBody
        preview={{
          allowed: false,
          problem: 'departments unlock at 10 staff',
          energy_cost: 0,
          morale_changes: [],
        }}
      />,
    );
    expect(refused).toContain('departments unlock at 10 staff');
  });
});

describe('org text helpers', () => {
  it.each([
    [3, '+3'],
    [-2, '−2'],
    [-0.04, '0'],
    [1.25, '+1.3'],
  ])('signed(%f) = %s', (value, text) => {
    expect(signed(value)).toBe(text);
  });

  it('marks inherited policies', () => {
    expect(policyText(null, 'remote')).toBe('Remote (inherited)');
    expect(policyText('office', 'office')).toBe('Office');
  });
});

describe('RaiseFacts', () => {
  it('shows the change, ratio to market, morale, monthly cost and energy from the preview', () => {
    const html = wrap(
      <RaiseFacts
        roleText="Mid software engineer"
        pv={{
          allowed: true,
          problem: null,
          energy_cost: 2,
          level: 'mid',
          new_level: 'mid',
          salary_cents: 9_500_000,
          new_salary_cents: 10_000_000,
          market_rate_cents: 9_100_000,
          new_market_rate_cents: 9_100_000,
          pay_term: 2.6,
          new_pay_term: 5.9,
          salary_change_bp: 526,
          market_ratio: 1.04,
          new_market_ratio: 1.0989,
          monthly_cost_change_cents: 50_000,
          below_market: false,
          morale_change: 3,
        }}
      />,
    );
    expect(html).toContain('Up 5.26% from $95,000');
    expect(html).toContain('market rate $91,000: this is 1.10×');
    expect(html).toContain('+3');
    expect(html).toContain('+$500');
  });
});

describe('inbox additions', () => {
  it.each(['plan_activity', 'plan_filled', 'plan_paused'])('%s has the Delegate badge', (kind) => {
    expect(kindLabel(kind)).toBe('Delegate');
    expect(renderToStaticMarkup(<KindBadge kind={kind} />)).toContain('>Delegate<');
    expect(matchesFilter({ kind, read: true }, 'hiring')).toBe(true);
  });

  it.each([
    [0, 50, 342, '1–50 of 342'],
    [50, 50, 342, '51–100 of 342'],
    [300, 42, 342, '301–342 of 342'],
    [0, 0, 0, '0 of 0'],
  ])('pageRange(%i, %i, %i) = %s', (offset, shown, total, text) => {
    expect(pageRange(offset, shown, total)).toBe(text);
  });
});
