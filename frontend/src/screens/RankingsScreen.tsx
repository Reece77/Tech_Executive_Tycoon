// Industry rankings (M15b, formulas.md 30.4): each January's three lists, from public or
// revealed measures: Top 50 by revenue, Best places to work and Most innovative.
import { NativeSelect } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import { useRankings, type RankingList } from '../hooks/modes';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

type Entry = RankingList['entries'][number];
const helper = createColumnHelper<GameTableFeatures, Entry>();
const TERMS: Record<string, string> = {
  revenue: 'rank.revenue',
  places: 'rank.places',
  innovative: 'rank.innovative',
};

export function RankingsScreen() {
  const { saveId = '' } = useParams();
  const [year, setYear] = useState<number | undefined>(undefined);
  const rankings = useRankings(saveId, year);
  if (rankings.error)
    return <LoadError title="Could not load the rankings" error={rankings.error} />;
  if (!rankings.data) return <Loading />;
  const r = rankings.data;
  return (
    <>
      <ScreenTitle
        aside={
          r.years.length > 1 && (
            <NativeSelect
              aria-label="Year"
              value={String(r.year ?? '')}
              onChange={(e) => setYear(Number(e.currentTarget.value))}
              data={r.years.map((y) => String(y))}
              data-testid="rankings-year"
              style={{ marginLeft: 'auto' }}
            />
          )
        }
      >
        Rankings {r.year ?? ''}
      </ScreenTitle>
      {r.year === null || r.year === undefined ? (
        <Panel title="No rankings yet" testId="rankings-empty">
          <span className="tst-muted">
            The first lists are published in January, from the year before.{' '}
            <Link to={`/game/${saveId}/competitors`}>Back to competitors</Link>
          </span>
        </Panel>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
          {r.lists.map((list) => (
            <section
              key={list.kind}
              aria-label={list.label}
              style={{ flex: '1 1 320px', minWidth: 0 }}
              data-testid={`rankings-${list.kind}`}
            >
              <Panel title={list.label}>
                <Term term={TERMS[list.kind] ?? 'rankings'}>
                  <span className="tst-muted" style={{ fontSize: 12 }}>
                    How this list is made
                  </span>
                </Term>
                <RankingTable saveId={saveId} list={list} />
              </Panel>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function RankingTable({ saveId, list }: { saveId: string; list: RankingList }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('place', {
          header: '#',
          meta: { term: 'rank.place' },
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
        helper.accessor('name', {
          header: 'Company',
          enableSorting: false,
          cell: ({ row }) =>
            row.original.is_you ? (
              <strong data-testid="rankings-you">{row.original.name} (you)</strong>
            ) : (
              <Link to={`/game/${saveId}/competitors/${row.original.company_id}`}>
                {row.original.name}
              </Link>
            ),
        }),
        helper.accessor('value_label', {
          meta: { term: 'rank.value' },
          header: list.kind === 'revenue' ? 'Revenue a year' : 'Score',
          enableSorting: false,
          cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
        }),
      ]),
    [saveId, list.kind],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: list.entries,
    getRowId: (e) => String(e.company_id),
  });
  return <DataTable table={table} label={list.label} rowTestId="ranking-row" empty="Nobody yet." />;
}
