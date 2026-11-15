// M30: long tables render only the rows near their viewport. Static markup, as in org.test.
import { MantineProvider } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { WINDOW_FROM, gameTableFeatures, rowWindow, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';

interface Row {
  id: number;
  name: string;
}

const helper = createColumnHelper<GameTableFeatures, Row>();
const columns = helper.columns([helper.accessor('name', { header: 'Name' })]);

function Harness({ count }: { count: number }) {
  const data = Array.from({ length: count }, (_, i) => ({ id: i, name: `Row ${i}` }));
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data,
    getRowId: (r) => String(r.id),
  });
  return <DataTable table={table} label="Rows" rowTestId="row" />;
}

const rendered = (count: number) =>
  renderToStaticMarkup(
    <MantineProvider>
      <Harness count={count} />
    </MantineProvider>,
  );

const rowCount = (html: string) => html.split('data-testid="row"').length - 1;

describe('DataTable windowing', () => {
  it('renders every row of a table up to the threshold', () => {
    const html = rendered(WINDOW_FROM);
    expect(rowCount(html)).toBe(WINDOW_FROM);
    expect(html).not.toContain('tst-table-wrap--windowed');
  });

  it('renders the first screen of a long table and holds the rest as space', () => {
    const html = rendered(5000);
    expect(html).toContain('tst-table-wrap--windowed');
    expect(html).toContain('aria-rowcount="5001"');
    const shown = rowCount(html);
    expect(shown).toBeGreaterThan(20);
    expect(shown).toBeLessThan(100);
    expect(html).toContain('Row 0');
    expect(html).not.toContain('Row 4999');
  });

  it('moves the window with the scroll position', () => {
    expect(rowWindow(1000, 0, 660, 33)).toEqual({ start: 0, end: 40, before: 0, after: 960 * 33 });
    const mid = rowWindow(1000, 3300, 660, 33); // row 100 at the top
    expect(mid.start).toBe(80);
    expect(mid.end).toBe(140);
    expect(mid.before + (mid.end - mid.start) * 33 + mid.after).toBe(1000 * 33);
    const last = rowWindow(1000, 1000 * 33 - 660, 660, 33);
    expect(last.end).toBe(1000);
    expect(last.after).toBe(0);
  });
});
