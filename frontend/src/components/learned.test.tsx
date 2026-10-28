// Component tests render to static markup: no DOM library is in ADR-0001's dependency list.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Learned } from '../hooks/api';
import { LearnedCard } from './LearnedPanel';

const base: Learned = {
  person_id: 7,
  name: 'Ada Mensah',
  action: 'interview',
  ranges: [
    {
      key: 'software_engineering',
      label: 'Software engineering',
      group: 'technical',
      before: { min: 8, max: 18 },
      after: { min: 10, max: 16 },
    },
    {
      key: 'loyalty',
      label: 'Loyalty',
      group: 'personality',
      before: { min: 3, max: 17 },
      after: { min: 6, max: 15 },
    },
  ],
  potential_before: 'limited to outstanding',
  potential_after: 'decent to outstanding',
  interests: ['ai'],
  work_style: 'builder',
  tags: [],
};

describe('LearnedCard', () => {
  it('shows each narrowed range before and after, and the potential phrase', () => {
    const html = renderToStaticMarkup(<LearnedCard learned={base} />);
    expect(html.match(/data-testid="learned-range"/g)).toHaveLength(2);
    expect(html).toContain('>8–18<');
    expect(html).toContain('>10–16<');
    expect(html).toContain('limited to outstanding');
    expect(html).toContain('decent to outstanding');
    expect(html).toContain('Interests: Ai');
    expect(html).toContain('works as a builder');
  });

  it('lists the focus skills and personality, and counts the other skills', () => {
    const html = renderToStaticMarkup(<LearnedCard learned={base} focus={['data']} />);
    expect(html.match(/data-testid="learned-range"/g)).toHaveLength(1); // loyalty only
    expect(html).toContain('and 1 other skill narrowed');
  });

  it('says so when nothing changed', () => {
    const html = renderToStaticMarkup(
      <LearnedCard
        learned={{
          ...base,
          action: 'reference_check',
          ranges: [],
          potential_before: 'good',
          potential_after: 'good',
          interests: null,
          work_style: null,
        }}
      />,
    );
    expect(html).toContain('Nothing new');
    expect(html).toContain('still good');
    expect(html).toContain('References');
  });
});
