import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, type HTMLAttributes } from 'react';
import { Link } from 'react-router';
import type { MarketProduct, MarketSegment } from '../hooks/api';
import { formatMoneyWhole } from '../lib/format';
import { formatAppeal, formatCount, formatPercent, formatScore } from '../lib/products';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';

const helper = createColumnHelper<GameTableFeatures, MarketProduct>();

/** "621,600 businesses · 122,900 use a product, 498,700 do not yet · typical price $50". */
export function segmentSummary(s: MarketSegment): string {
  const noun = s.counts_users ? 'users' : 'businesses';
  const parts = [
    `${formatCount(s.addressable)} ${noun}`,
    `${formatCount(s.served)} use a product, ${formatCount(s.unserved)} do not yet`,
    `typical price ${formatMoneyWhole(s.reference_price_cents)}`,
  ];
  if (s.reach === 'sales') parts.push('sales-led');
  if (!s.player_sells) parts.push('you do not sell here');
  return parts.join(' · ');
}

/** Every product selling in one segment, sorted by appeal; the player's rows highlighted. */
export function MarketTable({
  segment,
  productHref,
}: {
  segment: MarketSegment;
  productHref?: (productId: number) => string;
}) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Product',
          sortFn: 'alphanumeric',
          cell: ({ row }) =>
            row.original.is_player && productHref ? (
              <Link
                to={productHref(row.original.product_id)}
                style={{ fontWeight: 600, textDecoration: 'none' }}
              >
                {row.original.name}
              </Link>
            ) : (
              <span style={{ fontWeight: 600 }}>{row.original.name}</span>
            ),
        }),
        helper.accessor('company_name', {
          header: 'Company',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <span style={{ color: 'var(--tst-text-2)' }}>
              {row.original.company_name}
              {row.original.is_player ? ' (you)' : ''}
              {row.original.status === 'sunset' ? ' · sunset' : ''}
            </span>
          ),
        }),
        helper.accessor('quality', {
          header: 'Quality',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatScore(getValue())}</span>,
        }),
        helper.accessor('feature_score', {
          header: 'Features',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatScore(getValue())}</span>,
        }),
        helper.accessor('brand', {
          header: 'Brand',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatScore(getValue())}</span>,
        }),
        helper.accessor('price_cents', {
          header: 'Price a month',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        helper.accessor('appeal', {
          header: 'Appeal',
          sortFn: 'basic',
          sortDescFirst: true,
          cell: ({ getValue }) => (
            <span className="tst-num" style={{ fontWeight: 600 }}>
              {formatAppeal(getValue())}
            </span>
          ),
        }),
        helper.accessor('customers', {
          header: 'Customers',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatCount(getValue())}</span>,
        }),
        helper.accessor('share_of_served', {
          header: 'Share of buyers',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="tst-num" style={{ width: 48 }}>
                {formatPercent(row.original.share_of_served)}
              </span>
              <span
                aria-hidden="true"
                style={{ width: 90, height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
              >
                <span
                  style={{
                    display: 'block',
                    height: 6,
                    borderRadius: 3,
                    background: row.original.is_player ? 'var(--tst-accent)' : '#6B7686',
                    width: `${Math.max(row.original.share_of_served * 100, 1)}%`,
                  }}
                />
              </span>
            </span>
          ),
        }),
      ]),
    [productHref],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: segment.products,
    getRowId: (p) => String(p.product_id),
    initialState: { sorting: [{ id: 'appeal', desc: true }] },
  });
  return (
    <DataTable
      table={table}
      label={`${segment.label} market`}
      rowTestId="market-row"
      empty="Nobody sells here yet."
      rowProps={(p) =>
        ({
          'data-selected': p.is_player,
          'data-mine': p.is_player,
        }) as HTMLAttributes<HTMLTableRowElement>
      }
    />
  );
}
