import { Alert, Button, NumberInput, Select, TextInput } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { LoadError, Loading, Panel } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useMines,
  useMiningAction,
  type Mine,
  type MineMonth,
  type MineQuote,
  type Mines,
  type MiningAction,
  type MiningCompany,
  type RegionEvent,
  type RivalMiner,
} from '../hooks/mining';
import { formatGrade } from '../lib/exploration';
import { formatMoneyWhole, humanize } from '../lib/format';
import {
  formatPerPound,
  formatPerTonne,
  formatShare,
  formatTonneAsPound,
  formatTonnes,
} from '../lib/mining';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const companyHelper = createColumnHelper<GameTableFeatures, MiningCompany>();
const quoteHelper = createColumnHelper<GameTableFeatures, MineQuote>();
const mineHelper = createColumnHelper<GameTableFeatures, Mine>();
const monthHelper = createColumnHelper<GameTableFeatures, MineMonth>();
const eventHelper = createColumnHelper<GameTableFeatures, RegionEvent>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalMiner>();

const CENTS = 100;
const MILLION = 1_000_000;

/** Mines (M19, formulas.md 35): found a mining subsidiary and move projects into it, build mines
 * on permitted projects, and run them: construction, output, grade, cost against price,
 * reserves as ranges, staff, sales, events and closure. Only revealed values. */
export function MinesScreen() {
  const { saveId = '' } = useParams();
  const mines = useMines(saveId);
  if (mines.isPending) return <Loading />;
  if (mines.error) return <LoadError title="Could not load mines" error={mines.error} />;
  return <Body saveId={saveId} x={mines.data} />;
}

function Body({ saveId, x }: { saveId: string; x: Mines }) {
  const act = useMiningAction(saveId);
  const run = (a: MiningAction) => act.mutate(a);
  // An event's link opens its mine (M23c): ?mine=<id>
  const [params] = useSearchParams();
  const linked = Number(params.get('mine'));
  const [selected, setSelected] = useState<number | null>(
    x.mines.some((m) => m.id === linked) ? linked : (x.mines[0]?.id ?? null),
  );
  const mine = x.mines.find((m) => m.id === selected) ?? x.mines[0] ?? null;
  return (
    <>
      <div style={{ display: 'flex', gap: 12, fontSize: 13 }}>
        <Link to={`/game/${saveId}/products`} style={{ textDecoration: 'none' }}>
          ← Products
        </Link>
        <Link to={`/game/${saveId}/products/exploration`} style={{ textDecoration: 'none' }}>
          Exploration
        </Link>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Mines</h1>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          {x.turn_label}. A mine is a long, risky bet on a price you don&apos;t control. Reserves
          are the resource estimate&apos;s range; the deposit&apos;s truth and a build&apos;s{' '}
          <Term term="mining.overrun">overrun</Term> are never shown until revealed.
        </span>
      </div>
      {act.error && (
        <Alert color="warn" data-testid="mines-error">
          {act.error.message}
        </Alert>
      )}
      <Panel title="Group companies" testId="companies-panel">
        <CompaniesTable companies={x.companies} />
        <FoundForm x={x} busy={act.isPending} onAct={run} />
        <TransferForm x={x} busy={act.isPending} onAct={run} />
      </Panel>
      <Panel title="Build a mine" testId="quotes-panel">
        {x.quotes.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 13 }}>
            No permitted project without a mine. Take a project to a permit on the Exploration
            screen.
          </p>
        ) : (
          <QuotesTable
            quotes={x.quotes}
            busy={act.isPending}
            energy={x.build_energy}
            onBuild={(q, capacity) => run({ kind: 'build', projectId: q.project_id, capacity })}
          />
        )}
      </Panel>
      <Panel title="Mines" testId="mines-panel">
        {x.mines.length === 0 ? (
          <p className="tst-muted" style={{ fontSize: 13 }}>
            No mines yet.
          </p>
        ) : (
          <MinesTable mines={x.mines} onSelect={setSelected} />
        )}
      </Panel>
      {mine && <MinePanel key={mine.id} m={mine} x={x} busy={act.isPending} onAct={run} />}
      {x.bids.length > 0 && (
        <Panel title="Rivals' bids" testId="bids-panel">
          {x.bids.map((b) => (
            <div
              key={b.id}
              style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}
              data-testid="bid-row"
            >
              <span>
                {b.bidder} offers {formatMoneyWhole(b.cents)} for {b.asset} (open to{' '}
                {b.expires_label})
              </span>
              <Button
                size="compact-xs"
                onClick={() => run({ kind: 'bid', bidId: b.id, accept: true })}
              >
                Accept
              </Button>
              <Button
                size="compact-xs"
                variant="default"
                onClick={() => run({ kind: 'bid', bidId: b.id, accept: false })}
              >
                Decline
              </Button>
            </div>
          ))}
        </Panel>
      )}
      <Panel title="Resource nationalism" testId="risk-panel">
        <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
          {x.regions
            .map(
              (r) =>
                `${r.label}: royalty ${formatShare(r.royalty_rate)}, nationalism ${r.resource_nationalism.toFixed(2)}`,
            )
            .join(' · ')}
        </p>
        <EventsTable events={x.events} />
      </Panel>
      <Panel title="Rival miners" testId="rivals-panel">
        <RivalsTable rivals={x.rivals} />
      </Panel>
    </>
  );
}

function CompaniesTable({ companies }: { companies: MiningCompany[] }) {
  const columns = useMemo(
    () =>
      companyHelper.columns([
        companyHelper.accessor('name', { header: 'Company' }),
        companyHelper.accessor('role', { header: 'Role' }),
        companyHelper.accessor('region', {
          header: 'Region',
          cell: ({ getValue }) => (getValue() ? humanize(getValue() as string) : '—'),
        }),
        companyHelper.accessor('cash_cents', {
          header: 'Cash',
          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: companies,
    getRowId: (c) => String(c.id),
  });
  return <DataTable table={table} label="Group companies" rowTestId="company-row" />;
}

function FoundForm({
  x,
  busy,
  onAct,
}: {
  x: Mines;
  busy: boolean;
  onAct: (a: MiningAction) => void;
}) {
  const [name, setName] = useState('');
  const [region, setRegion] = useState(x.regions[0]?.key ?? '');
  const [millions, setMillions] = useState<number | string>(
    Math.max(1, x.found_min_cents / CENTS / MILLION) * 100,
  );
  const gated = x.group_stage < x.found_min_stage;
  const how = gated ? x.found_how : name.trim() === '' ? 'name the subsidiary first' : '';
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
      <TextInput
        label="Found a subsidiary"
        placeholder="Name"
        size="xs"
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        data-testid="found-name"
      />
      <Select
        aria-label="Region"
        size="xs"
        data={x.regions.map((r) => ({ value: r.key, label: r.label }))}
        value={region}
        onChange={(v) => v && setRegion(v)}
        allowDeselect={false}
        data-testid="found-region"
      />
      <NumberInput
        aria-label="Cash injection, $M"
        size="xs"
        suffix=" $M"
        min={1}
        value={millions}
        onChange={setMillions}
        data-testid="found-cents"
        style={{ width: 120 }}
      />
      <Button
        size="xs"
        disabled={busy || gated || name.trim() === ''}
        title={how ? `How: ${how}` : undefined}
        onClick={() =>
          onAct({
            kind: 'found',
            name: name.trim(),
            region,
            cents: Math.round(Number(millions) * MILLION * CENTS),
          })
        }
        data-testid="found-subsidiary"
      >
        Found · {x.found_energy} energy
      </Button>
      {gated && (
        <span className="tst-muted" style={{ fontSize: 12 }}>
          Opens at stage {x.found_min_stage}.
        </span>
      )}
    </div>
  );
}

function TransferForm({
  x,
  busy,
  onAct,
}: {
  x: Mines;
  busy: boolean;
  onAct: (a: MiningAction) => void;
}) {
  const [asset, setAsset] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const chosen = x.assets.find((a) => `${a.kind}:${a.id}` === asset);
  return (
    <div
      style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 8 }}
    >
      <Select
        label="Move at book value"
        placeholder="Project or facility"
        size="xs"
        data={x.assets.map((a) => ({
          value: `${a.kind}:${a.id}`,
          label: `${a.label} (${a.company_name}, ${formatMoneyWhole(a.book_cents)})`,
        }))}
        value={asset}
        onChange={setAsset}
        data-testid="asset-select"
        style={{ minWidth: 320 }}
      />
      <Select
        aria-label="To company"
        placeholder="To"
        size="xs"
        data={x.companies
          .filter((c) => c.id !== chosen?.company_id)
          .map((c) => ({ value: String(c.id), label: c.name }))}
        value={to}
        onChange={setTo}
        data-testid="to-select"
      />
      <Button
        size="xs"
        disabled={busy || !chosen || to === null}
        onClick={() =>
          chosen &&
          to !== null &&
          onAct({
            kind: 'transfer',
            to: Number(to),
            projectId: chosen.kind === 'project' ? chosen.id : undefined,
            facilityId: chosen.kind === 'facility' ? chosen.id : undefined,
          })
        }
        data-testid="transfer"
      >
        Transfer
      </Button>
    </div>
  );
}

function QuotesTable({
  quotes,
  busy,
  energy,
  onBuild,
}: {
  quotes: MineQuote[];
  busy: boolean;
  energy: number;
  onBuild: (q: MineQuote, capacity: number | null) => void;
}) {
  const columns = useMemo(
    () =>
      quoteHelper.columns([
        quoteHelper.accessor('label', { header: 'Project' }),
        quoteHelper.accessor('company_name', { header: 'Company' }),
        quoteHelper.accessor('commodity_label', { header: 'Commodity' }),
        quoteHelper.accessor('subtype_label', { header: 'Mine' }),
        quoteHelper.accessor('design_t', {
          header: 'Capacity',
          cell: ({ row }) =>
            row.original.allowed
              ? `${formatTonnes(row.original.capacity_low_t)}–${formatTonnes(row.original.capacity_high_t)}/yr`
              : '—',
        }),
        quoteHelper.accessor('estimate_cents', {
          header: 'Capex (study)',
          cell: ({ row }) =>
            row.original.allowed
              ? `${formatMoneyWhole(row.original.estimate_cents)} · overrun ${formatShare(row.original.overrun_low)}–${formatShare(row.original.overrun_high)}`
              : row.original.reason,
        }),
        quoteHelper.accessor('construction_low', {
          header: 'Build',
          cell: ({ row }) =>
            row.original.allowed
              ? `${row.original.construction_low}–${row.original.construction_high} months`
              : '—',
        }),
        quoteHelper.accessor('npv_mid_cents', {
          header: 'NPV (mid)',
          cell: ({ getValue }) =>
            getValue() === null ? '—' : formatMoneyWhole(getValue() as number),
        }),
        quoteHelper.display({
          id: 'build',
          header: '',
          cell: ({ row }) =>
            row.original.allowed ? (
              <Button
                size="compact-xs"
                disabled={busy}
                onClick={() => onBuild(row.original, null)}
                data-testid="build-mine"
              >
                Build · {energy}
              </Button>
            ) : (
              <span
                className="tst-muted"
                style={{ fontSize: 12, whiteSpace: 'normal' }}
                data-testid="build-mine-how"
                title={row.original.reason}
              >
                How: {row.original.how}
              </span>
            ),
        }),
      ]),
    [busy, energy, onBuild],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: quotes,
    getRowId: (q) => String(q.project_id),
  });
  return <DataTable table={table} label="Permitted projects" rowTestId="quote-row" />;
}

function MinesTable({ mines, onSelect }: { mines: Mine[]; onSelect: (id: number) => void }) {
  const columns = useMemo(
    () =>
      mineHelper.columns([
        mineHelper.accessor('name', {
          header: 'Mine',
          cell: ({ row }) => (
            <Button variant="subtle" size="compact-xs" onClick={() => onSelect(row.original.id)}>
              {row.original.name}
            </Button>
          ),
        }),
        mineHelper.accessor('company_name', { header: 'Company' }),
        mineHelper.accessor('status', { header: 'Status' }),
        mineHelper.accessor('last_output_t', {
          header: 'Output (month)',
          cell: ({ getValue }) => formatTonnes(getValue()),
        }),
        mineHelper.accessor('price_usd_t', {
          header: 'Price',
          cell: ({ getValue }) => formatPerTonne(getValue()),
        }),
        mineHelper.accessor('cost_usd_t', {
          header: 'Cost',
          meta: { term: 'mining.aisc' },
          cell: ({ getValue }) => formatPerTonne(getValue()),
        }),
        mineHelper.accessor('book_cents', {
          header: 'Book value',
          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
      ]),
    [onSelect],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: mines,
    getRowId: (m) => String(m.id),
  });
  return <DataTable table={table} label="Mines" rowTestId="mine-row" />;
}

function MinePanel({
  m,
  x,
  busy,
  onAct,
}: {
  m: Mine;
  x: Mines;
  busy: boolean;
  onAct: (a: MiningAction) => void;
}) {
  const [unit, setUnit] = useState<string | null>(m.unit_id === null ? null : String(m.unit_id));
  const [buyer, setBuyer] = useState<string>(m.buyer_id === null ? 'spot' : String(m.buyer_id));
  const [priceKind, setPriceKind] = useState(m.price_kind);
  const [volume, setVolume] = useState<number | string>(Math.round(m.capacity_t / 4));
  const copper = m.price_usd_lb !== null;
  const open = !['closed', 'seized'].includes(m.status);
  const price = copper ? formatPerPound(m.price_usd_lb) : formatPerTonne(m.price_usd_t);
  const cost = copper ? formatPerPound(m.cost_usd_lb) : formatPerTonne(m.cost_usd_t);
  const capex =
    m.revised_cents === null
      ? `${formatMoneyWhole(m.estimate_cents)} (the study's estimate; overrun ${formatShare(m.overrun_low)}–${formatShare(m.overrun_high)} possible)`
      : `${formatMoneyWhole(m.revised_cents)} (revised; estimate ${formatMoneyWhole(m.estimate_cents)})`;
  return (
    <Panel title={m.name} testId="mine-panel">
      <div
        style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 16 }}
      >
        <dl className="tst-facts" style={{ fontSize: 13, margin: 0 }} data-testid="mine-facts">
          <Fact label="Status" value={humanize(m.status)} testId="mine-status" />
          <Fact label="Owner" value={m.company_name} />
          <Fact
            label="Mine"
            value={`${m.subtype_label}, ${formatTonnes(m.capacity_t)}/yr of ${m.commodity_label.toLowerCase()} (${humanize(m.level)} study)`}
          />
          <Fact
            label="Construction"
            value={`${m.construction_done} of ${m.construction_months} months (ready ${m.ready_label})`}
            testId="mine-construction"
          />
          <Fact label="Capex" term="mining.overrun" value={capex} testId="mine-capex" />
          <Fact
            label="Output"
            value={
              m.last_output_t === null
                ? '—'
                : `${formatTonnes(m.last_output_t)} last month; ${formatTonnes(m.product_t)} in all`
            }
            testId="mine-output"
          />
          <Fact
            label="Grade"
            term="mining.grade"
            value={
              m.last_grade === null
                ? `design ${formatGrade(m.design_grade, 'pct')}`
                : `${formatGrade(m.last_grade, 'pct')} reconciled (design ${formatGrade(m.design_grade, 'pct')})`
            }
          />
          <Fact
            label="Price against cost"
            term="mining.aisc"
            value={`${price} against ${cost}${m.below_cost_months > 0 ? ` · ${m.below_cost_months} months below cost` : ''} (at capacity ${formatPerTonne(m.expected_cost_usd_t)})`}
            testId="mine-margin"
          />
          <Fact
            label="Reserves (est.)"
            term="mining.reserves"
            value={
              m.reserves_low_t === null || m.reserves_high_t === null
                ? '—'
                : `${formatTonnes(m.reserves_low_t)}–${formatTonnes(m.reserves_high_t)} of product left`
            }
          />
          <Fact
            label="Staff"
            value={`${m.staff} of ${m.staff_needed} mining engineers (${formatShare(m.coverage)} covered)`}
          />
          <Fact
            label="Sales"
            value={
              m.buyer_name
                ? `to ${m.buyer_name} at ${humanize(m.price_kind)}`
                : 'at spot' + (m.deals.length ? `, ${m.deals.length} contracts` : '')
            }
          />
          {m.state_share > 0 && (
            <Fact label="State partner" value={`${formatShare(m.state_share)} of the mine`} />
          )}
          {m.ban_until_label && <Fact label="Export ban" value={`to ${m.ban_until_label}`} />}
          {m.open_event && (
            <Fact
              label="Open event"
              value={`${humanize(m.open_event)}: answer it in the inbox`}
              testId="mine-event"
            />
          )}
          <Fact
            label="Reclamation"
            value={`${formatMoneyWhole(m.reclamation_owed_cents)} owed (provisioned ${formatMoneyWhole(m.reclamation_provisioned_cents)})`}
          />
          {m.closed_label && (
            <Fact
              label="Closed"
              value={`${m.closed_label}${m.close_reason ? ` (${humanize(m.close_reason)})` : ''}${m.arbitration_label ? `; arbitration award due ${m.arbitration_label}` : ''}`}
            />
          )}
        </dl>
        {open && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Select
              label="Staffed by"
              size="xs"
              data={x.units.map((u) => ({
                value: String(u.id),
                label: `${u.name} (${u.company_name}, ${u.mining_engineers} mining engineers)`,
              }))}
              value={unit}
              onChange={(v) => {
                setUnit(v);
                onAct({ kind: 'staff', mineId: m.id, unitId: v === null ? null : Number(v) });
              }}
              data-testid="staff-select"
            />
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <Select
                label="Sell to"
                size="xs"
                data={[
                  { value: 'spot', label: 'The market (spot)' },
                  ...x.companies
                    .filter((c) => c.id !== m.company_id)
                    .map((c) => ({ value: String(c.id), label: c.name })),
                ]}
                value={buyer}
                onChange={(v) => v && setBuyer(v)}
                allowDeselect={false}
                data-testid="buyer-select"
              />
              <Select
                aria-label="Transfer price"
                size="xs"
                data={x.transfer_kinds.map((k) => ({ value: k, label: humanize(k) }))}
                value={priceKind}
                onChange={(v) => v && setPriceKind(v)}
                allowDeselect={false}
                disabled={buyer === 'spot'}
              />
              <Button
                size="xs"
                disabled={busy}
                onClick={() =>
                  onAct({
                    kind: 'sales',
                    mineId: m.id,
                    buyerId: buyer === 'spot' ? null : Number(buyer),
                    priceKind,
                  })
                }
                data-testid="set-sales"
              >
                Set
              </Button>
            </div>
            <Select
              label="Safety spend"
              size="xs"
              data={x.safety_levels.map((s) => ({ value: s, label: humanize(s) }))}
              value={m.safety}
              onChange={(v) => v && onAct({ kind: 'safety', mineId: m.id, safety: v })}
              allowDeselect={false}
            />
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <NumberInput
                label="Sell forward, t/yr"
                size="xs"
                min={1}
                value={volume}
                onChange={setVolume}
                style={{ width: 130 }}
              />
              <Button
                size="xs"
                variant="default"
                disabled={busy}
                onClick={() =>
                  onAct({
                    kind: 'deal',
                    mineId: m.id,
                    dealKind: 'contract',
                    volume: Number(volume),
                    months: 12,
                  })
                }
              >
                12-month contract
              </Button>
              <Button
                size="xs"
                variant="default"
                disabled={busy}
                onClick={() =>
                  onAct({
                    kind: 'deal',
                    mineId: m.id,
                    dealKind: 'offtake',
                    volume: Number(volume),
                    years: 5,
                  })
                }
              >
                5-year offtake
              </Button>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {m.status === 'producing' && (
                <Button
                  size="xs"
                  variant="default"
                  disabled={busy}
                  onClick={() => onAct({ kind: 'care', mineId: m.id, restart: false })}
                  data-testid="care"
                >
                  Care and maintenance
                </Button>
              )}
              {m.status === 'care' && (
                <Button
                  size="xs"
                  disabled={busy}
                  onClick={() => onAct({ kind: 'care', mineId: m.id, restart: true })}
                  data-testid="restart"
                >
                  Restart
                </Button>
              )}
              <Button
                size="xs"
                color="red"
                variant="light"
                disabled={busy}
                onClick={() => onAct({ kind: 'close', mineId: m.id })}
                data-testid="close-mine"
              >
                Close the mine
              </Button>
            </div>
          </div>
        )}
      </div>
      {m.history.length > 0 && <HistoryTable months={m.history} copper={copper} />}
    </Panel>
  );
}

function HistoryTable({ months, copper }: { months: MineMonth[]; copper: boolean }) {
  const columns = useMemo(
    () =>
      monthHelper.columns([
        monthHelper.accessor('label', { header: 'Month' }),
        monthHelper.accessor('output_t', {
          header: 'Output',
          cell: ({ getValue }) => formatTonnes(getValue()),
        }),
        monthHelper.accessor('grade', {
          header: 'Grade',
          cell: ({ getValue }) => (getValue() > 0 ? formatGrade(getValue(), 'pct') : '—'),
        }),
        monthHelper.accessor('price_usd_t', {
          header: 'Price',
          cell: ({ getValue }) =>
            copper ? formatTonneAsPound(getValue()) : formatPerTonne(getValue()),
        }),
        monthHelper.accessor('cost_usd_t', {
          header: 'Cost',
          cell: ({ getValue }) =>
            getValue() > 0
              ? copper
                ? formatTonneAsPound(getValue())
                : formatPerTonne(getValue())
              : '—',
        }),
        monthHelper.accessor('revenue_cents', {
          header: 'Revenue',
          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
        monthHelper.accessor('margin_cents', {
          header: 'Margin',
          cell: ({ getValue }) => formatMoneyWhole(getValue()),
        }),
      ]),
    [copper],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: [...months].reverse(),
    getRowId: (r) => String(r.turn),
  });
  return <DataTable table={table} label="Months" rowTestId="month-row" />;
}

function EventsTable({ events }: { events: RegionEvent[] }) {
  const columns = useMemo(
    () =>
      eventHelper.columns([
        eventHelper.accessor('label', { header: 'Month' }),
        eventHelper.accessor('region_label', { header: 'Region' }),
        eventHelper.accessor('kind', {
          header: 'Kind',
          cell: ({ getValue }) => humanize(getValue()),
        }),
        eventHelper.accessor('title', { header: 'Event' }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: events,
    getRowId: (e) => `${e.turn}-${e.region}-${e.commodity ?? ''}-${e.title}`,
  });
  return <DataTable table={table} label="Resource-nationalism events" rowTestId="event-row" />;
}

function RivalsTable({ rivals }: { rivals: RivalMiner[] }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', { header: 'Miner' }),
        rivalHelper.accessor('commodity_label', { header: 'Commodity' }),
        rivalHelper.accessor('region_label', { header: 'Region' }),
        rivalHelper.accessor('capacity_share', {
          header: 'Capacity (world share)',
          cell: ({ getValue }) => formatShare(getValue()),
        }),
        rivalHelper.accessor('output_share', {
          header: 'Output now',
          cell: ({ getValue }) => formatShare(getValue()),
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rivals,
    getRowId: (r) => `${r.supplier}-${r.commodity}`,
  });
  return <DataTable table={table} label="Rival miners" rowTestId="rival-row" />;
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
