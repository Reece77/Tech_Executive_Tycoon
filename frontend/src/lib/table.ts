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
