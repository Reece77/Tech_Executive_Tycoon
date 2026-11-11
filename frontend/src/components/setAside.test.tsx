// M23c: setting a critical decision aside, its links, and the read-only guard's allow list.
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { GameEventOut } from '../hooks/api';
import { allowedWhileReadOnly } from '../lib/setAside';
import { EventCard } from './EventCard';

const CRASH: GameEventOut = {
  template_id: 'mine_price_crash',
  event_id: 9,
  turn: 80,
  date_label: 'Sep 2016',
  category: 'mining',
  category_label: 'Mining',
  severity: 'critical',
  status: 'open',
  title: 'Copper is under your cost',
  body: 'Three months under the all-in cost.',
  choices: [{ key: 'A', label: 'Keep running', effects: [], do_nothing: false }],
  chosen: null,
  written_by: 'template',
  storyline: null,
  follow_up_note: null,
  person_ids: [],
  links: [
    { path: 'products/mines?mine=3', label: 'Copper mine #3, Latin America' },
    { path: 'products/mines', label: 'Mines' },
  ],
};

const html = (event: GameEventOut) =>
  renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider>
        <MemoryRouter>
          <EventCard saveId="s" event={event} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );

describe('look before you decide (M23c)', () => {
  it('links an open event to the screens that matter for it', () => {
    const out = html(CRASH);
    expect(out).toContain('Look first:');
    expect(out).toContain('href="/game/s/products/mines?mine=3"');
    expect(out).toContain('Copper mine #3, Latin America');
  });

  it('drops the links once the event is answered', () => {
    expect(html({ ...CRASH, status: 'answered', chosen: 'A' })).not.toContain('Look first:');
  });

  it('lets reads, previews and the answer through while read only, and nothing else', () => {
    expect(allowedWhileReadOnly('GET', '/api/saves/s/products/mines')).toBe(true);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/events/9/choose')).toBe(true);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/products/4/price-preview')).toBe(true);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/commodities/offtakes/quote')).toBe(true);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/inbox/3/read')).toBe(true);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/advance')).toBe(false);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/mines/3/close')).toBe(false);
    expect(allowedWhileReadOnly('POST', '/api/saves/s/exploration/licence')).toBe(false);
    expect(allowedWhileReadOnly('PUT', '/api/saves/s/public/ceo/authority')).toBe(false);
  });
});
