// The founder's own investments on their profile (M26, formulas.md 37): net worth and its
// history, angel stakes and open rounds, backing someone from the network, listed shares and
// trades, and the family office. Personal money only; values come from the API only (a
// trade's regulatory risk never reaches the front end: only a "sensitive window" flag).
import { Alert, Badge, Button, NativeSelect, NumberInput, SegmentedControl } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  CartesianGrid,
  Line as ChartLine,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  useBackStartup,
  useFormFamilyOffice,
  useInvestments,
  useJoinRound,
  useMoveFamilyOffice,
  useSetOfficeMandate,
  useTradeShares,
  type AngelStake,
  type Holding,
  type Investments,
  type Listed,
  type OpenRound,
  type Trade,
} from '../hooks/investing';
import { formatMoneyShort, formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Panel } from './ScreenState';

const CENTS = 100;

function Row({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span className="tst-muted">{label}</span>
      <span className="tst-num" data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

function Problem({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <Alert color="orange" role="alert">
      {error.message}
    </Alert>
  );
}

export function InvestmentsTab({ saveId }: { saveId: string }) {
  const q = useInvestments(saveId);
  if (!q.data) return null;
  const inv = q.data;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="investments">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        <NetWorthPanel inv={inv} />
        <FamilyOfficePanel saveId={saveId} inv={inv} />
      </div>
      <AngelPanel saveId={saveId} inv={inv} />
      <BackPanel saveId={saveId} inv={inv} />
      <SharesPanel saveId={saveId} inv={inv} />
    </div>
  );
}

function NetWorthPanel({ inv }: { inv: Investments }) {
  const n = inv.net_worth;
  return (
    <Panel title="Net worth" style={{ flex: '2 1 420px', minWidth: 0 }} testId="net-worth-panel">
      <span style={{ fontSize: 24, fontWeight: 700 }} className="tst-num" data-testid="net-worth">
        {formatMoneyWhole(n.total_cents)}
      </span>
      <Row label="Personal cash" value={formatMoneyWhole(n.cash_cents)} testId="inv-cash" />
      <Row label="Angel stakes (last round price)" value={formatMoneyWhole(n.angel_cents)} />
      <Row label="Listed shares" value={formatMoneyWhole(n.public_cents)} testId="inv-public" />
      <Row label="Family office" value={formatMoneyWhole(n.family_office_cents)} />
      <Row label="Your company stake" value={formatMoneyWhole(n.own_stake_cents)} />
      {inv.history.length > 1 && (
        <div role="img" aria-label="Net worth and your company stake at each month end">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={inv.history} margin={{ top: 12, right: 12, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
              <XAxis
                dataKey="date_label"
                stroke="var(--tst-muted)"
                fontSize={11}
                tickFormatter={(label: string) => label.split(' ')[1] ?? label}
              />
              <YAxis
                stroke="var(--tst-muted)"
                fontSize={11}
                tickFormatter={(v: number) => formatMoneyShort(v)}
                width={64}
              />
              <Tooltip formatter={(v) => formatMoneyWhole(Number(v))} />
              <ChartLine
                type="monotone"
                dataKey="total_cents"
                name="Net worth"
                stroke="var(--tst-accent)"
                dot={false}
                isAnimationActive={false}
              />
              <ChartLine
                type="monotone"
                dataKey="own_stake_cents"
                name="Your company stake"
                stroke="var(--tst-muted)"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

const stakeHelper = createColumnHelper<GameTableFeatures, AngelStake>();
const roundHelper = createColumnHelper<GameTableFeatures, OpenRound>();

function AngelPanel({ saveId, inv }: { saveId: string; inv: Investments }) {
  const join = useJoinRound(saveId);
  const [amounts, setAmounts] = useState<Record<number, number | string>>({});
  const stakeColumns = useMemo(
    () =>
      stakeHelper.columns([
        stakeHelper.accessor('company', {
          id: 'inv.stake_company',
          header: 'Startup',
          cell: ({ row }) => (
            <Link to={`/game/${saveId}/competitors/${row.original.company_id}`}>
              {row.original.company}
            </Link>
          ),
        }),
        stakeHelper.accessor('status', { id: 'inv.stake_status', header: 'Status' }),
        stakeHelper.accessor('stake_pct', {
          id: 'inv.stake_pct',
          header: 'Stake',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{getValue().toFixed(2)}%</span>,
        }),
        stakeHelper.accessor('cost_cents', {
          id: 'inv.stake_cost',
          header: 'Cost',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        stakeHelper.accessor('worth_cents', {
          id: 'inv.stake_value',
          header: 'Value / proceeds',
          sortFn: 'basic',
          cell: ({ row }) => (
            <span className="tst-num">
              {formatMoneyWhole(
                row.original.status === 'acquired'
                  ? row.original.proceeds_cents
                  : row.original.worth_cents,
              )}
            </span>
          ),
        }),
        stakeHelper.accessor('cash_band', {
          id: 'inv.stake_cash',
          header: 'Cash',
          cell: ({ getValue }) => getValue() ?? '',
        }),
        stakeHelper.accessor('funding', {
          id: 'inv.stake_rounds',
          header: 'Rounds',
          enableSorting: false,
          cell: ({ getValue }) =>
            getValue()
              .map((r) => `${r.date_label} ${formatMoneyShort(r.raised_cents)}`)
              .join(' · '),
        }),
        stakeHelper.accessor('conflict', {
          id: 'inv.stake_conflict',
          header: 'Conflict',
          cell: ({ getValue }) => getValue() ?? '',
        }),
      ]),
    [saveId],
  );
  const roundColumns = useMemo(
    () =>
      roundHelper.columns([
        roundHelper.accessor('company', {
          id: 'inv.round_company',
          header: 'Startup',
          cell: ({ row }) => (
            <Link to={`/game/${saveId}/competitors/${row.original.company_id}`}>
              {row.original.company}
            </Link>
          ),
        }),
        roundHelper.accessor('category_label', { id: 'inv.round_category', header: 'Category' }),
        roundHelper.accessor('date_label', { id: 'inv.round_month', header: 'Closed' }),
        roundHelper.accessor('raised_cents', {
          id: 'inv.round_raised',
          header: 'Raised',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        roundHelper.accessor('post_cents', {
          id: 'inv.round_post',
          header: 'Post-money',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        roundHelper.display({
          id: 'inv.round_invest',
          header: 'Invest',
          cell: ({ row }) => {
            const r = row.original;
            return (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <NumberInput
                  size="xs"
                  aria-label={`Dollars into ${r.company}`}
                  value={amounts[r.company_id] ?? ''}
                  onChange={(v) => setAmounts((a) => ({ ...a, [r.company_id]: v }))}
                  min={1}
                  max={r.max_cents / CENTS}
                  thousandSeparator=","
                  style={{ width: 120 }}
                  data-testid={`round-amount-${r.company_id}`}
                />
                <Button
                  size="xs"
                  disabled={!Number(amounts[r.company_id])}
                  loading={join.isPending}
                  onClick={() =>
                    join.mutate({
                      company_id: r.company_id,
                      cents: Math.round(Number(amounts[r.company_id]) * CENTS),
                    })
                  }
                  data-testid={`round-invest-${r.company_id}`}
                >
                  Invest
                </Button>
              </div>
            );
          },
        }),
      ]),
    [saveId, amounts, join],
  );
  const stakes = useTable({
    features: gameTableFeatures,
    columns: stakeColumns,
    data: inv.stakes,
    getRowId: (s) => String(s.id),
  });
  const rounds = useTable({
    features: gameTableFeatures,
    columns: roundColumns,
    data: inv.open_rounds,
    getRowId: (r) => String(r.company_id),
  });
  return (
    <Panel title="Angel investing" testId="angel-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Join a startup&apos;s round in the month after it closes, at its price (min{' '}
        {formatMoneyWhole(inv.rules.round_min_cents)}, {inv.rules.join_energy} energy). Later rounds
        dilute you unless you follow on.
      </span>
      <Problem error={join.error} />
      <DataTable
        table={rounds}
        label="Open rounds"
        rowTestId="open-round"
        empty="No startup has a round open to you this month."
      />
      <DataTable
        table={stakes}
        label="Your angel stakes"
        rowTestId="angel-stake"
        empty="No angel stakes yet."
      />
    </Panel>
  );
}

function BackPanel({ saveId, inv }: { saveId: string; inv: Investments }) {
  const back = useBackStartup(saveId);
  const [person, setPerson] = useState('');
  const [category, setCategory] = useState(inv.categories[0]?.key ?? '');
  const [dollars, setDollars] = useState<number | string>(inv.rules.min_cheque_cents / CENTS);
  const chosen = person || String(inv.network[0]?.person_id ?? '');
  return (
    <Panel title="Back a new startup" testId="back-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Fund someone from your network (people who left your company, your candidates) to found a
        startup: your cheque is its founding cash, for {inv.rules.seed_stake_low_pct}–
        {inv.rules.seed_stake_high_pct}% by size ({inv.rules.back_energy} energy). People whose
        skills you know well are marked.
      </span>
      {inv.network.length === 0 ? (
        <span className="tst-muted">Your network is empty.</span>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
          <NativeSelect
            label="Founder"
            value={chosen}
            onChange={(e) => setPerson(e.currentTarget.value)}
            data={inv.network.map((p) => ({
              value: String(p.person_id),
              label: `${p.name}, ${p.role_label}${p.known ? ' (known)' : ''}${p.source === 'candidate' ? ' (candidate)' : ''}`,
            }))}
            data-testid="back-founder"
          />
          <NativeSelect
            label="Category"
            value={category}
            onChange={(e) => setCategory(e.currentTarget.value)}
            data={inv.categories.map((c) => ({ value: c.key, label: c.label }))}
            data-testid="back-category"
          />
          <NumberInput
            label="Cheque ($)"
            value={dollars}
            onChange={setDollars}
            min={inv.rules.min_cheque_cents / CENTS}
            thousandSeparator=","
            data-testid="back-amount"
          />
          <Button
            onClick={() =>
              back.mutate({
                founder_id: Number(chosen),
                category,
                cents: Math.round(Number(dollars) * CENTS),
              })
            }
            disabled={!chosen || !Number(dollars)}
            loading={back.isPending}
            data-testid="back-startup"
          >
            Back the startup
          </Button>
        </div>
      )}
      <Problem error={back.error} />
    </Panel>
  );
}

const listedHelper = createColumnHelper<GameTableFeatures, Listed>();
const holdingHelper = createColumnHelper<GameTableFeatures, Holding>();
const tradeHelper = createColumnHelper<GameTableFeatures, Trade>();

function SharesPanel({ saveId, inv }: { saveId: string; inv: Investments }) {
  const trade = useTradeShares(saveId);
  const [counts, setCounts] = useState<Record<number, number | string>>({});
  const listedColumns = useMemo(
    () =>
      listedHelper.columns([
        listedHelper.accessor('company', {
          id: 'inv.listed_company',
          header: 'Company',
          cell: ({ row }) => (
            <span>
              {row.original.company}
              {row.original.own && ' (yours)'}
              {row.original.sensitive && (
                <Badge color="orange" size="xs" ml={6}>
                  sensitive window
                </Badge>
              )}
            </span>
          ),
        }),
        listedHelper.accessor('price_cents', {
          id: 'inv.listed_price',
          header: 'Share price',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        listedHelper.display({
          id: 'inv.listed_trade',
          header: 'Trade',
          cell: ({ row }) => {
            const c = row.original;
            const n = Number(counts[c.company_id]);
            if (!c.window_open) return <span className="tst-muted">closed before earnings</span>;
            return (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <NumberInput
                  size="xs"
                  aria-label={`Shares of ${c.company}`}
                  value={counts[c.company_id] ?? ''}
                  onChange={(v) => setCounts((a) => ({ ...a, [c.company_id]: v }))}
                  min={1}
                  thousandSeparator=","
                  style={{ width: 120 }}
                  data-testid={`shares-count-${c.company_id}`}
                />
                <Button
                  size="xs"
                  disabled={!n}
                  loading={trade.isPending}
                  onClick={() => trade.mutate({ company_id: c.company_id, side: 'buy', shares: n })}
                  data-testid={`shares-buy-${c.company_id}`}
                >
                  Buy
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  disabled={!n}
                  loading={trade.isPending}
                  onClick={() =>
                    trade.mutate({ company_id: c.company_id, side: 'sell', shares: n })
                  }
                  data-testid={`shares-sell-${c.company_id}`}
                >
                  Sell
                </Button>
              </div>
            );
          },
        }),
      ]),
    [counts, trade],
  );
  const holdingColumns = useMemo(
    () =>
      holdingHelper.columns([
        holdingHelper.accessor('company', { id: 'inv.holding_company', header: 'Company' }),
        holdingHelper.accessor('shares', {
          id: 'inv.holding_shares',
          header: 'Shares',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatWhole(getValue())}</span>,
        }),
        holdingHelper.accessor('worth_cents', {
          id: 'inv.holding_value',
          header: 'Value',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        holdingHelper.accessor('cost_cents', {
          id: 'inv.holding_cost',
          header: 'Cost',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
      ]),
    [],
  );
  const tradeColumns = useMemo(
    () =>
      tradeHelper.columns([
        tradeHelper.accessor('date_label', { id: 'inv.trade_month', header: 'Month' }),
        tradeHelper.accessor('company', { id: 'inv.trade_company', header: 'Company' }),
        tradeHelper.accessor('side', {
          id: 'inv.trade_side',
          header: 'Side',
          cell: ({ getValue }) => humanize(getValue()),
        }),
        tradeHelper.accessor('shares', {
          id: 'inv.trade_shares',
          header: 'Shares',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatWhole(getValue())}</span>,
        }),
        tradeHelper.accessor('price_cents', {
          id: 'inv.trade_price',
          header: 'Price',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyShort(getValue())}</span>,
        }),
        tradeHelper.display({
          id: 'inv.trade_flags',
          header: 'Notes',
          cell: ({ row }) => {
            const t = row.original;
            const notes = [
              t.sensitive ? 'in a sensitive window' : '',
              t.filed ? 'public filing' : '',
              t.investigation === 'open' ? 'under investigation' : '',
              t.investigation === 'finding' ? 'finding against you' : '',
            ].filter(Boolean);
            return <span data-testid="trade-notes">{notes.join(' · ')}</span>;
          },
        }),
      ]),
    [],
  );
  const listed = useTable({
    features: gameTableFeatures,
    columns: listedColumns,
    data: inv.listed,
    getRowId: (c) => String(c.company_id),
  });
  const holdings = useTable({
    features: gameTableFeatures,
    columns: holdingColumns,
    data: inv.holdings,
    getRowId: (h) => String(h.company_id),
  });
  const trades = useTable({
    features: gameTableFeatures,
    columns: tradeColumns,
    data: inv.trades,
    getRowId: (t) => String(t.id),
  });
  return (
    <Panel title="Listed shares" testId="shares-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        Trade at last month&apos;s share price ({inv.rules.trade_cost_pct}% cost,{' '}
        {inv.rules.trade_energy} energy). Your own company&apos;s shares are closed in the month
        before earnings; trading ahead of news you know about can bring an investigation.
      </span>
      <Problem error={trade.error} />
      <DataTable table={holdings} label="Your holdings" rowTestId="holding" empty="No holdings." />
      <DataTable table={trades} label="Your trades" rowTestId="trade" empty="No trades yet." />
      <DataTable table={listed} label="Listed companies" rowTestId="listed-company" />
    </Panel>
  );
}

function FamilyOfficePanel({ saveId, inv }: { saveId: string; inv: Investments }) {
  const form = useFormFamilyOffice(saveId);
  const move = useMoveFamilyOffice(saveId);
  const mandate = useSetOfficeMandate(saveId);
  const [choice, setChoice] = useState('balanced');
  const [dollars, setDollars] = useState<number | string>('');
  const office = inv.family_office;
  const f = inv.family_office_form;
  if (!office) {
    return (
      <Panel title="Family office" style={{ flex: '1 1 280px' }} testId="family-office-panel">
        <Row label="Wealth outside your company" value={formatMoneyWhole(f.wealth_cents)} />
        <Row label="Needed to form one" value={formatMoneyWhole(f.min_cents)} />
        <SegmentedControl
          value={choice}
          onChange={setChoice}
          data={f.mandates.map((m) => ({ value: m, label: humanize(m) }))}
          data-testid="office-mandate"
        />
        <Button
          disabled={!f.can_form}
          loading={form.isPending}
          onClick={() => form.mutate({ mandate: choice as 'balanced' })}
          data-testid="form-office"
        >
          Form a family office ({f.energy} energy)
        </Button>
        <Problem error={form.error} />
      </Panel>
    );
  }
  return (
    <Panel title="Family office" style={{ flex: '1 1 280px' }} testId="family-office-panel">
      <Row label="Balance" value={formatMoneyWhole(office.balance_cents)} testId="office-balance" />
      <Row
        label={`Manager: ${office.manager_name}`}
        value={`finance ${office.manager_skill_low}–${office.manager_skill_high}`}
      />
      {office.trailing_year_pct !== null && (
        <Row
          label="Last 12 months (index)"
          value={`${office.trailing_year_pct}% (${office.index_year_pct ?? '–'}%)`}
        />
      )}
      <SegmentedControl
        value={office.mandate}
        onChange={(m) => mandate.mutate({ mandate: m as 'balanced' })}
        data={f.mandates.map((m) => ({ value: m, label: humanize(m) }))}
        data-testid="office-mandate"
      />
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <NumberInput
          label="Move ($; negative takes it out)"
          value={dollars}
          onChange={setDollars}
          thousandSeparator=","
          data-testid="office-move-amount"
          style={{ flex: 1 }}
        />
        <Button
          disabled={!Number(dollars)}
          loading={move.isPending}
          onClick={() => move.mutate(Math.round(Number(dollars) * CENTS))}
          data-testid="office-move"
        >
          Move
        </Button>
      </div>
      <Problem error={move.error ?? mandate.error} />
    </Panel>
  );
}

/** "Invest" (an open round) and "Buy shares" (a listed company) on a Rival page (37.2-37.3),
 * with the founder's own money. Nothing shows when neither applies. */
export function PersonalInvestPanel({ saveId, companyId }: { saveId: string; companyId: number }) {
  const q = useInvestments(saveId);
  const join = useJoinRound(saveId);
  const trade = useTradeShares(saveId);
  const [dollars, setDollars] = useState<number | string>('');
  const [count, setCount] = useState<number | string>('');
  const inv = q.data;
  if (!inv) return null;
  const round = inv.open_rounds.find((r) => r.company_id === companyId);
  const listed = inv.listed.find((c) => c.company_id === companyId);
  const stake = inv.stakes.find((s) => s.company_id === companyId && s.status === 'open');
  const held = inv.holdings.find((h) => h.company_id === companyId);
  if (!round && !listed && !stake && !held) return null;
  return (
    <Panel title="Your own money" testId="personal-invest">
      <Row label="Personal cash" value={formatMoneyWhole(inv.personal_cash_cents)} />
      {stake && (
        <Row label="Your stake" value={`${stake.stake_pct.toFixed(2)}%`} testId="my-stake" />
      )}
      {held && <Row label="Your shares" value={formatWhole(held.shares)} testId="my-shares" />}
      {round && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <NumberInput
            label={`Join its ${round.date_label} round ($, at most ${formatMoneyWhole(round.max_cents)})`}
            value={dollars}
            onChange={setDollars}
            min={1}
            thousandSeparator=","
            data-testid="invest-amount"
            style={{ flex: 1 }}
          />
          <Button
            disabled={!Number(dollars)}
            loading={join.isPending}
            onClick={() =>
              join.mutate({ company_id: companyId, cents: Math.round(Number(dollars) * CENTS) })
            }
            data-testid="invest"
          >
            Invest
          </Button>
        </div>
      )}
      {listed && listed.window_open && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <NumberInput
            label={`Shares at ${formatMoneyShort(listed.price_cents)}`}
            value={count}
            onChange={setCount}
            min={1}
            thousandSeparator=","
            data-testid="buy-shares-count"
            style={{ flex: 1 }}
          />
          <Button
            disabled={!Number(count)}
            loading={trade.isPending}
            onClick={() =>
              trade.mutate({ company_id: companyId, side: 'buy', shares: Number(count) })
            }
            data-testid="buy-shares"
          >
            Buy shares
          </Button>
        </div>
      )}
      {listed?.sensitive && (
        <Badge color="orange" size="sm">
          A trade now would be in a sensitive window
        </Badge>
      )}
      <Problem error={join.error ?? trade.error} />
    </Panel>
  );
}
