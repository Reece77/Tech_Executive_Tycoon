import { Button, Checkbox, Menu, TextInput, UnstyledButton } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { AttributeRange } from '../components/AttributeRange';
import { DataTable } from '../components/DataTable';
import { KpiTile } from '../components/KpiTile';
import { MoraleBar } from '../components/MoraleBar';
import { LoadError, Loading, ScreenTitle } from '../components/ScreenState';
import { StatusChip } from '../components/StatusChip';
import {
  useNewGameMeta,
  useOverview,
  usePeople,
  type NewGameMeta,
  type Overview,
  type Person,
} from '../hooks/api';
import { byStrength } from '../lib/attr';
import { formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import { statusOf } from '../lib/status';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

type View = 'overview' | 'skills';
const helper = createColumnHelper<GameTableFeatures, Person>();
const TOP_SKILLS = 3;

function overviewColumns(saveId: string) {
  return helper.columns([
    helper.accessor('name', {
      header: 'Name',
      sortFn: 'alphanumeric',
      enableHiding: false,
      cell: ({ row }) => (
        <Link
          to={`/game/${saveId}/people/${row.original.person_id}`}
          style={{ fontWeight: 600, textDecoration: 'none' }}
        >
          {row.original.name}
        </Link>
      ),
    }),
    helper.accessor((p) => p.role_label ?? '', {
      id: 'role',
      header: 'Role',
      sortFn: 'alphanumeric',
    }),
    helper.accessor((p) => p.level ?? '', {
      id: 'level',
      header: 'Level',
      sortFn: 'alphanumeric',
      cell: ({ getValue }) => (
        <span style={{ color: 'var(--tst-text-2)' }}>{humanize(getValue())}</span>
      ),
    }),
    helper.accessor('age', {
      header: 'Age',
      sortFn: 'basic',
      cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
    }),
    helper.accessor((p) => (p.is_founder ? undefined : p.employment?.salary_cents), {
      id: 'salary',
      header: 'Salary',
      sortFn: 'basic',
      sortUndefined: 'last',
      cell: ({ row }) => (
        <span className="tst-num">
          {row.original.is_founder || !row.original.employment
            ? '—'
            : formatMoneyWhole(row.original.employment.salary_cents)}
        </span>
      ),
    }),
    helper.accessor((p) => p.morale ?? undefined, {
      id: 'morale',
      header: 'Morale',
      sortFn: 'basic',
      sortUndefined: 'last',
      cell: ({ row }) => <MoraleBar morale={row.original.morale} width={64} />,
    }),
    helper.display({
      id: 'form',
      header: 'Form',
      cell: () => <span className="tst-muted">From M3</span>,
    }),
    helper.display({
      id: 'top',
      header: 'Top skills',
      cell: ({ row }) => (
        <span style={{ display: 'flex', gap: 10 }}>
          {[...row.original.skills]
            .sort(byStrength)
            .slice(0, TOP_SKILLS)
            .map((s) => (
              <span key={s.key} style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                <span className="tst-muted" style={{ fontSize: 12 }}>
                  {s.label}
                </span>
                <AttributeRange range={s.range} label={s.label} />
              </span>
            ))}
        </span>
      ),
    }),
    helper.accessor((p) => statusOf(p), {
      id: 'status',
      header: 'Status',
      sortFn: 'alphanumeric',
      cell: ({ row }) => <StatusChip status={statusOf(row.original)} />,
    }),
  ]);
}

function skillColumns(saveId: string, meta: NewGameMeta) {
  return helper.columns([
    helper.accessor('name', {
      header: 'Name',
      sortFn: 'alphanumeric',
      enableHiding: false,
      cell: ({ row }) => (
        <Link
          to={`/game/${saveId}/people/${row.original.person_id}`}
          style={{ fontWeight: 600, textDecoration: 'none' }}
        >
          {row.original.name}
        </Link>
      ),
    }),
    helper.accessor((p) => p.role_label ?? '', {
      id: 'role',
      header: 'Role',
      sortFn: 'alphanumeric',
    }),
    ...meta.skills.map((skill) =>
      helper.accessor(
        (p) => {
          const r = p.skills.find((s) => s.key === skill.key)?.range;
          return r ? r.min + r.max : 0; // sort by midpoint (display order only)
        },
        {
          id: skill.key,
          header: skill.label,
          sortFn: 'basic',
          sortDescFirst: true,
          cell: ({ row }) => {
            const attr = row.original.skills.find((s) => s.key === skill.key);
            return attr ? <AttributeRange range={attr.range} label={attr.label} /> : null;
          },
        },
      ),
    ),
  ]);
}

export function PeopleScreen() {
  const { saveId = '' } = useParams();
  const people = usePeople(saveId);
  const overview = useOverview(saveId);
  const meta = useNewGameMeta();
  const error = people.error ?? overview.error ?? meta.error;
  if (error) return <LoadError title="Could not load your people" error={error} />;
  if (!people.data || !overview.data || !meta.data) return <Loading />;
  return (
    <PeopleBody saveId={saveId} people={people.data} meta={meta.data} overview={overview.data} />
  );
}

function PeopleBody({
  saveId,
  people,
  meta,
  overview,
}: {
  saveId: string;
  people: Person[];
  meta: NewGameMeta;
  overview: Overview;
}) {
  const [view, setView] = useState<View>('overview');
  const [filter, setFilter] = useState('');
  const columns = useMemo(
    () => (view === 'overview' ? overviewColumns(saveId) : skillColumns(saveId, meta)),
    [view, saveId, meta],
  );
  const data = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return people;
    return people.filter(
      (p) => p.name.toLowerCase().includes(q) || (p.role_label ?? '').toLowerCase().includes(q),
    );
  }, [people, filter]);
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data,
    getRowId: (p) => String(p.person_id),
  });

  const interestLabel = new Map(meta.interests.map((i) => [i.key, i.label]));
  const team = overview.team;
  return (
    <>
      <ScreenTitle
        aside={
          <>
            <div
              role="group"
              aria-label="Column view"
              style={{
                display: 'flex',
                border: '1px solid var(--tst-border)',
                borderRadius: 6,
                overflow: 'hidden',
              }}
            >
              {(['overview', 'skills'] as const).map((v, i) => (
                <UnstyledButton
                  key={v}
                  aria-pressed={view === v}
                  onClick={() => setView(v)}
                  style={{
                    fontSize: 13,
                    padding: '8px 14px',
                    minHeight: 36,
                    color: view === v ? 'var(--tst-text)' : 'var(--tst-text-2)',
                    background: view === v ? 'var(--tst-panel-active)' : 'transparent',
                    borderLeft: i ? '1px solid var(--tst-border)' : 0,
                  }}
                >
                  {humanize(v)}
                </UnstyledButton>
              ))}
            </div>
            <Menu closeOnItemClick={false} position="bottom-start">
              <Menu.Target>
                <Button variant="default" size="sm" h={36}>
                  Columns
                </Button>
              </Menu.Target>
              <Menu.Dropdown mah={360} style={{ overflowY: 'auto' }}>
                {table
                  .getAllLeafColumns()
                  .filter((c) => c.getCanHide())
                  .map((c) => (
                    <Menu.Item key={c.id} onClick={() => c.toggleVisibility()}>
                      <Checkbox
                        size="xs"
                        readOnly
                        checked={c.getIsVisible()}
                        label={typeof c.columnDef.header === 'string' ? c.columnDef.header : c.id}
                      />
                    </Menu.Item>
                  ))}
              </Menu.Dropdown>
            </Menu>
            <TextInput
              ml="auto"
              w={200}
              type="search"
              placeholder="Name or role"
              aria-label="Filter by name or role"
              leftSection={<span style={{ fontSize: 12 }}>Filter</span>}
              leftSectionWidth={48}
              value={filter}
              onChange={(e) => setFilter(e.currentTarget.value)}
            />
          </>
        }
      >
        People
      </ScreenTitle>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <KpiTile
          label="Headcount"
          value={String(team.headcount)}
          note={team.on_notice ? `${team.on_notice} on notice` : 'None on notice'}
          testId="people-headcount"
        />
        <KpiTile
          label="Monthly people cost"
          value={formatMoneyWhole(team.people_cost_cents)}
          note="Salaries, benefits, office"
          testId="people-cost"
        />
        <KpiTile
          label="Average morale"
          value={team.avg_morale === null ? 'n/a' : formatWhole(team.avg_morale)}
          note="Employees only"
          testId="people-morale"
        />
        <KpiTile
          label="Company mission"
          small
          value={overview.mission.map((k) => interestLabel.get(k) ?? k).join(' · ') || 'None'}
          note="Shared interests lift morale"
        />
      </div>
      <DataTable
        table={table}
        label="Roster"
        rowTestId="person-row"
        empty="No one matches the filter."
      />
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Skill values are ranges until you know someone well; colors follow the range midpoint: grey
        1–5, white 6–10, green 11–15, gold 16–20.
      </p>
    </>
  );
}
