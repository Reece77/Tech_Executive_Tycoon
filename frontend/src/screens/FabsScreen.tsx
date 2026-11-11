import { Alert, Button, Checkbox, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { NodeTimeline } from '../components/NodeTimeline';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { useOrg } from '../hooks/api';
import {
  useFabAction,
  useFabQuote,
  useFabs,
  type Fab,
  type FabAction,
  type Fabs,
} from '../hooks/fabs';
import { formatMoney, formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const fabHelper = createColumnHelper<GameTableFeatures, Fab>();

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`;
const starts = (v: number) => Math.round(v).toLocaleString();
const STATUS: Record<string, string> = {
  building: 'building',
  waiting_tools: 'waiting for EUV tools',
  converting: 'converting',
  live: 'in production',
  closed: 'closed',
};

/** Fabs (M21, formulas.md 38): each fab's node, capacity, use, yield curve, cost a start and per
 * good die against the market, and its foundry customers; building, converting and staffing;
 * the node timeline. Display only: every number comes from the API. */
export function FabsScreen() {
  const { saveId = '' } = useParams();
  const fabs = useFabs(saveId);
  if (fabs.isPending) return <Loading />;
  if (fabs.error) return <LoadError title="Could not load fabs" error={fabs.error} />;
  return <Body saveId={saveId} x={fabs.data} />;
}

function Body({ saveId, x }: { saveId: string; x: Fabs }) {
  const act = useFabAction(saveId);
  const [selected, setSelected] = useState<number | null>(x.fabs[0]?.id ?? null);
  const run = (a: FabAction) => act.mutate(a);
  const fab = x.fabs.find((f) => f.id === selected) ?? x.fabs[0] ?? null;
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Fabs</h1>
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="fab-process-level">
          Process level {x.process_level.toFixed(1)}
        </span>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="fab-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Fabs" testId="fabs-panel">
        {x.fabs.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12, margin: 0 }}>
            No fabs yet. A fab is the biggest bet in the game: it pays only at the edge and at high
            use.
          </p>
        ) : (
          <FabsTable fabs={x.fabs} onSelect={setSelected} />
        )}
      </Panel>
      {fab && <FabPanel key={fab.id} saveId={saveId} f={fab} busy={act.isPending} onAct={run} />}
      <BuildPanel saveId={saveId} x={x} busy={act.isPending} onAct={run} />
      <Panel title="Process nodes" testId="fab-nodes">
        <NodeTimeline nodes={x.timeline} />
      </Panel>
    </>
  );
}

function FabsTable({ fabs, onSelect }: { fabs: Fab[]; onSelect: (id: number) => void }) {
  const columns = useMemo(
    () =>
      fabHelper.columns([
        fabHelper.accessor('name', {
          header: 'Fab',
          cell: ({ row }) => (
            <Button variant="subtle" size="compact-xs" onClick={() => onSelect(row.original.id)}>
              {row.original.name}
            </Button>
          ),
        }),
        fabHelper.accessor('node_label', { header: 'Node' }),
        fabHelper.accessor('status', {
          header: 'Status',
          cell: ({ getValue }) => STATUS[getValue()] ?? getValue(),
        }),
        fabHelper.accessor('size', {
          header: 'Starts a month',
          cell: ({ getValue }) => starts(getValue()),
        }),
        fabHelper.accessor((f) => f.month?.utilization ?? 0, {
          id: 'use',
          header: 'Use',
          cell: ({ row }) => (row.original.month ? pct(row.original.month.utilization) : '—'),
        }),
        fabHelper.accessor('yield', { header: 'Yield', cell: ({ getValue }) => pct(getValue()) }),
        fabHelper.accessor((f) => f.month?.cost_per_start_cents ?? 0, {
          id: 'cost',
          header: 'Cost a start',
          cell: ({ row }) =>
            row.original.month && row.original.month.cost_per_start_cents > 0
              ? formatMoney(Math.round(row.original.month.cost_per_start_cents))
              : '—',
        }),
        fabHelper.accessor((f) => f.month?.market_cents ?? 0, {
          id: 'market',
          header: 'Market wafer',
          cell: ({ row }) =>
            row.original.month && row.original.month.market_cents > 0
              ? formatMoney(Math.round(row.original.month.market_cents))
              : '—',
        }),
      ]),
    [onSelect],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: fabs,
    getRowId: (f) => String(f.id),
  });
  return <DataTable table={table} label="Fabs" rowTestId="fab-row" />;
}

function FabPanel({
  saveId,
  f,
  busy,
  onAct,
}: {
  saveId: string;
  f: Fab;
  busy: boolean;
  onAct: (a: FabAction) => void;
}) {
  const org = useOrg(saveId);
  const units = (org.data?.units ?? []).filter((u) => u.unit_id !== null);
  const m = f.month;
  const status =
    f.status === 'live'
      ? `in production; book value ${formatMoneyWhole(f.book_value_cents)}`
      : f.status === 'converting'
        ? `converting to ${f.upgrade_label}, ready ${f.upgrade_ready_label}`
        : `${STATUS[f.status] ?? f.status}, ready ${f.ready_label}; paid ${formatMoneyWhole(f.capex_paid_cents)} of an estimated ${formatMoneyWhole(f.estimate_cents)}`;
  return (
    <Panel
      title={`${f.name} · ${f.company}`}
      testId="fab-panel"
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Select
            size="xs"
            placeholder="Assign a unit"
            aria-label="Staffing unit"
            data-testid="fab-staff-unit"
            disabled={busy}
            data={[
              { value: 'none', label: 'Nobody' },
              ...units.map((u) => ({ value: String(u.unit_id), label: u.name })),
            ]}
            value={f.unit_id === null ? null : String(f.unit_id)}
            onChange={(v) =>
              v &&
              onAct({ kind: 'staff', facilityId: f.id, unitId: v === 'none' ? null : Number(v) })
            }
          />
          <Button
            size="xs"
            variant="default"
            disabled={busy || !f.upgrade_allowed}
            title={
              f.upgrade_allowed ? undefined : `${f.upgrade_reason ?? ''}. How: ${f.upgrade_how}`
            }
            data-testid="fab-upgrade"
            onClick={() => onAct({ kind: 'upgrade', facilityId: f.id })}
          >
            Convert{f.next_node ? ` to ${f.next_node}` : ''}
            {f.upgrade_estimate_cents ? ` · ${formatMoneyWhole(f.upgrade_estimate_cents)}` : ''}
          </Button>
          <Button
            size="xs"
            variant="default"
            disabled={busy || f.status === 'closed'}
            data-testid="fab-sell"
            onClick={() => onAct({ kind: 'sell', facilityId: f.id })}
          >
            Sell
          </Button>
        </div>
      }
    >
      <dl className="tst-facts" style={{ fontSize: 13, margin: 0 }} data-testid="fab-facts">
        <Fact label="Node" value={`${f.node_label}${f.duv ? ' (DUV)' : ''} in ${f.region_label}`} />
        <Fact label="Status" value={status} testId="fab-status" />
        <Fact
          label="Capacity"
          value={`${starts(f.size)} wafer starts a month; staff ${f.staff} of ${f.staff_needed} (${pct(f.coverage)})`}
        />
        {f.tools > 0 && (
          <Fact
            label="EUV tools"
            value={`${f.tools} tools, arriving ${f.tools_label ?? 'not yet known'}`}
            testId="fab-tools"
          />
        )}
        <Fact
          label="Yield"
          value={`${pct(f.yield)} after ${f.months_run} months of production`}
          testId="fab-yield"
        />
        {m && m.available > 0 && (
          <>
            <Fact
              label="Use"
              value={`${pct(m.utilization)}: own chips ${starts(m.own)}, foundry slots ${starts(m.sold)} of ${starts(m.available)}`}
              testId="fab-use"
            />
            <Fact
              label="Cost a start"
              value={`${formatMoney(Math.round(m.cost_per_start_cents))} against ${formatMoney(Math.round(m.market_cents))} at market (slots at ${formatMoney(Math.round(m.slot_price_cents))})`}
              testId="fab-cost"
            />
            {m.die_cost_cents !== null && m.die_market_cents !== null && (
              <Fact
                label="Per good die"
                value={`${formatMoney(Math.round(m.die_cost_cents))} an AI accelerator die here against ${formatMoney(Math.round(m.die_market_cents))} on a foundry slot`}
                testId="fab-die"
              />
            )}
            <div style={{ fontSize: 12 }}>
              Why this cost per good die?{' '}
              <Explain metric="fab_die_cost" entity={f.id} label="Cost per good die" />
            </div>
            <Fact
              label="Costs"
              value={`depreciation ${formatMoneyWhole(m.depreciation_cents)}, fixed ${formatMoneyWhole(m.fixed_cents)}, materials ${formatMoneyWhole(m.materials_cents)}, power ${formatMoneyWhole(m.power_cents)}, engineers ${formatMoneyWhole(m.staff_cents)}`}
            />
            <Fact
              label="Foundry sales"
              value={`${formatMoneyWhole(m.revenue_cents)} this month`}
              testId="fab-revenue"
            />
          </>
        )}
        {f.chips.length > 0 && <Fact label="Supplies" value={f.chips.join(', ')} />}
      </dl>
      {f.customers.length > 0 && (
        <p style={{ fontSize: 13 }} data-testid="fab-customers">
          Foundry customers:{' '}
          {f.customers.map((c) => `${c.name} (${starts(c.starts)} starts)`).join(' · ')}
        </p>
      )}
      {f.history.length > 0 && (
        <p className="tst-muted" style={{ fontSize: 12 }} data-testid="fab-history">
          Yield curve:{' '}
          {f.history
            .slice(-12)
            .map((h) => `${h.label} ${pct(h.yield)}`)
            .join(' · ')}
        </p>
      )}
    </Panel>
  );
}

function BuildPanel({
  saveId,
  x,
  busy,
  onAct,
}: {
  saveId: string;
  x: Fabs;
  busy: boolean;
  onAct: (a: FabAction) => void;
}) {
  const choices = x.timeline.nodes.filter((n) => n.orderable);
  const [node, setNode] = useState(choices[0]?.key ?? '');
  const [region, setRegion] = useState(x.regions[0] ?? '');
  const [size, setSize] = useState<number>(x.sizes[0] ?? 0);
  const [duv, setDuv] = useState(false);
  const row = x.timeline.nodes.find((n) => n.key === node);
  const useDuv = duv && Boolean(row?.duv_route);
  const quote = useFabQuote(saveId, node, region, size, useDuv);
  const q = quote.data;
  return (
    <Panel
      title="Build a fab"
      testId="fab-build-panel"
      action={
        <Button
          size="xs"
          data-testid="build-fab"
          disabled={busy || !q?.allowed}
          title={q && !q.allowed ? `${q.reason ?? ''}. How: ${q.how}` : undefined}
          onClick={() => onAct({ kind: 'build', node, region, size, duv: useDuv })}
        >
          Build · energy {x.build_energy}
        </Button>
      }
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Node"
          data-testid="fab-node"
          size="xs"
          data={choices.map((n) => ({ value: n.key, label: n.label }))}
          value={node}
          onChange={(v) => v && setNode(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Region"
          data-testid="fab-region"
          size="xs"
          data={x.regions.map((r) => ({ value: r, label: r.replaceAll('_', ' ') }))}
          value={region}
          onChange={(v) => v && setRegion(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Size"
          data-testid="fab-size"
          size="xs"
          data={x.sizes.map((s) => ({ value: String(s), label: `${s.toLocaleString()} starts` }))}
          value={String(size)}
          onChange={(v) => v && setSize(Number(v))}
          allowDeselect={false}
        />
        {row?.duv_route && (
          <Checkbox
            size="xs"
            label="DUV route (no EUV tools)"
            checked={duv}
            onChange={(e) => setDuv(e.currentTarget.checked)}
          />
        )}
      </div>
      {q && (
        <dl className="tst-facts" style={{ fontSize: 13, marginTop: 8 }} data-testid="fab-quote">
          <Fact
            label="Capex"
            value={`${formatMoneyWhole(q.capex_cents)} estimated (it may run over), ${q.build_months} months, ${q.staff_needed} fab engineers`}
          />
          <Fact
            label="Ready"
            value={`${q.ready_label}${q.euv ? `; ${q.tools} EUV tools arrive ${q.tools_label ?? 'not yet known'}` : ''}`}
            testId="fab-quote-ready"
          />
          <Fact
            label="A start at full use"
            value={`${formatMoney(Math.round(q.cost_per_start_cents))} before staff and power${q.market_cents ? `, against ${formatMoney(Math.round(q.market_cents))} at market` : ''}`}
          />
          <Fact
            label="Research"
            value={`needs process level ${q.need_level.toFixed(0)}; yours ${q.level.toFixed(0)}`}
          />
          {q.reason && <Fact label="Not possible" value={q.reason} testId="fab-quote-reason" />}
          {q.how && <Fact label="How to unlock" value={q.how} testId="fab-quote-how" />}
        </dl>
      )}
    </Panel>
  );
}

function Fact({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
      <dt className="tst-muted" style={{ width: 170, flexShrink: 0 }}>
        {label}
      </dt>
      <dd style={{ margin: 0 }} data-testid={testId}>
        {value}
      </dd>
    </div>
  );
}
