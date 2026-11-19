// Space (M40, formulas.md 56): the reusability programme, the player's launch vehicles (cost a
// kg, cadence, record), launches flown, cost a kg by vehicle, the world's launches and providers,
// constellations (shells, coverage, capacity, payback), broadband subscribers and licences by
// region, rivals' public constellations and the milestones so far. No game values are computed
// here: figures are formatted.
import { Alert, Button, Checkbox, NumberInput, Select, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useApplyLicence,
  usePlanConstellation,
  useSetD2dPartner,
  useSetLaunchSpec,
  useSetTerminalPrice,
  useSpace,
  type BroadbandLine,
  type ConstellationRow,
  type CostPerKg,
  type LaunchRow,
  type RegionService,
  type RivalConstellation,
  type Space,
  type Vehicle,
} from '../hooks/space';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const vehicleHelper = createColumnHelper<GameTableFeatures, Vehicle>();
const launchHelper = createColumnHelper<GameTableFeatures, LaunchRow>();
const kgHelper = createColumnHelper<GameTableFeatures, CostPerKg>();
const regionHelper = createColumnHelper<GameTableFeatures, RegionService>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalConstellation>();

const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;
const LEVEL: Record<string, string> = {
  expendable: 'Expendable',
  recovery: 'First-stage recovery',
  full: 'Full reuse',
};

export function SpaceScreen() {
  const { saveId = '' } = useParams();
  const q = useSpace(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load space" error={q.error} />;
  return <SpaceBody saveId={saveId} s={q.data} />;
}

function SpaceBody({ saveId, s }: { saveId: string; s: Space }) {
  if (!s.open) {
    return (
      <>
        <ScreenTitle>Space</ScreenTitle>
        <p className="tst-muted">This game has no space markets (a save from before M40).</p>
      </>
    );
  }
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="space.scale">Markets at the game&apos;s scale</Term> · {s.month}
          </span>
        }
      >
        Space
      </ScreenTitle>
      <Panel title="Reusability" testId="space-reuse">
        <p style={{ margin: '0 0 8px' }}>
          Your <Term term="space.reusability">reusability</Term> lead{' '}
          {s.reusability_lead.toFixed(1)}
          {s.programme_started
            ? `, programme since ${s.programme_started}.`
            : ': no programme yet (start a Reusability research project).'}
        </p>
        <ul style={{ margin: 0 }}>
          {s.reuse_levels.map((l) => (
            <li key={l.key} data-testid={`reuse-level-${l.key}`}>
              {l.label}: {l.lead} lead points and {l.min_months} months of programme{' '}
              {l.reached ? '(reached)' : ''}
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Your launch vehicles" testId="space-vehicles">
        <VehicleTable saveId={saveId} s={s} />
        {s.undesigned.length > 0 && <NewDesign saveId={saveId} s={s} />}
        <p className="tst-muted" style={{ fontSize: 13 }}>
          Make a vehicle line from Products (Launch services), set its design here, and build a
          launch site (Facilities) in a region with a range: {s.site_regions.join(', ')}. A bought
          launch costs {formatMoneyShort(s.bought_launch_cents)} for{' '}
          {Math.round(s.bought_payload_kg).toLocaleString()} kg.
        </p>
      </Panel>
      <Panel title="Launches" testId="space-launches">
        <LaunchTable s={s} />
      </Panel>
      <Panel title="Constellations" testId="space-constellations">
        {s.constellations.map((c) => (
          <ConstellationCard key={c.id} c={c} />
        ))}
        <PlanConstellation saveId={saveId} s={s} />
      </Panel>
      <Panel title="Subscribers by region" testId="space-regions">
        {s.broadband.length === 0 ? (
          <p className="tst-muted">You sell no satellite broadband yet.</p>
        ) : (
          s.broadband.map((b) => <BroadbandCard key={b.product_id} saveId={saveId} b={b} />)
        )}
      </Panel>
      <Panel title="Licences" testId="space-licences">
        <Licences saveId={saveId} s={s} />
      </Panel>
      <Panel title="Cost a kg to low Earth orbit" testId="space-cost-per-kg">
        <CostTable s={s} />
      </Panel>
      <Panel title="The world's launches" testId="space-world">
        <p style={{ margin: '0 0 8px' }}>
          {s.world_launches
            .slice(-6)
            .map((w) => `${w.year}: ${Math.round(w.launches)}`)
            .join(' · ')}
        </p>
        <ul style={{ margin: 0 }}>
          {s.providers.map((p) => (
            <li key={p.company}>
              {p.company}: {Math.round(p.launches_year)} launches a year
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Rival constellations" testId="space-rivals">
        <RivalTable s={s} />
        <p className="tst-muted" style={{ fontSize: 13 }}>
          <Term term="space.direct_to_device">Direct to device</Term>:{' '}
          {s.d2d_open ? `open since ${s.d2d_open}` : 'not open yet'}.
          {s.debris_rule ? ` Tighter debris rules since ${s.debris_rule}.` : ''}
        </p>
      </Panel>
      {s.milestones.length > 0 && (
        <Panel title="Milestones" testId="space-milestones">
          <ul style={{ margin: 0 }}>
            {s.milestones.map((m) => (
              <li key={`${m.month}-${m.label}`}>
                {m.month}: {m.label}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

function VehicleTable({ saveId, s }: { saveId: string; s: Space }) {
  const columns = useMemo(
    () =>
      vehicleHelper.columns([
        vehicleHelper.accessor('name', { header: 'Vehicle' }),
        vehicleHelper.accessor('payload_kg', {
          header: 'Payload',
          meta: { term: 'space.leo' },
          cell: (c) => `${Math.round(c.getValue()).toLocaleString()} kg`,
        }),
        vehicleHelper.accessor('level', {
          header: 'Reuse',
          meta: { term: 'space.reusability' },
          cell: (c) => `${LEVEL[c.getValue()] ?? c.getValue()} (aims ${c.row.original.aim})`,
        }),
        vehicleHelper.accessor((v) => v.cost.cost_per_kg_cents, {
          id: 'per_kg',
          header: 'Cost a kg',
          meta: { term: 'space.cost_per_kg' },
          cell: (c) => (
            <span>
              {formatMoney(Math.round(c.getValue()))}{' '}
              <span className="tst-muted">
                (expendable {formatMoney(Math.round(c.row.original.cost.expendable_per_kg_cents))})
              </span>
            </span>
          ),
        }),
        vehicleHelper.accessor((v) => v.cost.flight_cents, {
          id: 'flight',
          header: 'A launch',
          cell: (c) => (
            <span>
              {formatMoneyShort(c.getValue())}{' '}
              <Explain
                metric="launch_price"
                entity={c.row.original.product_id}
                label="launch cost"
              />
            </span>
          ),
        }),
        vehicleHelper.accessor('flights', {
          header: 'Record',
          meta: { term: 'space.failure' },
          cell: (c) =>
            `${c.getValue()} flights, ${c.row.original.failures} failed; next ${pct(
              c.row.original.failure_rate_lo,
            )}-${pct(c.row.original.failure_rate_hi)}`,
        }),
        vehicleHelper.accessor('cadence', {
          header: 'Launches a month',
          cell: (c) =>
            c.row.original.grounded_until
              ? `Grounded until ${c.row.original.grounded_until}`
              : c.getValue().toFixed(1),
        }),
        vehicleHelper.display({
          id: 'design',
          header: 'Design',
          cell: (c) => <Design saveId={saveId} v={c.row.original} />,
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: s.vehicles,
    getRowId: (v) => String(v.product_id),
  });
  if (s.vehicles.length === 0)
    return <p className="tst-muted">You have no launch vehicle with a design yet.</p>;
  return <DataTable table={table} label="Your launch vehicles" rowTestId="vehicle-row" />;
}

function Design({ saveId, v }: { saveId: string; v: Vehicle }) {
  const set = useSetLaunchSpec(saveId);
  const [payload, setPayload] = useState<number>(v.payload_kg);
  const [reuse, setReuse] = useState(v.aim);
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <NumberInput
        aria-label="Payload kg"
        size="xs"
        w={100}
        value={payload}
        onChange={(x) => setPayload(Number(x) || 0)}
      />
      <Select
        aria-label="Reuse"
        size="xs"
        w={140}
        data={Object.entries(LEVEL).map(([value, label]) => ({ value, label }))}
        value={reuse}
        onChange={(x) => setReuse(x ?? 'expendable')}
      />
      <Button
        size="compact-xs"
        variant="light"
        disabled={set.isPending}
        onClick={() =>
          set.mutate({ productId: v.product_id, body: { payload_kg: payload, reuse } })
        }
      >
        Set
      </Button>
    </span>
  );
}

function NewDesign({ saveId, s }: { saveId: string; s: Space }) {
  const set = useSetLaunchSpec(saveId);
  const [line, setLine] = useState<string | null>(String(s.undesigned[0]?.product_id ?? ''));
  const [payload, setPayload] = useState<number>(20000);
  const [reuse, setReuse] = useState('recovery');
  return (
    <div data-testid="new-design" style={{ display: 'flex', gap: 6, margin: '8px 0' }}>
      <Select
        aria-label="Launch line"
        size="xs"
        data={s.undesigned.map((l) => ({ value: String(l.product_id), label: l.name }))}
        value={line}
        onChange={setLine}
      />
      <NumberInput
        aria-label="New payload kg"
        size="xs"
        w={110}
        value={payload}
        onChange={(x) => setPayload(Number(x) || 0)}
      />
      <Select
        aria-label="New reuse"
        size="xs"
        w={160}
        data={Object.entries(LEVEL).map(([value, label]) => ({ value, label }))}
        value={reuse}
        onChange={(x) => setReuse(x ?? 'expendable')}
      />
      <Button
        size="compact-sm"
        data-testid="design-vehicle"
        disabled={set.isPending || !line}
        onClick={() =>
          set.mutate({ productId: Number(line), body: { payload_kg: payload, reuse } })
        }
      >
        Design vehicle
      </Button>
      {set.error && <Alert color="red">{String(set.error.message)}</Alert>}
    </div>
  );
}

function LaunchTable({ s }: { s: Space }) {
  const columns = useMemo(
    () =>
      launchHelper.columns([
        launchHelper.accessor('month', { header: 'Month' }),
        launchHelper.accessor('vehicle', { header: 'Vehicle' }),
        launchHelper.accessor('purpose', {
          header: 'For',
          cell: (c) =>
            c.getValue() === 'own' ? (c.row.original.constellation ?? 'Own') : 'A customer',
        }),
        launchHelper.accessor('satellites', { header: 'Satellites' }),
        launchHelper.accessor('ok', {
          header: 'Outcome',
          cell: (c) =>
            c.getValue()
              ? 'Success'
              : `Failure${
                  c.row.original.insured_cents
                    ? ` (insurer paid ${formatMoneyShort(c.row.original.insured_cents)})`
                    : ''
                }`,
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: s.launches });
  if (s.launches.length === 0) return <p className="tst-muted">No launches flown yet.</p>;
  return <DataTable table={table} label="Launches" rowTestId="launch-row" />;
}

function ConstellationCard({ c }: { c: ConstellationRow }) {
  return (
    <div data-testid="constellation" style={{ marginBottom: 12 }}>
      <strong>{c.name}</strong> ({c.kind === 'eo' ? 'Earth observation' : 'broadband'}
      {c.product ? `, serving ${c.product}` : ''}): {c.in_orbit.toLocaleString()} of{' '}
      {c.planned.toLocaleString()} satellites in orbit, {c.ground} waiting, {c.lost} lost;{' '}
      {Math.round(c.capacity_gbps).toLocaleString()} Gbps. A satellite{' '}
      {formatMoneyShort(c.satellite_cents)}.
      <ul style={{ margin: '4px 0' }}>
        {c.shells.map((sh) => (
          <li key={sh.index} data-testid={`shell-${sh.index}`}>
            <Term term="space.shell">{sh.label}</Term>: {sh.satellites} of {sh.size}{' '}
            {sh.complete ? '(complete)' : ''}
            {sh.regions.length > 0 ? ` · opens ${sh.regions.join(', ')}` : ''}
          </li>
        ))}
      </ul>
      <span data-testid="coverage">
        Covers:{' '}
        {c.covered.length > 0
          ? c.covered.map((r) => r.replaceAll('_', ' ')).join(', ')
          : 'nothing yet'}
        .
      </span>{' '}
      Cash flow so far {formatMoneyShort(c.payback.cash_cents)}
      {c.payback.paid_back
        ? `, paid back ${c.payback.paid_back}`
        : c.payback.months_to_payback != null
          ? `, about ${Math.round(c.payback.months_to_payback)} months to payback`
          : ''}{' '}
      <Explain metric="constellation_payback" entity={c.id} label="payback" />
    </div>
  );
}

function PlanConstellation({ saveId, s }: { saveId: string; s: Space }) {
  const plan = usePlanConstellation(saveId);
  const [kind, setKind] = useState('broadband');
  const lines = kind === 'eo' ? s.eo_lines : s.broadband;
  const [name, setName] = useState('');
  const [product, setProduct] = useState<string | null>(null);
  const [shells, setShells] = useState(4);
  const [mass, setMass] = useState(300);
  const [life, setLife] = useState(60);
  const [build, setBuild] = useState(20);
  const [launches, setLaunches] = useState(1);
  const [vehicle, setVehicle] = useState<string | null>(null);
  const [d2d, setD2d] = useState(false);
  if (s.broadband.length === 0 && s.eo_lines.length === 0)
    return (
      <p className="tst-muted">
        Make a Satellite broadband or Earth observation line from Products to plan a constellation.
      </p>
    );
  return (
    <div data-testid="plan-constellation" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      <TextInput
        aria-label="Constellation name"
        size="xs"
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
      />
      <Select
        aria-label="Kind"
        size="xs"
        w={160}
        data={[
          { value: 'broadband', label: 'Broadband' },
          { value: 'eo', label: 'Earth observation' },
        ]}
        value={kind}
        onChange={(x) => {
          setKind(x ?? 'broadband');
          setProduct(null);
        }}
      />
      <Select
        aria-label="Broadband line"
        size="xs"
        data={lines.map((l) => ({ value: String(l.product_id), label: l.name }))}
        value={product}
        onChange={setProduct}
      />
      <NumberInput
        aria-label="Shells"
        size="xs"
        w={70}
        value={shells}
        onChange={(x) => setShells(Number(x) || 1)}
      />
      <NumberInput
        aria-label="Satellite kg"
        size="xs"
        w={90}
        value={mass}
        onChange={(x) => setMass(Number(x) || 0)}
      />
      <NumberInput
        aria-label="Life months"
        size="xs"
        w={90}
        value={life}
        onChange={(x) => setLife(Number(x) || 0)}
      />
      <NumberInput
        aria-label="Built a month"
        size="xs"
        w={90}
        value={build}
        onChange={(x) => setBuild(Number(x) || 0)}
      />
      <NumberInput
        aria-label="Launches a month"
        size="xs"
        w={90}
        value={launches}
        onChange={(x) => setLaunches(Number(x) || 0)}
      />
      <Select
        aria-label="Vehicle"
        size="xs"
        data={[
          { value: '', label: 'Bought launches' },
          ...s.vehicles.map((v) => ({ value: String(v.product_id), label: v.name })),
        ]}
        value={vehicle ?? ''}
        onChange={(x) => setVehicle(x || null)}
      />
      <Checkbox label="D2D" checked={d2d} onChange={(e) => setD2d(e.currentTarget.checked)} />
      <Button
        size="compact-sm"
        disabled={plan.isPending || !product || !name}
        onClick={() =>
          plan.mutate({
            name,
            kind,
            product_id: Number(product),
            shells,
            mass_kg: mass,
            life_months: life,
            build_per_month: build,
            launches_per_month: launches,
            vehicle_product_id: vehicle ? Number(vehicle) : null,
            d2d,
            insured: true,
          })
        }
      >
        Plan constellation
      </Button>
      {plan.error && <Alert color="red">{String(plan.error.message)}</Alert>}
    </div>
  );
}

function BroadbandCard({ saveId, b }: { saveId: string; b: BroadbandLine }) {
  const terminal = useSetTerminalPrice(saveId);
  const partner = useSetD2dPartner(saveId);
  const [price, setPrice] = useState(b.terminal_price_cents / 100);
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region' }),
        regionHelper.accessor('covered', {
          header: 'Covered',
          cell: (c) => (c.getValue() ? 'Yes' : 'No'),
        }),
        regionHelper.accessor('licence', {
          header: 'Licence',
          meta: { term: 'space.licence' },
          cell: (c) => c.getValue() ?? '—',
        }),
        regionHelper.accessor('subscribers', {
          header: 'Subscribers',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        regionHelper.accessor('serviceable', {
          header: 'Serviceable',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        regionHelper.accessor('d2d_subscribers', {
          header: 'Phones (D2D)',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: b.regions,
    getRowId: (r) => r.region,
  });
  return (
    <div data-testid="broadband-line" style={{ marginBottom: 12 }}>
      <strong>{b.name}</strong>: a terminal costs {formatMoney(b.terminal_cost_cents)} to make.{' '}
      <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
        <NumberInput
          aria-label="Terminal price $"
          size="xs"
          w={90}
          value={price}
          onChange={(x) => setPrice(Number(x) || 0)}
        />
        <Button
          size="compact-xs"
          variant="light"
          disabled={terminal.isPending}
          onClick={() =>
            terminal.mutate({
              productId: b.product_id,
              body: { price_cents: Math.round(price * 100) },
            })
          }
        >
          Set price
        </Button>
        <Checkbox
          label="Carrier partner (D2D)"
          checked={b.d2d_partner}
          disabled={partner.isPending}
          onChange={(e) =>
            partner.mutate({ productId: b.product_id, body: { partner: e.currentTarget.checked } })
          }
        />
      </span>
      <DataTable table={table} label={`${b.name} by region`} rowTestId="region-service-row" />
    </div>
  );
}

function Licences({ saveId, s }: { saveId: string; s: Space }) {
  const apply = useApplyLicence(saveId);
  const [region, setRegion] = useState<string | null>(null);
  const regions = s.broadband[0]?.regions ?? [];
  return (
    <>
      <ul style={{ margin: '0 0 8px' }}>
        {s.licences.map((l) => (
          <li key={l.region} data-testid={`licence-${l.region}`}>
            {l.label}: {l.status} (applied {l.applied}
            {l.granted ? `, granted ${l.granted}` : ''})
          </li>
        ))}
      </ul>
      {regions.length > 0 && (
        <span style={{ display: 'inline-flex', gap: 4 }}>
          <Select
            aria-label="Region"
            size="xs"
            data={regions.map((r) => ({ value: r.region, label: r.label }))}
            value={region}
            onChange={setRegion}
          />
          <Button
            size="compact-sm"
            disabled={apply.isPending || !region}
            onClick={() => region && apply.mutate({ region })}
          >
            Apply for a licence
          </Button>
        </span>
      )}
      {apply.error && <Alert color="red">{String(apply.error.message)}</Alert>}
    </>
  );
}

function CostTable({ s }: { s: Space }) {
  const columns = useMemo(
    () =>
      kgHelper.columns([
        kgHelper.accessor('vehicle', { header: 'Vehicle' }),
        kgHelper.accessor('company', { header: 'Maker' }),
        kgHelper.accessor('cost_per_kg_cents', {
          header: 'Cost a kg',
          meta: { term: 'space.cost_per_kg' },
          cell: (c) =>
            `${formatMoney(Math.round(c.getValue()))}${c.row.original.target ? ' (target)' : ''}`,
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: s.cost_per_kg });
  return <DataTable table={table} label="Cost a kg" rowTestId="cost-row" />;
}

function RivalTable({ s }: { s: Space }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', { header: 'Constellation' }),
        rivalHelper.accessor('company', { header: 'Operator' }),
        rivalHelper.accessor('satellites', {
          header: 'Satellites',
          meta: { term: 'space.constellation' },
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        rivalHelper.accessor('subscribers', {
          header: 'Subscribers (thousands)',
          cell: (c) =>
            c.getValue() == null ? '—' : Math.round(c.getValue() ?? 0).toLocaleString(),
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: s.rivals });
  return (
    <DataTable table={table} label="Rival constellations" rowTestId="rival-constellation-row" />
  );
}
