import type { ReactTable, RowData } from '@tanstack/react-table';
import type { HTMLAttributes } from 'react';
import { columnTerm, type GameTableFeatures } from '../lib/table';
import { Term } from './Term';

const ARROWS = { asc: ' ▲', desc: ' ▼' } as const;

interface Props<T extends RowData> {
  table: ReactTable<GameTableFeatures, T>;
  label: string;
  rowTestId?: string;
  selectedRowId?: string;
  empty?: string;
  rowProps?: (row: T) => HTMLAttributes<HTMLTableRowElement>; // e.g. draggable rows (Org)
}

/** Table markup for a TanStack table: header click sorts, wide tables scroll in the panel. */
export function DataTable<T extends RowData>({
  table,
  label,
  rowTestId,
  selectedRowId,
  empty,
  rowProps,
}: Props<T>) {
  const rows = table.getRowModel().rows;
  return (
    <div className="tst-table-wrap">
      <table className="tst-table" aria-label={label}>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => {
                if (header.isPlaceholder) return <th key={header.id} />;
                const sorted = header.column.getIsSorted();
                const toggle = header.column.getToggleSortingHandler();
                return (
                  <th
                    key={header.id}
                    aria-sort={
                      sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined
                    }
                  >
                    {header.column.getCanSort() && toggle ? (
                      <button type="button" onClick={toggle}>
                        <Term term={columnTerm(header.column)}>
                          <table.FlexRender header={header} />
                        </Term>
                        {sorted ? ARROWS[sorted] : ''}
                      </button>
                    ) : (
                      <Term term={columnTerm(header.column)}>
                        <table.FlexRender header={header} />
                      </Term>
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="tst-muted" colSpan={table.getVisibleLeafColumns().length}>
                {empty ?? 'Nothing to show.'}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={row.id}
                data-testid={rowTestId}
                data-selected={row.id === selectedRowId}
                {...rowProps?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
