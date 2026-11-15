import { Alert, Button, Checkbox, NumberInput, Select, Slider } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useEquipment,
  useOrderTools,
  usePrepay,
  useStartLitho,
  useStopLitho,
  type Equipment,
  type LithoStage,
  type ToolGeneration,
  type ToolOrder,
} from '../hooks/equipment';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const genHelper = createColumnHelper<GameTableFeatures, ToolGeneration>();
const orderHelper = createColumnHelper<GameTableFeatures, ToolOrder>();
const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`;

/** Equipment (M33, formulas.md 47): ASML's tool generations, prices and order book; your orders
 * and their place in the queue as a range of months; stock, controls and the lithography
 * programme. Display only: every number comes from the API. */
export function EquipmentScreen() {
  const { saveId = '' } = useParams();
  const eq = useEquipment(saveId);
  if (eq.isPending) return <Loading />;
  if (eq.error) return <LoadError title="Could not load equipment" error={eq.error} />;
  return <Body saveId={saveId} x={eq.data} />;
}

function Body({ saveId, x }: { saveId: string; x: Equipment }) {
  const order = useOrderTools(saveId);
  const prepay = usePrepay(saveId);
  const start = useStartLitho(saveId);
  const stop = useStopLitho(saveId);
  const error = order.error ?? prepay.error ?? start.error ?? stop.error;
  const busy = order.isPending || prepay.isPending || start.isPending || stop.isPending;
  return (
    <>
      <Link to={`/game/${saveId}/products/fabs`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Fabs
      </Link>
      <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Equipment</h1>
      <p className="tst-muted" style={{ fontSize: 12, margin: 0 }} data-testid="equipment-note">
        {x.note}
      </p>
      {error && (
        <Alert color="warn" data-testid="equipment-error">
          {error.message}
        </Alert>
      )}
      <Panel title="Tool generations" testId="equipment-generations">
        <Generations rows={x.generations} />
      </Panel>
      <OrderPanel x={x} busy={busy} onOrder={(b) => order.mutate(b)} />
      <Panel title="Your orders" testId="equipment-orders">
        {x.orders.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12, margin: 0 }}>
            No tool orders. A fab at an EUV node orders its tools when you build or convert it.
          </p>
        ) : (
          <Orders rows={x.orders} busy={busy} onPrepay={(id) => prepay.mutate(id)} />
        )}
      </Panel>
      {x.stock.length > 0 && (
        <Panel title="Tools in stock" testId="equipment-stock">
          <ul style={{ fontSize: 13, margin: 0 }}>
            {x.stock.map((s) => (
              <li key={`${s.generation}-${s.source}`}>
                {s.tools} {s.generation_label} ({s.source === 'own' ? 'our own' : 'ASML'}), at{' '}
                {formatMoneyWhole(s.book_cents)}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <Panel title="Controls on tools" testId="equipment-controls">
        {x.controls.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12, margin: 0 }}>
            No controls on lithography tools yet.
          </p>
        ) : (
          <ul style={{ fontSize: 13, margin: 0 }}>
            {x.controls.map((c) => (
              <li key={c.key} data-testid="equipment-control">
                {c.month_label}: {c.title} ({c.generation_labels.join(', ')}; to{' '}
                {c.destinations.join(', ')}){c.in_force ? '' : ' — no longer in force'}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Programme
        x={x}
        busy={busy}
        onStart={(stage, funding) => start.mutate({ stage, funding })}
        onStop={(stage) => stop.mutate(stage)}
      />
    </>
  );
}

function Generations({ rows }: { rows: ToolGeneration[] }) {
  const columns = useMemo(
    () =>
      genHelper.columns([
        genHelper.accessor('label', {
          header: 'Generation',
          cell: ({ row }) => (
            <Term
              term={
                row.original.key === 'euv_high'
                  ? 'equipment.high_na'
                  : row.original.queued
                    ? 'equipment.euv'
                    : 'equipment.duv'
              }
            >
              {row.original.label}
            </Term>
          ),
        }),
        genHelper.accessor('model', { header: 'Model' }),
        genHelper.accessor('wph', {
          header: () => <Term term="equipment.throughput">Wafers an hour</Term>,
          cell: ({ getValue }) => getValue().toFixed(0),
        }),
        genHelper.accessor('uptime', { header: 'Uptime', cell: ({ getValue }) => pct(getValue()) }),
        genHelper.accessor('price_cents', {
          header: 'Price',
          cell: ({ row }) =>
            `${formatMoneyWhole(row.original.price_cents)}${row.original.price_cents !== row.original.list_cents ? ` (list ${formatMoneyWhole(row.original.list_cents)})` : ''}`,
        }),
        genHelper.accessor((g) => g.shipments.at(-1)?.tools ?? 0, {
          id: 'shipped',
          header: 'Last year',
          cell: ({ row }) => {
            const last = row.original.shipments.at(-1);
            return last ? `${last.tools} (${last.year})` : '—';
          },
        }),
        genHelper.accessor('book', { header: 'Order book' }),
        genHelper.accessor('node_labels', {
          header: 'Nodes',
          cell: ({ getValue }) => getValue().join(', '),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (g) => g.key,
  });
  return <DataTable table={table} label="Tool generations" rowTestId="equipment-generation" />;
}

function OrderPanel({
  x,
  busy,
  onOrder,
}: {
  x: Equipment;
  busy: boolean;
  onOrder: (b: { generation: string; tools: number; prepay: boolean }) => void;
}) {
  const queued = x.generations.filter((g) => g.queued && g.shipping);
  const [generation, setGeneration] = useState(queued.at(-1)?.key ?? '');
  const [tools, setTools] = useState<number>(10);
  const [prepay, setPrepay] = useState(false);
  const g = queued.find((q) => q.key === generation);
  return (
    <Panel
      title="Order tools into stock"
      testId="equipment-order-panel"
      action={
        <Button
          size="xs"
          data-testid="equipment-order"
          disabled={busy || !g || tools < 1}
          onClick={() => onOrder({ generation, tools, prepay })}
        >
          Order · energy {x.order_energy}
        </Button>
      }
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Generation"
          data-testid="equipment-generation-select"
          size="xs"
          data={queued.map((q) => ({ value: q.key, label: q.label }))}
          value={generation}
          onChange={(v) => v && setGeneration(v)}
          allowDeselect={false}
        />
        <NumberInput
          aria-label="Tools"
          data-testid="equipment-tools"
          size="xs"
          min={1}
          max={x.max_order}
          value={tools}
          onChange={(v) => setTools(Number(v) || 0)}
          style={{ width: 90 }}
        />
        <Checkbox
          size="xs"
          label={`Prepay ${pct(x.prepay_share)} (moves the order up)`}
          data-testid="equipment-prepay-new"
          checked={prepay}
          onChange={(e) => setPrepay(e.currentTarget.checked)}
        />
        {g && (
          <span className="tst-muted" style={{ fontSize: 12 }}>
            {formatMoneyWhole(g.price_cents)} each; tools wait in stock until a fab takes them
          </span>
        )}
      </div>
    </Panel>
  );
}

function Orders({
  rows,
  busy,
  onPrepay,
}: {
  rows: ToolOrder[];
  busy: boolean;
  onPrepay: (id: number) => void;
}) {
  const columns = useMemo(
    () =>
      orderHelper.columns([
        orderHelper.accessor('generation_label', { header: 'Tools' }),
        orderHelper.accessor('tools', {
          header: 'Ordered',
          cell: ({ row }) => `${row.original.delivered} of ${row.original.tools} delivered`,
        }),
        orderHelper.accessor('fab', {
          header: 'For',
          cell: ({ getValue }) => getValue() ?? 'stock',
        }),
        orderHelper.accessor('placed_label', { header: 'Placed' }),
        orderHelper.accessor('lead_label', {
          header: () => <Term term="equipment.allocation">Queue place</Term>,
          cell: ({ row }) => (
            <span data-testid="equipment-lead">
              {row.original.lead_label}
              {row.original.status === 'open' && (
                <Explain metric="tool_wait" entity={row.original.id} label="the tool wait" />
              )}
            </span>
          ),
        }),
        orderHelper.accessor('status', { header: 'Status' }),
        orderHelper.display({
          id: 'prepay',
          header: 'Prepay',
          cell: ({ row }) =>
            row.original.prepaid ? (
              'prepaid'
            ) : row.original.prepay_cents !== null && row.original.prepay_cents !== undefined ? (
              <Button
                size="compact-xs"
                variant="default"
                disabled={busy}
                data-testid="equipment-prepay"
                onClick={() => onPrepay(row.original.id)}
              >
                {formatMoneyWhole(row.original.prepay_cents)}
              </Button>
            ) : (
              '—'
            ),
        }),
      ]),
    [busy, onPrepay],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (o) => String(o.id),
  });
  return <DataTable table={table} label="Tool orders" rowTestId="equipment-order-row" />;
}

function Programme({
  x,
  busy,
  onStart,
  onStop,
}: {
  x: Equipment;
  busy: boolean;
  onStart: (stage: string, funding: number) => void;
  onStop: (stage: string) => void;
}) {
  const p = x.programme;
  const [funding, setFunding] = useState(1.0);
  return (
    <Panel title="Lithography programme" testId="equipment-programme">
      <p className="tst-muted" style={{ fontSize: 12, margin: '0 0 6px' }}>
        Building your own scanners is a decade-long bet: tens of billions, years per stage, and a
        real chance a stage never works. Prototype tools start slower and less reliable than
        ASML&apos;s and improve as more are installed.
        {p.unlocked
          ? ` Lithography level ${p.level.toFixed(0)}; ${p.researchers} researchers on lithography.`
          : ` ${p.unlock_reason ?? ''}`}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, maxWidth: 420 }}>
        <span style={{ fontSize: 12 }}>Funding</span>
        <Slider
          aria-label="Funding"
          data-testid="litho-funding"
          min={p.funding_low}
          max={p.funding_high}
          step={0.05}
          value={funding}
          onChange={setFunding}
          style={{ flex: 1 }}
        />
        <span style={{ fontSize: 12, width: 48 }}>{pct(funding)}</span>
      </div>
      {p.stages.map((s) => (
        <Stage key={s.key} s={s} busy={busy} funding={funding} onStart={onStart} onStop={onStop} />
      ))}
      {p.own_tools.length > 0 && (
        <ul style={{ fontSize: 13 }} data-testid="litho-own-tools">
          {p.own_tools.map((t) => (
            <li key={t.stage}>
              {t.stage}: {t.made} made ({t.per_year} a year), {t.in_stock} in stock, {t.installed}{' '}
              installed, {t.sold} sold; throughput {pct(t.throughput)} of ASML&apos;s, yield{' '}
              {t.yield_cut.toFixed(1)} points lower, maturity {pct(t.maturity)}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Stage({
  s,
  busy,
  funding,
  onStart,
  onStop,
}: {
  s: LithoStage;
  busy: boolean;
  funding: number;
  onStart: (stage: string, funding: number) => void;
  onStop: (stage: string) => void;
}) {
  const facts =
    s.status === 'running'
      ? `running since ${s.started_label} (${s.months_running} months, attempt ${s.attempt}): ${formatMoneyWhole(s.spent_cents)} spent at ${pct(s.funding)} funding; expected to end ${s.end_window_label}`
      : s.status === 'succeeded'
        ? `works: first tools at ${pct(s.throughput)} of ASML's throughput, ${s.yield_cut?.toFixed(0)} yield points lower`
        : s.status === 'failed'
          ? `failed after ${s.months_running} months and ${formatMoneyWhole(s.spent_cents)}`
          : `estimate ${formatMoneyWhole(s.cost_cents)} over ${s.months_low}-${s.months_high} months (${formatMoneyWhole(s.reference_cents)} a month); needs level ${s.level.toFixed(0)} and ${s.staff} researchers${s.after_stage ? `, after ${s.after_stage}` : ''}`;
  return (
    <div
      style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', fontSize: 13 }}
      data-testid={`litho-stage-${s.key}`}
    >
      <strong style={{ width: 200 }}>{s.label}</strong>
      <span style={{ flex: 1 }} data-testid={`litho-status-${s.key}`}>
        {s.status}: {facts}
        {s.why_not && s.status !== 'running' ? ` (${s.why_not})` : ''}
      </span>
      {s.status === 'running' ? (
        <Button size="compact-xs" variant="default" disabled={busy} onClick={() => onStop(s.key)}>
          Stop
        </Button>
      ) : (
        <Button
          size="compact-xs"
          disabled={busy || s.status !== 'open'}
          data-testid={`litho-start-${s.key}`}
          title={s.why_not ?? undefined}
          onClick={() => onStart(s.key, funding)}
        >
          Start
        </Button>
      )}
    </div>
  );
}
