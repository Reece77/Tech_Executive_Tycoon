// Vehicles (M38, formulas.md 49): EV markets by region (share, sales, charging, subsidies,
// tariffs, approvals), battery prices, rivals' line-ups and shares, the player's cars, vehicle
// plants, cell plants and charging networks; building a cell plant or a network. A car line's page
// shows its bill of materials, range, platform, autonomy by region, subsidy eligibility and
// software revenue, and sets its design. No game values are computed here: figures are formatted.
import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import { turnLabel } from '../hooks/power';
import {
  pct,
  useBuildCellPlant,
  useBuildCharging,
  useSetChargingAccess,
  useSetVehicleSpec,
  useVehicleCar,
  useVehicles,
  type CellPlant,
  type Charging,
  type MyCar,
  type RivalCar,
  type VehicleRegion,
  type Vehicles,
} from '../hooks/vehicles';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const regionHelper = createColumnHelper<GameTableFeatures, VehicleRegion>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalCar>();
const carHelper = createColumnHelper<GameTableFeatures, MyCar>();
const cellHelper = createColumnHelper<GameTableFeatures, CellPlant>();
const chargeHelper = createColumnHelper<GameTableFeatures, Charging>();

const LEVEL_LABELS: Record<string, string> = {
  none: 'None',
  l2: 'L2',
  l2_plus: 'L2+',
  l3: 'L3',
  l4: 'L4',
};

function level(key: string): string {
  return LEVEL_LABELS[key] ?? key;
}

export function VehiclesScreen() {
  const { saveId = '' } = useParams();
  const q = useVehicles(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load vehicles" error={q.error} />;
  return <VehiclesBody saveId={saveId} v={q.data} />;
}

function VehiclesBody({ saveId, v }: { saveId: string; v: Vehicles }) {
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="vehicles.scale">{v.scale_note}</Term>
            {v.in_history && ' History holds to December 2025.'}
          </span>
        }
      >
        Vehicles
      </ScreenTitle>
      <Panel title="Markets" testId="vehicles-regions">
        <RegionTable v={v} />
      </Panel>
      <Panel title="Batteries" testId="vehicles-battery">
        <p data-testid="battery-price" style={{ margin: '0 0 8px' }}>
          Cells {formatMoney(Math.round(v.battery.cell_cents))} a{' '}
          <Term term="vehicles.kwh">kWh</Term>, packs{' '}
          {formatMoney(Math.round(v.battery.pack_cents))} a kWh (2010 dollars){' '}
          <Explain metric="battery_price" entity={null} label="battery price" />
        </p>
        <table className="tst-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>
                <Term term="vehicles.chemistry">Chemistry</Term>
              </th>
              <th>
                <Term term="vehicles.wh_per_kg">Wh/kg</Term>
              </th>
              <th>
                <Term term="vehicles.cost_mult">Cost</Term>
              </th>
              <th>
                <Term term="vehicles.range_mult">Range</Term>
              </th>
            </tr>
          </thead>
          <tbody>
            {v.battery.chemistries.map((c) => (
              <tr key={c.key}>
                <td>
                  <Term term={`vehicles.${c.key}`}>{c.label}</Term>
                </td>
                <td className="tst-num">{c.wh_per_kg.toFixed(0)}</td>
                <td className="tst-num">×{c.cost_mult.toFixed(2)}</td>
                <td className="tst-num">×{c.range_mult.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Cell makers:{' '}
          {v.battery.cell_makers
            .map((m) => `${m.name} (${m.country}, ${pct(m.share, 0)} of cells)`)
            .join(', ')}
          .
        </p>
      </Panel>
      <Panel title="Rivals" testId="vehicles-rivals">
        <RivalTable v={v} />
      </Panel>
      <Panel title="Your cars" testId="vehicles-cars">
        <CarTable saveId={saveId} v={v} />
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Make a car line from Products (category Electric vehicles), assemble it in a vehicle plant
          or under a contract from Hardware, and set its design on its page here.
        </p>
      </Panel>
      <Panel title="Vehicle plants" testId="vehicles-plants">
        {v.vehicle_plants.length === 0 ? (
          <p className="tst-muted">You own no vehicle plants.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {v.vehicle_plants.map((p) => (
              <li key={p.facility_id}>
                {p.name}: {p.cars_month.toLocaleString()} cars a month, {p.status}, ran{' '}
                {p.run_units.toFixed(0)} last month (yield {pct(p.yield_rate, 0)})
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Cell plants" testId="vehicles-cell-plants">
        <CellTable v={v} />
        <BuildCell saveId={saveId} v={v} />
      </Panel>
      <Panel title="Charging networks" testId="vehicles-charging">
        <ChargingTable saveId={saveId} v={v} />
        <BuildCharging saveId={saveId} v={v} />
      </Panel>
      {v.incidents.length > 0 && (
        <Panel title="Incidents and recalls" testId="vehicles-incidents">
          <ul style={{ margin: 0 }}>
            {v.incidents.map((i) => (
              <li key={`${i.turn}-${i.product}-${i.region}`}>
                {i.when}: {i.product} in {i.region} ({level(i.level)}), {i.cars_recalled.toFixed(0)}{' '}
                cars recalled, {formatMoneyShort(i.cost_cents)}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

function RegionTable({ v }: { v: Vehicles }) {
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region' }),
        regionHelper.accessor('ev_share', {
          header: 'EV share',
          meta: { term: 'vehicles.ev_share' },
          cell: (c) => pct(c.getValue()),
        }),
        regionHelper.accessor('ev_sales_year', {
          header: 'EVs a year',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        regionHelper.accessor('coverage', {
          header: 'Charging',
          meta: { term: 'vehicles.coverage' },
          cell: (c) => pct(c.getValue(), 0),
        }),
        regionHelper.accessor((r) => r.subsidies.map((s) => s.title).join('; ') || '—', {
          id: 'subsidies',
          header: 'Subsidies',
          meta: { term: 'vehicles.subsidy' },
        }),
        regionHelper.accessor(
          (r) => r.tariffs.map((t) => `${pct(t.rate, 0)} on ${t.origin}`).join('; ') || '—',
          { id: 'tariffs', header: 'Tariffs' },
        ),
        regionHelper.accessor((r) => r.approved_levels.map(level).join(', ') || '—', {
          id: 'approved',
          header: 'Approved',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: v.regions,
    getRowId: (r) => r.region,
  });
  return <DataTable table={table} label="EV markets" rowTestId="vehicle-region-row" />;
}

function RivalTable({ v }: { v: Vehicles }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('company', { header: 'Maker' }),
        rivalHelper.accessor('product', { header: 'Line' }),
        rivalHelper.accessor('price_cents', {
          header: 'Price',
          cell: (c) => {
            const p = c.getValue();
            return p == null ? 'not launched' : formatMoneyShort(p);
          },
        }),
        rivalHelper.accessor(
          (r) =>
            r.shares
              .filter((s) => s.share >= 0.005)
              .map((s) => `${s.region.replaceAll('_', ' ')} ${pct(s.share, 0)}`)
              .join(', ') || '—',
          { id: 'shares', header: 'Shares of EV buyers' },
        ),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: v.rivals,
    getRowId: (r) => String(r.company_id),
  });
  return <DataTable table={table} label="Rival car makers" rowTestId="vehicle-rival-row" />;
}

function CarTable({ saveId, v }: { saveId: string; v: Vehicles }) {
  const columns = useMemo(
    () =>
      carHelper.columns([
        carHelper.accessor('name', {
          header: 'Line',
          cell: (c) => (
            <Link to={`/game/${saveId}/products/vehicles/cars/${c.row.original.product_id}`}>
              {c.getValue()}
            </Link>
          ),
        }),
        carHelper.accessor('status', { header: 'Status' }),
        carHelper.accessor('range_km', {
          header: 'Range',
          cell: (c) => `${c.getValue().toFixed(0)} km`,
        }),
        carHelper.accessor('level', { header: 'Autonomy', cell: (c) => level(c.getValue()) }),
        carHelper.accessor('units_last_month', {
          header: 'Sold last month',
          cell: (c) => c.getValue().toFixed(0),
        }),
        carHelper.accessor('unit_cost_cents', {
          header: 'Unit cost',
          cell: (c) => (
            <span data-testid={`car-unit-cost-${c.row.original.product_id}`}>
              {formatMoney(Math.round(c.getValue()))}{' '}
              <Explain
                metric="car_unit_cost"
                entity={c.row.original.product_id}
                label="unit cost"
              />
            </span>
          ),
        }),
        carHelper.accessor('software_share', {
          header: 'Software',
          meta: { term: 'vehicles.attach' },
          cell: (c) => pct(c.getValue()),
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: v.cars,
    getRowId: (r) => String(r.product_id),
  });
  if (v.cars.length === 0) return <p className="tst-muted">You make no cars yet.</p>;
  return <DataTable table={table} label="Your cars" rowTestId="vehicle-car-row" />;
}

function CellTable({ v }: { v: Vehicles }) {
  const columns = useMemo(
    () =>
      cellHelper.columns([
        cellHelper.accessor('name', { header: 'Plant' }),
        cellHelper.accessor('chemistry', { header: 'Chemistry' }),
        cellHelper.accessor('status', { header: 'Status' }),
        cellHelper.accessor('capacity_mwh', {
          header: 'MWh a month',
          cell: (c) => c.getValue().toLocaleString(),
        }),
        cellHelper.accessor('yield_rate', { header: 'Yield', cell: (c) => pct(c.getValue(), 0) }),
        cellHelper.accessor('unit_cents', {
          header: 'Cost a kWh',
          cell: (c) =>
            c.getValue() > 0
              ? `${formatMoney(Math.round(c.getValue()))} (market ${formatMoney(Math.round(c.row.original.market_cents))})`
              : '—',
        }),
        cellHelper.accessor('capex_paid_cents', {
          header: 'Capex',
          cell: (c) =>
            `${formatMoneyShort(c.getValue())} paid of ${formatMoneyShort(c.row.original.estimate_cents)} quoted`,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: v.cell_plants,
    getRowId: (r) => String(r.facility_id),
  });
  if (v.cell_plants.length === 0) return <p className="tst-muted">You own no cell plants.</p>;
  return <DataTable table={table} label="Cell plants" rowTestId="cell-plant-row" />;
}

function ChargingTable({ saveId, v }: { saveId: string; v: Vehicles }) {
  const access = useSetChargingAccess(saveId);
  const columns = useMemo(
    () =>
      chargeHelper.columns([
        chargeHelper.accessor('name', { header: 'Network' }),
        chargeHelper.accessor('chargers', { header: 'Chargers' }),
        chargeHelper.accessor('status', { header: 'Status' }),
        chargeHelper.accessor('kwh_sold', {
          header: 'kWh sold',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        chargeHelper.accessor('revenue_cents', {
          header: 'Revenue',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        chargeHelper.display({
          id: 'access',
          header: 'Access',
          cell: (c) => (
            <Button
              size="compact-xs"
              variant="light"
              disabled={access.isPending}
              onClick={() =>
                access.mutate({
                  facilityId: c.row.original.facility_id,
                  exclusive: !c.row.original.exclusive,
                })
              }
            >
              {c.row.original.exclusive ? 'Exclusive: open it' : 'Open: make exclusive'}
            </Button>
          ),
        }),
      ]),
    [access],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: v.charging,
    getRowId: (r) => String(r.facility_id),
  });
  if (v.charging.length === 0) return <p className="tst-muted">You run no charging networks.</p>;
  return <DataTable table={table} label="Charging networks" rowTestId="charging-row" />;
}

function BuildCell({ saveId, v }: { saveId: string; v: Vehicles }) {
  const build = useBuildCellPlant(saveId);
  const sizes = v.options.cell_plant_sizes;
  const [size, setSize] = useState<number>(sizes[1] ?? sizes[0] ?? 250);
  const [chem, setChem] = useState('lfp');
  const [region, setRegion] = useState('north_america');
  return (
    <div data-testid="build-cell-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Cell plant size"
          data-testid="cell-plant-size"
          size="xs"
          data={sizes.map((s) => ({ value: String(s), label: `${s} MWh a month` }))}
          value={String(size)}
          onChange={(x) => x && setSize(Number(x))}
          allowDeselect={false}
        />
        <Select
          aria-label="Chemistry"
          data-testid="cell-plant-chemistry"
          size="xs"
          data={v.options.chemistries.map((c) => ({ value: c, label: c.toUpperCase() }))}
          value={chem}
          onChange={(x) => x && setChem(x)}
          allowDeselect={false}
        />
        <Select
          aria-label="Region"
          data-testid="cell-plant-region"
          size="xs"
          data={v.regions.map((r) => ({ value: r.region, label: r.label }))}
          value={region}
          onChange={(x) => x && setRegion(x)}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="build-cell-plant"
          disabled={build.isPending}
          onClick={() => build.mutate({ region, mwh_month: size, chemistry: chem })}
        >
          Build cell plant
        </Button>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          Needs stage {v.options.cell_plant_stage}. Your group&apos;s lithium supplies it first.
        </span>
      </div>
      {build.error && <Alert color="red">{String(build.error.message ?? build.error)}</Alert>}
    </div>
  );
}

function BuildCharging({ saveId, v }: { saveId: string; v: Vehicles }) {
  const build = useBuildCharging(saveId);
  const sizes = v.options.charging_sizes;
  const [size, setSize] = useState<number>(sizes[1] ?? sizes[0] ?? 50);
  const [region, setRegion] = useState('north_america');
  const [exclusive, setExclusive] = useState('open');
  return (
    <div data-testid="build-charging-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Chargers"
          data-testid="charging-size"
          size="xs"
          data={sizes.map((s) => ({ value: String(s), label: `${s} chargers` }))}
          value={String(size)}
          onChange={(x) => x && setSize(Number(x))}
          allowDeselect={false}
        />
        <Select
          aria-label="Region"
          data-testid="charging-region"
          size="xs"
          data={v.regions.map((r) => ({ value: r.region, label: r.label }))}
          value={region}
          onChange={(x) => x && setRegion(x)}
          allowDeselect={false}
        />
        <Select
          aria-label="Access"
          data-testid="charging-access"
          size="xs"
          data={[
            { value: 'open', label: 'Open to every EV' },
            { value: 'exclusive', label: 'Exclusive to your cars' },
          ]}
          value={exclusive}
          onChange={(x) => x && setExclusive(x)}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="build-charging"
          disabled={build.isPending}
          onClick={() =>
            build.mutate({ region, chargers: size, exclusive: exclusive === 'exclusive' })
          }
        >
          Build network
        </Button>
      </div>
      {build.error && <Alert color="red">{String(build.error.message ?? build.error)}</Alert>}
    </div>
  );
}

// --- A car line's page ---------------------------------------------------------------------------

export function VehicleCarScreen() {
  const { saveId = '', productId = '0' } = useParams();
  const vq = useVehicles(saveId);
  const q = useVehicleCar(saveId, Number(productId));
  if (q.isPending || vq.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load the car line" error={q.error} />;
  if (vq.error) return <LoadError title="Could not load vehicles" error={vq.error} />;
  return <CarBody saveId={saveId} car={q.data} v={vq.data} />;
}

function CarBody({ saveId, car, v }: { saveId: string; car: MyCar; v: Vehicles }) {
  return (
    <>
      <ScreenTitle
        aside={
          <Link to={`/game/${saveId}/products/${car.product_id}`} data-testid="car-product-link">
            Product page (price, team, launch)
          </Link>
        }
      >
        {car.name}
      </ScreenTitle>
      <Panel title="Design" testId="car-design">
        <p data-testid="car-summary" style={{ margin: '0 0 8px' }}>
          {car.spec.pack_kwh} kWh {car.spec.chemistry.toUpperCase()}, {car.range_km.toFixed(0)} km,{' '}
          {car.spec.charge_kw} kW charging, autonomy {level(car.level)} (capable{' '}
          {level(car.capable_level)}), {car.spec.platform} platform, cells{' '}
          {car.spec.cells === 'own' ? 'from your own plants' : car.spec.cells}; {car.status}.
        </p>
        <SpecForm saveId={saveId} car={car} v={v} />
      </Panel>
      <Panel title="Cost of a car" testId="car-cost">
        <table className="tst-table" style={{ width: '100%' }}>
          <tbody>
            {car.unit_cost.map((l) => (
              <tr key={l.line} data-testid="car-cost-line">
                <td>{l.line}</td>
                <td className="tst-num">{formatMoney(Math.round(l.cents))}</td>
              </tr>
            ))}
            <tr>
              <td>
                <strong>Total</strong>
              </td>
              <td className="tst-num" data-testid="car-unit-cost">
                <strong>{formatMoney(Math.round(car.unit_cost_cents))}</strong>{' '}
                <Explain metric="car_unit_cost" entity={car.product_id} label="unit cost" />
              </td>
            </tr>
          </tbody>
        </table>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Price {car.price_cents == null ? 'not set' : formatMoney(car.price_cents)}; sold{' '}
          {car.units_last_month.toFixed(0)} last month; {car.customers.toFixed(0)} on the road.
        </p>
      </Panel>
      <Panel title="Subsidies" testId="car-eligibility">
        {car.eligibility.length === 0 ? (
          <p className="tst-muted">No subsidy runs where this line sells.</p>
        ) : (
          <table className="tst-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>
                  <Term term="vehicles.region">Region</Term>
                </th>
                <th>
                  <Term term="vehicles.subsidy">Scheme</Term>
                </th>
                <th>
                  <Term term="vehicles.amount">Amount</Term>
                </th>
                <th>
                  <Term term="vehicles.eligible">Eligible</Term>
                </th>
              </tr>
            </thead>
            <tbody>
              {car.eligibility.map((e) => (
                <tr key={`${e.region}-${e.scheme}`} data-testid="eligibility-row">
                  <td>{e.region.replaceAll('_', ' ')}</td>
                  <td>{e.scheme}</td>
                  <td className="tst-num">{formatMoney(e.amount_cents)}</td>
                  <td>{e.eligible ? 'eligible' : `not eligible: ${e.failed.join('; ')}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Autonomy by region" testId="car-autonomy">
        <ul style={{ margin: 0 }}>
          {car.levels.map((l) => (
            <li key={l.region}>
              {l.region.replaceAll('_', ' ')}: runs {level(l.level)}; approved{' '}
              {l.approved
                .filter((x) => x !== 'none')
                .map(level)
                .join(', ') || 'none'}
            </li>
          ))}
        </ul>
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Your autonomy lead is {v.options.autonomy_lead.toFixed(1)}. Levels:{' '}
          {v.options.levels
            .filter((l) => l.key !== 'none')
            .map((l) => (
              <span key={l.key}>
                <Term term={`vehicles.${l.key}`}>{l.label}</Term> (lead {l.lead}
                {l.ai_quality > 0 ? `, AI model ${l.ai_quality}` : ''}){' '}
              </span>
            ))}
        </p>
      </Panel>
      <Panel title="Software" testId="car-software">
        <p style={{ margin: 0 }}>
          {formatMoney(car.software_cents_last_month)} of subscriptions last month;{' '}
          <span data-testid="car-software-share">{pct(car.software_share)}</span> of the line&apos;s
          revenue to date (<Term term="vehicles.attach">attach rate</Term> by platform).
        </p>
        {car.history.length > 0 && (
          <p className="tst-muted" style={{ fontSize: 13 }}>
            Last months:{' '}
            {car.history
              .slice(-6)
              .map(
                (h) =>
                  `${turnLabel(h.turn)} ${h.units.toFixed(0)} cars, ${formatMoneyShort(h.software_cents)} software`,
              )
              .join('; ')}
          </p>
        )}
      </Panel>
    </>
  );
}

function SpecForm({ saveId, car, v }: { saveId: string; car: MyCar; v: Vehicles }) {
  const set = useSetVehicleSpec(saveId, car.product_id);
  const [pack, setPack] = useState<number>(car.spec.pack_kwh);
  const [chem, setChem] = useState(car.spec.chemistry);
  const [charge, setCharge] = useState<number>(car.spec.charge_kw);
  const [autonomy, setAutonomy] = useState(car.spec.autonomy);
  const [platform, setPlatform] = useState(car.spec.platform);
  const [cells, setCells] = useState(car.spec.cells);
  const makers = new Map(v.battery.cell_makers.map((m) => [m.key, `${m.name} (${m.country})`]));
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'end' }}>
      <NumberInput
        label="Pack kWh"
        data-testid="spec-pack"
        size="xs"
        min={v.options.pack_kwh[0]}
        max={v.options.pack_kwh[1]}
        value={pack}
        onChange={(x) => setPack(Number(x))}
        style={{ width: 100 }}
      />
      <Select
        label="Chemistry"
        data-testid="spec-chemistry"
        size="xs"
        data={v.options.chemistries.map((c) => ({ value: c, label: c.toUpperCase() }))}
        value={chem}
        onChange={(x) => x && setChem(x)}
        allowDeselect={false}
      />
      <NumberInput
        label="Charging kW"
        data-testid="spec-charge"
        size="xs"
        min={v.options.charge_kw[0]}
        max={v.options.charge_kw[1]}
        value={charge}
        onChange={(x) => setCharge(Number(x))}
        style={{ width: 100 }}
      />
      <Select
        label="Autonomy"
        data-testid="spec-autonomy"
        size="xs"
        data={v.options.levels.map((l) => ({ value: l.key, label: l.label }))}
        value={autonomy}
        onChange={(x) => x && setAutonomy(x)}
        allowDeselect={false}
      />
      <Select
        label="Platform"
        data-testid="spec-platform"
        size="xs"
        data={v.options.platforms.map((p) => ({ value: p, label: p }))}
        value={platform}
        onChange={(x) => x && setPlatform(x)}
        allowDeselect={false}
      />
      <Select
        label="Cells"
        data-testid="spec-cells"
        size="xs"
        data={v.options.cell_sources.map((c) => ({
          value: c,
          label: c === 'own' ? 'Your own cell plants' : (makers.get(c) ?? c),
        }))}
        value={cells}
        onChange={(x) => x && setCells(x)}
        allowDeselect={false}
      />
      <Button
        size="xs"
        data-testid="save-spec"
        disabled={set.isPending}
        onClick={() =>
          set.mutate({
            pack_kwh: pack,
            chemistry: chem,
            charge_kw: charge,
            autonomy,
            platform,
            cells,
            os_product_id: car.spec.os_product_id,
          })
        }
      >
        Save design
      </Button>
      {set.error && <Alert color="red">{String(set.error.message ?? set.error)}</Alert>}
    </div>
  );
}
