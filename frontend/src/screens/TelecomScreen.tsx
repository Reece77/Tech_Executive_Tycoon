// Telecom (M53, formulas.md 62): subscribers and coverage by region and generation, capacity and
// quality, spectrum holdings, the auctions (bid, results), the networks (towers, radios, fibre,
// subsea cables) with equipment by vendor and bans (rip-and-replace), each region's network
// payback, the operators and your lines' settings. No game values are computed here: figures
// are formatted.
import { Alert, Button, Checkbox, NumberInput, Select, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useAddRadios,
  useBidSpectrum,
  useBuildCable,
  useBuildFibre,
  useBuildTowers,
  useReplaceRadios,
  useSetTelecomLine,
  useTelecom,
  type Auction,
  type Licence,
  type Operator,
  type Radio,
  type RegionNetwork,
  type Telecom,
  type Vendor,
} from '../hooks/telecom';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const regionHelper = createColumnHelper<GameTableFeatures, RegionNetwork>();
const radioHelper = createColumnHelper<GameTableFeatures, Radio>();
const licenceHelper = createColumnHelper<GameTableFeatures, Licence>();
const vendorHelper = createColumnHelper<GameTableFeatures, Vendor>();
const operatorHelper = createColumnHelper<GameTableFeatures, Operator>();

const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;
const big = (x: number) => Math.round(x).toLocaleString();

export function TelecomScreen() {
  const { saveId = '' } = useParams();
  const q = useTelecom(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load telecom" error={q.error} />;
  return <TelecomBody saveId={saveId} t={q.data} />;
}

function TelecomBody({ saveId, t }: { saveId: string; t: Telecom }) {
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            <Term term="telecom.scale">Markets at the game&apos;s scale</Term> · {t.month}
            {t.history ? ' · rivals follow their history to 2025' : ''}
          </span>
        }
      >
        Telecom
      </ScreenTitle>
      <Panel title="Generations" testId="telecom-generations">
        <p style={{ margin: 0 }}>
          {t.generations.map((g) => (
            <span key={g.key} data-testid={`generation-${g.key}`} style={{ marginRight: 12 }}>
              <Term term="telecom.generation">{g.label}</Term>:{' '}
              {g.open ? `commercial since ${g.first ?? ''}` : 'not yet commercial'}
            </span>
          ))}
        </p>
      </Panel>
      <Panel title="Subscribers and coverage by region" testId="telecom-regions">
        <RegionTable t={t} />
      </Panel>
      <Panel title="Spectrum auctions" testId="telecom-auctions">
        <Auctions saveId={saveId} t={t} />
      </Panel>
      <Panel title="Spectrum you hold" testId="telecom-licences">
        <LicenceTable t={t} />
      </Panel>
      <Panel title="Networks" testId="telecom-networks">
        <RadioTable saveId={saveId} t={t} />
        <BuildNetwork saveId={saveId} t={t} />
      </Panel>
      <Panel title="Fibre and subsea cables" testId="telecom-fixed">
        <Fixed saveId={saveId} t={t} />
      </Panel>
      <Panel title="Network payback" testId="telecom-payback">
        {t.payback.length === 0 ? (
          <p className="tst-muted">No network yet.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {t.payback.map((p) => (
              <li key={p.region} data-testid={`payback-${p.region}`}>
                {p.label}: cumulative cash {formatMoneyShort(p.cash_cents)} on{' '}
                {formatMoneyShort(p.capex_cents)} of capex
                {p.paid_back
                  ? `, paid back in ${p.paid_back}`
                  : p.months_to_payback !== null && p.months_to_payback !== undefined
                    ? `, about ${Math.round(p.months_to_payback)} months to go`
                    : ''}{' '}
                <Explain metric="network_payback" entity={p.region} label="payback" />
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Equipment by vendor" testId="telecom-vendors">
        <VendorTable t={t} />
      </Panel>
      <Panel title="Bans" testId="telecom-bans">
        {t.bans.length === 0 ? (
          <p className="tst-muted">No vendor bans announced yet.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {t.bans.map((b) => (
              <li key={`${b.label}-${b.area}`} data-testid="ban-row">
                {b.label} ({b.vendor}, {b.area}): no new radios from {b.no_new}
                {b.replace_by ? `; replaced by ${b.replace_by}` : '; no removal ordered'}
                {b.scope < 1 ? ` (${pct(b.scope)} of its networks)` : ''}
              </li>
            ))}
          </ul>
        )}
        <p className="tst-muted" style={{ fontSize: 13 }}>
          <Term term="telecom.rip_and_replace">Rip-and-replace</Term>: swap a banned vendor&apos;s
          radios from the Networks table before a ban&apos;s deadline, or its sites go dark.
        </p>
      </Panel>
      <Panel title="Your lines" testId="telecom-lines">
        <Lines saveId={saveId} t={t} />
      </Panel>
      <Panel title="Operators" testId="telecom-operators">
        <OperatorTable t={t} />
      </Panel>
    </>
  );
}

function RegionTable({ t }: { t: Telecom }) {
  const columns = useMemo(
    () =>
      regionHelper.columns([
        regionHelper.accessor('label', { header: 'Region', meta: { term: 'telecom.coverage' } }),
        regionHelper.accessor('mobile_subscribers', {
          header: 'Your mobile',
          meta: { term: 'telecom.arpu' },
          cell: (c) => `${big(c.getValue())} of ${big(c.row.original.mobile_market)}`,
        }),
        regionHelper.accessor('fixed_subscribers', {
          header: 'Your broadband',
          meta: { term: 'telecom.arpu' },
          cell: (c) => `${big(c.getValue())} (${big(c.row.original.homes_passed)} homes passed)`,
        }),
        regionHelper.accessor('coverage', {
          header: 'Coverage',
          meta: { term: 'telecom.coverage' },
          cell: (c) => (
            <span data-testid={`coverage-${c.row.original.region}`}>
              {pct(c.getValue())}
              {Object.entries(c.row.original.coverage_by_generation)
                .map(([g, v]) => ` · ${g.replace('g', '')}G ${pct(v)}`)
                .join('')}
            </span>
          ),
        }),
        regionHelper.accessor('sites', {
          header: 'Sites',
          meta: { term: 'telecom.coverage' },
          cell: (c) => big(c.getValue()),
        }),
        regionHelper.accessor('quality', {
          header: 'Capacity',
          meta: { term: 'telecom.capacity' },
          cell: (c) =>
            c.row.original.capacity_gb > 0 ? `${pct(c.getValue())} of demand met` : '—',
        }),
        regionHelper.accessor((r) => r.licensed.mid ?? 0, {
          id: 'spectrum',
          header: 'Spectrum',
          meta: { term: 'telecom.band' },
          cell: (c) =>
            Object.entries(c.row.original.mhz)
              .filter(([, v]) => v > 0)
              .map(([b, v]) => `${b} ${v.toFixed(0)} MHz`)
              .join(', ') || 'none',
        }),
        regionHelper.accessor((r) => r.rivals[0]?.name ?? '', {
          id: 'leader',
          header: 'Largest rivals',
          meta: { term: 'telecom.arpu' },
          cell: (c) =>
            c.row.original.rivals.map((r) => `${r.name} ${pct(r.share)}`).join(', ') || '—',
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: t.regions });
  return <DataTable table={table} label="Regions" rowTestId="telecom-region-row" />;
}

function Auctions({ saveId, t }: { saveId: string; t: Telecom }) {
  if (t.auctions.length === 0) {
    return <p className="tst-muted">No auction announced or run in the last three years.</p>;
  }
  return (
    <>
      {t.auctions.map((a) => (
        <AuctionCard key={a.id} saveId={saveId} a={a} />
      ))}
      <p className="tst-muted" style={{ fontSize: 13 }}>
        <Term term="telecom.auction">A clock auction</Term>: register blocks and the most you pay a
        block before its month; rivals&apos; limits are never shown.
      </p>
    </>
  );
}

function AuctionCard({ saveId, a }: { saveId: string; a: Auction }) {
  const bid = useBidSpectrum(saveId);
  const [blocks, setBlocks] = useState<number | string>(a.my_blocks || 1);
  const [limit, setLimit] = useState<number | string>(
    a.my_limit_cents ? a.my_limit_cents / 100 : (a.reserve_cents * 2) / 100,
  );
  return (
    <div data-testid={`auction-${a.id}`} style={{ marginBottom: 10 }}>
      <strong>{a.label}</strong> · {a.area_label} · {a.band} band, {a.mhz.toLocaleString()} MHz in{' '}
      {a.blocks} blocks · reserve {formatMoneyShort(a.reserve_cents)} a block · {a.month} ·{' '}
      {a.term_years}-year licences
      {a.obligation > 0 ? (
        <>
          {' '}
          · <Term term="telecom.coverage_obligation">obligation</Term> {pct(a.obligation)} in{' '}
          {a.obligation_years} years
        </>
      ) : null}
      {a.status === 'closed' ? (
        <div data-testid={`auction-result-${a.id}`}>
          Closed after {a.rounds} rounds at {formatMoneyShort(a.price_cents)} a block:{' '}
          {a.awards.map((w) => `${w.yours ? 'you' : w.bidder} ${w.blocks}`).join(', ') || 'unsold'}
        </div>
      ) : a.biddable ? (
        <div style={{ display: 'flex', gap: 6, alignItems: 'end', marginTop: 4 }}>
          <NumberInput
            label="Blocks"
            size="xs"
            min={0}
            max={a.blocks}
            value={blocks}
            onChange={setBlocks}
            data-testid={`bid-blocks-${a.id}`}
          />
          <NumberInput
            label="Limit a block ($)"
            size="xs"
            min={0}
            value={limit}
            onChange={setLimit}
            data-testid={`bid-limit-${a.id}`}
          />
          <Button
            size="compact-sm"
            disabled={bid.isPending}
            data-testid={`bid-submit-${a.id}`}
            onClick={() =>
              bid.mutate({
                auctionId: a.id,
                body: { blocks: Number(blocks), limit_cents: Math.round(Number(limit) * 100) },
              })
            }
          >
            {a.my_blocks ? 'Change bid' : 'Register a bid'}
          </Button>
          {a.my_blocks > 0 && (
            <span data-testid={`bid-registered-${a.id}`}>
              Registered: {a.my_blocks} blocks up to {formatMoneyShort(a.my_limit_cents)}
            </span>
          )}
        </div>
      ) : (
        <div className="tst-muted">Spectrum here is assigned administratively.</div>
      )}
      {bid.error && <Alert color="red">{String(bid.error.message)}</Alert>}
    </div>
  );
}

function LicenceTable({ t }: { t: Telecom }) {
  const columns = useMemo(
    () =>
      licenceHelper.columns([
        licenceHelper.accessor('area_label', {
          header: 'Area',
          meta: { term: 'telecom.spectrum' },
        }),
        licenceHelper.accessor('band', { header: 'Band', meta: { term: 'telecom.band' } }),
        licenceHelper.accessor('mhz', {
          header: 'MHz',
          meta: { term: 'telecom.band' },
          cell: (c) => c.getValue().toFixed(0),
        }),
        licenceHelper.accessor('book_cents', {
          header: 'Book value',
          meta: { term: 'account.6760_spectrum_amortization' },
          cell: (c) =>
            `${formatMoneyShort(c.getValue())} of ${formatMoneyShort(c.row.original.paid_cents)}`,
        }),
        licenceHelper.accessor('expires', {
          header: 'Term',
          meta: { term: 'telecom.spectrum' },
          cell: (c) => `${c.row.original.since} to ${c.getValue()} (${c.row.original.status})`,
        }),
        licenceHelper.accessor('obligation', {
          header: 'Obligation',
          meta: { term: 'telecom.coverage_obligation' },
          cell: (c) =>
            c.getValue() > 0
              ? `${pct(c.getValue())} by ${c.row.original.obligation_due ?? ''}${
                  c.row.original.fines ? `, missed ${c.row.original.fines}x` : ''
                }`
              : '—',
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: t.licences });
  return t.licences.length === 0 ? (
    <p className="tst-muted">No spectrum yet: a mobile network carries nothing without it.</p>
  ) : (
    <DataTable table={table} label="Licences" rowTestId="licence-row" />
  );
}

function RadioTable({ saveId, t }: { saveId: string; t: Telecom }) {
  const replace = useReplaceRadios(saveId);
  const columns = useMemo(
    () =>
      radioHelper.columns([
        radioHelper.accessor('region', { header: 'Region', meta: { term: 'telecom.coverage' } }),
        radioHelper.accessor('generation', {
          header: 'Radios',
          meta: { term: 'telecom.generation' },
          cell: (c) =>
            `${c.getValue().replace('g', '')}G, ${c.row.original.vendor_label}${
              c.row.original.overlay ? ' (on existing sites)' : ''
            }`,
        }),
        radioHelper.accessor('sites', {
          header: 'Sites',
          meta: { term: 'telecom.coverage' },
          cell: (c) =>
            `${big(c.row.original.live_sites)} live of ${big(c.getValue())} (${c.row.original.status}, ready ${c.row.original.ready})`,
        }),
        radioHelper.accessor('owed', {
          header: 'Bans',
          meta: { term: 'telecom.rip_and_replace' },
          cell: (c) => {
            const r = c.row.original;
            if (r.at_risk === 0) return '—';
            return (
              <span data-testid={`radio-ban-${r.facility_id}`}>
                {big(r.at_risk)} to replace, {big(r.replaced)} done
                {r.dark > 0 ? `, ${big(r.dark)} dark` : ''}{' '}
                <Button
                  size="compact-xs"
                  data-testid={`replace-${r.facility_id}`}
                  disabled={replace.isPending}
                  onClick={() => {
                    const vendor = t.vendors.find(
                      (v) => v.key !== r.vendor && !v.refused_in.includes(r.region),
                    );
                    const sizes = t.sizes.radio ?? [];
                    const want = Math.max(0, r.at_risk - r.replaced);
                    const size = sizes.find((s) => s >= want) ?? sizes[sizes.length - 1];
                    if (vendor && size) {
                      replace.mutate({
                        facilityId: r.facility_id,
                        body: { vendor: vendor.key, sites: Math.min(size, r.sites - r.replaced) },
                      });
                    }
                  }}
                >
                  Rip and replace
                </Button>
              </span>
            );
          },
        }),
        radioHelper.accessor('capex_cents', {
          header: 'Capex',
          meta: { term: 'telecom.coverage' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
      ]),
    [replace, t.vendors, t.sizes],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: t.radios });
  return (
    <>
      {t.radios.length === 0 ? (
        <p className="tst-muted">No towers yet.</p>
      ) : (
        <DataTable table={table} label="Networks" rowTestId="radio-row" />
      )}
      {replace.error && <Alert color="red">{String(replace.error.message)}</Alert>}
    </>
  );
}

function BuildNetwork({ saveId, t }: { saveId: string; t: Telecom }) {
  const towers = useBuildTowers(saveId);
  const radios = useAddRadios(saveId);
  const regions = t.regions.map((r) => ({ value: r.region, label: r.label }));
  const gens = t.generations.filter((g) => g.open).map((g) => ({ value: g.key, label: g.label }));
  const vendors = [
    ...t.vendors.map((v) => ({ value: v.key, label: v.label })),
    ...(t.has_own_equipment ? [{ value: 'own', label: 'Your own' }] : []),
  ];
  const sizes = (t.sizes.tower ?? []).map((s) => ({ value: String(s), label: s.toLocaleString() }));
  const [region, setRegion] = useState<string | null>(t.regions[0]?.region ?? null);
  const [gen, setGen] = useState<string | null>(gens[gens.length - 1]?.value ?? null);
  const [vendor, setVendor] = useState<string | null>('ericsson');
  const [size, setSize] = useState<string | null>(sizes[0]?.value ?? null);
  const v = t.vendors.find((x) => x.key === vendor);
  const radio = v && gen ? v.radio_cents[gen] : undefined;
  const ready = Boolean(region && gen && vendor && size);
  const body = {
    region: region ?? '',
    sites: Number(size),
    generation: gen ?? '',
    vendor: vendor ?? '',
  };
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'end', flexWrap: 'wrap', marginTop: 8 }}>
      <Select
        allowDeselect={false}
        label="Region"
        size="xs"
        data={regions}
        value={region}
        onChange={setRegion}
        data-testid="build-region"
      />
      <Select
        allowDeselect={false}
        label="Generation"
        size="xs"
        data={gens}
        value={gen}
        onChange={setGen}
        data-testid="build-generation"
      />
      <Select
        allowDeselect={false}
        label="Vendor"
        size="xs"
        data={vendors}
        value={vendor}
        onChange={setVendor}
        data-testid="build-vendor"
      />
      <Select
        allowDeselect={false}
        label="Sites"
        size="xs"
        data={sizes}
        value={size}
        onChange={setSize}
        data-testid="build-sites"
      />
      <Button
        size="compact-sm"
        disabled={!ready || towers.isPending}
        data-testid="build-towers"
        onClick={() => towers.mutate(body)}
      >
        Build towers
      </Button>
      <Button
        size="compact-sm"
        variant="default"
        disabled={!ready || radios.isPending}
        data-testid="add-radios"
        onClick={() => radios.mutate(body)}
      >
        Add radios to your sites
      </Button>
      <span className="tst-muted" style={{ fontSize: 13 }}>
        A site {formatMoneyShort(t.site_civil_cents)}
        {radio !== undefined ? ` + radios ${formatMoneyShort(radio)}` : ''}
      </span>
      {(towers.error ?? radios.error) && (
        <Alert color="red">{String((towers.error ?? radios.error)?.message)}</Alert>
      )}
    </div>
  );
}

function Fixed({ saveId, t }: { saveId: string; t: Telecom }) {
  const fibre = useBuildFibre(saveId);
  const cable = useBuildCable(saveId);
  const regions = t.regions.map((r) => ({ value: r.region, label: r.label }));
  const [region, setRegion] = useState<string | null>(t.regions[0]?.region ?? null);
  const homes = (t.sizes.fibre ?? []).map((s) => ({
    value: String(s),
    label: `${s.toLocaleString()}k homes`,
  }));
  const [size, setSize] = useState<string | null>(homes[0]?.value ?? null);
  const [name, setName] = useState('Atlantic');
  const [to, setTo] = useState<string | null>(t.regions[1]?.region ?? null);
  const [km, setKm] = useState<number | string>(6600);
  const tbps = (t.sizes.subsea_cable ?? []).map((s) => ({ value: String(s), label: `${s} Tbps` }));
  const [cap, setCap] = useState<string | null>(tbps[0]?.value ?? null);
  return (
    <>
      <ul style={{ margin: '0 0 8px' }}>
        {t.fibres.map((f) => (
          <li key={f.facility_id}>
            Fibre in {f.region}: {f.homes_thousands.toLocaleString()}k homes ({f.status}, ready{' '}
            {f.ready}), {formatMoneyShort(f.capex_cents)}
          </li>
        ))}
        {t.cables.map((c) => (
          <li key={c.facility_id}>
            {c.name}: {c.regions.join(' to ')}, {c.km.toLocaleString()} km, {c.tbps} Tbps (
            {c.status}, ready {c.ready}), {formatMoneyShort(c.capex_cents)}
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: 6, alignItems: 'end', flexWrap: 'wrap' }}>
        <Select
          allowDeselect={false}
          label="Region"
          size="xs"
          data={regions}
          value={region}
          onChange={setRegion}
        />
        <Select
          allowDeselect={false}
          label="Homes passed"
          size="xs"
          data={homes}
          value={size}
          onChange={setSize}
        />
        <Button
          size="compact-sm"
          disabled={!region || !size || fibre.isPending}
          onClick={() => region && size && fibre.mutate({ region, homes: Number(size) })}
        >
          Build fibre ({formatMoney(Math.round(t.fibre_home_cents))} a home)
        </Button>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'end', flexWrap: 'wrap', marginTop: 6 }}>
        <TextInput
          label="Cable"
          size="xs"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
        />
        <Select
          allowDeselect={false}
          label="From"
          size="xs"
          data={regions}
          value={region}
          onChange={setRegion}
        />
        <Select
          allowDeselect={false}
          label="To"
          size="xs"
          data={regions}
          value={to}
          onChange={setTo}
        />
        <NumberInput label="km" size="xs" value={km} onChange={setKm} />
        <Select
          allowDeselect={false}
          label="Capacity"
          size="xs"
          data={tbps}
          value={cap}
          onChange={setCap}
        />
        <Button
          size="compact-sm"
          disabled={!region || !to || !cap || cable.isPending}
          onClick={() =>
            region &&
            to &&
            cap &&
            cable.mutate({ name, regions: [region, to], km: Number(km), tbps: Number(cap) })
          }
        >
          Lay a subsea cable ({formatMoneyShort(t.cable_km_cents)} a km)
        </Button>
      </div>
      {(fibre.error ?? cable.error) && (
        <Alert color="red">{String((fibre.error ?? cable.error)?.message)}</Alert>
      )}
    </>
  );
}

function VendorTable({ t }: { t: Telecom }) {
  const columns = useMemo(
    () =>
      vendorHelper.columns([
        vendorHelper.accessor('label', {
          header: 'Vendor',
          meta: { term: 'telecom.rip_and_replace' },
        }),
        vendorHelper.accessor('world_share', {
          header: 'RAN share',
          meta: { term: 'telecom.generation' },
          cell: (c) => pct(c.getValue()),
        }),
        vendorHelper.accessor('price_mult', {
          header: 'Price',
          meta: { term: 'telecom.generation' },
          cell: (c) =>
            Object.entries(c.row.original.radio_cents)
              .map(([g, v]) => `${g.replace('g', '')}G ${formatMoneyShort(v)}`)
              .join(', '),
        }),
        vendorHelper.accessor((v) => v.refused_in.join(', '), {
          id: 'refused',
          header: 'Refused in',
          meta: { term: 'telecom.rip_and_replace' },
          cell: (c) => c.getValue() || '—',
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: t.vendors });
  return <DataTable table={table} label="Vendors" rowTestId="vendor-row" />;
}

function Lines({ saveId, t }: { saveId: string; t: Telecom }) {
  const set = useSetTelecomLine(saveId);
  if (t.lines.length === 0) {
    return (
      <p className="tst-muted">
        Make a Mobile, Fixed broadband or Wholesale line from Products: it sells where your networks
        and spectrum reach.
      </p>
    );
  }
  return (
    <>
      <ul style={{ margin: 0 }}>
        {t.lines.map((l) => (
          <li key={l.product_id}>
            {l.name} ({l.category.replace('_', ' ')})
            {l.category === 'mobile' && (
              <>
                {' '}
                <Checkbox
                  label={<Term term="telecom.net_neutrality">Zero-rating</Term>}
                  size="xs"
                  checked={l.zero_rating}
                  onChange={(e) =>
                    set.mutate({
                      productId: l.product_id,
                      body: {
                        zero_rating: e.currentTarget.checked,
                        satellite_partner: l.satellite_partner,
                      },
                    })
                  }
                />
                <Checkbox
                  label="A direct-to-device satellite partner"
                  size="xs"
                  checked={l.satellite_partner}
                  onChange={(e) =>
                    set.mutate({
                      productId: l.product_id,
                      body: {
                        zero_rating: l.zero_rating,
                        satellite_partner: e.currentTarget.checked,
                      },
                    })
                  }
                />
              </>
            )}
          </li>
        ))}
      </ul>
      {set.error && <Alert color="red">{String(set.error.message)}</Alert>}
    </>
  );
}

function OperatorTable({ t }: { t: Telecom }) {
  const columns = useMemo(
    () =>
      operatorHelper.columns([
        operatorHelper.accessor('name', { header: 'Operator', meta: { term: 'telecom.arpu' } }),
        operatorHelper.accessor('region', { header: 'Region', meta: { term: 'telecom.coverage' } }),
        operatorHelper.accessor('mobile', {
          header: 'Mobile (real, millions)',
          meta: { term: 'telecom.scale' },
          cell: (c) => c.getValue().toFixed(1),
        }),
        operatorHelper.accessor('fixed', {
          header: 'Broadband (real, millions)',
          meta: { term: 'telecom.scale' },
          cell: (c) => c.getValue().toFixed(1),
        }),
        operatorHelper.accessor((o) => o.supplier ?? '', {
          id: 'supplier',
          header: 'Main vendor',
          meta: { term: 'telecom.rip_and_replace' },
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: t.operators });
  return <DataTable table={table} label="Operators" rowTestId="operator-row" />;
}
