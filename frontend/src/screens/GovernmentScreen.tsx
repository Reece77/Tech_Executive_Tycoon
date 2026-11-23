// Government (M44, formulas.md 57): tenders by government and area with their requirements, the
// player's bids with score bands, published awards and protests, contracts and their
// performance, staff and facility clearances, governments' budgets this year and rivals'
// published awards. Rivals' bids are never sent by the API. No game values are computed here:
// figures are formatted.
import { Alert, Button, MultiSelect, NumberInput, Select, Switch } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { OpenNegotiation } from '../components/NegotiationPanel';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  usePlaceBid,
  useProtestAward,
  useRequestClearances,
  useSponsorFacility,
  useWithdrawBid,
  useGovernment,
  type GovClearance,
  type GovContract,
  type Government,
  type Buyer,
  type RivalAward,
  type Tender,
} from '../hooks/government';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const tenderHelper = createColumnHelper<GameTableFeatures, Tender>();
const contractHelper = createColumnHelper<GameTableFeatures, GovContract>();
const clearanceHelper = createColumnHelper<GameTableFeatures, GovClearance>();
const rivalHelper = createColumnHelper<GameTableFeatures, RivalAward>();
const buyerHelper = createColumnHelper<GameTableFeatures, Buyer>();

const AREAS = ['cloud', 'ai', 'space', 'chips', 'devices', 'cyber'];
const CONTRACT: Record<string, string> = {
  fixed_price: 'Fixed price',
  cost_plus: 'Cost-plus',
  idiq: 'IDIQ',
};
const LEVEL: Record<string, string> = {
  none: 'None',
  secret: 'Secret',
  top_secret: 'Top Secret',
};

export function GovernmentScreen() {
  const { saveId = '' } = useParams();
  const q = useGovernment(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load government" error={q.error} />;
  return <GovernmentBody saveId={saveId} g={q.data} />;
}

function GovernmentBody({ saveId, g }: { saveId: string; g: Government }) {
  const [area, setArea] = useState<string>('');
  const [closed, setClosed] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  if (!g.enabled) {
    return (
      <>
        <ScreenTitle>Government</ScreenTitle>
        <Panel>This game has no government tenders.</Panel>
      </>
    );
  }
  const tenders = g.tenders.filter(
    (t) =>
      (area === '' || t.area === area) &&
      (closed ||
        t.status === 'open' ||
        t.status === 'evaluating' ||
        t.status === 'protested' ||
        t.my_bid),
  );
  const chosen = g.tenders.find((t) => t.id === selected) ?? null;
  const r = g.record;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }} data-testid="government-record">
            {r.awards} defence awards ·{' '}
            <Term term="government.past_performance">past performance</Term>{' '}
            {r.past_performance.toFixed(0)} · {r.reactions} staff letters
            {r.controlled_products.length > 0 && (
              <>
                {' '}
                · <Term term="government.itar">controlled</Term>: {r.controlled_products.join(', ')}
              </>
            )}
          </span>
        }
      >
        Government
      </ScreenTitle>
      <Panel
        title="Tenders"
        testId="government-tenders"
        action={
          <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <Select
              aria-label="Area"
              size="xs"
              data={[
                { value: '', label: 'Every area' },
                ...AREAS.map((a) => ({ value: a, label: a })),
              ]}
              value={area}
              onChange={(x) => setArea(x ?? '')}
            />
            <Switch
              size="xs"
              label="Closed too"
              checked={closed}
              onChange={(e) => setClosed(e.currentTarget.checked)}
            />
          </span>
        }
      >
        <TenderTable tenders={tenders} onSelect={setSelected} />
      </Panel>
      {chosen && <TenderPanel saveId={saveId} g={g} t={chosen} />}
      <Panel title="Contracts" testId="government-contracts">
        <ContractTable saveId={saveId} g={g} />
      </Panel>
      <Panel title="Clearances" testId="government-clearances">
        <ClearanceTable g={g} />
        <ClearanceForm saveId={saveId} g={g} />
        <FacilityForm saveId={saveId} g={g} />
      </Panel>
      <Panel title="Governments" testId="government-budgets">
        <BudgetTable g={g} />
        <p className="tst-muted" style={{ fontSize: 12 }}>
          Budgets are real 2010 dollars (SIPRI to 2024); tenders are at the game's scale.
        </p>
      </Panel>
      <Panel title="Rivals' published awards" testId="government-rivals">
        <RivalTable g={g} />
      </Panel>
    </>
  );
}

function TenderTable({ tenders, onSelect }: { tenders: Tender[]; onSelect: (id: number) => void }) {
  const columns = useMemo(
    () =>
      tenderHelper.columns([
        tenderHelper.accessor('title', {
          header: 'Tender',
          cell: (c) => (
            <Button
              size="compact-xs"
              variant="subtle"
              data-testid={`tender-select-${c.row.original.id}`}
              onClick={() => onSelect(c.row.original.id)}
            >
              {c.getValue()}
              {c.row.original.historical ? ' (history)' : ''}
            </Button>
          ),
        }),
        tenderHelper.accessor('government_label', { header: 'Government' }),
        tenderHelper.accessor('area', { header: 'Area' }),
        tenderHelper.accessor('ceiling_cents', {
          header: 'Value',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        tenderHelper.accessor('contract', {
          header: 'Contract',
          meta: { term: 'government.idiq' },
          cell: (c) => CONTRACT[c.getValue()] ?? c.getValue(),
        }),
        tenderHelper.accessor('clearance', {
          header: 'Clearance',
          meta: { term: 'government.clearance' },
          cell: (c) => LEVEL[c.getValue()] ?? c.getValue(),
        }),
        tenderHelper.accessor('closes', { header: 'Closes' }),
        tenderHelper.accessor('status', { header: 'Status' }),
        tenderHelper.accessor((t) => t.winners.join(', '), {
          id: 'winners',
          header: 'Awarded to',
          cell: (c) => (
            <span>
              {c.getValue() || '—'}
              {c.row.original.winning_band ? ` (${c.row.original.winning_band})` : ''}
            </span>
          ),
        }),
        tenderHelper.accessor((t) => t.my_bid?.status ?? '', {
          id: 'mine',
          header: 'Your bid',
          cell: (c) => (
            <span data-testid={`tender-mine-${c.row.original.id}`}>{c.getValue() || '—'}</span>
          ),
        }),
      ]),
    [onSelect],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: tenders });
  return (
    <DataTable table={table} label="Tenders" rowTestId="tender-row" empty="No tenders open now." />
  );
}

function TenderPanel({ saveId, g, t }: { saveId: string; g: Government; t: Tender }) {
  const bid = usePlaceBid(saveId);
  const withdraw = useWithdrawBid(saveId);
  const protest = useProtestAward(saveId);
  const [product, setProduct] = useState<string>(
    t.options[0] ? String(t.options[0].product_id) : '',
  );
  const [price, setPrice] = useState<number>(Math.round(t.ceiling_cents / 100));
  const [team, setTeam] = useState<string[]>([]);
  const mine = t.my_bid;
  return (
    <Panel title={t.title} testId="tender-detail">
      <p style={{ margin: '0 0 6px' }}>
        {t.government_label}, {t.buyer} · {formatMoney(t.ceiling_cents)} over {t.term_months} months
        (base {t.base_months}) · {CONTRACT[t.contract]} · {t.awards} award{t.awards > 1 ? 's' : ''}{' '}
        · announced {t.announced}, bids close {t.closes}, award {t.award_month}
        {t.large ? ' · large' : ''}
      </p>
      <div data-testid="tender-requirements">
        Requirements:
        <ul style={{ margin: '2px 0 6px' }}>
          {t.requirements.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </div>
      {t.protest_by && (
        <p data-testid="tender-protest">
          <Term term="government.protest">Protested</Term> by {t.protest_by}: the award is held.
        </p>
      )}
      {t.winners.length > 0 && (
        <p data-testid="tender-winners">
          Awarded to {t.winners.join(', ')}
          {t.winning_band ? `, lowest winning band ${t.winning_band}` : ''}.
        </p>
      )}
      {mine && (
        <div data-testid="bid-status">
          Your bid: {mine.product}, {formatMoney(mine.price_cents)} ({mine.month}) —{' '}
          <b>{mine.status}</b>
          {mine.band && (
            <span data-testid="bid-band">
              {' '}
              · <Term term="government.score_band">score band</Term> {mine.band.total} (price{' '}
              {mine.band.price}, technical {mine.band.technical}, past performance{' '}
              {mine.band.past_performance}){' '}
              <Explain metric="bid_score" entity={mine.id} label="score band" />
            </span>
          )}
          {mine.reasons.length > 0 && (
            <ul data-testid="bid-reasons">
              {mine.reasons.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
          {mine.status === 'submitted' && t.status === 'open' && (
            <Button size="compact-xs" variant="subtle" onClick={() => withdraw.mutate(t.id)}>
              Withdraw
            </Button>
          )}
          {mine.can_protest && (
            <Button
              size="compact-xs"
              color="orange"
              data-testid="bid-protest"
              disabled={protest.isPending}
              onClick={() => protest.mutate(t.id)}
            >
              Protest the award ({formatMoney(g.protest_cost_cents)})
            </Button>
          )}
          {protest.error && (
            <Alert color="red">{String(protest.error.message ?? protest.error)}</Alert>
          )}
        </div>
      )}
      {!mine && t.status === 'open' && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {t.options.length === 0 ? (
            <span className="tst-muted">You have no live product in this area.</span>
          ) : (
            <>
              <Select
                label="Product"
                data-testid="bid-product"
                allowDeselect={false}
                size="xs"
                data={t.options.map((o) => ({
                  value: String(o.product_id),
                  label: `${o.product} (quality ${o.quality.toFixed(0)})${o.unmet.length ? ' — unmet' : ''}`,
                }))}
                value={product}
                onChange={(x) => setProduct(x ?? '')}
              />
              <NumberInput
                label="Price over the term ($)"
                data-testid="bid-price"
                size="xs"
                min={1}
                thousandSeparator=","
                value={price}
                onChange={(x) => setPrice(Number(x) || 0)}
                style={{ width: 180 }}
              />
              <MultiSelect
                label="Capture team"
                size="xs"
                data={g.staff.map((s) => ({
                  value: String(s.person_id),
                  label: `${s.name} (${s.role})`,
                }))}
                value={team}
                onChange={setTeam}
                style={{ minWidth: 220 }}
              />
              <Button
                size="xs"
                data-testid="bid-submit"
                disabled={bid.isPending || product === ''}
                onClick={() =>
                  bid.mutate({
                    tenderId: t.id,
                    body: {
                      product_id: Number(product),
                      price_cents: price * 100,
                      team: team.map(Number),
                    },
                  })
                }
              >
                Bid
              </Button>
            </>
          )}
          {bid.error && <Alert color="red">{String(bid.error.message ?? bid.error)}</Alert>}
        </div>
      )}
      {t.options.some((o) => o.unmet.length > 0) && (
        <div
          data-testid="tender-unmet"
          className="tst-muted"
          style={{ fontSize: 12, marginTop: 6 }}
        >
          {t.options
            .filter((o) => o.unmet.length > 0)
            .map((o) => (
              <div key={o.product_id}>
                {o.product} would not meet: {o.unmet.join('; ')}
              </div>
            ))}
        </div>
      )}
    </Panel>
  );
}

function ContractTable({ saveId, g }: { saveId: string; g: Government }) {
  const columns = useMemo(
    () =>
      contractHelper.columns([
        contractHelper.accessor('title', { header: 'Contract' }),
        contractHelper.accessor('government_label', { header: 'Government' }),
        contractHelper.accessor('product', { header: 'Product' }),
        contractHelper.accessor('contract', {
          header: 'Type',
          meta: { term: 'government.cost_plus' },
          cell: (c) => CONTRACT[c.getValue()] ?? c.getValue(),
        }),
        contractHelper.accessor('award_cents', {
          header: 'Value',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        contractHelper.accessor('status', { header: 'Status' }),
        contractHelper.accessor('options', { header: 'Options' }),
        contractHelper.accessor('performance', {
          header: 'Performance',
          meta: { term: 'government.past_performance' },
          cell: (c) => c.getValue().toFixed(0),
        }),
        contractHelper.accessor('revenue_cents', {
          header: 'Revenue',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        contractHelper.accessor('cost_cents', {
          header: 'Cost',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        contractHelper.accessor('end', { header: 'Ends' }),
        contractHelper.display({
          id: 'terms',
          header: 'Final terms',
          cell: ({ row }) =>
            row.original.terms_open ? (
              <OpenNegotiation
                saveId={saveId}
                kind="government"
                params={{ contract_id: row.original.id }}
              />
            ) : null,
        }),
      ]),
    [saveId],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: g.contracts });
  return <DataTable table={table} label="Contracts" empty="No government contracts yet." />;
}

function ClearanceTable({ g }: { g: Government }) {
  const columns = useMemo(
    () =>
      clearanceHelper.columns([
        clearanceHelper.accessor('name', { header: 'Person' }),
        clearanceHelper.accessor('level', {
          header: 'Level',
          cell: (c) => LEVEL[c.getValue()] ?? c.getValue(),
        }),
        clearanceHelper.accessor('status', {
          header: 'Status',
          cell: (c) => (
            <span data-testid={`clearance-${c.row.original.person_id}`}>{c.getValue()}</span>
          ),
        }),
        clearanceHelper.accessor('requested', { header: 'Requested' }),
        clearanceHelper.accessor((x) => x.decided ?? '—', { id: 'decided', header: 'Decided' }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: g.clearances });
  return <DataTable table={table} label="Clearances" empty="No clearances requested." />;
}

function ClearanceForm({ saveId, g }: { saveId: string; g: Government }) {
  const request = useRequestClearances(saveId);
  const [people, setPeople] = useState<string[]>([]);
  const [level, setLevel] = useState('secret');
  return (
    <div
      style={{ display: 'flex', gap: 8, alignItems: 'flex-end', marginTop: 8, flexWrap: 'wrap' }}
    >
      <MultiSelect
        label={<Term term="government.clearance">Request clearances for</Term>}
        size="xs"
        data-testid="clearance-people"
        data={g.staff.map((s) => ({
          value: String(s.person_id),
          label: `${s.name}${s.clearance ? ` — ${s.clearance}` : ''}`,
        }))}
        value={people}
        onChange={setPeople}
        style={{ minWidth: 260 }}
      />
      <Select
        label="Level"
        size="xs"
        allowDeselect={false}
        data={[
          {
            value: 'secret',
            label: `Secret (${formatMoney(g.clearance_cost_cents.secret ?? 0)} each)`,
          },
          {
            value: 'top_secret',
            label: `Top Secret (${formatMoney(g.clearance_cost_cents.top_secret ?? 0)} each)`,
          },
        ]}
        value={level}
        onChange={(x) => setLevel(x ?? 'secret')}
      />
      <Button
        size="xs"
        data-testid="clearance-submit"
        disabled={request.isPending || people.length === 0}
        onClick={() => request.mutate({ person_ids: people.map(Number), level })}
      >
        Request
      </Button>
      {request.error && <Alert color="red">{String(request.error.message ?? request.error)}</Alert>}
    </div>
  );
}

function FacilityForm({ saveId, g }: { saveId: string; g: Government }) {
  const sponsor = useSponsorFacility(saveId);
  const [facility, setFacility] = useState('');
  return (
    <div
      style={{ display: 'flex', gap: 8, alignItems: 'flex-end', marginTop: 8, flexWrap: 'wrap' }}
    >
      <Select
        label={<Term term="government.facility_clearance">Facility clearance for</Term>}
        size="xs"
        data={g.facilities.map((f) => ({ value: String(f.facility_id), label: f.name }))}
        value={facility}
        onChange={(x) => setFacility(x ?? '')}
        style={{ minWidth: 260 }}
      />
      <Button
        size="xs"
        disabled={sponsor.isPending || facility === ''}
        onClick={() => sponsor.mutate(Number(facility))}
      >
        Sponsor ({formatMoney(g.facility_cost_cents)})
      </Button>
      {g.facility_clearances.map((f) => (
        <span key={f.facility_id} className="tst-muted" style={{ fontSize: 12 }}>
          {f.name}: {f.status}
        </span>
      ))}
      {sponsor.error && <Alert color="red">{String(sponsor.error.message ?? sponsor.error)}</Alert>}
    </div>
  );
}

function RivalTable({ g }: { g: Government }) {
  const columns = useMemo(
    () =>
      rivalHelper.columns([
        rivalHelper.accessor('name', { header: 'Company' }),
        rivalHelper.accessor('awards', { header: 'Awards' }),
        rivalHelper.accessor('awarded_cents', {
          header: 'Value',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        rivalHelper.accessor((x) => x.areas.join(', '), { id: 'areas', header: 'Areas' }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: g.rivals });
  return <DataTable table={table} label="Rivals' awards" empty="No published awards yet." />;
}

function BudgetTable({ g }: { g: Government }) {
  const columns = useMemo(
    () =>
      buyerHelper.columns([
        buyerHelper.accessor('label', { header: 'Government' }),
        buyerHelper.accessor('defence_cents_year', {
          header: 'Defence this year',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        buyerHelper.accessor('civil_cents_year', {
          header: 'Civil technology',
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        buyerHelper.accessor((x) => `${x.open_to.join(', ')}${x.you_may_bid ? '' : ' (not you)'}`, {
          id: 'open_to',
          header: 'Takes bids from',
        }),
        buyerHelper.accessor('open_tenders', { header: 'Open tenders' }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: g.governments });
  return <DataTable table={table} label="Governments" />;
}
