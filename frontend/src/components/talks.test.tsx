// M49: the talk room (template and free-text modes, effects once over) and the one-to-one
// panel (flags, held this month, delegates, promises), rendered to static markup with the API's
// answers as the API would send them.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { Talk, TalkList } from '../hooks/talks';
import { OneToOneBody } from './OneToOnePanel';
import { TalkRoomBody } from './TalkRoom';

const SAVE = 's';

function render(node: ReactNode, url = '/'): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MantineProvider>
        <MemoryRouter initialEntries={[url]}>{node}</MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

const MODE = { mode: 'llm', reason: '', cap_cents: 1000, spent_cents: 0 };

const TALK: Talk = {
  talk_id: 1,
  kind: 'one_to_one',
  subject: 'One-to-one with Eric Brown, Jan 2019',
  source: 'person',
  status: 'open',
  opened_turn: 108,
  date_label: 'Jan 2019',
  error: null,
  counterpart: {
    name: 'Eric Brown',
    role: 'senior Software engineer',
    organisation: 'Quill',
    person_id: 3,
    beat: '',
    stance: '',
    morale: 65,
  },
  questions: [
    {
      n: 0,
      topic: 'morale',
      title: 'How things are',
      question: 'How are things going for you, Eric?',
      facts: ["Eric Brown's morale shows as 65 out of 100"],
      offer: '',
      rival: '',
    },
    {
      n: 1,
      topic: 'approach',
      title: "The rival's approach",
      question: "Salesforce has been in touch with me. I'm thinking it over.",
      facts: ['Salesforce has approached Eric Brown'],
      offer: 'a promotion to staff within 12 months',
      rival: 'Salesforce',
    },
  ],
  answers: [
    {
      n: 0,
      message: 'listened',
      message_source: 'template',
      reply: 'Thanks for asking. Salesforce has been in touch with me.',
      reply_source: 'template',
      claimed: [{ kind: 'listen', words: 'listened' }],
      moves: [{ kind: 'listen', words: 'listened' }],
      reaction: 'pleased',
      reaction_words: 'Thanks for asking.',
    },
  ],
  next_question: 1,
  opening_line: 'How are things going for you, Eric?',
  move_choices: [
    { kind: 'listen', label: 'Listen' },
    { kind: 'offer_raise', label: 'Offer a raise' },
    { kind: 'neutral', label: 'Say nothing of substance' },
  ],
  offer: 'a promotion to staff within 12 months',
  approached_by: 'Salesforce',
  delegated: false,
  effects: [],
  suggestions: ['I hear you.', 'You do excellent work.', 'I need more from you.'],
  mode: MODE,
};

describe('talk room', () => {
  it('shows move buttons in template mode, without a text box', () => {
    const html = render(
      <TalkRoomBody
        saveId={SAVE}
        t={{ ...TALK, mode: { ...MODE, mode: 'template', reason: 'budget' } }}
      />,
    );
    expect(html).toContain('data-testid="talk-room"');
    expect(html).toContain('Template mode (budget)');
    expect(html).toContain('data-testid="talk-move-listen"');
    expect(html).toContain('data-testid="talk-move-offer_raise"');
    expect(html).not.toContain('talk-move-neutral');
    expect(html).not.toContain('data-testid="talk-message"');
    expect(html).toContain('data-testid="talk-skip"');
    expect(html.split('data-testid="talk-answer"').length - 1).toBe(1);
    expect(html).toContain('a promotion to staff within 12 months');
    expect(html).toContain('approached by Salesforce');
  });

  it('shows three suggestions and a text box in free-text mode', () => {
    const html = render(<TalkRoomBody saveId={SAVE} t={TALK} />);
    expect(html).toContain('Free text');
    expect(html.split('data-testid="talk-suggestion"').length - 1).toBe(3);
    expect(html).toContain('data-testid="talk-message"');
    expect(html).not.toContain('talk-move-listen');
  });

  it('shows the effects once over, and nothing moved when skipped', () => {
    const done = render(
      <TalkRoomBody
        saveId={SAVE}
        t={{
          ...TALK,
          status: 'done',
          next_question: null,
          effects: [{ what: 'morale', change: 4, words: 'morale +4' }],
        }}
      />,
    );
    expect(done).toContain('data-testid="talk-effects"');
    expect(done).toContain('morale +4');
    expect(done).not.toContain('data-testid="talk-send"');
    const skipped = render(
      <TalkRoomBody saveId={SAVE} t={{ ...TALK, status: 'skipped', next_question: null }} />,
    );
    expect(skipped).toContain('Skipped: nothing changed.');
  });
});

const LIST: TalkList = {
  mode: MODE,
  available: [],
  items: [],
  people: [
    {
      person_id: 3,
      name: 'Eric Brown',
      role_label: 'senior Software engineer',
      morale: 45,
      flags: ['unhappy', 'approached'],
      approached_by: 'Salesforce',
      held: '',
      delegates: [5],
    },
    {
      person_id: 5,
      name: 'Jason White',
      role_label: 'exec Software engineer',
      morale: 70,
      flags: ['seat'],
      approached_by: '',
      held: 'done',
      delegates: [],
    },
  ],
  promises: [
    {
      promise_id: 9,
      person_id: 3,
      words: 'promote Eric Brown to staff by Jan 2020',
      made_label: 'Jan 2019',
      deadline_label: 'Jan 2020',
      status: 'open',
    },
  ],
  energy: 80,
  one_to_one_energy: 2,
};

describe('one-to-one panel', () => {
  it('flags the person, offers the talk and a delegate, and lists promises', () => {
    const html = render(<OneToOneBody saveId={SAVE} personId={3} list={LIST} />);
    expect(html).toContain('data-testid="person-flag-unhappy"');
    expect(html).toContain('Approached by Salesforce');
    expect(html).toMatch(/<button(?![^>]*disabled)[^>]*data-testid="one-to-one-open"/);
    expect(html).toContain('Ask Jason White to hold it');
    expect(html).toContain('data-testid="talk-promises"');
    expect(html).toContain('promote Eric Brown to staff by Jan 2020');
    expect(html).toContain('data-status="open"');
  });

  it('disables the talk with the reason once held this month', () => {
    const html = render(<OneToOneBody saveId={SAVE} personId={5} list={LIST} />);
    expect(html).toMatch(/<button[^>]*disabled[^>]*data-testid="one-to-one-open"/);
    expect(html).toContain('Already held this month (Over)');
    expect(html).not.toContain('one-to-one-delegate');
    expect(html).toContain('No promises made to Jason.');
  });
});
