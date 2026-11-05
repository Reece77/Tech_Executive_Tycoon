// Recruitment fixes (M14b, formulas.md 29.5): Replace for someone who resigned or was poached
// lately, and the search-by-interest filter for searches and hiring plans. Values and the
// reasons Replace is not offered come from the API.
import { Alert, Button, NativeSelect } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Link } from 'react-router';
import type { NewGameMeta } from '../hooks/api';
import { useReplace, useReplaceable, type Replaceable } from '../hooks/press';
import { humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Panel } from './ScreenState';
import { Term } from './Term';

const helper = createColumnHelper<GameTableFeatures, Replaceable>();
const ANY = '';

export function ReplacePanel({ saveId }: { saveId: string }) {
  const rows = useReplaceable(saveId);
  if (!rows.data || rows.data.length === 0) return null;
  return <ReplaceBody saveId={saveId} rows={rows.data} />;
}

export function ReplaceBody({ saveId, rows }: { saveId: string; rows: Replaceable[] }) {
  const replace = useReplace(saveId);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Name',
          sortFn: 'alphanumeric',
          cell: ({ row }) => (
            <Link
              to={`/game/${saveId}/people/${row.original.person_id}`}
              style={{ fontWeight: 600, textDecoration: 'none' }}
            >
              {row.original.name}
            </Link>
          ),
        }),
        helper.accessor('role', { header: 'Role', sortFn: 'alphanumeric' }),
        helper.accessor('level', {
          header: 'Level',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => humanize(getValue()),
        }),
        helper.accessor('reason', {
          id: 'replace.reason',
          header: 'Left',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => (getValue() === 'poached' ? 'Poached' : 'Resigned'),
        }),
        helper.display({
          id: 'replace',
          header: '',
          cell: ({ row }) => (
            // The wrapper carries the reason: a disabled button shows no tooltip of its own.
            <span title={row.original.problem ?? undefined} data-testid="replace-problem">
              <Button
                size="compact-sm"
                disabled={!row.original.can_replace}
                title={row.original.problem ?? undefined}
                loading={replace.isPending && replace.variables === row.original.person_id}
                onClick={() => replace.mutate(row.original.person_id)}
                data-testid={`replace-${row.original.person_id}`}
              >
                Replace
              </Button>
            </span>
          ),
        }),
      ]),
    [saveId, replace],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (r) => String(r.person_id),
  });
  return (
    <Panel
      title="Replace someone who left"
      testId="replace-panel"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="replace">Replace</Term> has your recruiter open a hiring plan for the same role
        and level; it fills faster than a normal search.
      </span>
      <DataTable table={table} label="Replaceable" rowTestId="replace-row" />
      {replace.error && (
        <Alert color="red" withCloseButton onClose={replace.reset}>
          {replace.error.message}
        </Alert>
      )}
      {replace.isSuccess && (
        <span style={{ fontSize: 13, color: 'var(--tst-good)' }} data-testid="replace-started">
          Your recruiter is on it: the plan is under Hiring plans below.
        </span>
      )}
    </Panel>
  );
}

/** "Search by interest" (29.5): only candidates with this revealed interest, for a fee. */
export function InterestFilter({
  interests,
  value,
  onChange,
}: {
  interests: NewGameMeta['interests'];
  value: string | null;
  onChange: (interest: string | null) => void;
}) {
  return (
    <NativeSelect
      label={<Term term="search_by_interest">Search by interest</Term>}
      value={value ?? ANY}
      data-testid="interest-filter"
      onChange={(e) => onChange(e.currentTarget.value || null)}
      data={[
        { value: ANY, label: 'Any interest (no fee)' },
        ...interests.map((i) => ({ value: i.key, label: i.label })),
      ]}
      description={
        value
          ? "Adds a fee to each search: 15% of the role's mid salary."
          : 'Optional: only candidates who care about one thing, for a fee.'
      }
    />
  );
}
