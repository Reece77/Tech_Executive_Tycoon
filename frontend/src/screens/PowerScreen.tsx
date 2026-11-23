// Power (M32, formulas.md 46): energy by region (demand, supply mix, cost, emissions), plants,
// contracts, the grid queue, outages that happened and plant types' published costs; ordering a
// plant and signing a PPA. A plant's page shows its quote, payments and last month. No game
// values are computed here: figures are formatted only.
import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { OpenNegotiation } from '../components/NegotiationPanel';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  formatMwh,
  turnLabel,
  useBuildPowerPlant,
  usePlantQuote,
  usePower,
  usePowerPlant,
  usePpaQuote,
  useSignPpa,
  useTerminatePpa,
  type Power,
  type PowerPlant,
  type PowerRegion,
  type Ppa,
} from '../hooks/power';
import { formatMoneyShort, formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const regionHelper = createColumnHelper<GameTableFeatures, PowerRegion>();
const plantHelper = createColumnHelper<GameTableFeatures, PowerPlant>();
const ppaHelper = createColumnHelper<GameTableFeatures, Ppa>();
const PERCENT = 100;

function pct(part: number, whole: number): string {
  return whole > 0 ? `${Math.round((part / whole) * PERCENT)}%` : '—';
}

export function PowerScreen() {
  const { saveId = '' } = useParams();
  const q = usePower(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load power" error={q.error} />;
  return <PowerBody saveId={saveId} p={q.data} />;
}

export function PowerBody({ saveId, p }: { saveId: string; p: Power }) {
  const waiting = p.queue.filter((q) => q.connected_turn === null);
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Emissions this year: scope 1 {p.scope1_year.toFixed(0)} t,{' '}
            <Term term="power.scope2">scope 2</Term> {p.scope2_year.toFixed(0)} t.{' '}
            {p.unlocked ? 'You can own plants.' : `Owned plants unlock at stage ${p.min_stage}.`}
          </span>
        }
      >
        Power
      </ScreenTitle>
      <Panel title="Energy by region" testId="power-regions">
        <RegionTable p={p} />
      </Panel>
      <Panel title="Plants" testId="power-plants">
        <PlantTable saveId={saveId} p={p} />
        {p.unlocked && <BuildPlant saveId={saveId} p={p} />}
      </Panel>
      <Panel title="Power contracts" testId="power-ppas">
        <PpaTable saveId={saveId} p={p} />
        <SignPpa saveId={saveId} p={p} />
      </Panel>
      <Panel title="Grid queue" testId="power-queue">
        {waiting.length === 0 ? (
          <p className="tst-muted">Nothing is waiting for a grid connection.</p>
        ) : (
          <table className="tst-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>
                  <Term term="power.project">Project</Term>
                </th>
                <th>
                  <Term term="power.mw">MW</Term>
                </th>
                <th>
                  <Term term="power.since">Since</Term>
                </th>
                <th>
                  <Term term="power.queue">Typical wait</Term>
                </th>
              </tr>
            </thead>
            <tbody>
              {waiting.map((q) => (
                <tr key={q.id} data-testid={`queue-${q.facility_id}`}>
                  <td>{q.name}</td>
                  <td className="tst-num">{q.mw.toFixed(0)}</td>
                  <td>{turnLabel(q.joined_turn)}</td>
                  <td>
                    {q.lo_months.toFixed(0)}–{q.hi_months.toFixed(0)} months
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Outages" testId="power-outages">
        {p.outages.length === 0 ? (
          <p className="tst-muted">No grid outages in the last two years.</p>
        ) : (
          <ul data-testid="power-outage-list" style={{ margin: 0 }}>
            {p.outages.map((o) => (
              <li key={`${o.turn}-${o.region}`}>
                {turnLabel(o.turn)}: the {o.region_label} grid went down
              </li>
            ))}
          </ul>
        )}
        <WafersLost p={p} />
      </Panel>
      <Panel title="Plant types" testId="power-types">
        <table className="tst-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>
                <Term term="power.type">Type</Term>
              </th>
              <th>$/kW</th>
              <th>
                <Term term="power.build">Build</Term>
              </th>
              <th>
                <Term term="power.intensity">tCO2/MWh</Term>
              </th>
              <th>
                <Term term="power.levelised">$/MWh</Term> (North America, Europe)
              </th>
            </tr>
          </thead>
          <tbody>
            {p.plant_types.map((t) => (
              <tr key={t.key}>
                <td>
                  {t.label}
                  {!t.available && ' (not yet)'}
                </td>
                <td className="tst-num">{t.capex_kw_usd.toFixed(0)}</td>
                <td>{t.build_months} months</td>
                <td className="tst-num">{t.intensity.toFixed(2)}</td>
                <td className="tst-num">
                  {(t.levelised['north_america'] ?? 0).toFixed(0)},{' '}
                  {(t.levelised['europe'] ?? 0).toFixed(0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function WafersLost({ p }: { p: Power }) {
  const lost = p.history.filter((h) => h.wafers_lost > 0);
  if (lost.length === 0) return null;
  return (
    <ul data-testid="power-wafers-lost" style={{ margin: '8px 0 0' }}>
      {lost.map((h) => (
        <li key={`${h.turn}-${h.region}`}>
          {turnLabel(h.turn)}: {h.wafers_lost.toFixed(0)} wafer starts lost to the outage
        </li>
      ))}
    </ul>
  );
}

function RegionTable({ p }: { p: Power }) {
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region' }),
        regionHelper.accessor('grid_usd_mwh', {
          header: 'Grid $/MWh',
          meta: { term: 'power.grid_price' },
          cell: (c) => c.getValue().toFixed(1),
        }),
        regionHelper.accessor('carbon_usd_t', {
          header: 'Carbon $/t',
          meta: { term: 'power.carbon_price' },
          cell: (c) => c.getValue().toFixed(0),
        }),
        regionHelper.accessor(
          (r) => `${r.queue_lo_months.toFixed(0)}–${r.queue_hi_months.toFixed(0)} mo`,
          {
            id: 'queue',
            header: 'Queue',
            meta: { term: 'power.queue' },
          },
        ),
        regionHelper.accessor('outages_a_year', {
          header: 'Outages',
          meta: { term: 'power.outages' },
          cell: (c) => `${c.getValue().toFixed(1)} a year`,
        }),
        regionHelper.accessor('demand_mwh', {
          header: 'Energy',
          cell: (c) => (c.getValue() > 0 ? formatMwh(c.getValue()) : '—'),
        }),
        regionHelper.accessor(
          (r) =>
            r.demand_mwh > 0
              ? `own ${pct(r.plant_mwh, r.demand_mwh)}, PPA ${pct(r.ppa_mwh, r.demand_mwh)}, grid ${pct(r.grid_mwh, r.demand_mwh)}`
              : '—',
          { id: 'mix', header: 'Supply' },
        ),
        regionHelper.accessor('net_cents', {
          header: 'Cost',
          cell: (c) => {
            const r = c.row.original;
            if (r.demand_mwh <= 0) return '—';
            return (
              <span data-testid={`power-cost-${r.region}`}>
                {formatMoneyShort(r.net_cents)} (grid {formatMoneyShort(r.grid_cents)}){' '}
                <Explain metric="energy_cost" entity={r.region} label="energy cost" />
              </span>
            );
          },
        }),
        regionHelper.accessor((r) => r.scope1_tonnes + r.scope2_tonnes, {
          id: 'emissions',
          header: 'tCO2',
          meta: { term: 'power.scope2' },
          cell: (c) => (c.getValue() > 0 ? c.getValue().toFixed(0) : '—'),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: p.regions,
    getRowId: (r) => r.region,
  });
  return <DataTable table={table} label="Energy by region" rowTestId="power-region-row" />;
}

function PlantTable({ saveId, p }: { saveId: string; p: Power }) {
  const columns = useMemo(
    () =>
      plantHelper.columns([
        plantHelper.accessor('name', {
          header: 'Plant',
          cell: (c) => (
            <Link to={`/game/${saveId}/products/power/plants/${c.row.original.facility_id}`}>
              {c.getValue()}
            </Link>
          ),
        }),
        plantHelper.accessor((x) => x.site_name ?? 'grid', {
          id: 'site',
          header: 'Supplies',
          meta: { term: 'power.behind_the_meter' },
        }),
        plantHelper.accessor('status', { header: 'Status' }),
        plantHelper.accessor((x) => x.expected_turn, {
          id: 'expected',
          header: 'Generating',
          cell: (c) => turnLabel(c.getValue()),
        }),
        plantHelper.accessor('paid_cents', {
          header: 'Capex',
          cell: (c) =>
            `${formatMoneyShort(c.getValue())} paid of ${formatMoneyShort(c.row.original.estimate_cents)} quoted`,
        }),
        plantHelper.accessor('levelised_usd_mwh', {
          header: '$/MWh',
          meta: { term: 'power.levelised' },
          cell: (c) => (
            <span>
              {c.getValue().toFixed(1)}{' '}
              <Explain
                metric="plant_levelised"
                entity={c.row.original.facility_id}
                label="levelised cost"
              />
            </span>
          ),
        }),
      ]),
    [saveId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: p.plants,
    getRowId: (x) => String(x.facility_id),
  });
  if (p.plants.length === 0) return <p className="tst-muted">You own no plants.</p>;
  return <DataTable table={table} label="Plants" rowTestId="power-plant-row" />;
}

function BuildPlant({ saveId, p }: { saveId: string; p: Power }) {
  const build = useBuildPowerPlant(saveId);
  const types = p.plant_types.filter((t) => t.available);
  const [kind, setKind] = useState(types[0]?.key ?? 'gas');
  const [mw, setMw] = useState<number>(p.sizes_mw[1] ?? p.sizes_mw[0] ?? 100);
  const [region, setRegion] = useState('north_america');
  const [site, setSite] = useState<string>('grid');
  const sites = p.sites.filter((s) => s.region === region);
  const siteId = site === 'grid' ? null : Number(site);
  const quote = usePlantQuote(saveId, kind, mw, region, siteId);
  const q = quote.data;
  return (
    <div data-testid="build-plant-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Plant type"
          data-testid="plant-type"
          size="xs"
          data={types.map((t) => ({ value: t.key, label: t.label }))}
          value={kind}
          onChange={(v) => v && setKind(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Size"
          data-testid="plant-size"
          size="xs"
          data={p.sizes_mw.map((s) => ({ value: String(s), label: `${s} MW` }))}
          value={String(mw)}
          onChange={(v) => v && setMw(Number(v))}
          allowDeselect={false}
        />
        <Select
          aria-label="Region"
          data-testid="plant-region"
          size="xs"
          data={p.regions.map((r) => ({ value: r.region, label: r.label }))}
          value={region}
          onChange={(v) => {
            if (v) {
              setRegion(v);
              setSite('grid');
            }
          }}
          allowDeselect={false}
        />
        <Select
          aria-label="Site"
          data-testid="plant-site"
          size="xs"
          data={[
            { value: 'grid', label: 'On the grid' },
            ...sites.map((s) => ({
              value: String(s.facility_id),
              label: `Behind the meter: ${s.name} (${s.mw.toFixed(0)} MW)`,
            })),
          ]}
          value={site}
          onChange={(v) => v && setSite(v)}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="build-plant"
          disabled={build.isPending || !q?.allowed}
          title={q && !q.allowed ? (q.reason ?? undefined) : undefined}
          onClick={() => build.mutate({ plant_type: kind, mw, region, site_id: siteId })}
        >
          Build
        </Button>
      </div>
      {q && (
        <div data-testid="plant-quote" style={{ fontSize: 13, marginTop: 6 }}>
          {formatMoneyShort(q.capex_cents)} over {q.build_months} months; about{' '}
          {formatMwh(q.mwh_year)} a year (<Term term="power.capacity_factor">capacity factor</Term>{' '}
          {Math.round(q.capacity_factor * PERCENT)}%);{' '}
          <Term term="power.levelised">${q.levelised_usd_mwh.toFixed(1)} a MWh</Term>;{' '}
          {q.behind_meter
            ? 'behind the meter: no queue'
            : `grid queue ${(q.queue_lo_months ?? 0).toFixed(0)}–${(q.queue_hi_months ?? 0).toFixed(0)} months`}
          {!q.allowed && q.reason && <Alert color="warn">{q.reason}</Alert>}
        </div>
      )}
      {build.error && <Alert color="red">{String(build.error.message ?? build.error)}</Alert>}
    </div>
  );
}

function PpaTable({ saveId, p }: { saveId: string; p: Power }) {
  const terminate = useTerminatePpa(saveId);
  const columns = useMemo(
    () =>
      ppaHelper.columns([
        ppaHelper.accessor('producer_name', { header: 'Generator' }),
        ppaHelper.accessor('region_label', { header: 'Region' }),
        ppaHelper.accessor('mwh_month', {
          header: 'MWh a month',
          cell: (c) => c.getValue().toFixed(0),
        }),
        ppaHelper.accessor('price_usd_mwh', {
          header: '$/MWh',
          meta: { term: 'power.ppa' },
          cell: (c) => c.getValue().toFixed(1),
        }),
        ppaHelper.accessor((x) => `${turnLabel(x.start_turn)}–${turnLabel(x.end_turn)}`, {
          id: 'term',
          header: 'Term',
        }),
        ppaHelper.accessor('status', { header: 'Status' }),
        ppaHelper.accessor('paid_cents', {
          header: 'Last month',
          cell: (c) => formatMoneyWhole(c.getValue()),
        }),
        ppaHelper.display({
          id: 'act',
          header: '',
          cell: (c) =>
            c.row.original.status === 'active' ? (
              <Button
                size="xs"
                variant="subtle"
                data-testid={`terminate-ppa-${c.row.original.id}`}
                onClick={() => terminate.mutate(c.row.original.id)}
              >
                Terminate
              </Button>
            ) : null,
        }),
      ]),
    [terminate],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: p.ppas,
    getRowId: (x) => String(x.id),
  });
  if (p.ppas.length === 0) return <p className="tst-muted">No power contracts.</p>;
  return <DataTable table={table} label="Power contracts" rowTestId="power-ppa-row" />;
}

function SignPpa({ saveId, p }: { saveId: string; p: Power }) {
  const sign = useSignPpa(saveId);
  const [region, setRegion] = useState('north_america');
  const sellers = p.sellers.filter((s) => s.region === region);
  const [producer, setProducer] = useState(sellers[0]?.key ?? '');
  const [mwh, setMwh] = useState<number>(1000);
  const [years, setYears] = useState<number>(10);
  const chosen = sellers.some((s) => s.key === producer) ? producer : (sellers[0]?.key ?? '');
  const quote = usePpaQuote(saveId, region, chosen, mwh, years);
  const q = quote.data;
  return (
    <div data-testid="sign-ppa-panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Select
          aria-label="Region"
          data-testid="ppa-region"
          size="xs"
          data={p.regions.map((r) => ({ value: r.region, label: r.label }))}
          value={region}
          onChange={(v) => v && setRegion(v)}
          allowDeselect={false}
        />
        <Select
          aria-label="Generator"
          data-testid="ppa-producer"
          size="xs"
          data={sellers.map((s) => ({ value: s.key, label: s.name }))}
          value={chosen}
          onChange={(v) => v && setProducer(v)}
          allowDeselect={false}
        />
        <NumberInput
          aria-label="MWh a month"
          data-testid="ppa-mwh"
          size="xs"
          min={1}
          step={1000}
          value={mwh}
          onChange={(v) => setMwh(Number(v) || 0)}
          w={130}
        />
        <Select
          aria-label="Years"
          data-testid="ppa-years"
          size="xs"
          data={p.ppa_years.map((y) => ({ value: String(y), label: `${y} years` }))}
          value={String(years)}
          onChange={(v) => v && setYears(Number(v))}
          allowDeselect={false}
        />
        <Button
          size="xs"
          data-testid="sign-ppa"
          disabled={sign.isPending || !chosen || mwh <= 0}
          onClick={() => sign.mutate({ region, producer: chosen, mwh_month: mwh, years })}
        >
          Sign
        </Button>
        {chosen && mwh > 0 && (
          <OpenNegotiation
            saveId={saveId}
            kind="ppa"
            params={{ region, producer: chosen, mwh_month: mwh, years }}
          />
        )}
      </div>
      {q && (
        <div data-testid="ppa-quote" style={{ fontSize: 13, marginTop: 6 }}>
          <Term term="power.ppa">${q.price_usd_mwh.toFixed(1)} a MWh</Term> against a forward of $
          {q.forward_usd_mwh.toFixed(1)}: {formatMoneyShort(q.monthly_cents)} a month,{' '}
          {turnLabel(q.start_turn)} to {turnLabel(q.end_turn)}; at least{' '}
          {formatMoneyShort(q.minimum_cents)} a month ({Math.round(p.take_or_pay * PERCENT)}%
          take-or-pay).
        </div>
      )}
      {sign.error && <Alert color="red">{String(sign.error.message ?? sign.error)}</Alert>}
    </div>
  );
}

export function PowerPlantScreen() {
  const { saveId = '', facilityId = '0' } = useParams();
  const q = usePowerPlant(saveId, Number(facilityId));
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load the plant" error={q.error} />;
  const x = q.data;
  const m = x.month;
  return (
    <>
      <ScreenTitle
        aside={
          <Link to={`/game/${saveId}/products/power`} className="tst-muted">
            Power
          </Link>
        }
      >
        {x.name}
      </ScreenTitle>
      <Panel title="Plant" testId="plant-page">
        <div className="tst-row">
          <span>Status</span>
          <span data-testid="plant-status">{x.status}</span>
        </div>
        <div className="tst-row">
          <span>Supplies</span>
          <span>{x.site_name ? `behind the meter of ${x.site_name}` : 'the grid'}</span>
        </div>
        <div className="tst-row">
          <span>Capex</span>
          <span>
            {formatMoneyShort(x.paid_cents)} paid of {formatMoneyShort(x.estimate_cents)} quoted
          </span>
        </div>
        <div className="tst-row">
          <span>Generating</span>
          <span>{turnLabel(x.expected_turn)}</span>
        </div>
        {x.queue_lo_months !== null && x.queue_hi_months !== null && (
          <div className="tst-row">
            <span>
              <Term term="power.queue">Grid queue</Term>
            </span>
            <span>
              {x.queued_months ?? 0} months so far; typically {x.queue_lo_months.toFixed(0)}–
              {x.queue_hi_months.toFixed(0)}
            </span>
          </div>
        )}
        <div className="tst-row">
          <span>
            <Term term="power.capacity_factor">Capacity factor</Term>
          </span>
          <span>
            {Math.round(x.capacity_factor * PERCENT)}% ({formatMwh(x.mwh_year)} a year)
          </span>
        </div>
        <div className="tst-row">
          <span>
            <Term term="power.levelised">Levelised cost</Term>
          </span>
          <span>
            ${x.levelised_usd_mwh.toFixed(1)} a MWh{' '}
            <Explain metric="plant_levelised" entity={x.facility_id} label="levelised cost" />
          </span>
        </div>
        {x.outage_until !== null && (
          <Alert color="warn">In a forced outage until {turnLabel(x.outage_until)}.</Alert>
        )}
      </Panel>
      {m && (
        <Panel title={`Last month (${turnLabel(m.turn)})`} testId="plant-month">
          <div className="tst-row">
            <span>Generated</span>
            <span>
              {formatMwh(m.output_mwh)}: used {formatMwh(m.used_mwh)}, sold{' '}
              {formatMwh(m.exported_mwh)}, curtailed {formatMwh(m.curtailed_mwh)}
            </span>
          </div>
          <div className="tst-row">
            <span>Costs</span>
            <span>
              fuel {formatMoneyShort(m.fuel_cents)}, operations {formatMoneyShort(m.om_cents)},
              carbon {formatMoneyShort(m.carbon_cents)}, grid charges{' '}
              {formatMoneyShort(m.grid_charge_cents)}
            </span>
          </div>
          <div className="tst-row">
            <span>Grid energy it replaced</span>
            <span>{formatMoneyShort(m.displaced_cents)}</span>
          </div>
          <div className="tst-row">
            <span>Emissions</span>
            <span>{m.tonnes.toFixed(0)} t CO2</span>
          </div>
        </Panel>
      )}
    </>
  );
}
