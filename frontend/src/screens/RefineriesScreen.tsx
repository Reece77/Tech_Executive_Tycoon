import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import { useOrg } from '../hooks/api';
import {
  useRefineries,
  useRefineryQuote,
  useRefiningAction,
  type Plant,
  type Refineries,
  type RefiningAction,
} from '../hooks/refining';
import { formatMoney, formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const plantHelper = createColumnHelper<GameTableFeatures, Plant>();
const dealHelper = createColumnHelper<GameTableFeatures, Refineries['deals'][number]>();

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;
const qty = (v: number) =>
  v >= 100
    ? Math.round(v).toLocaleString()
    : v.toLocaleString(undefined, { maximumFractionDigits: 2 });

/** Refineries (M20, formulas.md 36): each plant's inputs, outputs, yield, power cost and unit
 * cost against market; building, staffing and contracts; power by region; own supply. */
export function RefineriesScreen() {
  const { saveId = '' } = useParams();
  const refineries = useRefineries(saveId);
  if (refineries.isPending) return <Loading />;
  if (refineries.error) {
    return <LoadError title="Could not load refineries" error={refineries.error} />;
  }
  return <Body saveId={saveId} x={refineries.data} />;
}

function Body({ saveId, x }: { saveId: string; x: Refineries }) {
  const act = useRefiningAction(saveId);
  // An event's link opens its plant (M23c): ?plant=<facility id>
  const [params] = useSearchParams();
  const linked = Number(params.get('plant'));
  const [selected, setSelected] = useState<number | null>(
    x.plants.some((p) => p.id === linked) ? linked : (x.plants[0]?.id ?? null),
  );
  const run = (a: RefiningAction) => act.mutate(a);
  const plant = x.plants.find((p) => p.id === selected) ?? x.plants[0] ?? null;
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Refineries</h1>
        <span className="tst-muted" style={{ fontSize: 13 }} data-testid="process-level">
          <Term term="refining.process">Process level</Term> {x.process_level.toFixed(1)}{' '}
          (semiconductor grades need {x.semi_min_level})
        </span>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="refining-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Plants" testId="plants-panel">
        <PlantsTable plants={x.plants} onSelect={setSelected} />
      </Panel>
      {plant && (
        <PlantPanel key={plant.id} saveId={saveId} p={plant} busy={act.isPending} onAct={run} />
      )}
      <BuildPanel saveId={saveId} x={x} busy={act.isPending} onAct={run} />
      <Panel title="Contracts" testId="deals-panel">
        <DealsTable deals={x.deals} />
        <DealForm x={x} busy={act.isPending} onAct={run} />
      </Panel>
      <Panel title="Own supply this month" testId="supply-panel">
        {x.supply.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 12 }}>
            Nothing went to the group this month.
          </p>
        ) : (
          <ul style={{ fontSize: 13, margin: 0, paddingLeft: 18 }}>
            {x.supply.map((s, i) => (
              <li key={i} data-testid="supply-row">
                {qty(s.volume)} {s.good_label} from {s.seller} to {s.buyer}
                {s.product ? ` (${s.product})` : ''} at {formatMoney(Math.round(s.unit_cents))}{' '}
                against {formatMoney(Math.round(s.market_cents))} at market; used {qty(s.taken)}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Power by region" testId="power-panel">
        <p style={{ fontSize: 13, margin: 0 }}>
          {x.power.map((r) => `${r.label} ×${r.index.toFixed(2)}`).join(' · ')}
        </p>
      </Panel>
    </>
  );
}

function PlantsTable({ plants, onSelect }: { plants: Plant[]; onSelect: (id: number) => void }) {
  const columns = useMemo(
    () =>
      plantHelper.columns([
        plantHelper.accessor('name', {
          header: 'Plant',
          cell: ({ row }) => (
            <Button variant="subtle" size="compact-xs" onClick={() => onSelect(row.original.id)}>
              {row.original.name}
            </Button>
          ),
        }),
        plantHelper.accessor('recipe_label', { header: 'Recipe' }),
        plantHelper.accessor('status', { header: 'Status' }),
        plantHelper.accessor((p) => p.month?.made ?? 0, {
          id: 'output',
          header: 'Output',
          cell: ({ row }) =>
            row.original.month
              ? `${qty(row.original.month.made)} ${row.original.output_unit}`
              : '—',
        }),
        plantHelper.accessor((p) => p.month?.unit_cost_cents ?? 0, {
          id: 'unit',
          header: 'Unit cost',
          meta: { term: 'refining.unit_cost' },
          cell: ({ row }) =>
            row.original.month ? formatMoney(Math.round(row.original.month.unit_cost_cents)) : '—',
        }),
        plantHelper.accessor((p) => p.month?.market_cents ?? 0, {
          id: 'market',
          header: 'Market',
          cell: ({ row }) =>
            row.original.month ? formatMoney(Math.round(row.original.month.market_cents)) : '—',
        }),
        plantHelper.accessor((p) => p.month?.margin ?? null, {
          id: 'margin',
          header: 'Margin',
          meta: { term: 'refining.margin' },
          cell: ({ getValue }) => pct(getValue()),
        }),
        plantHelper.accessor((p) => p.month?.power_index ?? null, {
          id: 'power',
          header: 'Power',
          cell: ({ row }) =>
            row.original.month
              ? `${formatMoneyWhole(row.original.month.power_cents)} ×${row.original.month.power_index.toFixed(2)}`
              : '—',
        }),
      ]),
    [onSelect],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: plants,
    getRowId: (p) => String(p.id),
  });
  return <DataTable table={table} label="Plants" rowTestId="plant-row" />;
}

function PlantPanel({
  saveId,
  p,
  busy,
  onAct,
}: {
  saveId: string;
  p: Plant;
  busy: boolean;
  onAct: (a: RefiningAction) => void;
}) {
  const org = useOrg(saveId);
  const units = (org.data?.units ?? []).filter((u) => u.unit_id !== null);
  const m = p.month;
  return (
    <Panel
      title={`${p.name} · ${p.company}`}
      testId="plant-panel"
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Select
            size="xs"
            placeholder="Assign a unit"
            aria-label="Staffing unit"
            data-testid="plant-staff-unit"
            disabled={busy}
            data={[
              { value: 'none', label: 'Nobody' },
              ...units.map((u) => ({ value: String(u.unit_id), label: u.name })),
            ]}
            value={p.unit_id === null ? null : String(p.unit_id)}
            onChange={(v) =>
              v &&
              onAct({ kind: 'staff', facilityId: p.id, unitId: v === 'none' ? null : Number(v) })
            }
          />
          <Button
            size="xs"
            variant="default"
            disabled={busy || p.status === 'closed'}
            data-testid="plant-sell"
            onClick={() => onAct({ kind: 'sell', facilityId: p.id })}
          >
            Sell
          </Button>
        </div>
      }
    >
      <dl className="tst-facts" style={{ fontSize: 13, margin: 0 }} data-testid="plant-facts">
        <Fact
          label="Recipe"
          value={`${p.recipe_label} (${p.input_label ?? 'host stream'} → ${p.output_label})`}
        />
        <Fact
          label="Status"
          value={
            p.status === 'building'
              ? `building, ready ${p.ready_label}; paid ${formatMoneyWhole(p.capex_paid_cents)} of an estimated ${formatMoneyWhole(p.estimate_cents)}`
              : `${p.status}; book value ${formatMoneyWhole(p.book_value_cents)}`
          }
          testId="plant-status"
        />
        <Fact
          label="Capacity"
          value={`${p.size.toLocaleString()} ${p.unit}; staff ${p.staff} of ${p.staff_needed} (${pct(p.coverage)})`}
        />
        <Fact
          label="Yield"
          term="refining.yield"
          value={`${m ? m.yield.toFixed(2) : p.stated_yield.toFixed(2)} (stated ${p.stated_yield})${p.semi_grade ? ', semiconductor grade' : ''}`}
          testId="plant-yield"
        />
        {p.curbed_until && (
          <Fact
            label="Power curb"
            term="refining.curb"
            value={`running at ${pct(p.curb_run)} until ${p.curbed_until}`}
            testId="plant-curb"
          />
        )}
        {p.stopped_until && (
          <Fact label="Stopped" value={`after an incident, until ${p.stopped_until}`} />
        )}
        {m && (
          <>
            <Fact
              label="Latest month"
              value={`${qty(m.made)} ${p.output_unit} of ${qty(m.possible)} possible`}
              testId="plant-output"
            />
            <Fact
              label="Inputs"
              value={`group ${qty(m.input_group)}, contracts ${qty(m.input_contract)}, spot ${qty(m.input_spot)}${m.input_short > 0 ? `, short ${qty(m.input_short)}` : ''}; ${formatMoneyWhole(m.input_cents)}`}
              testId="plant-inputs"
            />
            <Fact
              label="Costs"
              value={`power ${formatMoneyWhole(m.power_cents)} (×${m.power_index.toFixed(2)}), other ${formatMoneyWhole(m.other_cents)}, fixed ${formatMoneyWhole(m.fixed_cents)}, depreciation ${formatMoneyWhole(m.depreciation_cents)}, staff ${formatMoneyWhole(m.staff_cents)}`}
            />
            <Fact
              label="Unit cost"
              term="refining.unit_cost"
              value={`${formatMoney(Math.round(m.unit_cost_cents))} against ${formatMoney(Math.round(m.market_cents))} at market (margin ${pct(m.margin)})`}
              testId="plant-unit-cost"
            />
            <Fact
              label="Output to"
              value={`group ${qty(m.to_group)}, contracts ${qty(m.to_contract)}, spot ${qty(m.to_spot)}; revenue ${formatMoneyWhole(m.revenue_cents)}`}
              testId="plant-outputs"
            />
          </>
        )}
      </dl>
      {p.history.length > 0 && (
        <p className="tst-muted" style={{ fontSize: 12 }} data-testid="plant-history">
          Unit cost against market:{' '}
          {p.history
            .slice(-6)
            .map(
              (h) =>
                `${h.label} ${formatMoneyWhole(Math.round(h.unit_cost_cents))}/${formatMoneyWhole(Math.round(h.market_cents))}`,
            )
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
  x: Refineries;
  busy: boolean;
  onAct: (a: RefiningAction) => void;
}) {
  const [recipe, setRecipe] = useState(x.recipes[0]?.key ?? '');
  const [region, setRegion] = useState(x.power[0]?.region ?? '');
  const r = x.recipes.find((y) => y.key === recipe);
  const [size, setSize] = useState<number | null>(r?.sizes[0] ?? null);
  const capacity = r && size !== null && r.sizes.includes(size) ? size : (r?.sizes[0] ?? null);
  const quote = useRefineryQuote(saveId, recipe, region, capacity);
  const q = quote.data;
  return (
    <Panel
      title="Build a plant"
      testId="build-panel"
      action={
        <Button
          size="xs"
          data-testid="build-refinery"
          disabled={busy || !capacity}
          onClick={() => capacity && onAct({ kind: 'build', recipe, region, capacity })}
        >
          Build · energy {x.build_energy}
        </Button>
      }
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Select
          aria-label="Recipe"
          data-testid="recipe-select"
          size="xs"
          data={x.recipes.map((y) => ({ value: y.key, label: `${y.kind_label}: ${y.label}` }))}
          value={recipe}
          onChange={(v) => v && setRecipe(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Region"
          data-testid="build-region"
          size="xs"
          data={x.power.map((p) => ({ value: p.region, label: p.label }))}
          value={region}
          onChange={(v) => v && setRegion(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Capacity"
          data-testid="build-size"
          size="xs"
          data={(r?.sizes ?? []).map((s) => ({
            value: String(s),
            label: `${s.toLocaleString()} ${r?.unit ?? ''}`,
          }))}
          value={capacity === null ? null : String(capacity)}
          onChange={(v) => v && setSize(Number(v))}
          allowDeselect={false}
        />
      </div>
      {q && r && (
        <dl className="tst-facts" style={{ fontSize: 13, marginTop: 8 }} data-testid="build-quote">
          <Fact
            label="Capex"
            value={`${formatMoneyWhole(q.capex_cents)} estimated (it may run over), ${q.build_months} months, ${q.staff_needed} process engineers`}
          />
          <Fact
            label="A unit at full output"
            term="refining.unit_cost"
            value={`${formatMoney(Math.round(q.unit_cost_cents))} before staff, against ${formatMoney(Math.round(q.market_cents))} at market (margin ${pct(q.margin)})`}
            testId="quote-unit-cost"
          />
          <Fact
            label="Of which power"
            value={`${formatMoney(Math.round(q.power_cents))} at ×${q.power_index.toFixed(2)}; input ${formatMoney(Math.round(q.input_cents))}`}
            testId="quote-power"
          />
        </dl>
      )}
    </Panel>
  );
}

function DealsTable({ deals }: { deals: Refineries['deals'] }) {
  const columns = useMemo(
    () =>
      dealHelper.columns([
        dealHelper.accessor('side', { header: 'Side' }),
        dealHelper.accessor('good_label', { header: 'Good' }),
        dealHelper.accessor('monthly_volume', {
          header: 'A month',
          cell: ({ row }) => `${qty(row.original.monthly_volume)} ${row.original.unit}`,
        }),
        dealHelper.accessor('price_cents', {
          header: 'Price',
          cell: ({ getValue }) => formatMoney(Math.round(getValue())),
        }),
        dealHelper.accessor('end_label', { header: 'Until' }),
        dealHelper.accessor('status', { header: 'Status' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: deals,
    getRowId: (d) => String(d.id),
  });
  return <DataTable table={table} label="Contracts" rowTestId="deal-row" />;
}

function DealForm({
  x,
  busy,
  onAct,
}: {
  x: Refineries;
  busy: boolean;
  onAct: (a: RefiningAction) => void;
}) {
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [good, setGood] = useState(x.goods[0]?.key ?? '');
  const [months, setMonths] = useState<number | string>(x.deal_months_low);
  const [volume, setVolume] = useState<number | string>(100);
  const g = x.goods.find((y) => y.key === good);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8, alignItems: 'end' }}>
      <Select
        aria-label="Side"
        size="xs"
        data={[
          { value: 'buy', label: 'Buy' },
          { value: 'sell', label: 'Sell' },
        ]}
        value={side}
        onChange={(v) => v && setSide(v as 'buy' | 'sell')}
        allowDeselect={false}
      />
      <Select
        aria-label="Good"
        data-testid="deal-good"
        size="xs"
        data={x.goods.map((y) => ({ value: y.key, label: y.label }))}
        value={good}
        onChange={(v) => v && setGood(v)}
        allowDeselect={false}
      />
      <NumberInput
        aria-label="Months"
        size="xs"
        min={x.deal_months_low}
        max={x.deal_months_high}
        value={months}
        onChange={setMonths}
        style={{ width: 80 }}
      />
      <NumberInput
        aria-label="Volume a month"
        size="xs"
        min={0}
        value={volume}
        onChange={setVolume}
        style={{ width: 110 }}
      />
      <span className="tst-muted" style={{ fontSize: 12 }}>
        {g
          ? `${g.unit} a month at ${formatMoney(Math.round(g.price_cents))} now; allocation ${pct(g.allocation)}`
          : ''}
      </span>
      <Button
        size="xs"
        data-testid="sign-deal"
        disabled={busy}
        onClick={() =>
          onAct({ kind: 'deal', side, good, months: Number(months), volume: Number(volume) })
        }
      >
        Sign · energy {x.deal_energy}
      </Button>
    </div>
  );
}

function Fact({
  label,
  value,
  term,
  testId,
}: {
  label: string;
  value: string;
  term?: string;
  testId?: string;
}) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
      <dt className="tst-muted" style={{ width: 170, flexShrink: 0 }}>
        {term ? <Term term={term}>{label}</Term> : label}
      </dt>
      <dd style={{ margin: 0 }} data-testid={testId}>
        {value}
      </dd>
    </div>
  );
}
