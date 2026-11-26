import { Button, Group, Stack } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { useCustomScenarios, useDeleteCustom, type CustomCard } from '../hooks/editor';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// The Scenarios screen's Custom section (M52, formulas.md 66.2): each custom scenario in
// saves/scenarios with its best result, from the custom results file (kept apart from M51's
// results, the Hall of Fame and achievements).

const helper = createColumnHelper<GameTableFeatures, CustomCard>();

export function CustomScenarios() {
  const { data, error, isPending } = useCustomScenarios();
  const remove = useDeleteCustom();
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('label', {
          header: 'Custom scenario',
          meta: { term: 'custom.scenario' },
          cell: ({ row }) => (
            <Stack gap={2}>
              <span style={{ fontWeight: 600 }}>{row.original.label}</span>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.slug}.yaml
                {row.original.opened_from ? ` · from ${row.original.opened_from}` : ''}
              </span>
            </Stack>
          ),
        }),
        helper.accessor('year', { header: 'Start', meta: { term: 'scenarios.start' } }),
        helper.accessor((c) => c.goal ?? '', {
          id: 'goal',
          header: 'Goal',
          meta: { term: 'scenarios.goal' },
          cell: ({ row }) =>
            row.original.goal
              ? `${row.original.goal} by ${row.original.deadline_label ?? ''}`
              : 'Open play',
        }),
        helper.accessor((c) => c.best?.adjusted ?? -1, {
          id: 'best',
          header: 'Best result',
          meta: { term: 'custom.best' },
          cell: ({ row }) => {
            const best = row.original.best;
            if (!best) return <span className="tst-muted">Not played</span>;
            return `${best.result === 'success' ? 'Won' : 'Lost'} · ${best.adjusted} · ${best.date_label}`;
          },
        }),
        helper.display({
          id: 'actions',
          header: '',
          meta: { term: 'custom.actions' },
          cell: ({ row }) => (
            <Group gap={6}>
              <Button
                component={Link}
                to={`/editor?custom=${row.original.slug}`}
                size="xs"
                variant="default"
                data-testid={`custom-edit-${row.original.slug}`}
              >
                Edit or play
              </Button>
              <Button
                size="xs"
                variant="subtle"
                color="red"
                disabled={remove.isPending}
                onClick={() => remove.mutate(row.original.slug)}
                data-testid={`custom-delete-${row.original.slug}`}
              >
                Delete
              </Button>
            </Group>
          ),
        }),
      ]),
    [remove],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: data ?? [],
    getRowId: (c) => c.slug,
  });
  return (
    <Panel title="Custom" testId="custom-scenarios">
      {isPending ? (
        <Loading />
      ) : error ? (
        <LoadError title="Could not load custom scenarios" error={error} />
      ) : (
        <DataTable
          table={table}
          label="Custom scenarios"
          rowTestId="custom-row"
          empty="No custom scenarios yet: make one in the scenario editor."
        />
      )}
    </Panel>
  );
}
