import { TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { ProductSegment } from '../hooks/api';
import { formatMoneyWhole } from '../lib/format';
import { formatCount, formatFlow, formatPercent, REACH_TEXT } from '../lib/products';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';

const helper = createColumnHelper<GameTableFeatures, ProductSegment>();

export interface PriceEditing {
  prices: Record<string, string>; // the text in each segment's price box
  editing: string | null; // the segment whose price preview is open
  onChange: (segment: string, text: string) => void;
}

/** A product's segments: the editable price and, once it sells, last month's numbers. */
export function SegmentTable({
  segments,
  price,
  selling,
}: {
  segments: ProductSegment[];
  price: PriceEditing;
  selling: boolean; // false in development: price and reach only
}) {
  const { prices, editing, onChange } = price;
  const columns = useMemo(() => {
    const segment = helper.accessor('label', {
      header: 'Segment',
      sortFn: 'alphanumeric',
      cell: ({ getValue }) => <span style={{ fontWeight: 600 }}>{getValue()}</span>,
    });
    const priceCol = helper.accessor((s) => s.price_cents ?? undefined, {
      id: 'price',
      header: 'Price a month',
      sortFn: 'basic',
      sortUndefined: 'last',
      cell: ({ row }) => (
        <TextInput
          size="xs"
          w={110}
          value={prices[row.original.segment] ?? ''}
          placeholder="Set a price"
          aria-label={`${row.original.label} price`}
          data-testid={`price-input-${row.original.segment}`}
          onChange={(e) => onChange(row.original.segment, e.currentTarget.value)}
          styles={{ input: { fontFamily: 'var(--tst-font-mono)' } }}
        />
      ),
    });
    const note = helper.display({
      id: 'note',
      header: '',
      cell: ({ row }) => {
        const s = row.original;
        if (s.segment === editing) {
          return (
            <span className="tst-muted" style={{ fontSize: 12 }}>
              Editing: preview below
            </span>
          );
        }
        if (s.note) {
          return (
            <span style={{ fontSize: 12, color: 'var(--tst-warn)' }} data-testid="capacity-note">
              {s.note}
            </span>
          );
        }
        return null;
      },
    });
    if (!selling) {
      return helper.columns([
        segment,
        helper.accessor('reach', {
          header: 'How it is reached',
          cell: ({ getValue }) => (
            <span style={{ color: 'var(--tst-text-2)' }}>
              {REACH_TEXT[getValue()] ?? getValue()}
            </span>
          ),
        }),
        priceCol,
        helper.display({
          id: 'priced',
          header: '',
          cell: ({ row }) =>
            row.original.price_cents === null ? (
              <span style={{ fontSize: 12, color: 'var(--tst-warn)' }}>Price missing</span>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--tst-good)' }}>Price set</span>
            ),
        }),
        note,
      ]);
    }
    return helper.columns([
      segment,
      priceCol,
      helper.accessor('customers', {
        header: 'Customers',
        sortFn: 'basic',
        cell: ({ row }) => (
          <span className="tst-num" data-testid="segment-customers">
            {formatCount(row.original.customers)}
            {row.original.counts_users ? ' users' : ''}
          </span>
        ),
      }),
      helper.accessor('share_of_served', {
        header: 'Share of buyers',
        sortFn: 'basic',
        cell: ({ getValue }) => <span className="tst-num">{formatPercent(getValue())}</span>,
      }),
      helper.accessor('new_last_month', {
        header: 'New',
        sortFn: 'basic',
        cell: ({ getValue }) => (
          <span className="tst-num" style={{ color: 'var(--tst-good)' }} data-testid="segment-new">
            {formatFlow(getValue(), '+')}
          </span>
        ),
      }),
      helper.accessor('churned_last_month', {
        header: 'Lost',
        sortFn: 'basic',
        cell: ({ getValue }) => (
          <span className="tst-num" style={{ color: 'var(--tst-warn)' }}>
            {formatFlow(getValue(), '-')}
          </span>
        ),
      }),
      helper.accessor((s) => s.churn_rate ?? undefined, {
        id: 'churn',
        header: 'Churn',
        sortFn: 'basic',
        sortUndefined: 'last',
        cell: ({ row }) => (
          <span className="tst-num">
            {row.original.churn_rate === null ? '—' : formatPercent(row.original.churn_rate)}
          </span>
        ),
      }),
      helper.accessor('mrr_cents', {
        header: 'MRR',
        sortFn: 'basic',
        cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
      }),
      note,
    ]);
  }, [selling, prices, editing, onChange]);

  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: segments,
    getRowId: (s) => s.segment,
  });
  return (
    <DataTable
      table={table}
      label="Segments"
      rowTestId="segment-row"
      selectedRowId={editing ?? undefined}
    />
  );
}
