import { NativeSelect, SegmentedControl } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { DataTable } from '../../components/DataTable';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import {
  useDivisionStatements,
  type DivisionColumn,
  type StatementPeriodKind,
} from '../../hooks/api';
import { formatThousands } from '../../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const PERIODS: { value: StatementPeriodKind; label: string }[] = [
  { value: 'month', label: 'Month' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'year', label: 'Year' },
];

type LineKey = keyof Pick<
  DivisionColumn,
  | 'revenue_cents'
  | 'salaries_benefits_cents'
  | 'hosting_cents'
  | 'marketing_cents'
  | 'office_cents'
  | 'tools_ga_cents'
  | 'direct_profit_cents'
  | 'shared_services_cents'
  | 'operating_profit_cents'
>;

const LINES: { key: LineKey; label: string; strong?: boolean; cost?: boolean }[] = [
  { key: 'revenue_cents', label: 'Revenue', strong: true },
  { key: 'salaries_benefits_cents', label: 'Salaries and benefits', cost: true },
  { key: 'hosting_cents', label: 'Hosting', cost: true },
  { key: 'marketing_cents', label: 'Marketing', cost: true },
  { key: 'office_cents', label: 'Office', cost: true },
  { key: 'tools_ga_cents', label: 'Tools and G&A', cost: true },
  { key: 'direct_profit_cents', label: 'Direct profit', strong: true },
  { key: 'shared_services_cents', label: 'Shared services' },
  { key: 'operating_profit_cents', label: 'Operating profit', strong: true },
];

const SHARED_TIP =
  'Corporate operating costs shared by headcount among corporate and the central divisions. ' +
  'A reporting line only: no cash moves between divisions.';

/** Finance > Divisions (M8): each division's statement and its shared-services allocation. */
export function DivisionsTab({ saveId }: { saveId: string }) {
  const [period, setPeriod] = useState<StatementPeriodKind>('month');
  const [index, setIndex] = useState(0);
  const q = useDivisionStatements(saveId, period);
  if (q.error) return <LoadError title="Could not load division statements" error={q.error} />;
  if (!q.data) return <Loading />;
  const periods = q.data.periods;
  const shown = periods[Math.min(index, Math.max(periods.length - 1, 0))];
  const divisions = shown?.columns.filter((c) => c.division_id !== null) ?? [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="divisions-tab">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <SegmentedControl
          data={PERIODS}
          value={period}
          onChange={(v) => {
            setPeriod(v as StatementPeriodKind);
            setIndex(0);
          }}
        />
        {periods.length > 0 && (
          <NativeSelect
            aria-label="Period"
            value={String(index)}
            data={periods.map((p, i) => ({ value: String(i), label: p.label }))}
            onChange={(e) => setIndex(Number(e.currentTarget.value))}
          />
        )}
      </div>
      {!shown || divisions.length === 0 ? (
        <Panel title="Divisions">
          <p className="tst-muted">
            No division has a month on the books yet. Divisions open at stage 3; create one on the
            Org screen.
          </p>
        </Panel>
      ) : (
        <>
          <Panel title={`Division statement · ${shown.label}`}>
            <DivisionTable columns={shown.columns} />
            <p className="tst-muted" style={{ fontSize: 12 }}>
              {SHARED_TIP} Amounts in thousands of dollars.
            </p>
          </Panel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {divisions.map((c) => (
              <Panel key={c.name} title={c.name} style={{ flex: '1 1 200px' }}>
                <div className="tst-row">
                  <span>Operating margin</span>
                  <span className="tst-num">
                    {c.operating_margin === null
                      ? '—'
                      : `${(c.operating_margin * 100).toFixed(0)}%`}
                  </span>
                </div>
                <div className="tst-row">
                  <span>Revenue growth, 12 months</span>
                  <span className="tst-num">
                    {c.revenue_growth_12m === null
                      ? '—'
                      : `${(c.revenue_growth_12m * 100).toFixed(0)}%`}
                  </span>
                </div>
                <div className="tst-row">
                  <span>Staff</span>
                  <span className="tst-num">{c.headcount}</span>
                </div>
              </Panel>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type Line = (typeof LINES)[number];
const helper = createColumnHelper<GameTableFeatures, Line>();

function DivisionTable({ columns: cols }: { columns: readonly DivisionColumn[] }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: 'line',
          header: '$k',
          cell: ({ row }) => (
            <span
              style={{ fontWeight: row.original.strong ? 600 : 400 }}
              title={row.original.key === 'shared_services_cents' ? SHARED_TIP : undefined}
            >
              {row.original.label}
            </span>
          ),
        }),
        ...cols.map((c) =>
          helper.display({
            id: `d${c.division_id ?? c.name}`,
            header: c.name,
            cell: ({ row }) => {
              const line = row.original;
              if (line.key === 'shared_services_cents' && c.embedded) return 'embedded';
              const value = line.cost ? -c[line.key] : c[line.key];
              return (
                <span
                  className="tst-num"
                  style={{
                    color: value < 0 ? 'var(--tst-warn)' : undefined,
                    fontWeight: line.strong ? 600 : 400,
                  }}
                >
                  {formatThousands(value)}
                </span>
              );
            },
          }),
        ),
      ]),
    [cols],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: LINES,
    getRowId: (l) => l.key,
  });
  return <DataTable table={table} label="Division statement" rowTestId="division-line" />;
}
