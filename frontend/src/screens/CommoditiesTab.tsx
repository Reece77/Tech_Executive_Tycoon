import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { components } from '../api/schema';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useCommodities,
  useCommodityAction,
  useCommodityPlan,
  useOfftakeQuote,
  type Commodities,
  type CommodityPlan,
  type OfftakeBody,
} from '../hooks/api';
import { formatMoney } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

type Good = components['schemas']['CommodityOut'];
type Deal = components['schemas']['CommodityDealOut'];
type Supplier = components['schemas']['SupplierOut'];

const goodHelper = createColumnHelper<GameTableFeatures, Good>();
const dealHelper = createColumnHelper<GameTableFeatures, Deal>();
const supplierHelper = createColumnHelper<GameTableFeatures, Supplier>();
const planHelper = createColumnHelper<GameTableFeatures, CommodityPlan>();

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

function price(x: number): string {
  return x.toLocaleString('en-US', { maximumFractionDigits: x < 100 ? 2 : 0 });
}

/** The Market screen's Commodities tab (M17, formulas.md 33): prices to this month with their
 * history, power by region, your contracts and offtakes, and the suppliers. Display only: every
 * number comes from the API. */
export function CommoditiesTab({ saveId }: { saveId: string }) {
  const data = useCommodities(saveId);
  const [selected, setSelected] = useState('lithium_carbonate');
  if (data.isPending) return <Loading />;
  if (data.error) return <LoadError title="Could not load commodities" error={data.error} />;
  const c = data.data;
  const good = c.goods.find((g) => g.good === selected) ?? c.goods[0];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="commodities">
      <GoodsTable goods={c.goods} selected={good?.good ?? ''} onSelect={setSelected} />
      {good && <PriceChart good={good} />}
      <PlanPanel saveId={saveId} />
      <PowerPanel c={c} />
      <DealsPanel deals={c.deals} />
      <OfftakeForm saveId={saveId} c={c} defaultGood={good?.good ?? ''} />
      <SuppliersTable suppliers={c.suppliers} />
    </div>
  );
}

function GoodsTable({
  goods,
  selected,
  onSelect,
}: {
  goods: Good[];
  selected: string;
  onSelect: (good: string) => void;
}) {
  const columns = useMemo(
    () =>
      goodHelper.columns([
        goodHelper.accessor('label', {
          header: 'Commodity',
          meta: { term: 'commodity.good' },
          cell: ({ row }) => (
            <button
              type="button"
              className="tst-link"
              aria-pressed={row.original.good === selected}
              onClick={() => onSelect(row.original.good)}
              data-testid={`commodity-${row.original.good}`}
            >
              {row.original.label}
            </button>
          ),
        }),
        goodHelper.accessor('price', {
          header: 'Price',
          meta: { term: 'commodity.price' },
          cell: ({ row }) => (
            <span className="tst-num">
              {price(row.original.price)} <span className="tst-muted">{row.original.unit}</span>
            </span>
          ),
        }),
        goodHelper.accessor('index', {
          header: 'Index',
          meta: { term: 'commodity.index' },
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(2)}</span>,
        }),
        goodHelper.accessor('change_12m', {
          header: '12 months',
          meta: { term: 'commodity.change' },
          cell: ({ getValue }) => (
            <span className="tst-num">
              {getValue() >= 0 ? '+' : ''}
              {pct(getValue())}
            </span>
          ),
        }),
        goodHelper.accessor('allocation', {
          header: 'Allocation',
          meta: { term: 'commodity.allocation' },
          cell: ({ row }) => (
            <span title={row.original.note}>
              {pct(row.original.allocation)}{' '}
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.note}
              </span>
            </span>
          ),
        }),
        goodHelper.accessor('use_month', {
          header: 'Your use',
          meta: { term: 'commodity.use' },
          cell: ({ row }) => (
            <span className="tst-num">
              {price(row.original.use_month)} {row.original.volume_unit}
            </span>
          ),
        }),
      ]),
    [selected, onSelect],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: goods,
    getRowId: (g) => g.good,
  });
  return (
    <DataTable
      table={table}
      label="Commodities"
      rowTestId="commodity-row"
      selectedRowId={selected}
    />
  );
}

function PriceChart({ good }: { good: Good }) {
  return (
    <Panel title={`${good.label}: price by month`} testId="commodity-chart">
      <p className="tst-muted" style={{ margin: 0, fontSize: 13 }} data-testid="commodity-peak">
        <Term term="commodity.peak">Highest shown</Term>: {price(good.peak_price)} {good.unit} (
        {good.peak_label}) · long-run level {price(good.long_run)} {good.unit} · largest producer{' '}
        {good.top_country} {pct(good.top_share)}
      </p>
      <div role="img" aria-label={`${good.label} price by month`}>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={good.history} margin={{ top: 10, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--tst-muted)"
              fontSize={11}
              fontFamily="var(--tst-font-mono)"
            />
            <YAxis
              stroke="var(--tst-muted)"
              fontSize={11}
              fontFamily="var(--tst-font-mono)"
              tickFormatter={(v: number) => price(v)}
              width={64}
            />
            <Tooltip
              formatter={(v) => `${price(Number(v))} ${good.unit}`}
              contentStyle={{
                background: 'var(--tst-panel)',
                border: '1px solid var(--tst-border)',
                fontFamily: 'var(--tst-font-mono)',
              }}
            />
            <Line
              type="linear"
              dataKey="price"
              name="Price"
              stroke="var(--tst-accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

function PowerPanel({ c }: { c: Commodities }) {
  return (
    <Panel title="Industrial power by region" testId="power-by-region">
      <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
        <Term term="commodity.power">Against North America (1.0)</Term>: a data centre&apos;s
        operating cost is multiplied by its region&apos;s index.
      </p>
      {c.power.map((p) => (
        <div key={p.region} className="tst-row" data-testid={`power-${p.region}`}>
          <span>{p.label}</span>
          <span className="tst-num">{p.index.toFixed(2)}</span>
        </div>
      ))}
    </Panel>
  );
}

function DealsPanel({ deals }: { deals: Deal[] }) {
  const columns = useMemo(
    () =>
      dealHelper.columns([
        dealHelper.accessor('good_label', {
          header: 'Deal',
          meta: { term: 'commodity.deal' },
          cell: ({ row }) => (
            <div>
              <div>
                {row.original.good_label} {row.original.kind}
                {row.original.supplier_name ? ` with ${row.original.supplier_name}` : ''}
              </div>
              <div className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.signed} – {row.original.ends} · {row.original.status} ·{' '}
                {price(row.original.volume_year)} a year
              </div>
            </div>
          ),
        }),
        dealHelper.accessor('price_now', {
          header: 'Collar',
          meta: { term: 'commodity.collar' },
          cell: ({ row }) => (
            <span className="tst-num">
              {price(row.original.floor)}–{price(row.original.ceiling)}{' '}
              <span className="tst-muted">pays {price(row.original.price_now)}</span>
            </span>
          ),
        }),
        dealHelper.accessor('hedge_cents', {
          header: 'Saved',
          meta: { term: 'commodity.saved' },
          cell: ({ getValue }) => <span className="tst-num">{formatMoney(getValue())}</span>,
        }),
        dealHelper.accessor('charged_cents', {
          header: 'Take-or-pay',
          meta: { term: 'commodity.take_or_pay' },
          cell: ({ getValue }) => <span className="tst-num">{formatMoney(getValue())}</span>,
        }),
        dealHelper.accessor('prepaid_left_cents', {
          header: 'Prepaid left',
          meta: { term: 'commodity.prepaid' },
          cell: ({ getValue }) => <span className="tst-num">{formatMoney(getValue())}</span>,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: deals,
    getRowId: (d) => String(d.deal_id),
  });
  return (
    <Panel title="Your contracts and offtakes" testId="commodity-deals">
      <DataTable
        table={table}
        label="Contracts and offtakes"
        rowTestId="deal-row"
        empty="No deals: you buy every commodity at spot."
      />
    </Panel>
  );
}

function OfftakeForm({
  saveId,
  c,
  defaultGood,
}: {
  saveId: string;
  c: Commodities;
  defaultGood: string;
}) {
  const quote = useOfftakeQuote(saveId);
  const act = useCommodityAction(saveId);
  const [good, setGood] = useState(defaultGood);
  const sellers = c.suppliers.filter((s) => s.goods.some((g) => g.good === good && g.open));
  const [supplier, setSupplier] = useState<string | null>(null);
  const pick = supplier && sellers.some((s) => s.key === supplier) ? supplier : sellers[0]?.key;
  const [years, setYears] = useState(c.offtake_years[0]);
  const [volume, setVolume] = useState(10);
  const [prepay, setPrepay] = useState(0);
  const body: OfftakeBody | null = pick
    ? { good, supplier: pick, years, volume_year: volume, prepay: prepay / 100 }
    : null;
  const unit = c.goods.find((g) => g.good === good)?.volume_unit ?? '';
  return (
    <Panel title="Sign an offtake" testId="offtake-form">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end' }}>
        <Select
          label="Commodity"
          data-testid="offtake-good"
          value={good}
          onChange={(v) => {
            if (v) setGood(v);
            quote.reset();
          }}
          data={c.goods.map((g) => ({ value: g.good, label: g.label }))}
        />
        <Select
          label="Supplier"
          data-testid="offtake-supplier"
          value={pick ?? null}
          onChange={(v) => {
            setSupplier(v);
            quote.reset();
          }}
          data={sellers.map((s) => ({ value: s.key, label: s.name }))}
        />
        <NumberInput
          label="Years"
          data-testid="offtake-years"
          min={c.offtake_years[0]}
          max={c.offtake_years[1]}
          value={years}
          onChange={(v) => setYears(Number(v) || c.offtake_years[0])}
        />
        <NumberInput
          label={`Volume a year (${unit})`}
          data-testid="offtake-volume"
          min={0}
          decimalScale={2}
          value={volume}
          onChange={(v) => setVolume(Number(v) || 0)}
        />
        <NumberInput
          label={`Prepay (% of year 1, at most ${pct(c.prepay_max)})`}
          data-testid="offtake-prepay"
          min={0}
          max={Math.round(c.prepay_max * 100)}
          value={prepay}
          onChange={(v) => setPrepay(Number(v) || 0)}
        />
        <Button
          variant="default"
          disabled={!body || quote.isPending}
          onClick={() => body && quote.mutate(body)}
          data-testid="offtake-quote"
        >
          Quote
        </Button>
        <Button
          disabled={!body || act.isPending}
          onClick={() => body && act.mutate({ kind: 'offtake', ...body })}
          data-testid="offtake-sign"
        >
          Sign ({c.offtake_energy} energy)
        </Button>
      </div>
      {quote.data && (
        <p style={{ margin: 0, fontSize: 13 }} data-testid="offtake-quote-out">
          <Term term="commodity.collar">Collar</Term> {price(quote.data.floor)}–
          {price(quote.data.ceiling)} around {price(quote.data.price)} now; a year&apos;s volume{' '}
          {formatMoney(quote.data.year_value_cents)}; prepaid{' '}
          {formatMoney(quote.data.prepaid_cents)}; take-or-pay {pct(c.offtake_take_or_pay)} of each
          month&apos;s volume.
        </p>
      )}
      {quote.error && <Alert color="red">{quote.error.message}</Alert>}
      {act.error && <Alert color="red">{act.error.message}</Alert>}
    </Panel>
  );
}

function SuppliersTable({ suppliers }: { suppliers: Supplier[] }) {
  const columns = useMemo(
    () =>
      supplierHelper.columns([
        supplierHelper.accessor('name', {
          header: 'Supplier',
          meta: { term: 'commodity.supplier' },
          cell: ({ row }) => (
            <div>
              <div>{row.original.name}</div>
              <div className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.region_label} · {row.original.listing} ·{' '}
                {row.original.goods.map((g) => `${g.label} ${pct(g.share)}`).join(', ') ||
                  'silicon wafers'}
              </div>
            </div>
          ),
        }),
        supplierHelper.accessor('reliability', {
          header: 'Reliability',
          meta: { term: 'commodity.reliability' },
          cell: ({ getValue }) => <span className="tst-num">{pct(getValue())}</span>,
        }),
        supplierHelper.accessor('revenue_2010_usd_m', {
          header: '2010 revenue',
          meta: { term: 'commodity.revenue_2010' },
          cell: ({ row }) => (
            <span className="tst-num" title={row.original.revenue_note ?? undefined}>
              {row.original.revenue_2010_usd_m === null
                ? '—'
                : `$${price(row.original.revenue_2010_usd_m)}M`}
            </span>
          ),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: suppliers,
    getRowId: (s) => s.key,
  });
  return (
    <Panel title="Suppliers" testId="suppliers">
      <DataTable table={table} label="Suppliers" rowTestId="supplier-row" />
    </Panel>
  );
}

function vol(x: number, unit: string): string {
  return `${x.toLocaleString('en-US', { maximumFractionDigits: x < 10 ? 2 : 0 })} ${unit}`;
}

/** The planning view (M23c, playtest 5): each commodity's need over the next 12 months at
 * this month's production, the products that drive it, and how much your contracts, offtakes
 * and own supply cover, month by month as deals end. A projection at the current run rate. */
function PlanPanel({ saveId }: { saveId: string }) {
  const plan = useCommodityPlan(saveId);
  const [open, setOpen] = useState<string | null>(null);
  const columns = useMemo(
    () =>
      planHelper.columns([
        planHelper.accessor('label', {
          header: 'Commodity',
          meta: { term: 'commodity.good' },
          cell: ({ row }) => (
            <Button
              variant="subtle"
              size="compact-xs"
              onClick={() => setOpen(row.original.good)}
              data-testid="plan-open"
            >
              {row.original.label}
            </Button>
          ),
        }),
        planHelper.accessor('need_12m', {
          header: 'Need, 12 months',
          meta: { term: 'commodity.need' },
          cell: ({ row }) => vol(row.original.need_12m, row.original.volume_unit),
        }),
        planHelper.accessor('deals_12m', {
          header: 'Deals cover',
          meta: { term: 'commodity.deal_cover' },
          cell: ({ row }) => vol(row.original.deals_12m, row.original.volume_unit),
        }),
        planHelper.accessor('own_12m', {
          header: 'Own supply',
          meta: { term: 'commodity.own_supply' },
          cell: ({ row }) => vol(row.original.own_12m, row.original.volume_unit),
        }),
        planHelper.accessor('cover', {
          header: 'Covered',
          meta: { term: 'commodity.cover' },
          cell: ({ getValue }) => {
            const v = getValue();
            return v === null || v === undefined ? '—' : pct(v);
          },
        }),
        planHelper.accessor('gap_12m', {
          header: 'Uncovered',
          meta: { term: 'commodity.gap' },
          cell: ({ row }) => vol(row.original.gap_12m, row.original.volume_unit),
        }),
        planHelper.display({
          id: 'drivers',
          header: 'Driven by',
          meta: { term: 'commodity.drivers' },
          cell: ({ row }) =>
            row.original.drivers.map((d) => `${d.name} ${pct(d.share)}`).join(', ') || '—',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: plan.data?.plans ?? [],
    getRowId: (p) => p.good,
  });
  if (plan.error) return <LoadError title="Could not load the plan" error={plan.error} />;
  if (!plan.data) return null;
  const shown = plan.data.plans.find((p) => p.good === open) ?? plan.data.plans[0];
  return (
    <Panel title="Planning: the next 12 months" testId="plan-panel">
      <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
        What your products will use at this month&apos;s production ({plan.data.turn_label}), and
        how much your running contracts and offtakes and your group&apos;s own supply cover. A
        projection at the current run rate: new launches and growth add to it.
      </p>
      {plan.data.plans.length === 0 ? (
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Your products use no commodities yet: devices and chips do.
        </p>
      ) : (
        <DataTable table={table} label="Commodity plan" rowTestId="plan-row" />
      )}
      {shown && (
        <div style={{ marginTop: 10 }} data-testid="plan-months">
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            {shown.label} by month ({shown.volume_unit}):
            {shown.deals_ending.length > 0 && (
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {' '}
                deals end {shown.deals_ending.join(', ')}
              </span>
            )}
            {shown.mines_12m > 0 && (
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {' '}
                · your mines produce {vol(shown.mines_12m, shown.volume_unit)} a year (sold at
                market unless supplied to the group)
              </span>
            )}
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
              gap: 4,
              fontSize: 11,
            }}
          >
            {shown.months.map((m) => {
              const covered = m.required > 0 ? Math.min(1, (m.deals + m.own) / m.required) : 1;
              return (
                <div
                  key={m.turn}
                  title={`${m.label}: need ${vol(m.required, shown.volume_unit)}, deals ${vol(m.deals, shown.volume_unit)}, own ${vol(m.own, shown.volume_unit)}, uncovered ${vol(m.gap, shown.volume_unit)}`}
                  data-testid="plan-month"
                >
                  <div
                    style={{
                      height: 28,
                      background: 'var(--tst-track)',
                      borderRadius: 3,
                      display: 'flex',
                      alignItems: 'flex-end',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: '100%',
                        height: `${Math.round(covered * 100)}%`,
                        background: 'var(--tst-accent)',
                      }}
                    />
                  </div>
                  <div className="tst-muted" style={{ textAlign: 'center' }}>
                    {m.label.slice(0, 3)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Panel>
  );
}
