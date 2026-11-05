// M14b: credibility and the Promises panel, the rival leader panel, Replace, the interest
// filter and leadership fit, rendered to static markup with the API's answers (as the API
// would send them).
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { pressKeys, type Press, type Replaceable, type RivalLeader } from '../hooks/press';
import { kindLabel, kindsFor } from '../lib/inbox';
import { signed, starRange, starWords } from '../lib/press';
import { LeadershipFit } from './LeadershipFit';
import { PressBody, PressPanels } from './PressPanels';
import { InterestFilter, ReplaceBody } from './ReplacePanel';
import { RivalLeaderBody } from './RivalLeaderPanel';

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

const count = (html: string, needle: string) => html.split(needle).length - 1;

const PRESS: Press = {
  credibility: {
    value: 58.4,
    history: [
      { turn: 1, label: 'Feb 2010', change: -2, cause: 'no comment to the press' },
      { turn: 2, label: 'Mar 2010', change: 5, cause: 'kept: ship Anvil by May 2010' },
      { turn: 3, label: 'Apr 2010', change: -10, cause: 'broken: make no layoffs' },
      { turn: 4, label: 'May 2010', change: 1, cause: 'drift' },
      { turn: 5, label: 'Jun 2010', change: 1, cause: 'drift' },
      { turn: 6, label: 'Jul 2010', change: 7.5, cause: 'kept: beat Sales Cloud' },
    ],
  },
  promises: [
    {
      promise_id: 3,
      kind: 'ship',
      words: 'ship Forge by Jan 2011',
      made: 'Jul 2010',
      deadline: 'Jan 2011',
      months_left: 6,
      status: 'open',
      progress: 'Forge: in development',
    },
    {
      promise_id: 2,
      kind: 'no_layoffs',
      words: 'make no layoffs until Feb 2011',
      made: 'Feb 2010',
      deadline: 'Feb 2011',
      months_left: 7,
      status: 'broken',
      progress: '',
    },
    {
      promise_id: 1,
      kind: 'ship',
      words: 'ship Anvil by May 2010',
      made: 'Feb 2010',
      deadline: 'May 2010',
      months_left: 0,
      status: 'kept',
      progress: 'Anvil: live',
    },
  ],
  moments: [],
  form: {
    moment_id: 7,
    open_count: 1,
    max_open: 3,
    energy: 2,
    months: [3, 18],
    in_development: [{ id: 4, name: 'Forge' }],
    live: [{ id: 1, name: 'Pipeline' }],
    rival_products: [{ id: 900000, name: 'Sales Cloud (Salesforce)' }],
    domains: [{ id: 'ai', name: 'AI (lead 0)' }],
  },
};

describe('PressBody', () => {
  it('shows credibility with its last five changes, newest first', () => {
    const html = render(<PressBody saveId={SAVE} press={PRESS} />);
    expect(html).toContain('data-testid="credibility-value"');
    expect(html).toMatch(/data-testid="credibility-value"[^>]*>58</);
    expect(count(html, 'data-testid="credibility-change"')).toBe(5);
    expect(html).not.toContain('no comment to the press'); // the sixth change back
    expect(html.indexOf('kept: beat Sales Cloud')).toBeLessThan(html.indexOf('broken: make'));
    expect(html).toContain('+7.5');
    expect(html).toContain('−10.0');
  });

  it('lists open, kept and broken promises with progress and deadline', () => {
    const html = render(<PressBody saveId={SAVE} press={PRESS} />);
    expect(count(html, 'data-testid="promise-row"')).toBe(3);
    for (const status of ['open', 'kept', 'broken']) {
      expect(html).toContain(`data-status="${status}"`);
    }
    expect(html).toContain('Forge: in development');
    expect(html).toContain('Jan 2011');
    expect(html).toContain('6 months'); // left on the open one
    expect(html).toContain('1 of 3 open');
  });

  it('offers a promise only after a press moment answered this month', () => {
    const html = render(<PressBody saveId={SAVE} press={PRESS} />);
    expect(html).toContain('data-testid="promise-open"');
    expect(html).toContain('Make a promise · 2 energy');
    const none = { ...PRESS, form: { ...PRESS.form, moment_id: null } };
    const later = render(<PressBody saveId={SAVE} press={none} />);
    expect(later).not.toContain('data-testid="promise-open"');
    expect(later).toContain('answer one boldly or measured');
  });

  it('disables the promise at the open limit', () => {
    const full = { ...PRESS, form: { ...PRESS.form, open_count: 3 } };
    const html = render(<PressBody saveId={SAVE} press={full} />);
    expect(html).toMatch(/<button[^>]*disabled[^>]*data-testid="promise-open"/);
    expect(html).toContain('At most 3 promises open at once');
  });

  it('renders from the cache on the Overview', () => {
    const html = render(<PressPanels saveId={SAVE} />, (c) =>
      c.setQueryData(pressKeys.press(SAVE), PRESS),
    );
    expect(html).toContain('data-testid="promises-panel"');
    expect(html).toContain('data-testid="credibility-panel"');
  });
});

const LEADER: RivalLeader = {
  rival_id: 2,
  ceo: "Jonas O'Brien",
  ceo_person_id: 5000008,
  statements: [
    { label: 'Feb 2010', kind: 'answer', text: 'Kestrel talks a good game.' },
    { label: 'Jan 2010', kind: 'jab', text: 'Some companies race to the bottom.' },
  ],
  feud: {
    rival_id: 2,
    rival: 'Salesforce',
    ceo: "Jonas O'Brien",
    score: 18,
    rivalry: false,
    causes: [
      { turn: 0, label: 'Jan 2010', change: 8, cause: 'Pipeline launched against them' },
      { turn: 1, label: 'Feb 2010', change: 10, cause: 'a bold claim named them' },
    ],
  },
};

describe('RivalLeaderBody', () => {
  it('shows the CEO, statements by kind and the feud with its causes', () => {
    const html = render(<RivalLeaderBody leader={LEADER} />);
    expect(html).toContain('data-testid="rival-ceo"');
    expect(html).toContain('Jonas O&#x27;Brien');
    expect(count(html, 'data-testid="rival-statement"')).toBe(2);
    expect(html).toContain('data-kind="jab"');
    expect(html).toContain('>Jab<');
    expect(html).toContain('data-score="18"');
    expect(html).toContain('a bold claim named them');
    expect(html).toContain('aria-valuenow="18"');
    expect(html).not.toContain('data-testid="feud-rivalry"');
  });

  it('marks a rivalry', () => {
    const rivalry = { ...LEADER, feud: { ...LEADER.feud, score: 62, rivalry: true } };
    const html = render(<RivalLeaderBody leader={rivalry} />);
    expect(html).toContain('data-testid="feud-rivalry"');
    expect(html).toContain('>Rivalry<');
  });
});

describe('ReplaceBody', () => {
  const rows: Replaceable[] = [
    {
      person_id: 3,
      name: 'Eric Edwards',
      role: 'Software engineer',
      level: 'senior',
      reason: 'poached',
      can_replace: true,
      problem: null,
    },
    {
      person_id: 9,
      name: 'Ana Silva',
      role: 'Designer',
      level: 'mid',
      reason: 'resigned',
      can_replace: false,
      problem: 'Replace needs a recruiter on staff',
    },
  ];

  it('offers Replace, disabled with the reason when it cannot', () => {
    const html = render(<ReplaceBody saveId={SAVE} rows={rows} />);
    expect(count(html, 'data-testid="replace-row"')).toBe(2);
    expect(html).toMatch(/<button(?![^>]*disabled)[^>]*data-testid="replace-3"/);
    expect(html).toMatch(/<button[^>]*disabled[^>]*data-testid="replace-9"/);
    expect(html).toContain('title="Replace needs a recruiter on staff"');
    expect(html).toContain('Poached');
    expect(html).toContain('Resigned');
  });
});

describe('InterestFilter', () => {
  const interests = [
    { key: 'ai', label: 'AI' },
    { key: 'privacy', label: 'Privacy' },
  ];
  it('lists the interests after "any", and notes the fee once one is chosen', () => {
    const none = render(<InterestFilter interests={interests} value={null} onChange={() => {}} />);
    expect(none).toContain('data-testid="interest-filter"');
    expect(none).toContain('Any interest (no fee)');
    expect(none).toContain('>Privacy<');
    const chosen = render(<InterestFilter interests={interests} value="ai" onChange={() => {}} />);
    expect(chosen).toContain('15% of the role&#x27;s mid salary');
  });
});

describe('leadership fit', () => {
  it('is a star range unless the range is one value', () => {
    expect(starRange(2, 4)).toBe('★★–★★★★');
    expect(starRange(3, 3)).toBe('★★★');
    expect(starWords(2, 4)).toBe('2–4 of 5 stars');
    const html = renderToStaticMarkup(<LeadershipFit low={1} high={5} />);
    expect(html).toContain('data-testid="leadership-fit"');
    expect(html).toContain('★–★★★★★');
    // the API's defaults (nothing revealed) are the whole scale
    expect(renderToStaticMarkup(<LeadershipFit />)).toContain('data-low="1" data-high="5"');
  });

  it('formats a credibility change with its sign', () => {
    expect(signed(5)).toBe('+5.0');
    expect(signed(-2)).toBe('−2.0');
  });
});

describe('press inbox items', () => {
  it.each(['promise_made', 'promise_kept', 'promise_broken', 'rival_statement'])(
    '%s is a Press item',
    (kind) => expect(kindLabel(kind)).toBe('Press'),
  );
  it('files Replace under hiring', () => {
    expect(kindLabel('replace_started')).toBe('Delegate');
    expect(kindsFor('hiring')).toContain('replace_started');
  });
});
