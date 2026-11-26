// Financial services and currencies (M54, formulas.md 64): the Bank screen (balance sheet, net
// interest margin, deposit beta, capital ratio against its line, stress tests, uninsured share and
// run risk as a band), the Payments screen (volume by region, take rate, acceptance, fraud), the
// Insurance screen (premiums by line, combined ratio, float, solvency) and the Currency screen
// (exposure by region, forwards and their settlement dates, a what-if of a dollar move). No game
// values are computed here: figures are formatted.
import { Alert, Button, NumberInput, Select } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  useApplyCharter,
  useApplyInsuranceLicence,
  useBankCapital,
  useBuyForward,
  useFinserv,
  useInsurerCapital,
  useLaunchNetwork,
  usePartnerBank,
  useSetBank,
  useSetHedgeProgramme,
  type Bank,
  type CurrencyRegion,
  type Finserv,
  type Hedge,
  type PaymentsRegion,
} from '../hooks/finserv';
import { formatMoney, formatMoneyShort } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

const paymentsHelper = createColumnHelper<GameTableFeatures, PaymentsRegion>();
const currencyHelper = createColumnHelper<GameTableFeatures, CurrencyRegion>();
const hedgeHelper = createColumnHelper<GameTableFeatures, Hedge>();

const pct = (x: number | null | undefined, digits = 1) =>
  x === null || x === undefined ? '—' : `${(x * 100).toFixed(digits)}%`;
const rate = (x: number) => `${x.toFixed(2)}%`;

function useScreen(title: string, body: (saveId: string, f: Finserv) => React.ReactNode) {
  const { saveId = '' } = useParams();
  const q = useFinserv(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title={`Could not load ${title}`} error={q.error} />;
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {q.data.month}
            {q.data.history ? ' · rivals follow their history to 2025' : ''}
          </span>
        }
      >
        {title}
      </ScreenTitle>
      {body(saveId, q.data)}
    </>
  );
}

function RegionPicker({
  regions,
  value,
  onChange,
  testId,
}: {
  regions: { region: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  testId: string;
}) {
  return (
    <Select
      size="xs"
      data={regions.map((r) => ({ value: r.region, label: r.label }))}
      value={value}
      onChange={(v) => onChange(v ?? value)}
      data-testid={testId}
      allowDeselect={false}
    />
  );
}

// --- Bank -----------------------------------------------------------------------------------

export function BankScreen() {
  return useScreen('Bank', (saveId, f) => <BankBody saveId={saveId} f={f} />);
}

function BankBody({ saveId, f }: { saveId: string; f: Finserv }) {
  const b = f.bank;
  const [region, setRegion] = useState(b.regions[0]?.region ?? 'north_america');
  const charter = useApplyCharter(saveId);
  const partner = usePartnerBank(saveId);
  const option = b.regions.find((r) => r.region === region);
  return (
    <>
      <Panel title="Start a bank" testId="bank-start">
        {!b.can_charter ? (
          <p className="tst-muted">
            A charter needs a Fintech or Banking line (make one from Products).
          </p>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
            <RegionPicker
              regions={b.regions}
              value={region}
              onChange={setRegion}
              testId="bank-region"
            />
            <Button
              size="compact-sm"
              disabled={charter.isPending}
              data-testid="bank-charter"
              onClick={() => charter.mutate({ region })}
            >
              Apply for a charter
            </Button>
            <Button
              size="compact-sm"
              variant="default"
              disabled={partner.isPending || !b.has_banking_line}
              data-testid="bank-partner"
              onClick={() => partner.mutate({ region })}
            >
              Use a partner bank
            </Button>
            <span className="tst-muted" style={{ fontSize: 13 }}>
              {option
                ? `${option.regulator}: about ${option.months} months${option.strict ? ' (strict)' : ''}`
                : ''}{' '}
              · opening capital {formatMoneyShort(b.charter_capital_cents)} and a fee of{' '}
              {formatMoneyShort(b.charter_fee_cents)} · a partner keeps{' '}
              {pct(1 - b.partner_share, 0)} of the interest
            </span>
          </div>
        )}
        {charter.error && <Alert color="red">{String(charter.error.message)}</Alert>}
        {partner.error && <Alert color="red">{String(partner.error.message)}</Alert>}
      </Panel>
      {b.banks.length === 0 ? (
        <Panel title="Your banks" testId="bank-none">
          <p className="tst-muted">No bank yet.</p>
        </Panel>
      ) : (
        b.banks.map((x) => <BankPanel key={x.id} saveId={saveId} bank={x} f={f} />)
      )}
      <Panel title="History" testId="bank-history">
        <ul style={{ margin: 0 }}>
          {b.charters.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Panel>
    </>
  );
}

function BankPanel({ saveId, bank, f }: { saveId: string; bank: Bank; f: Finserv }) {
  const set = useSetBank(saveId);
  const capital = useBankCapital(saveId);
  const [beta, setBeta] = useState<string | number>(bank.beta);
  const [ltd, setLtd] = useState<string | number>(bank.loan_to_deposit * 100);
  const [sec, setSec] = useState<string | number>(bank.securities_share * 100);
  const [dur, setDur] = useState<string | number>(bank.duration);
  const [amount, setAmount] = useState<string | number>(1_000_000);
  const live = bank.status === 'chartered';
  return (
    <Panel title={`${bank.label} · ${bank.status}`} testId={`bank-${bank.region}`}>
      <p style={{ margin: 0 }} data-testid={`bank-status-${bank.region}`}>
        {bank.regulator}
        {bank.charter_month ? ` decides in ${bank.charter_month}` : ''}
        {bank.restricted ? ' · restricted by its regulator' : ''}
        {bank.dividends_frozen_until ? ` · dividends frozen to ${bank.dividends_frozen_until}` : ''}
      </p>
      <table className="tst-kv" style={{ marginTop: 6 }}>
        <tbody>
          <tr>
            <td>Deposits</td>
            <td data-testid={`bank-deposits-${bank.region}`}>
              {formatMoney(bank.deposits_cents)} (consumer{' '}
              {formatMoneyShort(bank.consumer_deposits_cents)}, business{' '}
              {formatMoneyShort(bank.business_deposits_cents)})
            </td>
          </tr>
          <tr>
            <td>Loans</td>
            <td>
              {formatMoney(bank.loans_cents)}:{' '}
              {bank.loans
                .filter((l) => l.balance_cents > 0)
                .map(
                  (l) => `${l.label} ${formatMoneyShort(l.balance_cents)} at ${rate(l.yield_rate)}`,
                )
                .join(', ') || 'none'}
            </td>
          </tr>
          <tr>
            <td>Securities</td>
            <td>
              {formatMoney(bank.securities_cents)} at cost, worth{' '}
              {formatMoney(bank.securities_value_cents)}
              {bank.unrealised_loss_cents > 0
                ? ` (unrealised loss ${formatMoneyShort(bank.unrealised_loss_cents)})`
                : ''}
            </td>
          </tr>
          <tr>
            <td>Reserves</td>
            <td>{formatMoney(bank.reserves_cents)}</td>
          </tr>
          <tr>
            <td>
              <Term term="finserv.cet1">CET1</Term> /{' '}
              <Term term="finserv.rwa">risk-weighted assets</Term>
            </td>
            <td data-testid={`bank-ratio-${bank.region}`}>
              {formatMoneyShort(bank.cet1_cents)} / {formatMoneyShort(bank.rwa_cents)} ={' '}
              {pct(bank.ratio)} against a line of {pct(bank.requirement)} (minimum{' '}
              {pct(bank.minimum)})
            </td>
          </tr>
          <tr>
            <td>
              <Term term="finserv.nim">Net interest margin</Term>
            </td>
            <td data-testid={`bank-nim-${bank.region}`}>
              {pct(bank.nim, 2)} over the last year{' '}
              {live && (
                <Explain metric="bank_profit" entity={String(bank.id)} label="bank profit" />
              )}
            </td>
          </tr>
          <tr>
            <td>
              <Term term="finserv.deposit_beta">Deposit beta</Term>
            </td>
            <td data-testid={`bank-beta-${bank.region}`}>
              {bank.beta.toFixed(2)}: you pay {rate(bank.deposit_rate)} on deposits; the market{' '}
              {rate(bank.market_deposit_rate)}; policy rate {rate(bank.policy_rate)}
            </td>
          </tr>
          <tr>
            <td>
              <Term term="finserv.uninsured">Uninsured deposits</Term>
            </td>
            <td>
              {pct(bank.uninsured_share, 0)} (insured to{' '}
              {formatMoneyShort(bank.insured_limit_cents)} a depositor) ·{' '}
              <Term term="finserv.run_risk">run risk</Term>{' '}
              <span data-testid={`bank-run-risk-${bank.region}`}>{bank.run_risk}</span>
            </td>
          </tr>
        </tbody>
      </table>
      {bank.stress.length > 0 && (
        <p data-testid={`bank-stress-${bank.region}`}>
          <Term term="finserv.stress_test">Stress tests</Term>:{' '}
          {bank.stress
            .map((s) => `${s.month} ${s.passed ? 'passed' : 'failed'} (${pct(s.ratio_after)})`)
            .join(', ')}
        </p>
      )}
      {bank.runs.length > 0 && (
        <Alert color="red" data-testid={`bank-runs-${bank.region}`}>
          {bank.runs
            .map(
              (r) =>
                `${r.month}: ${formatMoneyShort(r.withdrawn_cents)} withdrawn, loss ${formatMoneyShort(r.realised_loss_cents)}${r.failed ? ', failed' : ''}`,
            )
            .join('; ')}
        </Alert>
      )}
      {bank.months.length > 0 && (
        <p
          className="tst-muted"
          style={{ fontSize: 13 }}
          data-testid={`bank-months-${bank.region}`}
        >
          Last months:{' '}
          {bank.months
            .slice(-6)
            .map((m) => `${m.month} NIM ${pct(m.nim, 2)} at ${rate(m.policy_rate)}`)
            .join(' · ')}
        </p>
      )}
      {bank.status !== 'failed' && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'end', flexWrap: 'wrap' }}>
          <NumberInput
            label="Deposit beta"
            size="xs"
            step={0.05}
            min={f.bank.beta_range[0]}
            max={f.bank.beta_range[1]}
            value={beta}
            onChange={setBeta}
            data-testid={`bank-set-beta-${bank.region}`}
          />
          <NumberInput
            label="Loans, % of deposits"
            size="xs"
            min={0}
            max={100}
            value={ltd}
            onChange={setLtd}
          />
          <NumberInput
            label="Securities, %"
            size="xs"
            min={0}
            max={100}
            value={sec}
            onChange={setSec}
          />
          <NumberInput
            label="Duration (years)"
            size="xs"
            min={f.bank.duration_range[0]}
            max={f.bank.duration_range[1]}
            value={dur}
            onChange={setDur}
          />
          <Button
            size="compact-sm"
            disabled={set.isPending}
            data-testid={`bank-save-${bank.region}`}
            onClick={() =>
              set.mutate({
                bankId: bank.id,
                body: {
                  beta: Number(beta),
                  loan_to_deposit: Number(ltd) / 100,
                  securities_share: Number(sec) / 100,
                  duration: Number(dur),
                },
              })
            }
          >
            Set
          </Button>
          {(live || bank.status === 'applying') && (
            <>
              <NumberInput label="Capital ($)" size="xs" value={amount} onChange={setAmount} />
              <Button
                size="compact-sm"
                variant="default"
                disabled={capital.isPending}
                onClick={() =>
                  capital.mutate({
                    bankId: bank.id,
                    body: { amount_cents: Math.round(Number(amount) * 100) },
                  })
                }
              >
                Move capital
              </Button>
            </>
          )}
        </div>
      )}
      {set.error && <Alert color="red">{String(set.error.message)}</Alert>}
      {capital.error && <Alert color="red">{String(capital.error.message)}</Alert>}
    </Panel>
  );
}

// --- Payments -------------------------------------------------------------------------------

export function PaymentsScreen() {
  return useScreen('Payments', (saveId, f) => <PaymentsBody saveId={saveId} f={f} />);
}

function PaymentsBody({ saveId, f }: { saveId: string; f: Finserv }) {
  const p = f.payments;
  const launch = useLaunchNetwork(saveId);
  const [region, setRegion] = useState('north_america');
  const columns = useMemo(
    () =>
      paymentsHelper.columns([
        paymentsHelper.accessor('label', {
          header: 'Region',
          meta: { term: 'finserv.interchange' },
        }),
        paymentsHelper.accessor('acquired_cents', {
          header: 'Volume acquired',
          meta: { term: 'finserv.take_rate' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        paymentsHelper.accessor('take_rate', {
          header: 'Take rate',
          meta: { term: 'finserv.take_rate' },
          cell: (c) => pct(c.getValue(), 2),
        }),
        paymentsHelper.accessor('interchange_bp', {
          header: 'Interchange',
          meta: { term: 'finserv.interchange' },
          cell: (c) => `${c.getValue().toFixed(0)} bp`,
        }),
        paymentsHelper.accessor('fraud_cents', {
          header: 'Fraud',
          meta: { term: 'finserv.interchange' },
          cell: (c) => formatMoneyShort(c.getValue()),
        }),
        paymentsHelper.accessor('rails_share', {
          header: 'Rails',
          meta: { term: 'finserv.rails' },
          cell: (c) => pct(c.getValue(), 0),
        }),
        paymentsHelper.accessor((r) => Object.keys(r.networks).join(','), {
          id: 'networks',
          header: 'Networks',
          meta: { term: 'finserv.acceptance' },
          cell: (c) =>
            Object.entries(c.row.original.networks)
              .map(([n, s]) => `${n} ${pct(s, 0)}`)
              .join(', ') || '—',
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: p.regions });
  return (
    <>
      <Panel title="Volume by region" testId="payments-regions">
        <DataTable table={table} label="Payments by region" rowTestId="payments-region-row" />
      </Panel>
      <Panel title="Your card networks" testId="payments-networks">
        {p.networks.length === 0 ? (
          <p className="tst-muted">No network yet.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {p.networks.map((n) => (
              <li key={n.id} data-testid={`network-${n.region}`}>
                {n.label} since {n.since}: {pct(n.share)} of card programmes,{' '}
                <Term term="finserv.acceptance">acceptance</Term> {pct(n.acceptance, 0)}, volume{' '}
                {formatMoneyShort(n.volume_cents)} this month
              </li>
            ))}
          </ul>
        )}
        {p.can_launch ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'end', marginTop: 6 }}>
            <RegionPicker
              regions={f.bank.regions}
              value={region}
              onChange={setRegion}
              testId="network-region"
            />
            <Button
              size="compact-sm"
              disabled={launch.isPending}
              data-testid="network-launch"
              onClick={() => launch.mutate({ region })}
            >
              Launch a network ({formatMoneyShort(p.network_cost_cents)})
            </Button>
          </div>
        ) : (
          <p className="tst-muted">A network needs a Payments line (make one from Products).</p>
        )}
        {launch.error && <Alert color="red">{String(launch.error.message)}</Alert>}
      </Panel>
    </>
  );
}

// --- Insurance ------------------------------------------------------------------------------

export function InsuranceScreen() {
  return useScreen('Insurance', (saveId, f) => <InsuranceBody saveId={saveId} f={f} />);
}

function InsuranceBody({ saveId, f }: { saveId: string; f: Finserv }) {
  const ins = f.insurance;
  const apply = useApplyInsuranceLicence(saveId);
  const capital = useInsurerCapital(saveId);
  const [region, setRegion] = useState('north_america');
  const [amount, setAmount] = useState<string | number>(1_000_000);
  const last = ins.months[ins.months.length - 1];
  return (
    <>
      <Panel title="Your insurer" testId="insurance-insurer">
        {!ins.has_insurer ? (
          <p className="tst-muted">No insurer yet: apply for a licence below.</p>
        ) : (
          <>
            <p style={{ margin: 0 }} data-testid="insurance-solvency">
              <Term term="finserv.solvency">Own funds</Term> {formatMoney(ins.own_funds_cents)}{' '}
              against {formatMoney(ins.required_cents)} required:{' '}
              {ins.solvent ? 'solvent' : 'cannot write new business'}
            </p>
            <p style={{ margin: 0 }} data-testid="insurance-float">
              <Term term="finserv.float">Float</Term> {formatMoney(ins.float_cents)} · invested{' '}
              {formatMoney(ins.investments_cents)}
              {last
                ? ` · investment income ${formatMoneyShort(last.investment_income_cents)} last month`
                : ''}
            </p>
            <p style={{ margin: 0 }} data-testid="insurance-premiums">
              Premiums this month:{' '}
              {Object.entries(ins.premiums_by_line)
                .map(([line, v]) => `${line} ${formatMoneyShort(v)}`)
                .join(', ') || 'none'}
              {last ? (
                <>
                  {' '}
                  · <Term term="finserv.combined_ratio">combined ratio</Term>{' '}
                  {pct(last.combined_ratio)}
                </>
              ) : null}
            </p>
            <ul style={{ margin: 0 }}>
              {ins.licences.map((l) => (
                <li key={l.region}>
                  {l.label}: {l.status}
                  {l.status === 'applying' && l.decided ? ` (decision ${l.decided})` : ''}
                </li>
              ))}
            </ul>
          </>
        )}
        {ins.can_apply ? (
          <div
            style={{ display: 'flex', gap: 8, alignItems: 'end', marginTop: 6, flexWrap: 'wrap' }}
          >
            <RegionPicker
              regions={ins.regions}
              value={region}
              onChange={setRegion}
              testId="insurance-region"
            />
            <Button
              size="compact-sm"
              disabled={apply.isPending}
              data-testid="insurance-apply"
              onClick={() => apply.mutate({ region })}
            >
              Apply for a licence
            </Button>
            {ins.has_insurer && (
              <>
                <NumberInput label="Capital ($)" size="xs" value={amount} onChange={setAmount} />
                <Button
                  size="compact-sm"
                  variant="default"
                  disabled={capital.isPending}
                  onClick={() => capital.mutate({ amount_cents: Math.round(Number(amount) * 100) })}
                >
                  Move capital
                </Button>
              </>
            )}
          </div>
        ) : (
          <p className="tst-muted">A licence needs an Insurance line (make one from Products).</p>
        )}
        {apply.error && <Alert color="red">{String(apply.error.message)}</Alert>}
        {capital.error && <Alert color="red">{String(capital.error.message)}</Alert>}
      </Panel>
      <Panel title="Catastrophes" testId="insurance-cats">
        {ins.catastrophes.length === 0 ? (
          <p className="tst-muted">None since 2026.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {ins.catastrophes.map((c) => (
              <li key={`${c.month}-${c.region}`}>
                {c.month}: {c.label}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}

// --- Currency -------------------------------------------------------------------------------

export function CurrencyScreen() {
  return useScreen('Currency', (saveId, f) => <CurrencyBody saveId={saveId} f={f} />);
}

function CurrencyBody({ saveId, f }: { saveId: string; f: Finserv }) {
  const c = f.currency;
  const buy = useBuyForward(saveId);
  const programme = useSetHedgeProgramme(saveId);
  const [region, setRegion] = useState(c.regions[0]?.region ?? 'europe');
  const [notional, setNotional] = useState<string | number>(100_000);
  const [months, setMonths] = useState<string | number>(6);
  const [share, setShare] = useState<string | number>(c.programme ? c.programme.share * 100 : 80);
  const columns = useMemo(
    () =>
      currencyHelper.columns([
        currencyHelper.accessor('label', { header: 'Region', meta: { term: 'fx.index' } }),
        currencyHelper.accessor('index', {
          header: 'Index',
          meta: { term: 'fx.index' },
          cell: (x) => `${x.getValue().toFixed(3)} (${x.row.original.currency})`,
        }),
        currencyHelper.accessor('change_12m', {
          header: '12 months',
          meta: { term: 'fx.index' },
          cell: (x) => pct(x.getValue()),
        }),
        currencyHelper.accessor('revenue_cents', {
          header: 'Revenue',
          meta: { term: 'fx.translation' },
          cell: (x) => (
            <span>
              {formatMoneyShort(x.getValue())} (
              {formatMoneyShort(x.row.original.untranslated_revenue_cents)} as set){' '}
              <Explain metric="fx_result" entity={x.row.original.region} label="currency result" />
            </span>
          ),
        }),
        currencyHelper.accessor('net_cents', {
          header: 'Net a month',
          meta: { term: 'fx.exposure' },
          cell: (x) => formatMoneyShort(x.getValue()),
        }),
        currencyHelper.accessor('exposure_cents', {
          header: 'Exposure, 12 months',
          meta: { term: 'fx.exposure' },
          cell: (x) => formatMoneyShort(x.getValue()),
        }),
        currencyHelper.accessor('unhedged_share', {
          header: 'Unhedged',
          meta: { term: 'fx.forward' },
          cell: (x) => (
            <span data-testid={`fx-unhedged-${x.row.original.region}`}>{pct(x.getValue(), 0)}</span>
          ),
        }),
        currencyHelper.accessor('what_if_cents', {
          header: `Dollar +${(c.what_if_move * 100).toFixed(0)}%`,
          meta: { term: 'fx.translation' },
          cell: (x) => formatMoneyShort(x.getValue()),
        }),
      ]),
    [c.what_if_move],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: c.regions });
  const hedgeColumns = useMemo(
    () =>
      hedgeHelper.columns([
        hedgeHelper.accessor('label', { header: 'Region', meta: { term: 'fx.forward' } }),
        hedgeHelper.accessor('notional_cents', {
          header: 'Notional',
          meta: { term: 'fx.forward' },
          cell: (x) => formatMoneyShort(x.getValue()),
        }),
        hedgeHelper.accessor('settles', { header: 'Settles', meta: { term: 'fx.forward' } }),
        hedgeHelper.accessor('forward_index', {
          header: 'Forward',
          meta: { term: 'fx.forward' },
          cell: (x) => `${x.getValue().toFixed(4)} (spot ${x.row.original.spot_index.toFixed(4)})`,
        }),
        hedgeHelper.accessor('value_cents', {
          header: 'Value',
          meta: { term: 'fx.forward' },
          cell: (x) =>
            x.row.original.status === 'settled'
              ? `settled ${formatMoneyShort(x.row.original.settled_cents)}`
              : formatMoneyShort(x.getValue()),
        }),
      ]),
    [],
  );
  const hedgeTable = useTable({
    features: gameTableFeatures,
    columns: hedgeColumns,
    data: c.hedges,
  });
  return (
    <>
      <Panel title="Exposure by region" testId="currency-regions">
        <p className="tst-muted" style={{ fontSize: 13, marginTop: 0 }}>
          {pct(c.foreign_share, 0)} of revenue is earned abroad ·{' '}
          <Term term="fx.translation">translated, not converted</Term> · currency gains less losses
          settled in the last year {formatMoneyShort(c.fx_result_12m_cents)}
        </p>
        <DataTable table={table} label="Currency exposure" rowTestId="currency-region-row" />
      </Panel>
      <Panel title="Forwards" testId="currency-hedges">
        <div style={{ display: 'flex', gap: 6, alignItems: 'end', flexWrap: 'wrap' }}>
          <RegionPicker
            regions={c.regions}
            value={region}
            onChange={setRegion}
            testId="forward-region"
          />
          <NumberInput
            label="Notional ($)"
            size="xs"
            min={1}
            value={notional}
            onChange={setNotional}
            data-testid="forward-notional"
          />
          <NumberInput
            label="Months"
            size="xs"
            min={c.term_range[0]}
            max={c.term_range[1]}
            value={months}
            onChange={setMonths}
            data-testid="forward-months"
          />
          <Button
            size="compact-sm"
            disabled={buy.isPending}
            data-testid="forward-buy"
            onClick={() =>
              buy.mutate({
                region,
                notional_cents: Math.round(Number(notional) * 100),
                months: Number(months),
              })
            }
          >
            Sell forward
          </Button>
        </div>
        {buy.error && <Alert color="red">{String(buy.error.message)}</Alert>}
        <div style={{ display: 'flex', gap: 6, alignItems: 'end', marginTop: 8 }}>
          <NumberInput
            label="Rolling hedge, % of net foreign revenue"
            size="xs"
            min={0}
            max={c.max_hedge_share * 100}
            value={share}
            onChange={setShare}
            data-testid="programme-share"
          />
          <Button
            size="compact-sm"
            variant="default"
            disabled={programme.isPending}
            data-testid="programme-set"
            onClick={() => programme.mutate({ share: Number(share) / 100, term_months: 12 })}
          >
            Set the programme (12 months ahead)
          </Button>
          <span data-testid="programme-status" className="tst-muted" style={{ fontSize: 13 }}>
            {c.programme
              ? `${pct(c.programme.share, 0)} hedged ${c.programme.term_months} months ahead${c.programme.by_cfo ? ' by your CFO' : ''}`
              : 'No programme'}
          </span>
        </div>
        {programme.error && <Alert color="red">{String(programme.error.message)}</Alert>}
        {c.hedges.length > 0 && (
          <DataTable table={hedgeTable} label="Forwards" rowTestId="hedge-row" />
        )}
      </Panel>
    </>
  );
}
