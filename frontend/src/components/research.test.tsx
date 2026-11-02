// M11: the era timeline shows who caused an arrived era and no date for eras to come.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Era } from '../hooks/api';
import { EraTimeline } from './EraTimeline';

const base: Era = {
  key: 'transformers',
  label: 'Transformers',
  domain_label: 'AI',
  status: 'arrived',
  arrived: 'Mar 2016',
  on_schedule: false,
  months_early: 15,
  caused_by: 'You',
  threshold: 43.5,
  your_level: 44.1,
  accelerates: 'AI models and inference: growth +20 points for 60 months',
  first_mover_reward: 'For 12 months: +5 quality cap',
};

describe('EraTimeline', () => {
  it('names who caused an early era and how early', () => {
    const html = renderToStaticMarkup(<EraTimeline eras={[base]} />);
    expect(html).toContain('Arrived Mar 2016, 15 months early (You)');
  });

  it('shows the next era with its threshold and the first-mover reward, no date', () => {
    const next: Era = {
      ...base,
      key: 'large_language_models',
      label: 'Large language models',
      status: 'next',
      arrived: null,
      on_schedule: null,
      months_early: null,
      caused_by: null,
    };
    const html = renderToStaticMarkup(<EraTimeline eras={[next]} />);
    expect(html).toContain('43.5');
    expect(html).toContain('For 12 months');
    expect(html).not.toContain('2022');
    expect(html).toContain('data-status="next"');
  });
});
