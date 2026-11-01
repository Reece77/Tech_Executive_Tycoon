import { Alert, Button, Modal, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { CitiesTable } from '../components/CitiesTable';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { useGeo, useGeoAction, useLeasePreview, useOrg, type Geo, type Office } from '../hooks/api';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const helper = createColumnHelper<GameTableFeatures, Office>();

/** Offices (M9, formulas.md 19.1-19.2): flexible HQ space, leases and every city. */
export function OfficesScreen() {
  const { saveId = '' } = useParams();
  const geo = useGeo(saveId);
  if (geo.isPending) return <Loading />;
  if (geo.error) return <LoadError title="Could not load the offices" error={geo.error} />;
  return <Body saveId={saveId} g={geo.data} />;
}

function Body({ saveId, g }: { saveId: string; g: Geo }) {
  const act = useGeoAction(saveId);
  const [leasing, setLeasing] = useState(false);
  const [closing, setClosing] = useState<Office | null>(null);
  return (
    <>
      <Link to={`/game/${saveId}/org`} style={{ fontSize: 13, textDecoration: 'none' }}>
        ← Org
      </Link>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Offices</h1>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          HQ {g.hq_label} · home region {g.home_region_label}
        </span>
        <Button
          style={{ marginLeft: 'auto' }}
          onClick={() => setLeasing(true)}
          data-testid="lease-open"
        >
          Lease an office
        </Button>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="geo-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Your offices" testId="offices-panel">
        <OfficesTable offices={g.offices} onClose={setClosing} />
        <MoveUnit
          saveId={saveId}
          g={g}
          busy={act.isPending}
          onMove={(unitId, officeId) => act.mutate({ kind: 'unitOffice', unitId, officeId })}
        />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Move a unit to an office from Org. Everyone in an office with more people than seats loses
          morale. New hires default to their unit&apos;s office city; relocating a hire costs{' '}
          {formatMoneyWhole(g.relocation_cents)}.
        </p>
      </Panel>
      <Panel title="Cities" testId="cities-panel">
        <CitiesTable cities={g.cities} />
      </Panel>
      {leasing && (
        <LeaseDialog
          saveId={saveId}
          g={g}
          onClose={() => setLeasing(false)}
          onLease={(city, seats) =>
            act.mutate({ kind: 'lease', city, seats }, { onSuccess: () => setLeasing(false) })
          }
          busy={act.isPending}
        />
      )}
      {closing && closing.office_id !== null && (
        <Modal opened onClose={() => setClosing(null)} title={`Close ${closing.city_label}`}>
          <p style={{ marginTop: 0 }}>
            Ending the lease early costs {g.close_penalty_months} months&apos; rent (
            {formatMoneyWhole(closing.close_penalty_cents ?? 0)}). Its teams move to flexible space
            if this is the HQ city, otherwise they work remotely from here.
          </p>
          <p className="tst-muted">Energy {g.close_energy}</p>
          <Button
            color="red"
            data-testid="close-confirm"
            loading={act.isPending}
            onClick={() =>
              act.mutate(
                { kind: 'close', officeId: closing.office_id ?? 0 },
                { onSuccess: () => setClosing(null) },
              )
            }
          >
            Close the office
          </Button>
        </Modal>
      )}
    </>
  );
}

function MoveUnit({
  saveId,
  g,
  busy,
  onMove,
}: {
  saveId: string;
  g: Geo;
  busy: boolean;
  onMove: (unitId: number, officeId: number | null) => void;
}) {
  const org = useOrg(saveId);
  const units = (org.data?.units ?? []).filter((u) => u.unit_id !== null);
  const [unit, setUnit] = useState<string | null>(null);
  const [office, setOffice] = useState<string>('flex');
  if (units.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 8 }}>
      <Select
        label="Move a unit"
        placeholder="Unit"
        data-testid="move-unit"
        data={units.map((u) => ({ value: String(u.unit_id), label: u.name }))}
        value={unit}
        onChange={setUnit}
      />
      <Select
        label="To"
        data-testid="move-office"
        data={g.offices.map((o) => ({
          value: o.office_id === null ? 'flex' : String(o.office_id),
          label: o.city_label,
        }))}
        value={office}
        onChange={(v) => v && setOffice(v)}
        allowDeselect={false}
      />
      <Button
        data-testid="move-confirm"
        disabled={unit === null}
        loading={busy}
        onClick={() => unit && onMove(Number(unit), office === 'flex' ? null : Number(office))}
      >
        Move (energy {g.assign_energy})
      </Button>
    </div>
  );
}

function OfficesTable({ offices, onClose }: { offices: Office[]; onClose: (o: Office) => void }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('city_label', { header: 'Office', meta: { term: 'geo.office' } }),
        helper.accessor('people', {
          header: 'People',
          meta: { term: 'geo.office_people' },
          cell: ({ row }) => (
            <span className="tst-num">
              {row.original.people}
              {row.original.seats !== null ? ` / ${row.original.seats} seats` : ''}
            </span>
          ),
        }),
        helper.accessor('monthly_rent_cents', {
          header: 'Rent a month',
          meta: { term: 'geo.rent' },
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        helper.accessor('cost_per_head_cents', {
          header: 'Cost per person',
          meta: { term: 'geo.cost_per_head' },
          cell: ({ getValue }) => {
            const v = getValue();
            return <span className="tst-num">{v === null ? '—' : formatMoneyWhole(v)}</span>;
          },
        }),
        helper.display({
          id: 'units',
          header: 'Units',
          meta: { term: 'geo.units' },
          cell: ({ row }) => row.original.units.map((u) => u.name).join(', ') || '—',
        }),
        helper.display({
          id: 'status',
          header: 'Status',
          meta: { term: 'geo.office_status' },
          cell: ({ row }) =>
            row.original.crowded ? (
              <span style={{ color: 'var(--tst-warn)' }} data-testid="crowded">
                Crowded: {row.original.crowded_morale} morale
              </span>
            ) : row.original.opened ? (
              `Since ${row.original.opened}`
            ) : (
              'Flexible'
            ),
        }),
        helper.display({
          id: 'actions',
          header: '',
          cell: ({ row }) =>
            row.original.office_id === null ? null : (
              <Button size="xs" variant="subtle" onClick={() => onClose(row.original)}>
                Close
              </Button>
            ),
        }),
      ]),
    [onClose],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: offices,
    getRowId: (o) => String(o.office_id ?? 'flex'),
  });
  return <DataTable table={table} label="Your offices" rowTestId="office-row" />;
}

function LeaseDialog({
  saveId,
  g,
  onClose,
  onLease,
  busy,
}: {
  saveId: string;
  g: Geo;
  onClose: () => void;
  onLease: (city: string, seats: number) => void;
  busy: boolean;
}) {
  const [city, setCity] = useState(g.cities.find((c) => !c.is_hq)?.key ?? g.hq_city);
  const [seats, setSeats] = useState(g.seat_sizes[0] ?? 25);
  const preview = useLeasePreview(saveId, city, seats, true);
  return (
    <Modal opened onClose={onClose} title="Lease an office">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Select
          label="City"
          data-testid="lease-city"
          data={g.cities.map((c) => ({ value: c.key, label: `${c.label} (${c.region_label})` }))}
          value={city}
          onChange={(v) => v && setCity(v)}
          allowDeselect={false}
        />
        <Select
          label="Seats"
          data-testid="lease-seats"
          data={g.seat_sizes.map((s) => ({ value: String(s), label: `${s} seats` }))}
          value={String(seats)}
          onChange={(v) => v && setSeats(Number(v))}
          allowDeselect={false}
        />
        {preview.data && (
          <div data-testid="lease-preview" style={{ fontSize: 14 }}>
            <div className="tst-row">
              <span>Rent</span>
              <span className="tst-num">
                {formatMoneyWhole(preview.data.monthly_rent_cents)} a month, full or not
              </span>
            </div>
            <div className="tst-row">
              <span>Fit-out, now</span>
              <span className="tst-num">{formatMoneyWhole(preview.data.fit_out_cents)}</span>
            </div>
            <div className="tst-row">
              <span>A senior engineer&apos;s market rate there</span>
              <span className="tst-num">
                {formatMoneyWhole(preview.data.example_rate_cents)} a year
              </span>
            </div>
          </div>
        )}
        <p className="tst-muted" style={{ margin: 0 }}>
          Energy {g.lease_energy}
        </p>
        <Button data-testid="lease-confirm" loading={busy} onClick={() => onLease(city, seats)}>
          Lease
        </Button>
      </div>
    </Modal>
  );
}
