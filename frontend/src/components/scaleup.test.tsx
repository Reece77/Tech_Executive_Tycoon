// M8: the scale-up display helpers and the division badge. Static markup, as in org.test.
import { MantineProvider } from '@mantine/core';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { pct } from '../lib/org';
import { UnitKindBadge } from './OrgNode';

describe('pct', () => {
  it('signs percentages the API computed with a true minus', () => {
    expect(pct(5)).toBe('+5%');
    expect(pct(-5.6)).toBe('−5.6%');
    expect(pct(0)).toBe('+0%');
  });
});

describe('UnitKindBadge', () => {
  it('labels a division', () => {
    const html = renderToStaticMarkup(
      <MantineProvider>
        <UnitKindBadge kind="division" />
      </MantineProvider>,
    );
    expect(html).toContain('data-kind="division"');
    expect(html).toContain('>Division<');
  });
});
