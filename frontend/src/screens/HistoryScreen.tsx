import { Button, NativeSelect, SegmentedControl, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DataTable } from '../components/DataTable';
import { Term } from '../components/Term';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useHallOfFame,
  useHistoryCharts,
  useHistoryStorylines,
  useTimeline,
  type HistoryRow,
  type KpiPoint,
  type TimelineQuery,
} from '../hooks/api';
import { TABLE_SEARCH_ATTR } from '../hooks/useGameHotkeys';
import { useTableViews } from '../hooks/useTableViews';
import { formatMoneyShort, formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

// History (nav key 9, M7b; formulas.md 17.2): the timeline, charts, storylines and the hall
// of fame. Everything comes from the API; the screen only formats and slices for display.

const TABS = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'charts', label: 'Charts' },
  { key: 'storylines', label: 'Storylines' },
  { key: 'fame', label: 'Hall of fame' },
] as const;

const HISTORY_PAGE = 50; // timeline rows per page

export function HistoryScreen() {
  const { saveId = '', tab = 'timeline' } = useParams();
  const current = TABS.find((t) => t.key === tab);
  if (!current) return <Navigate to={`/game/${saveId}/history/timeline`} replace />;
  return (
    <>
      <ScreenTitle>History</ScreenTitle>
      <div role="tablist" aria-label="History" className="tst-tabs">
        {TABS.map((t) => (
          <Link
            key={t.key}
            role="tab"
            aria-selected={t.key === current.key}
            className="tst-tab"
            to={`/game/${saveId}/history/${t.key}`}
            data-testid={`history-tab-${t.key}`}
          >
            {t.label}
          </Link>
        ))}
      </div>
      {current.key === 'timeline' && <TimelineTab saveId={saveId} />}
      {current.key === 'charts' && <ChartsTab saveId={saveId} />}
      {current.key === 'storylines' && <StorylinesTab saveId={saveId} />}
      {current.key === 'fame' && <FameTab saveId={saveId} />}
    </>
  );
}

// --- Timeline ---------------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  people: 'People',
  products: 'Products',
  finance: 'Finance',
  rivals: 'Rivals',
  events: 'Events',
};

const helper = createColumnHelper<GameTableFeatures, HistoryRow>();

function timelineColumns(saveId: string) {
  return helper.columns([
    helper.accessor('date_label', {
      id: 'month',
      header: 'Month',
      enableSorting: false,
      cell: ({ getValue }) => <span className="tst-num">{getValue()}</span>,
    }),
    helper.accessor('category', {
      id: 'category',
      header: 'Category',
      enableSorting: false,
      cell: ({ getValue }) => {
        const c = getValue();
        return c ? <span className="tst-chip">{CATEGORY_LABELS[c] ?? humanize(c)}</span> : null;
      },
    }),
    helper.accessor('title', {
      id: 'what',
      header: 'What happened',
      enableSorting: false,
      cell: ({ row }) => <WhatHappened saveId={saveId} row={row.original} />,
    }),
    helper.accessor('actor', {
      id: 'by',
      header: 'By',
      enableSorting: false,
      cell: ({ row }) => {
        const r = row.original;
        if (r.kind === 'month') return null;
        if (!r.actor) return <span className="tst-muted">—</span>;
        return r.source === 'delegate' ? `${r.actor} (delegate)` : r.actor;
      },
    }),
  ]);
}

function WhatHappened({ saveId, row }: { saveId: string; row: HistoryRow }) {
  if (row.kind === 'month') return <span className="tst-num">{row.title}</span>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span>{row.title}</span>
      {row.detail && row.category === 'events' && (
        <span className="tst-muted" style={{ fontSize: 12 }}>
          {row.detail}
        </span>
      )}
      <span style={{ display: 'flex', gap: 10, fontSize: 12 }}>
        {row.person_id != null && row.person_name && (
          <Link to={`/game/${saveId}/people/${row.person_id}`} data-testid="history-person-link">
            {row.person_name}
          </Link>
        )}
        {row.product_id != null && row.product_name && (
          <Link to={`/game/${saveId}/products/${row.product_id}`}>{row.product_name}</Link>
        )}
        {row.event_id != null && (
          <Link to={`/game/${saveId}/events/${row.event_id}`} data-testid="history-event-link">
            Open the event
          </Link>
        )}
      </span>
    </div>
  );
}

function TimelineTab({ saveId }: { saveId: string }) {
  const [search, setSearch] = useState('');
  const [year, setYear] = useState('');
  const [category, setCategory] = useState('');
  const [source, setSource] = useState('');
  const [person, setPerson] = useState('');
  const [offset, setOffset] = useState(0);
  const query: TimelineQuery = {
    search: search.trim() || undefined,
    year: year ? Number(year) : undefined,
    category: (category || undefined) as TimelineQuery['category'],
    source: (source || undefined) as TimelineQuery['source'],
    person_id: person ? Number(person) : undefined,
    offset,
    limit: HISTORY_PAGE,
  };
  const timeline = useTimeline(saveId, query);
  const columns = useMemo(() => timelineColumns(saveId), [saveId]);
  const views = useTableViews('history.timeline');
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: timeline.data?.rows ?? [],
    getRowId: (r) => r.key,
    ...views.tableProps,
  });
  const reset = (set: (v: string) => void) => (v: string) => {
    set(v);
    setOffset(0);
  };
  const t = timeline.data;
  const page = Math.floor(offset / HISTORY_PAGE) + 1;
  const pages = t ? Math.max(1, Math.ceil(t.total / HISTORY_PAGE)) : 1;
  return (
    <Panel>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <TextInput
          w={240}
          type="search"
          placeholder="Search names, titles…  ( / )"
          aria-label="Search the history"
          value={search}
          onChange={(e) => reset(setSearch)(e.currentTarget.value)}
          data-testid="history-search"
          {...{ [TABLE_SEARCH_ATTR]: '' }}
        />
        <NativeSelect
          aria-label="Year"
          value={year}
          onChange={(e) => reset(setYear)(e.currentTarget.value)}
          data={[{ value: '', label: 'All years' }, ...(t?.years ?? []).map(String)]}
        />
        <NativeSelect
          aria-label="Category"
          value={category}
          onChange={(e) => reset(setCategory)(e.currentTarget.value)}
          data={[
            { value: '', label: 'All categories' },
            ...Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label })),
          ]}
          data-testid="history-category"
        />
        <NativeSelect
          aria-label="Source"
          value={source}
          onChange={(e) => reset(setSource)(e.currentTarget.value)}
          data={[
            { value: '', label: 'Player, delegate, default' },
            { value: 'player', label: 'You' },
            { value: 'delegate', label: 'Delegates' },
            { value: 'default', label: 'Default (at Continue)' },
          ]}
        />
        <NativeSelect
          aria-label="Person"
          value={person}
          onChange={(e) => reset(setPerson)(e.currentTarget.value)}
          data={[
            { value: '', label: 'Everyone' },
            ...(t?.people ?? []).map((p) => ({ value: String(p.id), label: p.name })),
          ]}
        />
      </div>
      {timeline.isPending ? (
        <Loading />
      ) : timeline.error ? (
        <LoadError title="Could not load the history" error={timeline.error} />
      ) : (
        <>
          <p
            className="tst-muted"
            style={{ margin: '0 0 8px', fontSize: 13 }}
            data-testid="history-count"
          >
            {t?.total ?? 0} rows{query.search ? ` match "${query.search}"` : ''} · newest first
          </p>
          <DataTable
            views={views}
            table={table}
            label="Timeline"
            rowTestId="history-row"
            empty="Nothing matches."
            rowProps={(r) =>
              r.kind === 'month'
                ? { style: { color: 'var(--tst-muted)', fontSize: 12 }, className: 'tst-month-row' }
                : {}
            }
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10 }}>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              Month lines come from each month's snapshot
            </span>
            <Button
              ml="auto"
              size="compact-sm"
              variant="default"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - HISTORY_PAGE))}
            >
              Newer
            </Button>
            <span className="tst-num" style={{ fontSize: 12 }}>
              Page {page} of {pages}
            </span>
            <Button
              size="compact-sm"
              variant="default"
              disabled={page >= pages}
              onClick={() => setOffset(offset + HISTORY_PAGE)}
            >
              Older
            </Button>
          </div>
        </>
      )}
    </Panel>
  );
}

// --- Charts -----------------------------------------------------------------------------------

type KpiKey = Exclude<keyof KpiPoint, 'turn' | 'date_label'>;
const KPIS: { key: KpiKey; label: string; money?: boolean }[] = [
  { key: 'arr_cents', label: 'ARR', money: true },
  { key: 'mrr_cents', label: 'MRR', money: true },
  { key: 'cash_cents', label: 'Cash', money: true },
  { key: 'monthly_burn_cents', label: 'Monthly burn', money: true },
  { key: 'payroll_cents', label: 'Payroll', money: true },
  { key: 'headcount', label: 'Headcount' },
  { key: 'avg_morale', label: 'Average morale' },
  { key: 'founder_bp', label: 'Founder ownership (bp)' },
  { key: 'board_confidence', label: 'Board confidence' },
];
const RANGES = { '1y': 12, '3y': 36, all: Infinity } as const;
type Range = keyof typeof RANGES;
const LINE_COLORS = ['#5AA2FF', '#6FCF8E', '#F5C451', '#F5A25D', '#C792EA', '#7DD3FC'];

function lastN<T>(rows: T[], range: Range): T[] {
  const n = RANGES[range];
  return n === Infinity ? rows : rows.slice(-n);
}

function ChartsTab({ saveId }: { saveId: string }) {
  const charts = useHistoryCharts(saveId);
  const [kpi, setKpi] = useState<KpiKey>('arr_cents');
  const [range, setRange] = useState<Range>('all');
  if (charts.isPending) return <Loading />;
  if (charts.error) return <LoadError title="Could not load the charts" error={charts.error} />;
  const def = KPIS.find((k) => k.key === kpi) ?? KPIS[0];
  const points = lastN(charts.data.kpis, range);
  const fmt = (v: number) => (def.money ? formatMoneyShort(v) : formatWhole(v));
  const months = new Set(points.map((p) => p.turn));
  const products = charts.data.products.map((p) => ({
    ...p,
    points: p.points.filter((q) => months.has(q.turn)),
  }));
  const productRows = points.map((p) => {
    const row: Record<string, number | string> = { date_label: p.date_label };
    for (const s of products) {
      const q = s.points.find((x) => x.turn === p.turn);
      if (q) row[`p${s.product_id}`] = q.mrr_cents;
    }
    return row;
  });
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Panel
        title="Company"
        action={
          <div style={{ display: 'flex', gap: 8 }}>
            <NativeSelect
              aria-label="KPI"
              value={kpi}
              onChange={(e) => setKpi(e.currentTarget.value as KpiKey)}
              data={KPIS.map((k) => ({ value: k.key, label: k.label }))}
              data-testid="chart-kpi"
            />
            <SegmentedControl
              value={range}
              onChange={(v) => setRange(v as Range)}
              data={[
                { value: '1y', label: '1 year' },
                { value: '3y', label: '3 years' },
                { value: 'all', label: 'All' },
              ]}
              data-testid="chart-range"
            />
          </div>
        }
      >
        {points.length === 0 ? (
          <p className="tst-muted">No month has closed yet.</p>
        ) : (
          <div role="img" aria-label={`${def.label} by month`}>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={points} margin={{ top: 12, right: 16, bottom: 0, left: 8 }}>
                <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
                <XAxis dataKey="date_label" stroke="var(--tst-muted)" fontSize={11} />
                <YAxis
                  stroke="var(--tst-muted)"
                  fontSize={11}
                  width={64}
                  tickFormatter={(v: number) => fmt(v)}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--tst-panel)',
                    border: '1px solid var(--tst-border)',
                  }}
                  formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
                />
                <Line
                  type="monotone"
                  dataKey={kpi}
                  name={def.label}
                  stroke="var(--tst-accent)"
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
      <Panel title="Products: MRR by month">
        {products.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            No product has a month of history yet.
          </p>
        ) : (
          <>
            <div role="img" aria-label="Each product's MRR by month">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={productRows} margin={{ top: 12, right: 16, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
                  <XAxis dataKey="date_label" stroke="var(--tst-muted)" fontSize={11} />
                  <YAxis
                    stroke="var(--tst-muted)"
                    fontSize={11}
                    width={64}
                    tickFormatter={(v: number) => formatMoneyShort(v)}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--tst-panel)',
                      border: '1px solid var(--tst-border)',
                    }}
                    formatter={(v) => (typeof v === 'number' ? formatMoneyShort(v) : String(v))}
                  />
                  <Legend />
                  {products.map((p, i) => (
                    <Line
                      key={p.product_id}
                      type="monotone"
                      dataKey={`p${p.product_id}`}
                      name={p.name}
                      stroke={LINE_COLORS[i % LINE_COLORS.length]}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <table className="tst-table" aria-label="Products now" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>
                    <Term term="name">Product</Term>
                  </th>
                  <th>
                    <Term term="mrr_cents">MRR</Term>
                  </th>
                  <th>
                    <Term term="customers">Customers</Term>
                  </th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const last = p.points[p.points.length - 1];
                  return (
                    <tr key={p.product_id}>
                      <td>{p.name}</td>
                      <td className="tst-num">{last ? formatMoneyWhole(last.mrr_cents) : '—'}</td>
                      <td className="tst-num">{last ? formatWhole(last.customers) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </Panel>
    </div>
  );
}

// --- Storylines -------------------------------------------------------------------------------

function StorylinesTab({ saveId }: { saveId: string }) {
  const stories = useHistoryStorylines(saveId);
  if (stories.isPending) return <Loading />;
  if (stories.error) return <LoadError title="Could not load storylines" error={stories.error} />;
  if (stories.data.length === 0) {
    return (
      <Panel>
        <p className="tst-muted" style={{ margin: 0 }}>
          No storyline has started yet. Some events open a story that runs over several months.
        </p>
      </Panel>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {stories.data.map((s) => (
        <Panel key={s.storyline_id} title={s.title} label={`Storyline ${s.title}`}>
          <p className="tst-muted" style={{ margin: '0 0 10px', fontSize: 13 }}>
            {s.status === 'active' ? 'Ongoing' : 'Ended'} · from {s.started_label}
            {s.ended_label ? ` to ${s.ended_label}` : ''}
          </p>
          <ol
            style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}
          >
            {s.steps.map((step) => (
              <li key={step.event_id} data-testid="story-step">
                <span className="tst-num tst-muted" style={{ marginRight: 8 }}>
                  {step.date_label}
                </span>
                <Link to={`/game/${saveId}/events/${step.event_id}`} data-testid="story-step-link">
                  {step.title}
                </Link>
                {step.choice && (
                  <span className="tst-muted">
                    {' '}
                    · chose “{step.choice}”{step.by ? ` (${step.by})` : ''}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </Panel>
      ))}
      <SaveIdNote saveId={saveId} />
    </div>
  );
}

function SaveIdNote({ saveId }: { saveId: string }) {
  return (
    <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
      Steps answered by default resolved to their first choice at Continue. See the{' '}
      <Link to={`/game/${saveId}/history/timeline`}>timeline</Link> for every month.
    </p>
  );
}

// --- Hall of fame -----------------------------------------------------------------------------

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      className="tst-row"
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: 12,
        padding: '6px 0',
        borderBottom: '1px solid var(--tst-rule)',
        fontSize: 14,
      }}
    >
      <span className="tst-muted">{label}</span>
      <span className="tst-num" style={{ textAlign: 'right' }}>
        {children}
      </span>
    </div>
  );
}

function FameTab({ saveId }: { saveId: string }) {
  const fame = useHallOfFame(saveId);
  if (fame.isPending) return <Loading />;
  if (fame.error) return <LoadError title="Could not load the hall of fame" error={fame.error} />;
  const f = fame.data;
  const people = (
    title: string,
    rows: typeof f.best_hires,
    show: (r: (typeof f.best_hires)[number]) => string,
  ) => (
    <div>
      <h3 className="tst-ptitle" style={{ marginTop: 12 }}>
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0, fontSize: 13 }}>
          No one yet.
        </p>
      ) : (
        rows.map((r) => (
          <Fact key={`${title}-${r.person_id}`} label={r.name}>
            <Link to={`/game/${saveId}/people/${r.person_id}`} style={{ color: 'inherit' }}>
              {show(r)}
            </Link>
          </Fact>
        ))
      )}
    </div>
  );
  return (
    <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 16,
        }}
      >
        <Panel title="Company records">
          <Fact label="Peak ARR">
            {f.peak_arr ? `${formatMoneyShort(f.peak_arr.value)} · ${f.peak_arr.date_label}` : '—'}
          </Fact>
          <Fact label="Peak headcount">
            {f.peak_headcount ? `${f.peak_headcount.value} · ${f.peak_headcount.date_label}` : '—'}
          </Fact>
          <Fact label="Biggest round">
            {f.biggest_round
              ? `${f.biggest_round.series} ${formatMoneyShort(f.biggest_round.amount_cents)}${f.biggest_round.lead ? ` · ${f.biggest_round.lead}` : ''} · ${f.biggest_round.date_label}`
              : '—'}
          </Fact>
          {f.firsts.map((x) => (
            <Fact key={x.label} label={x.label}>
              {x.date_label ? `${x.detail ? `${x.detail} · ` : ''}${x.date_label}` : 'Not yet'}
            </Fact>
          ))}
        </Panel>
        <Panel title="People">
          {people(
            'Longest serving',
            f.longest_serving,
            (r) => `${r.months} mo${r.current ? '' : ' (former)'}`,
          )}
          {people(
            'Best hires (rise in shown rating)',
            f.best_hires,
            (r) => r.detail ?? `+${r.value}`,
          )}
          {people(
            'Notable departures',
            f.notable_departures,
            (r) => `${r.value.toFixed(0)} · ${r.detail ?? ''}`,
          )}
        </Panel>
        <Panel title="Products and rivals">
          <Fact label="Best product">
            {f.best_product_mrr
              ? `${f.best_product_mrr.name} · ${formatMoneyShort(f.best_product_mrr.value)} MRR`
              : '—'}
          </Fact>
          <Fact label="Highest quality shown">
            {f.best_product_quality
              ? `${f.best_product_quality.name} · ${formatWhole(f.best_product_quality.value)}`
              : '—'}
          </Fact>
          <Fact label="Rivals outlasted">
            {f.rivals_outlasted.length
              ? f.rivals_outlasted.map((r) => `${r.name} (${r.date_label})`).join(', ')
              : 'None yet'}
          </Fact>
        </Panel>
      </div>
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        Ratings are the midpoint of what you've learned about a person, never their hidden values.
      </p>
    </>
  );
}
