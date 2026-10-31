import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { CapTable as CapTableData, Holder } from '../hooks/api';
import {
  formatFraction,
  formatShares,
  holderColor,
  holderName,
  shareClassText,
} from '../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import type { TableViewsApi } from '../hooks/useTableViews';
import { DataTable } from './DataTable';

/** A holder line, or the total row (`total`). */
type Row = Holder & { total?: boolean };

const helper = createColumnHelper<GameTableFeatures, Row>();

/** A percentage bar coloured by kind of holder; `fraction` is 0-1 from the API. */
export function ShareBar({
  fraction,
  color,
  width = 150,
}: {
  fraction: number;
  color: string;
  width?: number;
}) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'block',
        width,
        height: 8,
        background: 'var(--tst-hover)',
        borderRadius: 4,
      }}
    >
      <span
        data-color={color}
        style={{
          display: 'block',
          height: 8,
          borderRadius: 4,
          background: color,
          width: `${Math.min(100, Math.max(0, fraction * 100))}%`,
        }}
      />
    </span>
  );
}

/** Holders by class with shares and their share of fully diluted shares, and a total. */
export function CapTable({ cap, views }: { cap: CapTableData; views?: TableViewsApi }) {
  const rows = useMemo<Row[]>(
    () => [
      ...cap.holders,
      {
        holder: 'Total',
        holder_kind: 'total',
        share_class: '',
        shares: cap.fd_shares,
        fraction: 1,
        total: true,
      },
    ],
    [cap],
  );
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('holder', {
          header: 'Holder',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <span style={{ fontWeight: row.original.total ? 700 : 600 }}>
              {holderName(row.original)}
            </span>
          ),
        }),
        helper.accessor('share_class', {
          header: 'Class',
          sortFn: 'alphanumeric',
          cell: ({ row }) =>
            row.original.total ? null : (
              <span style={{ color: 'var(--tst-text-2)' }}>
                {shareClassText(row.original.share_class, row.original.holder_kind)}
              </span>
            ),
        }),
        helper.accessor('shares', {
          header: 'Shares',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span
              className="tst-num"
              style={{
                display: 'block',
                textAlign: 'right',
                fontWeight: row.original.total ? 700 : 400,
              }}
              data-testid={row.original.total ? 'cap-total-shares' : 'cap-shares'}
            >
              {formatShares(row.original.shares)}
            </span>
          ),
        }),
        helper.accessor('fraction', {
          header: 'Fully diluted',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span
              className="tst-num"
              style={{
                display: 'block',
                textAlign: 'right',
                fontWeight: row.original.total ? 700 : 400,
              }}
              data-testid={row.original.is_founder ? 'cap-founder-pct' : undefined}
            >
              {formatFraction(row.original.fraction)}
            </span>
          ),
        }),
        helper.display({
          id: 'bar',
          header: '',
          cell: ({ row }) =>
            row.original.total ? null : (
              <ShareBar fraction={row.original.fraction} color={holderColor(row.original)} />
            ),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => `${r.holder_kind}:${r.holder}:${r.share_class}`,
    ...(views?.tableProps ?? {}),
  });
  return <DataTable views={views} table={table} label="Holders" rowTestId="cap-row" />;
}
