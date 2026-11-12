// The Group screen (M16, formulas.md 31.2 and 31.10): the entity tree from the listed entity
// (the holding company once formed) down, each company's stake, treatment and public numbers,
// and the holding company's gate. Numbers come from the API; nothing is computed here.
import { Alert, Button, NativeSelect, NumberInput, SegmentedControl } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { DataTable } from '../../components/DataTable';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { useRefineries } from '../../hooks/refining';
import { Term } from '../../components/Term';
import {
  useCapitalHistory,
  useFormHolding,
  useGroup,
  useGroupAction,
  useSubsidiaryUpdates,
  type CapitalAction,
  type GroupEntity,
} from '../../hooks/group';
import { useMines, useMiningAction } from '../../hooks/mining';
import { FoundForm } from '../MinesScreen';
import { formatBpPercent, formatMoneyShort } from '../../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const helper = createColumnHelper<GameTableFeatures, GroupEntity>();
const ROLE: Record<string, string> = {
  holding: 'Holding company',
  operating: 'Operating company',
  subsidiary: 'Subsidiary',
  company: 'Company',
};
const TREATMENT: Record<string, string> = {
  root: '—',
  consolidated: 'Consolidated',
  equity: 'Associate',
  fair_value: 'Fair value',
};

function value(e: GroupEntity): string {
  if (e.market_cap_cents !== null && e.market_cap_cents !== undefined)
    return formatMoneyShort(e.market_cap_cents);
  if (e.value_low_cents !== null && e.value_low_cents !== undefined && e.value_high_cents)
    return `${formatMoneyShort(e.value_low_cents)}–${formatMoneyShort(e.value_high_cents)}`;
  return '—';
}

export function GroupTab({ saveId }: { saveId: string }) {
  const group = useGroup(saveId);
  const form = useFormHolding(saveId);
  const act = useGroupAction(saveId);
  const [pct, setPct] = useState<Record<number, number>>({});
  const holdingId = group.data?.holding_id ?? null;
  const [flow, setFlow] = useState({ seller: '', buyer: '', good: 'compute' });
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('name', {
          header: 'Company',
          enableSorting: false,
          cell: ({ row }) => (
            <span style={{ paddingLeft: row.original.depth * 16 }}>
              <Link
                to={`/game/${saveId}/finance/statements?company=${row.original.company_id}`}
                data-testid="group-entity-link"
              >
                {row.original.name}
              </Link>
            </span>
          ),
        }),
        helper.accessor('role', {
          header: 'Role',
          meta: { term: 'group.role' },
          enableSorting: false,
          cell: ({ getValue }) => ROLE[getValue()] ?? getValue(),
        }),
        helper.accessor('stake_bp', {
          header: 'Stake',
          meta: { term: 'group.stake' },
          enableSorting: false,
          cell: ({ row }) =>
            row.original.depth === 0 ? (
              '—'
            ) : (
              <span className="tst-num">{formatBpPercent(row.original.stake_bp)}</span>
            ),
        }),
        helper.accessor('treatment', {
          header: 'Treatment',
          meta: { term: 'group.treatment' },
          enableSorting: false,
          cell: ({ getValue }) => TREATMENT[getValue()] ?? getValue(),
        }),
        helper.accessor('revenue_cents', {
          header: 'Revenue (12 months)',
          meta: { term: 'group.revenue' },
          enableSorting: false,
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        helper.accessor('operating_margin', {
          header: 'Operating margin',
          meta: { term: 'group.margin' },
          enableSorting: false,
          cell: ({ getValue }) => {
            const m = getValue();
            return (
              <span className="tst-num">
                {m === null || m === undefined ? '—' : `${(m * 100).toFixed(1)}%`}
              </span>
            );
          },
        }),
        helper.accessor('cash_cents', {
          header: 'Cash',
          meta: { term: 'group.cash' },
          enableSorting: false,
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        helper.display({
          id: 'value',
          header: 'Value',
          meta: { term: 'group.value' },
          cell: ({ row }) => <span className="tst-num">{value(row.original)}</span>,
        }),
        helper.accessor('ceo', {
          header: 'CEO',
          meta: { term: 'group.ceo' },
          enableSorting: false,
          cell: ({ getValue }) => getValue() ?? '—',
        }),
        helper.display({
          id: 'mandate',
          header: 'Mandate',
          meta: { term: 'group.mandate' },
          cell: ({ row }) =>
            row.original.ceo ? (
              <div>
                <SegmentedControl
                  size="xs"
                  data-testid="group-mandate"
                  value={row.original.mandate ?? ''}
                  onChange={(v) =>
                    act.mutate({
                      kind: 'mandate',
                      body: { company_id: row.original.company_id, mandate: v },
                    })
                  }
                  data={[
                    { value: 'grow', label: 'Grow' },
                    { value: 'margin', label: 'Margin' },
                    { value: 'return_cash', label: 'Return cash' },
                  ]}
                />
                {row.original.review && (
                  <div className="tst-muted" style={{ fontSize: 12 }} data-testid="group-review">
                    {row.original.review}
                  </div>
                )}
                {row.original.replacement_proposed && (
                  <Button
                    size="xs"
                    mt={4}
                    color="orange"
                    data-testid="group-replace-ceo"
                    onClick={() =>
                      act.mutate({ kind: 'replace', companyId: row.original.company_id })
                    }
                  >
                    Replace the CEO
                  </Button>
                )}
              </div>
            ) : (
              '—'
            ),
        }),
        helper.display({
          id: 'capital',
          header: 'Capital',
          meta: { term: 'group.capital' },
          cell: ({ row }) => {
            const e = row.original;
            if (!e.ceo) return '—';
            const share = pct[e.company_id] ?? 30;
            const bp = Math.round(share * 100);
            return (
              <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                <NumberInput
                  size="xs"
                  w={70}
                  min={1}
                  max={49}
                  suffix="%"
                  value={share}
                  aria-label={`Share of ${e.name}`}
                  data-testid="group-pct"
                  onChange={(v) => setPct((p) => ({ ...p, [e.company_id]: Number(v) || 0 }))}
                />
                <Button
                  size="xs"
                  variant="default"
                  data-testid="group-sell"
                  onClick={() => act.mutate({ kind: 'sell', companyId: e.company_id, stakeBp: bp })}
                >
                  Sell
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  data-testid="group-carve"
                  onClick={() =>
                    act.mutate({ kind: 'carve', companyId: e.company_id, stakeBp: bp })
                  }
                >
                  Carve out
                </Button>
                {holdingId !== null && e.parent_id === holdingId && (
                  <Button
                    size="xs"
                    variant="default"
                    data-testid="group-spin"
                    onClick={() => act.mutate({ kind: 'spin', companyId: e.company_id, keepBp: 0 })}
                  >
                    Spin off
                  </Button>
                )}
                {e.stake_bp < 10_000 && (
                  <Button
                    size="xs"
                    variant="default"
                    data-testid="group-buyout"
                    onClick={() => act.mutate({ kind: 'buyout', companyId: e.company_id })}
                  >
                    Buy out
                  </Button>
                )}
              </div>
            );
          },
        }),
      ]),
    [saveId, act, pct, holdingId],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: group.data?.entities ?? [],
    getRowId: (e) => String(e.company_id),
  });
  if (group.error) return <LoadError title="Could not load the group" error={group.error} />;
  if (!group.data) return <Loading />;
  const g = group.data;
  return (
    <>
      {!g.formed && (
        <Panel title="Holding company" testId="group-gate">
          <Term term="group.holding">
            <span className="tst-muted" style={{ fontSize: 12 }}>
              What a holding company does
            </span>
          </Term>
          {g.can_form ? (
            <p>
              Form a holding company: it takes the listing, the cap table and the board, and your
              company and its brands become its subsidiaries. You chair it. Energy {g.form_energy};
              legal fees about {formatMoneyShort(g.form_fee_cents)}; its group office costs{' '}
              {formatMoneyShort(g.office_monthly_cents)} a month.
            </p>
          ) : (
            <ul data-testid="group-reasons">
              {g.reasons.map((r) => (
                <li key={r}>Not yet: {r}.</li>
              ))}
            </ul>
          )}
          <Button
            disabled={!g.can_form || form.isPending}
            loading={form.isPending}
            onClick={() => form.mutate()}
            data-testid="group-form"
          >
            Form the holding company
          </Button>
          {form.error && (
            <Alert color="red" role="alert" mt="sm">
              {form.error.message}
            </Alert>
          )}
        </Panel>
      )}
      <Pitches saveId={saveId} />
      <Panel title="Group" testId="group-tree">
        <DataTable table={table} label="Group" rowTestId="group-row" empty="No companies." />
        {act.error && (
          <Alert color="red" role="alert" mt="sm">
            {act.error.message}
          </Alert>
        )}
      </Panel>
      <SubsidiaryUpdates saveId={saveId} />
      <FoundSubsidiary saveId={saveId} />
      <CapitalHistory saveId={saveId} />
      <ValueChain saveId={saveId} />
      <GroupMines saveId={saveId} />
      {g.discount && (
        <Panel title="Conglomerate discount" testId="group-discount">
          <Term term="group.discount">
            <span className="tst-muted" style={{ fontSize: 12 }}>
              How analysts value the group
            </span>
          </Term>
          <p data-testid="group-discount-text">
            Analysts value the parts at {formatMoneyShort(g.discount.parts_cents)} and apply a{' '}
            {(g.discount.discount * 100).toFixed(1)}% conglomerate discount ({g.discount.segments}{' '}
            segments, {(g.discount.intra_share * 100).toFixed(1)}% of revenue intra-group):{' '}
            {formatMoneyShort(g.discount.after_discount_cents)}.
          </p>
        </Panel>
      )}
      {g.entities.length > 1 && (
        <Panel title="Intra-group supply" testId="group-flows">
          <Term term="group.transfer">
            <span className="tst-muted" style={{ fontSize: 12 }}>
              Transfer prices
            </span>
          </Term>
          {(g.flows ?? []).map((f) => (
            <div
              key={f.id}
              data-testid="group-flow"
              style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 6 }}
            >
              <span>
                {f.seller} → {f.buyer}: {f.good}, last {formatMoneyShort(f.last_price_cents)}
                {f.minorities && f.unfair_months > 0 && ` · unfair ${f.unfair_months} months`}
              </span>
              {f.complaint && (
                <strong style={{ color: 'var(--tst-warn)' }} data-testid="group-complaint">
                  Minority complaint
                </strong>
              )}
              <SegmentedControl
                size="xs"
                value={f.price_kind}
                onChange={(v) =>
                  act.mutate({
                    kind: 'flow',
                    body: {
                      seller_id: f.seller_id,
                      buyer_id: f.buyer_id,
                      good: f.good,
                      price_kind: v,
                    },
                  })
                }
                data={[
                  { value: 'cost', label: 'Cost' },
                  { value: 'cost_plus', label: 'Cost plus' },
                  { value: 'market', label: 'Market' },
                ]}
              />
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
            {(['seller', 'buyer'] as const).map((side) => (
              <NativeSelect
                key={side}
                size="xs"
                label={side === 'seller' ? 'Supplier' : 'Buyer'}
                value={flow[side]}
                onChange={(e) => setFlow((x) => ({ ...x, [side]: e.currentTarget.value }))}
                data={[
                  { value: '', label: '—' },
                  ...g.entities.map((e) => ({ value: String(e.company_id), label: e.name })),
                ]}
              />
            ))}
            <NativeSelect
              size="xs"
              label="Good"
              value={flow.good}
              onChange={(e) => setFlow((x) => ({ ...x, good: e.currentTarget.value }))}
              data={['compute', 'chips']}
            />
            <Button
              size="xs"
              disabled={!flow.seller || !flow.buyer}
              onClick={() =>
                act.mutate({
                  kind: 'flow',
                  body: {
                    seller_id: Number(flow.seller),
                    buyer_id: Number(flow.buyer),
                    good: flow.good,
                    price_kind: 'cost',
                  },
                })
              }
            >
              Start supplying
            </Button>
          </div>
        </Panel>
      )}
      {((g.stakes ?? []).length > 0 || (g.personal_stakes ?? []).length > 0) && (
        <Panel title="Stakes" testId="group-stakes">
          {(g.stakes ?? []).map((x) => (
            <div key={`s${x.company_id}`} data-testid="group-stake">
              {x.company}: {formatBpPercent(x.stake_bp)} ({TREATMENT[x.treatment] ?? x.treatment}),
              carried at {formatMoneyShort(x.carrying_cents)}
            </div>
          ))}
          {(g.personal_stakes ?? []).map((x) => (
            <div key={`p${x.company_id}`} data-testid="group-personal-stake">
              You hold {formatBpPercent(x.stake_bp)} of {x.company} in your own name
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}

/** Subsidiaries' requests for capital (31.4), first on the screen: the inbox message links
 * here (M23c, playtest 5: "a capital request had no link to it"). */
function Pitches({ saveId }: { saveId: string }) {
  const group = useGroup(saveId);
  const act = useGroupAction(saveId);
  const pitches = group.data?.pitches ?? [];
  if (pitches.length === 0) return null;
  return (
    <Panel title="Requests from subsidiaries" testId="group-pitches">
      {pitches.map((p) => (
        <div
          key={p.id}
          data-testid="group-pitch"
          style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}
        >
          <span>
            {p.ceo} ({p.company}) asks for {formatMoneyShort(p.amount_cents)}:{' '}
            {p.fits_mandate ? 'fits its mandate' : 'does not fit its mandate'}.
          </span>
          <Button
            size="xs"
            onClick={() => act.mutate({ kind: 'pitch', pitchId: p.id, approve: true })}
          >
            Approve
          </Button>
          <Button
            size="xs"
            variant="default"
            onClick={() => act.mutate({ kind: 'pitch', pitchId: p.id, approve: false })}
          >
            Decline
          </Button>
        </div>
      ))}
    </Panel>
  );
}

/** Found a subsidiary (35.3; on the Group screen since M23c), linked from Mines. */
function FoundSubsidiary({ saveId }: { saveId: string }) {
  const mines = useMines(saveId);
  const act = useMiningAction(saveId);
  if (!mines.data) return null;
  return (
    <Panel title="Found a subsidiary" testId="group-found">
      <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
        A new, wholly owned company with its own cash. Move projects and facilities into it from the{' '}
        <Link to={`/game/${saveId}/products/mines`}>Mines screen</Link>, and give it a mandate here.
      </p>
      <FoundForm x={mines.data} busy={act.isPending} onAct={(a) => act.mutate(a)} />
      {act.error && (
        <Alert color="red" role="alert" mt="sm">
          {act.error.message}
        </Alert>
      )}
      {act.isSuccess && (
        <p style={{ fontSize: 13 }} data-testid="group-found-done">
          Founded. It appears in the group above.
        </p>
      )}
    </Panel>
  );
}

/** Each subsidiary CEO's quarterly update in their own words, ending with a question; the
 * answer re-sets the mandate (M23c, playtest 5). */
function SubsidiaryUpdates({ saveId }: { saveId: string }) {
  const updates = useSubsidiaryUpdates(saveId);
  const act = useGroupAction(saveId);
  const list = updates.data?.updates ?? [];
  if (list.length === 0) return null;
  return (
    <Panel title="Quarterly updates from your CEOs" testId="group-updates">
      {list.map((u) => (
        <div
          key={u.company_id}
          data-testid="group-update"
          style={{ padding: '8px 0', borderBottom: '1px solid var(--tst-rule)' }}
        >
          <div style={{ fontSize: 12 }} className="tst-muted">
            {u.ceo}, CEO of {u.company} · quarter to {u.quarter_label}
          </div>
          <p style={{ margin: '4px 0', fontSize: 14, color: 'var(--tst-text-2)' }}>
            &ldquo;{u.body} {u.question}&rdquo;
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
            <span className="tst-muted" style={{ fontSize: 12 }}>
              Your advice ({u.advice_energy} energy, sets the mandate):
            </span>
            {u.advice.map((a) => (
              <Button
                key={a.mandate}
                size="compact-xs"
                variant={a.current ? 'filled' : 'default'}
                disabled={a.current || act.isPending}
                data-testid="group-advice"
                data-mandate={a.mandate}
                onClick={() =>
                  act.mutate({
                    kind: 'mandate',
                    body: {
                      company_id: u.company_id,
                      mandate: a.mandate,
                      capex_limit_cents: u.capex_limit_cents,
                      categories: u.categories,
                      regions: u.regions,
                    },
                  })
                }
              >
                {a.label}
                {a.current ? ' (current)' : ''}
              </Button>
            ))}
          </div>
        </div>
      ))}
      {act.error && (
        <Alert color="red" role="alert" mt="sm">
          {act.error.message}
        </Alert>
      )}
    </Panel>
  );
}

const historyHelper = createColumnHelper<GameTableFeatures, CapitalAction>();

/** What the group's capital actions accomplished (M23c, playtest 5: "I sold and did a
 * carve-out but can't see where this is tracked"). */
function CapitalHistory({ saveId }: { saveId: string }) {
  const history = useCapitalHistory(saveId);
  const columns = useMemo(
    () =>
      historyHelper.columns([
        historyHelper.accessor('date_label', { header: 'Date', enableSorting: false }),
        historyHelper.accessor('kind_label', { header: 'Action' }),
        historyHelper.accessor('company', { header: 'Company' }),
        historyHelper.accessor('proceeds_cents', {
          header: 'Proceeds',
          cell: ({ getValue }) => formatMoneyShort(getValue()),
        }),
        historyHelper.display({
          id: 'ownership',
          header: 'Ownership',
          cell: ({ row }) =>
            `${formatBpPercent(row.original.stake_before_bp)} → ${formatBpPercent(row.original.stake_after_bp)}`,
        }),
        historyHelper.accessor('nci_cents', {
          header: 'NCI',
          meta: { term: 'group.nci' },
          cell: ({ getValue }) => formatMoneyShort(getValue()),
        }),
        historyHelper.accessor('value_created_cents', {
          header: 'Value created',
          cell: ({ row }) => (
            <span title={row.original.value_note}>
              {formatMoneyShort(row.original.value_created_cents)}
            </span>
          ),
        }),
        historyHelper.accessor('stake_value_now_cents', {
          header: 'Stake worth now',
          cell: ({ getValue }) => {
            const v = getValue();
            return v === null || v === undefined ? '—' : formatMoneyShort(v);
          },
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: history.data?.actions ?? [],
    getRowId: (a) => `${a.turn}-${a.kind}-${a.company_id}-${a.proceeds_cents}`,
  });
  if (!history.data || history.data.actions.length === 0) return null;
  return (
    <Panel title="Capital actions" testId="group-history">
      <p className="tst-muted" style={{ fontSize: 12, marginTop: 0 }}>
        Stake sales, carve-outs, spin-offs and buyouts: what each raised, the ownership it left, the
        minorities&apos; share of book equity (NCI) and the value it created on the owner&apos;s
        books (hover for what it means).
      </p>
      <DataTable table={table} label="Capital actions" rowTestId="capital-action" />
    </Panel>
  );
}

const STAGES = ['mine', 'refinery', 'wafer', 'fab', 'chip', 'device'] as const;

/** The group's value chain (M20, formulas.md 36; M21's fabs): mine → refinery → wafer → fab →
 * chip → device. */
function ValueChain({ saveId }: { saveId: string }) {
  const refineries = useRefineries(saveId);
  const chain = refineries.data?.chain ?? [];
  if (chain.length === 0) return null;
  return (
    <Panel title="Value chain" testId="group-chain">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${STAGES.length}, minmax(0, 1fr))`,
          gap: 8,
        }}
      >
        {STAGES.map((stage) => (
          <div key={stage} data-testid={`chain-${stage}`}>
            <div className="tst-muted" style={{ fontSize: 12, textTransform: 'capitalize' }}>
              {stage}
            </div>
            {chain
              .filter((l) => l.stage === stage)
              .map((l) => (
                <div key={l.name} style={{ fontSize: 13, padding: '2px 0' }} title={l.detail}>
                  {l.name}
                  <span className="tst-muted"> · {l.company}</span>
                  {l.supplies.length > 0 && (
                    <div className="tst-muted" style={{ fontSize: 11 }}>
                      → {l.supplies.join(', ')}
                    </div>
                  )}
                </div>
              ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}

/** M19 (35): the group's mines by company, from the Mines screen's read model. */
function GroupMines({ saveId }: { saveId: string }) {
  const mines = useMines(saveId);
  const list = mines.data?.mines ?? [];
  if (list.length === 0) return null;
  return (
    <Panel title="Mines" testId="group-mines">
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
        {list.map((m) => (
          <li key={m.id} data-testid="group-mine">
            {m.name}: {m.company_name}, {m.status}
            {m.state_share > 0 ? `, state partner ${Math.round(m.state_share * 100)}%` : ''}; book{' '}
            {formatMoneyShort(m.book_cents)}
          </li>
        ))}
      </ul>
      <Link to={`/game/${saveId}/products/mines`} style={{ fontSize: 13 }}>
        Open Mines
      </Link>
    </Panel>
  );
}
