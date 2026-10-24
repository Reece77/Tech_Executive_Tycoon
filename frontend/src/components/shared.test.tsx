// Component tests render to static markup: no DOM library is in ADR-0001's dependency list.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { attributeTier, byStrength, moraleBand, rangeText } from '../lib/attr';
import { kindLabel, matchesFilter, preview } from '../lib/inbox';
import { statusOf } from '../lib/status';
import { AttributeRange } from './AttributeRange';
import { KindBadge } from './KindBadge';
import { MoraleBar } from './MoraleBar';
import { StatusChip } from './StatusChip';

describe('AttributeRange', () => {
  it.each([
    [{ min: 1, max: 5 }, 1, '1–5'],
    [{ min: 5, max: 6 }, 1, '5–6'], // midpoint 5.5
    [{ min: 6, max: 10 }, 2, '6–10'],
    [{ min: 10, max: 12 }, 3, '10–12'], // midpoint 11
    [{ min: 14, max: 17 }, 3, '14–17'],
    [{ min: 16, max: 16 }, 4, '16'],
    [{ min: 20, max: 20 }, 4, '20'],
  ])('%o -> tier %i, %s', (range, tier, text) => {
    expect(attributeTier(range)).toBe(tier);
    expect(rangeText(range)).toBe(text);
    const html = renderToStaticMarkup(<AttributeRange range={range} />);
    expect(html).toContain(`tst-tier-${tier}`);
    expect(html).toContain(`>${text}<`);
  });

  it('sorts strongest first', () => {
    const skills = [
      { label: 'B', range: { min: 8, max: 12 } },
      { label: 'A', range: { min: 9, max: 11 } },
      { label: 'C', range: { min: 14, max: 17 } },
    ];
    expect([...skills].sort(byStrength).map((s) => s.label)).toEqual(['C', 'A', 'B']);
  });
});

describe('MoraleBar', () => {
  it.each([
    [31, 'low'],
    [39.9, 'low'],
    [40, 'mid'],
    [59, 'mid'],
    [60, 'high'],
    [72, 'high'],
  ])('%f is %s', (morale, band) => {
    expect(moraleBand(morale)).toBe(band);
    const html = renderToStaticMarkup(<MoraleBar morale={morale} />);
    expect(html).toContain(`data-band="${band}"`);
    expect(html).toContain(`>${Math.round(morale)}<`);
  });

  it('shows n/a for the founder', () => {
    expect(renderToStaticMarkup(<MoraleBar morale={null} />)).toContain('n/a');
  });
});

describe('KindBadge', () => {
  it.each([
    ['offer_accepted', 'Hire'],
    ['candidates_arrived', 'Search'],
    ['tag_revealed', 'Scout'],
    ['resigned', 'Notice'],
    ['culture_carrier_left', 'Notice'],
    ['offer_declined', 'Declined'],
    ['something_new', 'Notice'],
  ])('%s -> %s', (kind, label) => {
    expect(kindLabel(kind)).toBe(label);
    expect(renderToStaticMarkup(<KindBadge kind={kind} />)).toContain(`>${label}<`);
  });

  it('filters by group and read state', () => {
    expect(matchesFilter({ kind: 'offer_accepted', read: true }, 'hiring')).toBe(true);
    expect(matchesFilter({ kind: 'offer_accepted', read: true }, 'people')).toBe(false);
    expect(matchesFilter({ kind: 'fired', read: false }, 'unread')).toBe(true);
    expect(matchesFilter({ kind: 'fired', read: true }, 'unread')).toBe(false);
    expect(preview('First. Second.')).toBe('First.');
  });
});

describe('StatusChip', () => {
  it('derives status from the API person', () => {
    expect(statusOf({ is_founder: true, employment: { status: 'active' } })).toBe('Founder');
    expect(statusOf({ is_founder: false, employment: { status: 'notice' } })).toBe('Notice');
    expect(statusOf({ is_founder: false, employment: { status: 'active' } })).toBe('Active');
    expect(renderToStaticMarkup(<StatusChip status="Notice" />)).toContain('>Notice<');
  });
});
