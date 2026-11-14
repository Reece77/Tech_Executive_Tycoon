import {
  type CellData,
  type RowData,
  type TableFeatures,
  columnOrderingFeature,
  columnVisibilityFeature,
  createSortedRowModel,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  tableFeatures,
} from '@tanstack/react-table';

/** Shared features for game tables: sortable headers, hideable and reorderable columns. */
export const gameTableFeatures = tableFeatures({
  rowSortingFeature,
  columnVisibilityFeature,
  columnOrderingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { basic: sortFn_basic, alphanumeric: sortFn_alphanumeric },
});
export type GameTableFeatures = typeof gameTableFeatures;

declare module '@tanstack/react-table' {
  // The glossary term a column header explains (M7b); the column id when unset. The type
  // parameters must match the library's declaration to merge with it.
  /* eslint-disable @typescript-eslint/no-unused-vars */
  interface ColumnMeta<
    TFeatures extends TableFeatures,
    TData extends RowData,
    TValue extends CellData = CellData,
  > {
    term?: string;
  }
  /* eslint-enable @typescript-eslint/no-unused-vars */
}

/** The glossary id of a column header: `meta.term`, else the column id. */
export function columnTerm(column: {
  id: string;
  columnDef: { meta?: { term?: string } };
}): string {
  return column.columnDef.meta?.term ?? column.id;
}

// M30: a long table renders only the rows near its viewport (windowing in our own component;
// TanStack Virtual is not a dependency). Shorter tables render every row, as before.
export const WINDOW_FROM = 200; // rows: tables longer than this scroll inside their panel
export const OVERSCAN = 20; // rows rendered above and below the visible ones
export const ROW_PX = 33; // a row's height until the first rendered row is measured
export const VIEW_PX = 700; // the viewport's height until it is measured (and in tests: no layout)

/** The rows of a windowed table to render, and the space the others take above and below. */
export function rowWindow(
  count: number,
  scrollTop: number,
  viewport: number,
  rowPx: number,
): { start: number; end: number; before: number; after: number } {
  const first = Math.floor(scrollTop / rowPx);
  const start = Math.max(0, first - OVERSCAN);
  const end = Math.min(count, Math.ceil((scrollTop + viewport) / rowPx) + OVERSCAN);
  return { start, end, before: start * rowPx, after: Math.max(0, count - end) * rowPx };
}
