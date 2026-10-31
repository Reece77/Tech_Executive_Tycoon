import {
  functionalUpdate,
  type ColumnOrderState,
  type ColumnVisibilityState,
  type SortingState,
  type Updater,
} from '@tanstack/react-table';
import { useState } from 'react';
import { useSaveTableViews, useUiSettings, type TableView, type TableViews } from './api';

// Saved column views (M7b; spec 13): one hook gives a TanStack table its column visibility,
// order and sort, named views, the built-in Default view (it cannot be deleted), and the view
// last used. Views live in saves/ui_settings.json through the API, shared by every save.

export const DEFAULT_VIEW = 'Default';

export interface ViewState {
  sorting: SortingState;
  columnVisibility: ColumnVisibilityState;
  columnOrder: ColumnOrderState;
}

const EMPTY: ViewState = { sorting: [], columnVisibility: {}, columnOrder: [] };

function stateOf(view: TableView | undefined, base: ViewState): ViewState {
  if (!view) return base;
  return {
    sorting: (view.sort ?? []).map((s) => ({ id: s.id, desc: s.desc ?? false })),
    columnVisibility: view.visibility ?? {},
    columnOrder: view.order ?? [],
  };
}

function viewOf(name: string, state: ViewState): TableView {
  return {
    name,
    visibility: state.columnVisibility as Record<string, boolean>,
    order: state.columnOrder,
    sort: state.sorting.map((s) => ({ id: s.id, desc: s.desc })),
  };
}

/** A short summary of a view's sort for the menu: "Salary ↓". */
export function sortSummary(view: TableView, label: (id: string) => string): string {
  const sort = view.sort ?? [];
  if (sort.length === 0) return 'No sort';
  return sort.map((s) => `${label(s.id)} ${s.desc ? '↓' : '↑'}`).join(', ');
}

export interface TableViewsApi {
  tableId: string;
  /** Spread into useTable's options. */
  tableProps: {
    state: ViewState;
    onSortingChange: (u: Updater<SortingState>) => void;
    onColumnVisibilityChange: (u: Updater<ColumnVisibilityState>) => void;
    onColumnOrderChange: (u: Updater<ColumnOrderState>) => void;
  };
  /** Pass to useTable: `state` and the three change handlers. */
  state: ViewState;
  onSortingChange: (u: Updater<SortingState>) => void;
  onColumnVisibilityChange: (u: Updater<ColumnVisibilityState>) => void;
  onColumnOrderChange: (u: Updater<ColumnOrderState>) => void;
  views: TableView[];
  current: string;
  modified: boolean; // the table differs from the current view
  select: (name: string) => void;
  saveAs: (name: string) => void;
  remove: (name: string) => void;
}

/**
 * The views of one table. `base` is the Default view (e.g. a screen's initial sort); the
 * state shown is the current view until the player changes the table, then their changes.
 */
export function useTableViews(tableId: string, base: ViewState = EMPTY): TableViewsApi {
  const settings = useUiSettings();
  const save = useSaveTableViews();
  const stored: TableViews = settings.data?.tables?.[tableId] ?? {
    views: [],
    current: DEFAULT_VIEW,
  };
  const views = stored.views ?? [];
  const current = stored.current ?? DEFAULT_VIEW;
  const [override, setOverride] = useState<{ table: string; state: ViewState } | null>(null);
  const saved = stateOf(
    views.find((v) => v.name === current),
    base,
  );
  const mine = override && override.table === tableId ? override.state : null;
  const state = mine ?? saved;

  const write = (next: TableViews) => save.mutate({ tableId, views: next });
  const change =
    <K extends keyof ViewState>(key: K) =>
    (u: Updater<ViewState[K]>) =>
      setOverride({ table: tableId, state: { ...state, [key]: functionalUpdate(u, state[key]) } });

  const handlers = {
    onSortingChange: change('sorting'),
    onColumnVisibilityChange: change('columnVisibility'),
    onColumnOrderChange: change('columnOrder'),
  };
  return {
    tableId,
    tableProps: { state, ...handlers },
    state,
    ...handlers,
    views,
    current,
    modified: mine !== null,
    select: (name) => {
      setOverride(null);
      write({ views, current: name });
    },
    saveAs: (name) => {
      const clean = name.trim();
      if (!clean || clean === DEFAULT_VIEW) return;
      const others = views.filter((v) => v.name !== clean);
      setOverride(null);
      write({ views: [...others, viewOf(clean, state)], current: clean });
    },
    remove: (name) => {
      if (name === DEFAULT_VIEW) return;
      setOverride(null);
      write({
        views: views.filter((v) => v.name !== name),
        current: current === name ? DEFAULT_VIEW : current,
      });
    },
  };
}
