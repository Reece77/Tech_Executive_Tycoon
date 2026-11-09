import { Alert, Button, Modal, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { KpiTile } from '../components/KpiTile';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import {
  useBuildPreview,
  useInfraAction,
  useInfrastructure,
  useOrg,
  type Facility,
  type Infrastructure,
  type InfraAction,
} from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole, formatWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, Facility>();

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

/** Infrastructure (M12a, formulas.md 22.6): components, data centres, contracts, Cloud hosting. */
export function InfrastructureScreen() {
  const { saveId = '' } = useParams();
  const infra = useInfrastructure(saveId);
  if (infra.isPending) return <Loading />;
  if (infra.error) return <LoadError title="Could not load infrastructure" error={infra.error} />;
  return <Body saveId={saveId} infra={infra.data} />;
}

function Body({ saveId, infra }: { saveId: string; infra: Infrastructure }) {
  const act = useInfraAction(saveId);
  const [params] = useSearchParams(); // a data-centre pitch's Modify (M15b)
  const [building, setBuilding] = useState(params.get('build') !== null);
  const [contracting, setContracting] = useState(false);
  const [selling, setSelling] = useState<Facility | null>(null);
  const run = (a: InfraAction, done?: () => void) => act.mutate(a, { onSuccess: done });
  const live = infra.facilities.filter((f) => f.status !== 'building').length;
  return (
    <>
      <Link to={`/game/${saveId}/products`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Products
      </Link>
      <ScreenTitle
        aside={
          <>
            <span className="tst-muted" style={{ fontSize: 13 }} data-testid="infra-summary">
              {infra.facilities.length} data centres · {formatWhole(infra.total_live_units)} CU live
              · {formatWhole(infra.total_building_units)} CU building
            </span>
            <Button
              variant="default"
              style={{ marginLeft: 'auto' }}
              onClick={() => setContracting(true)}
              data-testid="contract-open"
            >
              Sign a contract · {infra.contract_energy}
            </Button>
            <Button onClick={() => setBuilding(true)} data-testid="build-open">
              Build a data centre · {infra.build_energy}
            </Button>
          </>
        }
      >
        Infrastructure
      </ScreenTitle>
      {act.error && (
        <Alert color="warn" data-testid="infra-error">
          {act.error.message}
        </Alert>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }} data-testid="component-strip">
        {infra.components.map((c) => (
          <KpiTile
            key={c.good}
            label={c.label}
            term="infra.component_index"
            value={`${c.index.toFixed(2)}×`}
            note={`${c.change_12m >= 0 ? '+' : ''}${pct(c.change_12m)} this year · ${c.note}`}
            warn={c.allocation < 1}
            testId={`component-${c.good}`}
          />
        ))}
        {infra.spot.map((s) => (
          <KpiTile
            key={s.good}
            label={`Spot: ${s.label}`}
            term="infra.spot"
            value={`${formatMoneyWhole(s.cents_per_unit)} / CU`}
            note={s.index === 1 ? 'a month' : `a month (AI index ${s.index.toFixed(2)})`}
          />
        ))}
      </div>
      <Panel title="Data centres" testId="facilities-panel">
        <FacilitiesTable
          facilities={infra.facilities}
          onSell={setSelling}
          saveId={saveId}
          busy={act.isPending}
          onStaff={(facilityId, unitId) => run({ kind: 'staff', facilityId, unitId })}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Your products use your own capacity first, in the data centre&apos;s region or its
          neighbour. Spare capacity is sold on the Cloud hosting market. A general data centre
          breaks even against spot at about {pct(infra.break_even_utilization)} use. Staff it with a
          unit of DevOps or security engineers; short staffing lowers reliability and brings
          outages.
        </p>
      </Panel>
      <CloudPanel
        infra={infra}
        busy={act.isPending}
        onStart={() => run({ kind: 'cloud' })}
        canStart={infra.cloud.can_start && live + infra.facilities.length > 0}
      />
      <Panel title="Component contracts" testId="contracts-panel">
        {infra.contracts.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }}>
            No contracts. A contract locks a component&apos;s index for {infra.contract_months[0]}–
            {infra.contract_months[1]} months and gives its builds full allocation; any volume left
            unused at the end costs {pct(infra.take_or_pay)} of its value.
          </p>
        ) : (
          infra.contracts.map((c) => (
            <div key={c.contract_id} className="tst-row" data-testid="contract-row">
              <span>
                {c.good_label} at {c.index.toFixed(2)}× · {formatWhole(c.used)} of{' '}
                {formatWhole(c.volume)} CU used · until {c.ends}
              </span>
              <span className="tst-num">
                {c.status === 'active'
                  ? `take-or-pay now ${formatMoneyWhole(c.take_or_pay_cents)}`
                  : `settled ${formatMoneyWhole(c.settled_cents)}`}
              </span>
            </div>
          ))
        )}
      </Panel>
      {building && (
        <BuildDialog
          saveId={saveId}
          infra={infra}
          busy={act.isPending}
          onClose={() => setBuilding(false)}
          onBuild={(facilityKind, region, units, contractId) =>
            run({ kind: 'build', facilityKind, region, units, contractId }, () =>
              setBuilding(false),
            )
          }
        />
      )}
      {contracting && (
        <ContractDialog
          infra={infra}
          busy={act.isPending}
          onClose={() => setContracting(false)}
          onSign={(good, months, volume) =>
            run({ kind: 'contract', good, months, volume }, () => setContracting(false))
          }
        />
      )}
      {selling && (
        <Modal opened onClose={() => setSelling(null)} title={`Sell ${selling.name}`}>
          <p style={{ marginTop: 0 }}>
            A buyer pays {pct(infra.sale_share)} of book value:{' '}
            {formatMoneyWhole(selling.sale_value_cents)}. Its staff stay in their unit; your
            products go back to spot hosting.
          </p>
          <p className="tst-muted">Energy {infra.sell_energy}</p>
          <Button
            color="red"
            data-testid="sell-confirm"
            loading={act.isPending}
            onClick={() =>
              run({ kind: 'sell', facilityId: selling.facility_id }, () => setSelling(null))
            }
          >
            Sell
          </Button>
        </Modal>
      )}
    </>
  );
}

function UseBar({ f }: { f: Facility }) {
  if (f.live_units === 0) return <span className="tst-muted">—</span>;
  const own = (f.own_use / f.live_units) * 100;
  const sold = (f.sold_use / f.live_units) * 100;
  return (
    <div style={{ minWidth: 160 }}>
      <div
        style={{ display: 'flex', height: 8, background: 'var(--tst-border)', borderRadius: 2 }}
        aria-hidden
      >
        <div style={{ width: `${own}%`, background: 'var(--tst-accent)' }} />
        <div style={{ width: `${sold}%`, background: 'var(--tst-good, #3fa66b)' }} />
      </div>
      <div className="tst-muted" style={{ fontSize: 12 }} data-testid="use-text">
        your products {formatWhole(f.own_use)} · sold {formatWhole(f.sold_use)} · free{' '}
        {formatWhole(f.free)} ({pct(f.utilization)})
      </div>
    </div>
  );
}

function FacilitiesTable({
  facilities,
  onSell,
  onStaff,
  saveId,
  busy,
}: {
  facilities: Facility[];
  onSell: (f: Facility) => void;
  onStaff: (facilityId: number, unitId: number | null) => void;
  saveId: string;
  busy: boolean;
}) {
  const org = useOrg(saveId);
  const units = (org.data?.units ?? []).filter((u) => u.unit_id !== null);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Site',
          meta: { term: 'infra.site' },
          cell: ({ row }) => (
            <div>
              <div>{row.original.name}</div>
              <div className="tst-muted" style={{ fontSize: 12 }}>
                {row.original.kind_label} ·{' '}
                {row.original.status === 'building' ? 'ordered' : 'since'} {row.original.since}
              </div>
            </div>
          ),
        }),
        helper.accessor('units', {
          header: 'Size',
          meta: { term: 'infra.size' },
          cell: ({ row }) => (
            <span className="tst-num">
              {formatWhole(row.original.units)} {row.original.unit}
            </span>
          ),
        }),
        helper.display({
          id: 'use',
          header: 'Use',
          meta: { term: 'infra.use' },
          cell: ({ row }) =>
            row.original.status === 'building' ? (
              <span data-testid="build-progress">
                {pct(row.original.build_progress ?? 0)} built · ready {row.original.ready}
                {row.original.late_units > 0 &&
                  ` (${formatWhole(row.original.late_units)} CU by ${row.original.late_ready})`}
              </span>
            ) : (
              <UseBar f={row.original} />
            ),
        }),
        helper.accessor('reliability', {
          header: 'Reliability',
          meta: { term: 'infra.reliability' },
          cell: ({ getValue }) => {
            const v = getValue();
            return <span className="tst-num">{v === null ? '—' : Math.round(v)}</span>;
          },
        }),
        helper.display({
          id: 'staff',
          header: 'Staff',
          meta: { term: 'infra.staff' },
          cell: ({ row }) => {
            const f = row.original;
            return (
              <div>
                <span
                  className="tst-num"
                  style={{ color: f.coverage < 1 ? 'var(--tst-warn)' : undefined }}
                  data-testid="staff-text"
                >
                  {f.staff} of {f.staff_needed}
                </span>
                <Select
                  size="xs"
                  placeholder="Assign a unit"
                  aria-label="Staffing unit"
                  data-testid="staff-unit"
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
        helper.accessor('power_cents', {
          header: 'Power per CU',
          meta: { term: 'infra.power' },
          cell: ({ row }) => (
            <span className="tst-num" data-testid="power-per-cu">
              {formatMoneyWhole(row.original.power_cents ?? 0)}{' '}
              <span className="tst-muted">× {(row.original.power_index ?? 1).toFixed(2)}</span>
            </span>
          ),
        }),
        helper.accessor('cost_per_used_cents', {
          header: 'Cost per used CU',
          meta: { term: 'infra.cost_per_used' },
          cell: ({ row }) => {
            const f = row.original;
            if (f.cost_per_used_cents === null) return <span className="tst-muted">—</span>;
            return (
              <span className="tst-num" data-testid="cost-per-used">
                {formatMoneyWhole(f.cost_per_used_cents)}{' '}
                <span className="tst-muted">spot {formatMoneyWhole(f.spot_cents)}</span>
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
            <Button size="xs" variant="subtle" onClick={() => onSell(row.original)}>
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
    data: facilities,
    getRowId: (f) => String(f.facility_id),
  });
  if (facilities.length === 0) {
    return (
      <p className="tst-muted" style={{ margin: 0 }} data-testid="no-facilities">
        No data centres yet: your products buy compute on spot.
      </p>
    );
  }
  return <DataTable table={table} label="Data centres" rowTestId="facility-row" />;
}

function CloudPanel({
  infra,
  busy,
  onStart,
  canStart,
}: {
  infra: Infrastructure;
  busy: boolean;
  onStart: () => void;
  canStart: boolean;
}) {
  const c = infra.cloud;
  return (
    <Panel title="Cloud hosting (selling spare capacity)" testId="cloud-panel">
      {!c.selling ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="tst-muted">
            Sell what your products leave free to SMB, mid-market, enterprise and hyperscale buyers.
            Your reliability is the product&apos;s quality.
          </span>
          <Button disabled={!canStart} loading={busy} onClick={onStart} data-testid="cloud-start">
            Sell spare capacity
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <KpiTile
            label="Customers"
            term="infra.cloud_customers"
            value={formatWhole(c.customers)}
            note={c.segments
              .filter((s) => s.customers >= 0.5)
              .map((s) => `${s.label} ${formatWhole(s.customers)}`)
              .join(' · ')}
            testId="cloud-customers"
          />
          <KpiTile
            label="Revenue"
            term="infra.cloud_revenue"
            value={formatMoneyWhole(c.revenue_cents)}
            note={`a month · ${formatWhole(c.units_sold)} CU sold · ${formatWhole(c.spare_units)} CU spare`}
          />
          <KpiTile
            label="Price per CU"
            term="infra.cloud_price"
            value={c.price_per_unit_cents === null ? '—' : formatMoneyWhole(c.price_per_unit_cents)}
            note={
              c.leader_name && c.leader_price_per_unit_cents !== null
                ? `${c.leader_name} ${formatMoneyWhole(c.leader_price_per_unit_cents)}`
                : undefined
            }
          />
          <KpiTile
            label="Outages in 12 months"
            term="infra.outages"
            value={String(c.outages_12m)}
            warn={c.outages_12m > 0}
            testId="cloud-outages"
          />
        </div>
      )}
    </Panel>
  );
}

function BuildDialog({
  saveId,
  infra,
  busy,
  onClose,
  onBuild,
}: {
  saveId: string;
  infra: Infrastructure;
  busy: boolean;
  onClose: () => void;
  onBuild: (kind: string, region: string, units: number, contractId: number | null) => void;
}) {
  const [params] = useSearchParams();
  const [kind, setKind] = useState(params.get('build') ?? infra.kinds[0]?.key ?? '');
  const [region, setRegion] = useState(
    params.get('region') ??
      infra.regions.find((r) => r.is_home)?.key ??
      infra.regions[0]?.key ??
      '',
  );
  const [units, setUnits] = useState(
    Number(params.get('units')) || (infra.sizes[1] ?? infra.sizes[0] ?? 100),
  );
  const [contract, setContract] = useState<string>('none');
  const good = infra.kinds.find((k) => k.key === kind)?.input_good;
  const contracts = infra.contracts.filter(
    (c) => c.status === 'active' && c.good === good && c.used < c.volume,
  );
  const contractId = contract === 'none' ? null : Number(contract);
  const preview = useBuildPreview(saveId, kind, region, units, contractId);
  const p = preview.data;
  return (
    <Modal opened onClose={onClose} title="Build a data centre">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Select
          label="Kind"
          data-testid="build-kind"
          data={infra.kinds.map((k) => ({ value: k.key, label: k.label }))}
          value={kind}
          onChange={(v) => v && setKind(v)}
          allowDeselect={false}
        />
        <Select
          label="Region"
          data-testid="build-region"
          data={infra.regions.map((r) => ({ value: r.key, label: r.label }))}
          value={region}
          onChange={(v) => v && setRegion(v)}
          allowDeselect={false}
        />
        <Select
          label="Size"
          data-testid="build-units"
          data={infra.sizes.map((s) => ({ value: String(s), label: `${formatWhole(s)} CU` }))}
          value={String(units)}
          onChange={(v) => v && setUnits(Number(v))}
          allowDeselect={false}
        />
        {contracts.length > 0 && (
          <Select
            label="Contract"
            data-testid="build-contract"
            data={[
              { value: 'none', label: 'None' },
              ...contracts.map((c) => ({
                value: String(c.contract_id),
                label: `${c.good_label} at ${c.index.toFixed(2)}× (${formatWhole(c.volume - c.used)} CU left)`,
              })),
            ]}
            value={contract}
            onChange={(v) => v && setContract(v)}
            allowDeselect={false}
          />
        )}
        {p && (
          <div data-testid="build-preview" style={{ fontSize: 14 }}>
            <div className="tst-row">
              <span>Capex (paid over {p.build_months} months)</span>
              <span className="tst-num">{formatMoneyShort(p.capex_cents)}</span>
            </div>
            <div className="tst-row">
              <span>Ready</span>
              <span>{p.ready}</span>
            </div>
            <div className="tst-row">
              <span>Cost per CU at full use</span>
              <span className="tst-num">
                {formatMoneyWhole(p.cost_per_unit_full_cents)} (spot{' '}
                {formatMoneyWhole(p.spot_cents)})
              </span>
            </div>
            <div className="tst-row">
              <span>Power a CU a month</span>
              <span className="tst-num" data-testid="build-power">
                {formatMoneyWhole(p.power_cents ?? 0)} (region × {(p.power_index ?? 1).toFixed(2)})
              </span>
            </div>
            <div className="tst-row">
              <span>Staff needed</span>
              <span>{p.staff_needed} infrastructure people</span>
            </div>
            <div className="tst-row">
              <span>Shortage delay</span>
              <span data-testid="build-delay">
                {p.late > 0
                  ? `${formatWhole(p.late)} CU about ${p.late_months} months late`
                  : 'none: full allocation'}
              </span>
            </div>
            {p.late > 0 && (
              <p className="tst-muted" style={{ margin: 0, fontSize: 12 }}>
                Lock component prices with a contract to get full allocation.
              </p>
            )}
            {!p.can_afford && (
              <Alert color="warn">Not enough cash for the first capex payment.</Alert>
            )}
          </div>
        )}
        <p className="tst-muted" style={{ margin: 0 }}>
          Energy {infra.build_energy}
        </p>
        <Button
          data-testid="build-confirm"
          loading={busy}
          disabled={!p || !p.can_afford}
          onClick={() => onBuild(kind, region, units, contractId)}
        >
          Build
        </Button>
      </div>
    </Modal>
  );
}

function ContractDialog({
  infra,
  busy,
  onClose,
  onSign,
}: {
  infra: Infrastructure;
  busy: boolean;
  onClose: () => void;
  onSign: (good: string, months: number, volume: number) => void;
}) {
  const [good, setGood] = useState(infra.components[0]?.good ?? 'server');
  const [months, setMonths] = useState(infra.contract_months[0] ?? 12);
  const [volume, setVolume] = useState(500);
  const component = infra.components.find((c) => c.good === good);
  const kind = infra.kinds.find((k) => k.input_good === good);
  const value = (kind?.capex_per_unit_cents ?? 0) * volume;
  return (
    <Modal opened onClose={onClose} title="Sign a component contract">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Select
          label="Component"
          data-testid="contract-good"
          data={infra.components.map((c) => ({ value: c.good, label: c.label }))}
          value={good}
          onChange={(v) => v && setGood(v)}
          allowDeselect={false}
        />
        <NumberInput
          label="Months"
          data-testid="contract-months"
          min={infra.contract_months[0]}
          max={infra.contract_months[1]}
          value={months}
          onChange={(v) => setMonths(Number(v) || 0)}
        />
        <NumberInput
          label="Volume (CU of builds)"
          data-testid="contract-volume"
          min={1}
          step={100}
          value={volume}
          onChange={(v) => setVolume(Number(v) || 0)}
        />
        <p style={{ margin: 0, fontSize: 14 }}>
          Locks {component?.label ?? good} at {component?.index.toFixed(2)}× with full allocation
          for builds worth about {formatMoneyShort(value)}. Any volume unused at the end costs{' '}
          {pct(infra.take_or_pay)} of its value (take-or-pay).
        </p>
        <p className="tst-muted" style={{ margin: 0 }}>
          Energy {infra.contract_energy}
        </p>
        <Button
          data-testid="contract-confirm"
          loading={busy}
          disabled={volume <= 0}
          onClick={() => onSign(good, months, volume)}
        >
          Sign
        </Button>
      </div>
    </Modal>
  );
}
