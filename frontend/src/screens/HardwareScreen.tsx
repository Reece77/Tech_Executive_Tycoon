import { Alert, Button, Modal, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { KpiTile } from '../components/KpiTile';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useHardware,
  useHardwareAction,
  useOrg,
  type Hardware,
  type HardwareAction,
  type Manufacturing,
  type Plant,
} from '../hooks/api';
import { formatMoney, formatMoneyShort, formatMoneyWhole, formatWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, Plant>();

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

/** Hardware (M12b, formulas.md 26.5): plants, contracts, chips and hardware indexes. */
export function HardwareScreen() {
  const { saveId = '' } = useParams();
  const hw = useHardware(saveId);
  if (hw.isPending) return <Loading />;
  if (hw.error) return <LoadError title="Could not load hardware" error={hw.error} />;
  return <Body saveId={saveId} hw={hw.data} />;
}

type Dialog = 'cm' | 'plant' | 'wafer' | null;

function Body({ saveId, hw }: { saveId: string; hw: Hardware }) {
  const act = useHardwareAction(saveId);
  const [params] = useSearchParams(); // a plant pitch's Modify (M15b)
  const [dialog, setDialog] = useState<Dialog>(params.get('plant') !== null ? 'plant' : null);
  const run = (a: HardwareAction, done?: () => void) => act.mutate(a, { onSuccess: done });
  const devices = hw.products.filter((p) => !hw.chips.some((c) => c.product_id === p.product_id));
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <ScreenTitle
        aside={
          <>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="hardware-summary">
              {devices.length} devices and servers · {hw.chips.length} chips · {hw.plants.length}{' '}
              plants · {hw.contracts.filter((c) => c.status === 'active').length} contracts
            </span>
            <Button
              variant="default"
              style={{ marginLeft: 'auto' }}
              disabled={devices.length === 0}
              onClick={() => setDialog('cm')}
              data-testid="cm-open"
            >
              Sign a manufacturing contract · {hw.contract_energy}
            </Button>
            <Button variant="default" onClick={() => setDialog('plant')} data-testid="plant-open">
              Build a plant · {hw.build_energy}
            </Button>
            <Button
              disabled={hw.chips.length === 0}
              onClick={() => setDialog('wafer')}
              data-testid="wafer-open"
            >
              Sign a foundry contract · {hw.wafer_energy}
            </Button>
          </>
        }
      >
        Hardware
      </ScreenTitle>
      {act.error && (
        <Alert color="warn" data-testid="hardware-error">
          {act.error.message}
        </Alert>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }} data-testid="hardware-strip">
        {hw.components.map((c) => (
          <KpiTile
            key={c.good}
            label={c.label}
            term="infra.component_index"
            value={`${c.index.toFixed(2)}×`}
            note={`${c.change_12m >= 0 ? '+' : ''}${pct(c.change_12m)} this year · ${c.note}`}
            warn={c.allocation < 1}
            testId={`hw-component-${c.good}`}
          />
        ))}
      </div>
      {hw.products.length === 0 && (
        <Panel title="Unit cost">
          <p className="tst-muted" style={{ margin: 0 }} data-testid="no-hardware">
            No hardware products yet. Create a device, server or chip on Products; it needs a
            manufacturing contract (or a foundry contract for a chip) before it can launch.
          </p>
        </Panel>
      )}
      {hw.products.map((p) => (
        <ManufacturingPanel key={p.product_id} m={p} />
      ))}
      <Panel title="Assembly plants" testId="plants-panel">
        <PlantsTable
          plants={hw.plants}
          saveId={saveId}
          busy={act.isPending}
          onStaff={(facilityId, unitId) => run({ kind: 'staff', facilityId, unitId })}
          onSell={(facilityId) => run({ kind: 'sell', facilityId })}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Your products use your plants first, then their contracts. A plant needs one manufacturing
          engineer per {formatWhole(hw.plant_staff_per)} units a month (assign a unit); its yield
          comes from their manufacturing skill. It costs its fixed cost every month, so it pays off
          only when it is well used.
        </p>
      </Panel>
      <CmPanel hw={hw} busy={act.isPending} onStart={() => run({ kind: 'sell_capacity' })} />
      <Panel title="Contracts" testId="hw-contracts-panel">
        {hw.contracts.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            No contracts. Contract manufacturing runs {hw.contract_months[0]}–
            {hw.contract_months[1]} months and charges {pct(hw.contract_take_or_pay)} of the fee on
            unused volume each month; foundry contracts run {hw.wafer_months[0]}–
            {hw.wafer_months[1]} months ({pct(hw.wafer_take_or_pay)} on unused wafers). A contract
            signed before a shortage keeps full allocation.
          </p>
        ) : (
          hw.contracts.map((c) => (
            <div key={c.contract_id} className="tst-row" data-testid="hw-contract-row">
              <span>
                {c.kind === 'assembly' ? 'Assembly' : 'Wafers'} for {c.product_name} ·{' '}
                {c.supplier_label}
                {c.city_label ? ` in ${c.city_label}` : ''} · {formatWhole(c.units)}
                {c.kind === 'wafer' ? ' wafers' : ' units'} a month at {formatMoney(c.price_cents)}{' '}
                · until {c.ends}
              </span>
              <span className="tst-num">
                used {formatWhole(c.used)} of {formatWhole(c.delivered)} · take-or-pay{' '}
                {formatMoneyWhole(c.take_or_pay_cents)}
              </span>
            </div>
          ))
        )}
      </Panel>
      <ChipsPanel hw={hw} />
      {dialog === 'cm' && (
        <CmDialog
          hw={hw}
          products={devices}
          busy={act.isPending}
          onClose={() => setDialog(null)}
          onSign={(a) => run(a, () => setDialog(null))}
        />
      )}
      {dialog === 'plant' && (
        <PlantDialog
          hw={hw}
          busy={act.isPending}
          onClose={() => setDialog(null)}
          onBuild={(a) => run(a, () => setDialog(null))}
        />
      )}
      {dialog === 'wafer' && (
        <WaferDialog
          hw={hw}
          busy={act.isPending}
          onClose={() => setDialog(null)}
          onSign={(a) => run(a, () => setDialog(null))}
        />
      )}
    </>
  );
}

/** A product's unit cost by line and its manufacturing (also on the Product screen). */
export function ManufacturingPanel({ m }: { m: Manufacturing }) {
  return (
    <Panel title={`Unit cost: ${m.name}`} testId="manufacturing-panel">
      {m.lines.map((line) => (
        <div key={line.line} className="tst-row" data-testid="bom-line">
          <span>
            {line.line} <span className="tst-muted">· {line.detail}</span>
          </span>
          <span className="tst-num">{formatMoney(line.cents)}</span>
        </div>
      ))}
      {(m.commodity_lines ?? []).length > 0 && (
        <div data-testid="commodity-lines" style={{ marginTop: 6 }}>
          <div className="tst-muted" style={{ fontSize: 12 }}>
            <Term term="commodity.cost_line">Commodities in a unit</Term> · spot, then after your
            deals (<Term term="commodity.hedged">share hedged</Term>)
          </div>
          {(m.commodity_lines ?? []).map((c) => (
            <div key={c.good} className="tst-row" data-testid={`commodity-line-${c.good}`}>
              <span>
                {c.label}{' '}
                <span className="tst-muted">
                  · weight {Math.round(c.weight * 100)}% · index {c.index.toFixed(2)}
                </span>
              </span>
              <span className="tst-num">
                {formatMoney(Math.round(c.spot_cents))} spot
                {c.hedged_share > 0 && (
                  <span data-testid={`commodity-hedged-${c.good}`}>
                    {' '}
                    → {formatMoney(Math.round(c.deal_cents))} ({Math.round(c.hedged_share * 100)}%
                    hedged)
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8 }}>
        <KpiTile
          label="Unit cost"
          term="hardware.unit_cost"
          value={formatMoney(m.unit_cost_cents)}
          testId="unit-cost"
        />
        <KpiTile
          label="Gross margin"
          term="hardware.gross_margin"
          value={m.gross_margin === null ? '—' : pct(m.gross_margin)}
          note={m.price_cents === null ? 'no price yet' : `at ${formatMoney(m.price_cents)}`}
          warn={m.gross_margin !== null && m.gross_margin < 0}
          testId="gross-margin"
        />
        <KpiTile
          label="Sold last month"
          term="hardware.units_sold"
          value={formatWhole(m.units_sold)}
          note={m.units_lost > 0.5 ? `${formatWhole(m.units_lost)} more wanted` : undefined}
          warn={m.units_lost > 0.5}
          testId="units-sold"
        />
      </div>
      {m.sources.map((s) => (
        <div key={s.label} className="tst-row" data-testid="source-row">
          <span>{s.label}</span>
          <span className="tst-num">
            made {formatWhole(s.units)} of {formatWhole(s.available)}
          </span>
        </div>
      ))}
      {!m.can_launch_source && (
        <p className="tst-muted" style={{ fontSize: 12 }} data-testid="needs-source">
          No manufacturing source yet: sign a {m.chip_source === null ? 'foundry' : 'manufacturing'}{' '}
          contract{m.chip_source === null ? '' : ' or build a plant'} before launch.
        </p>
      )}
    </Panel>
  );
}

function PlantsTable({
  plants,
  saveId,
  busy,
  onStaff,
  onSell,
}: {
  plants: Plant[];
  saveId: string;
  busy: boolean;
  onStaff: (facilityId: number, unitId: number | null) => void;
  onSell: (facilityId: number) => void;
}) {
  const org = useOrg(saveId);
  const units = (org.data?.units ?? []).filter((u) => u.unit_id !== null);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Plant',
          meta: { term: 'hardware.plant' },
          cell: ({ row }) => (
            <div>
              <div>{row.original.name}</div>
              <div className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.city_label ?? ''} ·{' '}
                {row.original.status === 'building' ? 'ordered' : 'since'} {row.original.since}
              </div>
            </div>
          ),
        }),
        helper.accessor('units', {
          header: 'Size',
          meta: { term: 'hardware.plant_size' },
          cell: ({ getValue }) => (
            <span className="tst-num">{formatWhole(getValue())} / month</span>
          ),
        }),
        helper.display({
          id: 'use',
          header: 'Use',
          meta: { term: 'hardware.plant_use' },
          cell: ({ row }) =>
            row.original.status === 'building' ? (
              <span data-testid="plant-progress">
                {pct(row.original.build_progress ?? 0)} built · ready {row.original.ready}
              </span>
            ) : (
              <span data-testid="plant-use">
                yours {formatWhole(row.original.own_use)} · sold{' '}
                {formatWhole(row.original.sold_use)} ({pct(row.original.utilization)})
              </span>
            ),
        }),
        helper.accessor('plant_yield', {
          header: 'Yield',
          meta: { term: 'hardware.plant_yield' },
          cell: ({ getValue }) => {
            const v = getValue();
            return <span className="tst-num">{v === null ? '—' : `${(v * 100).toFixed(1)}%`}</span>;
          },
        }),
        helper.display({
          id: 'staff',
          header: 'Staff',
          meta: { term: 'hardware.plant_staff' },
          cell: ({ row }) => {
            const f = row.original;
            return (
              <div>
                <span
                  className="tst-num"
                  style={{ color: f.coverage < 1 ? 'var(--tst-warn)' : undefined }}
                >
                  {f.staff} of {f.staff_needed}
                </span>
                <Select
                  size="xs"
                  placeholder="Assign a unit"
                  aria-label="Plant staffing unit"
                  data-testid="plant-staff-unit"
                  disabled={busy}
                  data={[
                    { value: 'none', label: 'Nobody' },
                    ...units.map((u) => ({ value: String(u.unit_id), label: u.name })),
                  ]}
                  value={f.unit_id === null ? null : String(f.unit_id)}
                  onChange={(v) => v && onStaff(f.facility_id, v === 'none' ? null : Number(v))}
                />
              </div>
            );
          },
        }),
        helper.accessor('cost_per_good_unit_cents', {
          header: 'Cost per good unit',
          meta: { term: 'hardware.cost_per_good' },
          cell: ({ row }) => {
            const f = row.original;
            if (f.cost_per_good_unit_cents === null) return <span className="tst-muted">—</span>;
            return (
              <span className="tst-num" data-testid="plant-cost">
                {formatMoney(f.cost_per_good_unit_cents)}{' '}
                <span className="tst-muted">contract {formatMoney(f.contract_fee_cents)}</span>
              </span>
            );
          },
        }),
        helper.accessor('book_value_cents', {
          header: 'Book value',
          meta: { term: 'infra.book_value' },
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        helper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) => (
            <Button
              size="xs"
              variant="subtle"
              disabled={busy}
              onClick={() => onSell(row.original.facility_id)}
            >
              Sell
            </Button>
          ),
        }),
      ]),
    [onSell, onStaff, units, busy],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: plants,
    getRowId: (f) => String(f.facility_id),
  });
  if (plants.length === 0) {
    return (
      <p className="tst-muted" style={{ margin: 0 }} data-testid="no-plants">
        No plants: contract manufacturers build your devices for a fee a unit.
      </p>
    );
  }
  return <DataTable table={table} label="Assembly plants" rowTestId="plant-row" />;
}

function CmPanel({ hw, busy, onStart }: { hw: Hardware; busy: boolean; onStart: () => void }) {
  const cm = hw.cm;
  return (
    <Panel title="Contract manufacturing (selling spare plant capacity)" testId="cm-panel">
      {!cm.started ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="tst-muted">
            Sell what your products leave free in your plants to other device makers, against
            Foxconn and Pegatron. Your yield times reliability is the product&apos;s quality.
          </span>
          <Button disabled={!cm.can_start} loading={busy} onClick={onStart} data-testid="cm-start">
            Sell spare capacity
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <KpiTile
            label="Units sold"
            term="hardware.cm_units"
            value={formatWhole(cm.units_sold)}
            note={`a month · ${formatWhole(cm.spare_units)} spare`}
            testId="cm-units"
          />
          <KpiTile
            label="Revenue"
            term="hardware.cm_revenue"
            value={formatMoneyWhole(cm.revenue_cents)}
            note="a month"
          />
        </div>
      )}
    </Panel>
  );
}

function ChipsPanel({ hw }: { hw: Hardware }) {
  return (
    <Panel title="Chips" testId="chips-panel">
      {hw.chips.length === 0 ? (
        <p className="tst-muted" style={{ margin: 0 }}>
          No chips. Design a mobile SoC, server CPU or AI accelerator on Products; it is made on
          wafers a foundry processes for you on a foundry contract.
        </p>
      ) : (
        hw.chips.map((c) => (
          <div key={c.product_id} className="tst-row" data-testid="chip-row">
            <span>
              {c.name} · {c.chip_label} · {c.per_wafer} a wafer · yield {pct(c.chip_yield)} ·{' '}
              {formatWhole(c.wafers)} wafer starts a month on foundry contracts (about{' '}
              {formatWhole(c.wafers * c.per_wafer * c.chip_yield)} good chips)
              {c.gpu_capex_factor !== null && (
                <span data-testid="gpu-capex">
                  {' '}
                  · GPU data-centre capex ×{c.gpu_capex_factor.toFixed(2)}
                </span>
              )}
            </span>
            <span className="tst-num" data-testid="chip-cost">
              {formatMoney(c.unit_cost_cents)} a chip ={' '}
              <Term term="chips.material">wafer material</Term> {formatMoney(c.material_cents)} +{' '}
              <Term term="chips.processing">foundry processing</Term>{' '}
              {formatMoney(c.processing_cents)} + packaging {formatMoney(c.packaging_cents)} (market{' '}
              {formatMoney(c.market_price_cents)})
            </span>
            <span className="tst-num" data-testid="chip-use">
              {c.used_in.length > 0 || c.internal_units > 0
                ? `used in ${formatWhole(c.internal_units)} of your ${c.used_in.join(', ') || 'devices'} last month (at cost: its revenue is the devices')`
                : 'not used in your devices'}
              {' · '}sold {formatWhole(c.market_units)} to the chip market
            </span>
          </div>
        ))
      )}
      <p className="tst-muted" style={{ fontSize: 12 }}>
        Your own devices and servers use your own chip of their type first, at cost: that books no
        revenue. An AI accelerator of your own cuts your GPU data centres&apos; capex.
      </p>
    </Panel>
  );
}

function CmDialog({
  hw,
  products,
  busy,
  onClose,
  onSign,
}: {
  hw: Hardware;
  products: Manufacturing[];
  busy: boolean;
  onClose: () => void;
  onSign: (a: HardwareAction) => void;
}) {
  const [productId, setProductId] = useState(String(products[0]?.product_id ?? ''));
  const [manufacturer, setManufacturer] = useState(hw.manufacturers[0]?.key ?? '');
  const [city, setCity] = useState(hw.cheap_city);
  const [units, setUnits] = useState<number>(10_000);
  const [months, setMonths] = useState<number>(hw.contract_months[1]);
  return (
    <Modal opened onClose={onClose} title="Contract manufacturing">
      <Select
        label="Product"
        data={products.map((p) => ({ value: String(p.product_id), label: p.name }))}
        value={productId}
        onChange={(v) => v && setProductId(v)}
        data-testid="cm-product"
      />
      <Select
        label="Manufacturer"
        data={hw.manufacturers.map((m) => ({ value: m.key, label: m.label }))}
        value={manufacturer}
        onChange={(v) => v && setManufacturer(v)}
      />
      <Select
        label="City (Shenzhen is cheapest)"
        data={hw.cities.map((c) => ({ value: c.key, label: c.label }))}
        value={city}
        onChange={(v) => v && setCity(v)}
        searchable
      />
      <NumberInput
        label="Units a month"
        value={units}
        min={1}
        onChange={(v) => setUnits(Number(v))}
        data-testid="cm-units-input"
      />
      <NumberInput
        label="Months"
        value={months}
        min={hw.contract_months[0]}
        max={hw.contract_months[1]}
        onChange={(v) => setMonths(Number(v))}
      />
      <p className="tst-muted" style={{ fontSize: 12 }}>
        Unused volume costs {pct(hw.contract_take_or_pay)} of the fee each month. Energy{' '}
        {hw.contract_energy}.
      </p>
      <Button
        loading={busy}
        data-testid="cm-sign"
        onClick={() =>
          onSign({
            kind: 'cm',
            productId: Number(productId),
            manufacturer,
            city,
            units,
            months,
          })
        }
      >
        Sign
      </Button>
    </Modal>
  );
}

function PlantDialog({
  hw,
  busy,
  onClose,
  onBuild,
}: {
  hw: Hardware;
  busy: boolean;
  onClose: () => void;
  onBuild: (a: HardwareAction) => void;
}) {
  const [params] = useSearchParams();
  const [city, setCity] = useState(hw.cheap_city);
  const [units, setUnits] = useState(params.get('plant') || String(hw.plant_sizes[0] ?? ''));
  const size = Number(units);
  return (
    <Modal opened onClose={onClose} title="Build an assembly plant">
      <Select
        label="City"
        data={hw.cities.map((c) => ({ value: c.key, label: c.label }))}
        value={city}
        onChange={(v) => v && setCity(v)}
        searchable
        data-testid="plant-city"
      />
      <Select
        label="Units a month"
        data={hw.plant_sizes.map((s) => ({ value: String(s), label: formatWhole(s) }))}
        value={units}
        onChange={(v) => v && setUnits(v)}
        data-testid="plant-size"
      />
      <p className="tst-muted" style={{ fontSize: 12 }} data-testid="plant-quote">
        Capex {formatMoneyWhole(size * hw.plant_capex_per_unit_cents)}, paid over{' '}
        {hw.plant_build_months} months; needs {Math.ceil(size / hw.plant_staff_per)} manufacturing
        engineers. Energy {hw.build_energy}.
      </p>
      <Button
        loading={busy}
        data-testid="plant-build"
        onClick={() => onBuild({ kind: 'plant', city, units: size })}
      >
        Build
      </Button>
    </Modal>
  );
}

function WaferDialog({
  hw,
  busy,
  onClose,
  onSign,
}: {
  hw: Hardware;
  busy: boolean;
  onClose: () => void;
  onSign: (a: HardwareAction) => void;
}) {
  const [productId, setProductId] = useState(String(hw.chips[0]?.product_id ?? ''));
  const [foundry, setFoundry] = useState(hw.foundries[0]?.key ?? '');
  const [wafers, setWafers] = useState<number>(50);
  const [months, setMonths] = useState<number>(24);
  return (
    <Modal opened onClose={onClose} title="Foundry contract">
      <Select
        label="Chip"
        data={hw.chips.map((c) => ({ value: String(c.product_id), label: c.name }))}
        value={productId}
        onChange={(v) => v && setProductId(v)}
        data-testid="wafer-product"
      />
      <Select
        label="Foundry"
        data={hw.foundries.map((f) => ({ value: f.key, label: f.label }))}
        value={foundry}
        onChange={(v) => v && setFoundry(v)}
      />
      <NumberInput
        label="Wafer starts a month"
        value={wafers}
        min={1}
        onChange={(v) => setWafers(Number(v))}
        data-testid="wafer-count"
      />
      <NumberInput
        label="Months"
        value={months}
        min={hw.wafer_months[0]}
        max={hw.wafer_months[1]}
        onChange={(v) => setMonths(Number(v))}
      />
      <p className="tst-muted" style={{ fontSize: 12 }}>
        The wafer price is locked at this month&apos;s; unused wafers cost{' '}
        {pct(hw.wafer_take_or_pay)} of their price each month. Energy {hw.wafer_energy}.
      </p>
      <Button
        loading={busy}
        data-testid="wafer-sign"
        onClick={() =>
          onSign({ kind: 'wafer', productId: Number(productId), foundry, wafers, months })
        }
      >
        Sign
      </Button>
    </Modal>
  );
}
