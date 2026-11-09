// The founder's life on their profile (M24, formulas.md 32): Personal (the founder's own book,
// apart from the company's, and selling shares once listed), Foundation (create, give, grants
// and their effects), Persona (the four traits with their causes) and Government affairs
// (influence by region, lobbying spend, exposure as a word), and M26's Investments (37).
// Values come from the API only.
import {
  Alert,
  Button,
  NativeSelect,
  NumberInput,
  SegmentedControl,
  TextInput,
} from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import {
  useCreateFoundation,
  useFounder,
  useGive,
  useSellShares,
  useSetLobbying,
  type Founder,
  type InfluenceRow,
} from '../hooks/founder';
import { formatMoneyWhole, formatWhole, humanize } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { InvestmentsTab } from './InvestmentsTab';
import { Panel } from './ScreenState';
import { Term } from './Term';

type Tab = 'personal' | 'investments' | 'foundation' | 'persona' | 'government';
const TABS: { value: Tab; label: string }[] = [
  { value: 'personal', label: 'Personal' },
  { value: 'investments', label: 'Investments' },
  { value: 'foundation', label: 'Foundation' },
  { value: 'persona', label: 'Persona' },
  { value: 'government', label: 'Government affairs' },
];
const CENTS = 100;

function signed(n: number): string {
  return `${n > 0 ? '+' : ''}${Math.round(n * 10) / 10}`;
}

export function FounderPanels({ saveId }: { saveId: string }) {
  const founder = useFounder(saveId);
  const [tab, setTab] = useState<Tab>('personal');
  if (!founder.data) return null;
  return (
    <section
      className="tst-panel"
      aria-label="The founder's life"
      style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      data-testid="founder-life"
    >
      <SegmentedControl
        value={tab}
        onChange={(v) => setTab(v as Tab)}
        data={TABS}
        data-testid="founder-tabs"
      />
      {tab === 'personal' && <PersonalTab saveId={saveId} f={founder.data} />}
      {tab === 'investments' && <InvestmentsTab saveId={saveId} />}
      {tab === 'foundation' && <FoundationTab saveId={saveId} f={founder.data} />}
      {tab === 'persona' && <PersonaTab f={founder.data} />}
      {tab === 'government' && <GovernmentTab saveId={saveId} f={founder.data} />}
    </section>
  );
}

function Line({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span className="tst-muted">{label}</span>
      <span className="tst-num" data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

type Entry = Founder['personal']['entries'][number];
const entryHelper = createColumnHelper<GameTableFeatures, Entry>();

function PersonalTab({ saveId, f }: { saveId: string; f: Founder }) {
  const p = f.personal;
  const sell = useSellShares(saveId);
  const [shares, setShares] = useState<number | string>('');
  const columns = useMemo(
    () =>
      entryHelper.columns([
        entryHelper.accessor('date_label', {
          id: 'founder.entry_month',
          header: 'Month',
          enableSorting: false,
        }),
        entryHelper.accessor('memo', {
          id: 'founder.entry_memo',
          header: 'Entry',
          enableSorting: false,
        }),
        entryHelper.accessor('amount_cents', {
          id: 'founder.entry_amount',
          header: 'Personal cash',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: p.entries,
    getRowId: (_e, i) => String(i),
  });
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
      <Panel title="Personal account" style={{ flex: '1 1 260px' }} testId="personal-panel">
        <span className="tst-muted" style={{ fontSize: 12 }}>
          <Term term="founder.personal">Your own money</Term>, never the company&apos;s.
        </span>
        <Line label="Personal cash" value={formatMoneyWhole(p.cash_cents)} testId="personal-cash" />
        <Line label="Foundation endowment" value={formatMoneyWhole(p.endowment_cents)} />
        {Object.entries(p.income).map(([source, cents]) => (
          <Line
            key={source}
            label={`Income: ${humanize(source)}`}
            value={formatMoneyWhole(cents)}
          />
        ))}
        <Line label="Given to the foundation" value={formatMoneyWhole(p.gifts_cents)} />
        <Line label="Shares held" value={formatWhole(p.stake_shares)} testId="personal-shares" />
        {p.stake_value_cents !== null && (
          <Line label="Worth at today's price" value={formatMoneyWhole(p.stake_value_cents)} />
        )}
        {p.can_sell && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <NumberInput
              label="Sell shares"
              value={shares}
              onChange={setShares}
              min={1}
              max={p.stake_shares}
              thousandSeparator=","
              data-testid="sell-shares-input"
              style={{ flex: 1 }}
            />
            <Button
              onClick={() => sell.mutate(Number(shares))}
              disabled={!Number(shares)}
              loading={sell.isPending}
              data-testid="sell-shares"
            >
              Sell
            </Button>
          </div>
        )}
        {sell.error && (
          <Alert color="orange" role="alert">
            {sell.error.message}
          </Alert>
        )}
      </Panel>
      <Panel title="Entries" style={{ flex: '2 1 380px', minWidth: 0 }}>
        <DataTable
          table={table}
          label="Personal entries"
          rowTestId="personal-entry"
          empty="Nothing in your personal account yet."
        />
      </Panel>
    </div>
  );
}

function FoundationTab({ saveId, f }: { saveId: string; f: Founder }) {
  const create = useCreateFoundation(saveId);
  const give = useGive(saveId);
  const [cause, setCause] = useState(f.foundation_form.causes[0] ?? 'education');
  const [name, setName] = useState('');
  const [amount, setAmount] = useState<number | string>('');
  const fd = f.foundation;
  const form = f.foundation_form;
  const error = create.error ?? give.error;
  return (
    <Panel title="Foundation" testId="foundation-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="founder.foundation">Your foundation</Term> grants 5% of its endowment each
        December.
      </span>
      {fd === null ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
          <NativeSelect
            label="Cause"
            value={cause}
            onChange={(e) => setCause(e.currentTarget.value)}
            data={form.causes.map((c) => ({ value: c, label: humanize(c) }))}
            data-testid="foundation-cause"
          />
          <TextInput
            label="Name"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            placeholder="Optional"
          />
          <Button
            onClick={() => create.mutate({ cause, name })}
            disabled={!form.can_create}
            loading={create.isPending}
            title={
              form.can_create
                ? undefined
                : `Needs ${formatMoneyWhole(form.min_cents)} of personal cash`
            }
            data-testid="foundation-create"
          >
            Create · {form.energy} energy
          </Button>
        </div>
      ) : (
        <>
          <strong data-testid="foundation-name">{fd.name}</strong>
          <Line label="Cause" value={fd.city ? `${fd.cause_label}, ${fd.city}` : fd.cause_label} />
          <Line label="Founded" value={fd.created_label} />
          <Line
            label="Endowment"
            value={formatMoneyWhole(fd.endowment_cents)}
            testId="foundation-endowment"
          />
          <Line
            label="Lifetime grants"
            value={formatMoneyWhole(fd.grants_cents)}
            testId="foundation-grants"
          />
          {fd.last_grant_label && (
            <Line
              label={`Last grants (${fd.last_grant_label})`}
              value={formatMoneyWhole(fd.last_grant_cents)}
            />
          )}
          {fd.effect && (
            <span style={{ fontSize: 13 }} data-testid="foundation-effect">
              Running: {fd.effect} until {fd.effect_until_label}.
            </span>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <NumberInput
              label="Give (dollars)"
              value={amount}
              onChange={setAmount}
              min={1}
              thousandSeparator=","
              data-testid="foundation-gift-input"
              style={{ flex: 1 }}
            />
            <Button
              onClick={() => give.mutate(Math.round(Number(amount) * CENTS))}
              disabled={!Number(amount)}
              loading={give.isPending}
              data-testid="foundation-give"
            >
              Give
            </Button>
          </div>
        </>
      )}
      {error && (
        <Alert color="orange" role="alert">
          {error.message}
        </Alert>
      )}
    </Panel>
  );
}

function PersonaTab({ f }: { f: Founder }) {
  const p = f.persona;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
      <Panel title="Persona" style={{ flex: '1 1 300px' }} testId="persona-panel">
        <span className="tst-muted" style={{ fontSize: 12 }}>
          <Term term="founder.persona">How the public sees you</Term>. At {p.effect_at} or more a
          trait has effects.
        </span>
        {p.traits.map((t) => (
          <div key={t.key} data-testid={`trait-${t.key}`} data-strong={t.strong}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <strong>{t.label}</strong>
              <span className="tst-num">{Math.round(t.value)}</span>
            </div>
            <div
              role="meter"
              aria-label={t.label}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={t.value}
              style={{ height: 6, background: 'var(--tst-track)', borderRadius: 3 }}
            >
              <div
                style={{
                  width: `${Math.min(100, t.value)}%`,
                  height: 6,
                  borderRadius: 3,
                  background: t.strong ? 'var(--tst-warn)' : 'var(--tst-accent)',
                }}
              />
            </div>
            {t.strong && (
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {t.effects}
              </span>
            )}
          </div>
        ))}
      </Panel>
      <Panel title="What shaped it" style={{ flex: '1 1 300px' }}>
        {p.causes.length === 0 && <span className="tst-muted">Nothing yet.</span>}
        {p.causes.map((c, i) => (
          <span key={i} style={{ fontSize: 13 }} data-testid="trait-cause">
            {c.date_label}: {humanize(c.trait)} {signed(c.change)}, {c.cause}
          </span>
        ))}
      </Panel>
    </div>
  );
}

const govHelper = createColumnHelper<GameTableFeatures, InfluenceRow>();

function GovernmentTab({ saveId, f }: { saveId: string; f: Founder }) {
  const g = f.government;
  const lobby = useSetLobbying(saveId);
  const [region, setRegion] = useState(g.region_options[0]?.key ?? 'north_america');
  const [monthly, setMonthly] = useState<number | string>('');
  const columns = useMemo(
    () =>
      govHelper.columns([
        govHelper.accessor('region_label', {
          id: 'founder.region',
          header: 'Region',
          sortFn: 'alphanumeric',
        }),
        govHelper.accessor('influence', {
          id: 'founder.influence',
          header: 'Influence',
          sortFn: 'basic',
          cell: ({ getValue }) => (
            <span className="tst-num" data-testid="influence-value">
              {getValue().toFixed(1)}
            </span>
          ),
        }),
        govHelper.accessor('monthly_cents', {
          id: 'founder.monthly',
          header: 'Lobbying a month',
          sortFn: 'basic',
          cell: ({ getValue }) => <span className="tst-num">{formatMoneyWhole(getValue())}</span>,
        }),
        govHelper.accessor('exposure', {
          id: 'founder.exposure',
          header: 'Exposure',
          sortFn: 'alphanumeric',
          cell: ({ getValue }) => <span data-testid="exposure-value">{getValue()}</span>,
        }),
        govHelper.accessor('scandals', {
          id: 'founder.scandals',
          header: 'Scandals',
          sortFn: 'basic',
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: g.regions,
    getRowId: (r) => r.region,
  });
  return (
    <Panel title="Government affairs" testId="government-panel">
      <span className="tst-muted" style={{ fontSize: 12 }}>
        <Term term="founder.influence">Influence</Term> lowers antitrust blocks there;{' '}
        <Term term="founder.exposure">exposure</Term> is the risk of a scandal.
      </span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
        <NativeSelect
          label="Region"
          value={region}
          onChange={(e) => setRegion(e.currentTarget.value)}
          data={g.region_options.map((r) => ({ value: r.key, label: r.label }))}
          data-testid="lobby-region"
        />
        <NumberInput
          label="Lobbying a month (dollars)"
          value={monthly}
          onChange={setMonthly}
          min={0}
          max={g.max_monthly_cents / CENTS}
          thousandSeparator=","
          data-testid="lobby-monthly"
        />
        <Button
          onClick={() => lobby.mutate({ region, monthly_dollars: Number(monthly) || 0 })}
          loading={lobby.isPending}
          data-testid="lobby-set"
        >
          Set · {g.energy} energy
        </Button>
      </div>
      {lobby.error && (
        <Alert color="orange" role="alert">
          {lobby.error.message}
        </Alert>
      )}
      <DataTable
        table={table}
        label="Influence by region"
        rowTestId="influence-row"
        empty="No lobbying yet."
      />
      {g.scandals.map((s) => (
        <span key={`${s.region}-${s.turn}`} style={{ fontSize: 13 }} data-testid="scandal-row">
          {s.date_label}: a lobbying scandal in {s.region_label}
        </span>
      ))}
    </Panel>
  );
}

/** The legacy score with its parts (32.6), for Game over and the Hall of Fame. */
export function LegacyPanel({ legacy }: { legacy: Founder['legacy'] | null | undefined }) {
  if (!legacy) return null;
  return (
    <Panel title="Legacy" testId="legacy-panel">
      <span style={{ fontSize: 26, fontWeight: 700 }} className="tst-num" data-testid="legacy">
        <Term term="founder.legacy">{formatWhole(legacy.total)}</Term>
      </span>
      <Line
        label={`Best company score${legacy.best_company ? ` (${legacy.best_company})` : ''}`}
        value={formatWhole(legacy.best_score)}
      />
      <Line label="Giving" value={signed(legacy.giving)} />
      <Line label="Persona" value={signed(legacy.persona)} />
      <Line label="Lifetime grants" value={formatMoneyWhole(legacy.grants_cents)} />
      <Line label="Wealth" value={signed(legacy.wealth ?? 0)} />
      <Line label="Net worth" value={formatMoneyWhole(legacy.net_worth_cents ?? 0)} />
    </Panel>
  );
}
