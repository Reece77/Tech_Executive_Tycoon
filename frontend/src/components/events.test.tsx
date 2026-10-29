// Component tests render to static markup: no DOM library is in ADR-0001's dependency list.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { GameEventOut } from '../hooks/api';
import { kindLabel } from '../lib/inbox';
import { EventCard } from './EventCard';
import { KindBadge } from './KindBadge';

const wrap = (node: ReactNode) =>
  renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );

const EVENT: GameEventOut = {
  event_id: 7,
  turn: 32,
  date_label: 'Sep 2012',
  category: 'personnel',
  category_label: 'People',
  severity: 'major',
  status: 'open',
  title: 'Priya Patel has gone quiet',
  body: 'Priya used to be first into every design review.',
  choices: [
    { key: 'A', label: 'Book a long one-to-one', effects: ['morale lift for Priya Patel'] },
    {
      key: 'B',
      label: 'Give Priya a raise',
      effects: [
        'large morale lift for Priya Patel',
        'raise for Priya Patel · costs about $11,800 a year',
      ],
    },
  ],
  chosen: null,
  written_by: 'Claude',
  storyline: { storyline_id: 2, title: 'Priya is running hot', step: 2 },
  follow_up_note: null,
  person_ids: [3],
};

describe('event card (M6)', () => {
  it('shows the story, choices and their effects in words, never numbers or caps', () => {
    const html = wrap(<EventCard saveId="s" event={EVENT} />);
    expect(html).toContain('Priya Patel has gone quiet');
    expect(html).toContain('Priya is running hot · step 2');
    expect(html).toContain('A. Book a long one-to-one');
    expect(html).toContain('large morale lift for Priya Patel');
    expect(html).toContain('costs about $11,800 a year');
    expect(html).toContain('Effects apply at once. Written by AI');
    expect(html).not.toMatch(/cap|strength/i);
  });

  it('shows the answer once chosen and the follow-up note on a critical event', () => {
    const html = wrap(
      <EventCard
        saveId="s"
        event={{
          ...EVENT,
          severity: 'critical',
          status: 'answered',
          chosen: 'B',
          follow_up_note: 'Whatever you choose, a follow-up comes next month.',
        }}
      />,
    );
    expect(html).toContain('You chose B.');
    expect(html).toContain('Critical');
    expect(html).toContain('a follow-up comes next month');
  });

  it('labels event inbox items Event, and critical ones Critical', () => {
    expect(kindLabel('event')).toBe('Event');
    expect(kindLabel('critical_event')).toBe('Critical');
    expect(renderToStaticMarkup(<KindBadge kind="critical_event" />)).toContain('>Critical<');
  });
});
