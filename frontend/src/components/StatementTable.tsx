import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import type { StatementPeriod } from '../hooks/api';
import { formatThousands, pnlLines, type StatementLine } from '../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Term } from './Term';

/** The glossary id of a P&L line: an account code, or a computed line (M7b). */
function lineTerm(id: string): string {
  return /^\d/.test(id) ? `account.${id}` : `line.${id}`;
}

const helper = createColumnHelper<GameTableFeatures, StatementLine>();

/** Profit and loss with the periods side by side, in thousands of dollars. */
export function StatementTable({ periods }: { periods: readonly StatementPeriod[] }) {
  const lines = useMemo(() => pnlLines(periods), [periods]);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: 'label',
          header: '$k',
          meta: { term: 'statement_line' },
          cell: ({ row }) => (
            <span
              style={{
                // Long labels wrap so twelve months fit at 1440 wide (M7c).
                display: 'inline-block',
                minWidth: 120,
                maxWidth: 180,
                whiteSpace: 'normal',
                ...(row.original.indent
                  ? { paddingLeft: 12, color: 'var(--tst-text-2)' }
                  : { fontWeight: row.original.total ? 600 : 400 }),
              }}
            >
              <Term term={lineTerm(row.original.id)}>{row.original.label}</Term>
            </span>
          ),
        }),
        ...periods.map((p, i) =>
          helper.display({
            id: `p${p.first_turn}`,
            meta: { term: 'period' },
            header: () => (
              <span className="tst-num" style={{ display: 'block', textAlign: 'right' }}>
                {p.label}
                {p.complete ? '' : '*'}
              </span>
            ),
            cell: ({ row }) => {
              const value = row.original.values[i];
              return (
                <span
                  className="tst-num"
                  style={{
                    display: 'block',
                    textAlign: 'right',
                    fontWeight: row.original.total ? 600 : 400,
                    color: value < 0 ? 'var(--tst-warn)' : undefined,
                  }}
                  data-testid={row.original.id === 'net' ? 'pnl-net' : undefined}
                >
                  {formatThousands(value)}
                </span>
              );
            },
          }),
        ),
      ]),
    [periods],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: lines,
    getRowId: (l) => l.id,
  });
  return (
    <DataTable
      table={table}
      label="Profit and loss"
      rowTestId="pnl-row"
      empty="No month has closed yet."
      rowProps={(l) => (l.total ? { className: 'tst-subtotal' } : {})}
    />
  );
}
