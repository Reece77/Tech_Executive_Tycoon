// Mobility (M39, formulas.md 53.3): robotaxi cities (their L4 approval, ride-hailing market, fare,
// riders' acceptance and rival fleets), rival operators' services, the player's robotaxi services,
// zones with their permits, fleets, rides, utilisation and contribution, depots, and incidents that
// happened. Opening a zone, adding cars, setting a price, closing a zone and ordering a depot. No
// game values are computed here: figures are formatted.
import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  pct,
  useAddRobotaxis,
  useBuildDepot,
  useCloseZone,
  useMobility,
  useOpenZone,
  useSetRidePrice,
  type City,
  type Mobility,
  type RivalService,
  type Zone,
} from '../hooks/robotics';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const cityHelper = createColumnHelper<GameTableFeatures, City>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalService>();
const zoneHelper = createColumnHelper<GameTableFeatures, Zone>();

export function MobilityScreen() {
  const { saveId = '' } = useParams();
  const q = useMobility(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load mobility" error={q.error} />;
  return <MobilityBody saveId={saveId} m={q.data} />;
}

function MobilityBody({ saveId, m }: { saveId: string; m: Mobility }) {
  const o = m.options;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }} data-testid="l4-status">
            {o.can_drive_l4
              ? 'Your autonomy research and AI model reach L4.'
              : `L4 needs an autonomy lead of ${o.l4_lead} and an AI model of quality ${o.l4_ai_quality}.`}
          </span>
        }
      >
        Mobility
      </ScreenTitle>
      <Panel title="Cities" testId="mobility-cities">
        <CityTable m={m} />
      </Panel>
      <Panel title="Rival services" testId="mobility-rivals">
        <RivalTable m={m} />
        {m.history_incidents.length > 0 && (
          <ul style={{ margin: '8px 0 0' }}>
            {m.history_incidents.map((i) => (
              <li key={`${i.month}-${i.operator}`}>
                {i.month}: {i.label}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Your zones" testId="mobility-zones">
        <ZoneTable saveId={saveId} m={m} />
        <OpenZone saveId={saveId} m={m} />
      </Panel>
      <Panel title="Depots" testId="mobility-depots">
        {m.depots.length === 0 ? (
          <p className="tst-muted">You have no depots.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {m.depots.map((d) => (
              <li key={d.facility_id}>
                {d.name}: {d.cars.toLocaleString()} cars in {d.city.replaceAll('_', ' ')},{' '}
                {d.status} (ready {d.ready})
              </li>
            ))}
          </ul>
        )}
        <BuildDepot saveId={saveId} m={m} />
      </Panel>
      {m.incidents.length > 0 && (
        <Panel title="Incidents" testId="mobility-incidents">
          <ul style={{ margin: 0 }}>
            {m.incidents.map((i) => (
              <li key={`${i.month}-${i.zone_id}-${i.cost_cents}`} data-testid="robotaxi-incident">
                {i.month}: {i.serious ? 'serious' : 'minor'} incident in{' '}
                {i.city.replaceAll('_', ' ')}, {formatMoneyShort(i.cost_cents)}
                {i.suspended_until ? `; permit suspended until ${i.suspended_until}` : ''}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

function CityTable({ m }: { m: Mobility }) {
  const columns = useMemo(
    () =>
      cityHelper.columns([
        cityHelper.accessor('label', { header: 'City' }),
        cityHelper.accessor('l4_approved', {
          header: 'Driverless',
          cell: (c) => (c.getValue() ? 'approved' : 'not approved'),
        }),
        cityHelper.accessor('trips_month', {
          header: 'Trips a month',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        cityHelper.accessor('fare_cents', {
          header: 'Human fare',
          cell: (c) => formatMoney(Math.round(c.getValue())),
        }),
        cityHelper.accessor('acceptance', {
          header: 'Acceptance',
          meta: { term: 'mobility.acceptance' },
          cell: (c) => pct(c.getValue(), 0),
        }),
        cityHelper.accessor('rival_fleet', {
          header: 'Rival cars',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.cities,
    getRowId: (c) => c.key,
  });
  return <DataTable table={table} label="Robotaxi cities" rowTestId="mobility-city-row" />;
}

function RivalTable({ m }: { m: Mobility }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('operator', { header: 'Operator' }),
        rivalHelper.accessor('city', {
          header: 'City',
          cell: (c) => c.getValue().replaceAll('_', ' '),
        }),
        rivalHelper.accessor('since', { header: 'Since' }),
        rivalHelper.accessor('running', {
          header: 'Status',
          cell: (c) => (c.getValue() ? 'running' : 'stopped'),
        }),
        rivalHelper.accessor('fleet', {
          header: 'Cars',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        rivalHelper.accessor('rides_week', {
          header: 'Rides a week',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.rivals,
    getRowId: (r) => `${r.operator}-${r.city}`,
  });
  if (m.rivals.length === 0) return <p className="tst-muted">No driverless service runs yet.</p>;
  return <DataTable table={table} label="Rival robotaxi services" rowTestId="mobility-rival-row" />;
}

function ZoneTable({ saveId, m }: { saveId: string; m: Mobility }) {
  const close = useCloseZone(saveId);
  const columns = useMemo(
    () =>
      zoneHelper.columns([
        zoneHelper.accessor('city_label', { header: 'City' }),
        zoneHelper.accessor('size', { header: 'Zone', meta: { term: 'mobility.zone' } }),
        zoneHelper.accessor('status', {
          header: 'Permit',
          cell: (c) => {
            const z = c.row.original;
            if (z.status === 'applied') return `under review since ${z.applied}`;
            if (z.status === 'suspended') return `suspended until ${z.suspended_until ?? '—'}`;
            return z.status;
          },
        }),
        zoneHelper.accessor('cars', { header: 'Cars', cell: (c) => c.getValue().toLocaleString() }),
        zoneHelper.accessor((z) => z.month?.rides ?? 0, {
          id: 'rides',
          header: 'Rides',
          cell: (c) => Math.round(c.getValue()).toLocaleString(),
        }),
        zoneHelper.accessor((z) => z.month?.utilisation ?? 0, {
          id: 'utilisation',
          header: 'Utilisation',
          meta: { term: 'mobility.utilisation' },
          cell: (c) => pct(c.getValue(), 0),
        }),
        zoneHelper.accessor((z) => z.month?.contribution_per_ride_cents ?? null, {
          id: 'per_ride',
          header: 'Contribution a ride',
          cell: (c) => (
            <span data-testid={`zone-contribution-${c.row.original.zone_id}`}>
              {c.getValue() == null ? '—' : formatMoney(Math.round(c.getValue() ?? 0))}{' '}
              <Explain
                metric="ride_contribution"
                entity={c.row.original.zone_id}
                label="contribution a ride"
              />
            </span>
          ),
        }),
        zoneHelper.accessor((z) => z.month?.revenue_cents ?? 0, {
          id: 'revenue',
          header: 'Revenue',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        zoneHelper.accessor('breakeven_rides', {
          header: 'Break-even',
          meta: { term: 'mobility.breakeven' },
          cell: (c) => `${c.getValue().toFixed(1)} rides a car a day`,
        }),
        zoneHelper.display({
          id: 'act',
          header: 'Fleet',
          cell: (c) => (
            <span style={{ display: 'inline-flex', gap: 4 }}>
              <AddCars saveId={saveId} m={m} zone={c.row.original} />
              <Price saveId={saveId} zone={c.row.original} />
              {c.row.original.status !== 'closed' && (
                <Button
                  size="compact-xs"
                  variant="subtle"
                  color="red"
                  disabled={close.isPending}
                  onClick={() => close.mutate(c.row.original.zone_id)}
                >
                  Close
                </Button>
              )}
            </span>
          ),
        }),
      ]),
    [saveId, m, close],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: m.zones,
    getRowId: (z) => String(z.zone_id),
  });
  if (m.zones.length === 0) return <p className="tst-muted">You run no robotaxi zones.</p>;
  return <DataTable table={table} label="Your zones" rowTestId="mobility-zone-row" />;
}

function AddCars({ saveId, m, zone }: { saveId: string; m: Mobility; zone: Zone }) {
  const add = useAddRobotaxis(saveId);
  const [n, setN] = useState(50);
  const [source, setSource] = useState('');
  if (zone.status === 'closed' || zone.status === 'refused') return null;
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <NumberInput
        aria-label="Cars"
        data-testid={`zone-cars-${zone.zone_id}`}
        size="xs"
        min={1}
        max={m.options.max_cars}
        value={n}
        onChange={(x) => setN(Number(x) || 1)}
        style={{ width: 80 }}
      />
      <Select
        aria-label="Car source"
        size="xs"
        data={[
          { value: '', label: 'Bought' },
          ...m.options.own_car_lines.map((p) => ({ value: String(p.product_id), label: p.name })),
        ]}
        value={source}
        onChange={(x) => setSource(x ?? '')}
      />
      <Button
        size="compact-xs"
        data-testid={`add-cars-${zone.zone_id}`}
        disabled={add.isPending}
        onClick={() =>
          add.mutate({
            zoneId: zone.zone_id,
            body: { cars: n, car_product_id: source ? Number(source) : null },
          })
        }
      >
        Add cars
      </Button>
      {add.error && <Alert color="red">{String(add.error.message ?? add.error)}</Alert>}
    </span>
  );
}

function Price({ saveId, zone }: { saveId: string; zone: Zone }) {
  const set = useSetRidePrice(saveId);
  const [dollars, setDollars] = useState(Math.round(zone.price_cents) / 100);
  if (zone.status === 'closed' || zone.status === 'refused') return null;
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <NumberInput
        aria-label="Fare"
        size="xs"
        min={0}
        decimalScale={2}
        value={dollars}
        onChange={(x) => setDollars(Number(x) || 0)}
        style={{ width: 80 }}
      />
      <Button
        size="compact-xs"
        variant="light"
        disabled={set.isPending}
        onClick={() => set.mutate({ zoneId: zone.zone_id, priceCents: Math.round(dollars * 100) })}
      >
        Set fare
      </Button>
    </span>
  );
}

function OpenZone({ saveId, m }: { saveId: string; m: Mobility }) {
  const open = useOpenZone(saveId);
  const approved = m.cities.filter((c) => c.l4_approved);
  const [city, setCity] = useState(approved[0]?.key ?? m.cities[0]?.key ?? '');
  const [size, setSize] = useState('small');
  const [service, setService] = useState(
    String(m.services.find((s) => s.status === 'live')?.product_id ?? ''),
  );
  return (
    <div data-testid="open-zone-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Service"
          data-testid="zone-service"
          size="xs"
          data={m.services.map((s) => ({ value: String(s.product_id), label: s.name }))}
          value={service}
          onChange={(x) => setService(x ?? '')}
        />
        <Select
          aria-label="City"
          data-testid="zone-city"
          size="xs"
          data={m.cities.map((c) => ({ value: c.key, label: c.label }))}
          value={city}
          onChange={(x) => x && setCity(x)}
          allowDeselect={false}
        />
        <Select
          aria-label="Zone size"
          data-testid="zone-size"
          size="xs"
          data={m.options.zone_sizes.map((z) => ({
            value: z.key,
            label: `${z.key} (${pct(z.share, 0)} of trips, review ${z.review_months}+ months)`,
          }))}
          value={size}
          onChange={(x) => x && setSize(x)}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="open-zone"
          disabled={open.isPending || service === ''}
          onClick={() => open.mutate({ product_id: Number(service), city, size, price_cents: 0 })}
        >
          Apply for a permit
        </Button>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          A robotaxi service is a product (Robotaxi services); launch it first. A bought robotaxi
          costs {formatMoneyShort(Math.round(m.options.robotaxi_cents))}.
        </span>
      </div>
      {open.error && <Alert color="red">{String(open.error.message ?? open.error)}</Alert>}
    </div>
  );
}

function BuildDepot({ saveId, m }: { saveId: string; m: Mobility }) {
  const build = useBuildDepot(saveId);
  const sizes = m.options.depot_sizes;
  const [size, setSize] = useState<number>(sizes[1] ?? sizes[0] ?? 100);
  const [city, setCity] = useState(m.cities[0]?.key ?? '');
  return (
    <div data-testid="build-depot-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Depot size"
          data-testid="depot-size"
          size="xs"
          data={sizes.map((s) => ({ value: String(s), label: `${s} cars` }))}
          value={String(size)}
          onChange={(x) => x && setSize(Number(x))}
          allowDeselect={false}
        />
        <Select
          aria-label="Depot city"
          data-testid="depot-city"
          size="xs"
          data={m.cities.map((c) => ({ value: c.key, label: c.label }))}
          value={city}
          onChange={(x) => x && setCity(x)}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="build-depot"
          disabled={build.isPending}
          onClick={() => build.mutate({ city, capacity: size })}
        >
          Order <Term term="mobility.depot">depot</Term>
        </Button>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          {formatMoneyShort(Math.round(m.options.depot_capex_cents))} a car served;{' '}
          <Term term="mobility.remote_assistance">remote assistance</Term> is a car&apos;s monthly
          cost.
        </span>
      </div>
      {build.error && <Alert color="red">{String(build.error.message ?? build.error)}</Alert>}
    </div>
  );
}
