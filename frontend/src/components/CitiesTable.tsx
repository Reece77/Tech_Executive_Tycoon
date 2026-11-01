import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { City } from '../hooks/api';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';

const helper = createColumnHelper<GameTableFeatures, City>();

/** Every city with its region, salary and rent indexes, talent and your people (M9, 19.1). */
export function CitiesTable({ cities }: { cities: City[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', {
          header: 'City',
          meta: { term: 'geo.city' },
          cell: ({ row }) => (
            <span style={{ fontWeight: 600 }}>
              {row.original.label}
              {row.original.is_hq ? ' (HQ)' : ''}
            </span>
          ),
        }),
        helper.accessor('region_label', { header: 'Region', meta: { term: 'geo.region' } }),
        helper.accessor('salary_index', {
          header: 'Salary',
          meta: { term: 'geo.salary_index' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">×{getValue().toFixed(2)}</span>,
        }),
        helper.accessor('rent_index', {
          header: 'Rent',
          meta: { term: 'geo.rent_index' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">×{getValue().toFixed(2)}</span>,
        }),
        helper.display({
          id: 'talent',
          header: 'Talent',
          meta: { term: 'geo.talent' },
          cell: ({ row }) =>
            row.original.talent.map((t) => `${t.label} ${t.marks}`).join(', ') || '—',
        }),
        helper.accessor('people', {
          header: 'Your people',
          meta: { term: 'geo.people' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: cities,
    getRowId: (c) => c.key,
  });
  return <DataTable table={table} label="Cities" rowTestId="city-row" />;
}
