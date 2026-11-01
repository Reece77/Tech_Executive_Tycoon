import { Alert, Button, Modal, NumberInput, SegmentedControl } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { DataTable } from '../../components/DataTable';
import { MacroStrip } from '../../components/MacroStrip';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import {
  useLoanPreview,
  useLoans,
  useRepayLoan,
  useTakeLoan,
  type Loan,
  type LoanTerms,
  type Payment,
} from '../../hooks/api';
import { formatMoney, formatMoneyShort, formatMoneyWhole } from '../../lib/format';
import { formatRateBp, rangeSparkPoints } from '../../lib/finance';
import { gameTableFeatures, type GameTableFeatures } from '../../lib/table';

const PREVIEW_DEBOUNCE_MS = 250;
const helper = createColumnHelper<GameTableFeatures, Loan>();
const right = { display: 'block', textAlign: 'right' } as const;

/** Finance · Debt (M10, wireframes): the macro strip, loans with this month's payment and
 * covenant headroom, the balance over the term, and the Take a loan and Repay dialogs. */
export function DebtTab({ saveId }: { saveId: string }) {
  const loans = useLoans(saveId);
  const [taking, setTaking] = useState(false);
  const [repaying, setRepaying] = useState<Loan | null>(null);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('lender', {
          header: 'Lender',
          cell: (c) => (
            <span>
              {c.getValue()}
              <span className="tst-muted" style={{ display: 'block', fontSize: 12 }}>
                {c.row.original.instrument_label} · {c.row.original.status_label}
              </span>
            </span>
          ),
        }),
        helper.accessor('principal_cents', {
          header: () => <span style={right}>Borrowed</span>,
          cell: (c) => (
            <span className="tst-num" style={right}>
              {formatMoneyShort(c.getValue())}
            </span>
          ),
        }),
        helper.accessor('signed_label', { header: 'Signed' }),
        helper.accessor('warrant_shares', {
          header: () => <span style={right}>Warrants</span>,
          cell: (c) => (
            <span className="tst-num" style={right}>
              {c.getValue() ? c.getValue().toLocaleString('en-US') : '—'}
            </span>
          ),
        }),
        helper.accessor('balance_cents', {
          header: () => <span style={right}>Balance</span>,
          cell: (c) => (
            <span
              className="tst-num"
              style={right}
              data-testid={`loan-balance-${c.row.original.id}`}
            >
              {formatMoney(c.getValue())}
            </span>
          ),
        }),
        helper.accessor('rate_bp', {
          header: () => <span style={right}>Rate</span>,
          cell: (c) => (
            <span className="tst-num" style={right}>
              {formatRateBp(c.getValue())}
            </span>
          ),
        }),
        helper.accessor('next_payment', {
          header: 'This month',
          cell: (c) => {
            const p = c.getValue();
            if (!p) return <span className="tst-muted">—</span>;
            return (
              <span className="tst-num" style={{ fontSize: 13 }}>
                {formatMoney(p.interest_cents)} interest
                <span style={{ display: 'block' }}>{formatMoney(p.principal_cents)} principal</span>
              </span>
            );
          },
        }),
        helper.accessor('covenants', {
          header: 'Covenant',
          enableSorting: false,
          cell: (c) => {
            const loan = c.row.original;
            if (loan.covenants_resting_until_label)
              return (
                <span className="tst-muted" style={{ fontSize: 13 }}>
                  Waived until {loan.covenants_resting_until_label}
                </span>
              );
            return c.getValue().map((cv) => (
              <span
                key={cv.description}
                style={{
                  display: 'block',
                  fontSize: 13,
                  color: cv.holds ? undefined : 'var(--tst-warn)',
                }}
                data-testid="covenant"
                data-holds={cv.holds}
              >
                {cv.description} · headroom {formatMoneyShort(cv.headroom_cents)}
              </span>
            ));
          },
        }),
        helper.display({
          id: 'repay',
          header: '',
          cell: (c) =>
            c.row.original.status === 'active' ? (
              <Button
                size="xs"
                variant="default"
                onClick={() => setRepaying(c.row.original)}
                data-testid={`repay-${c.row.original.id}`}
              >
                Repay
              </Button>
            ) : null,
        }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    data: loans.data?.loans ?? [],
    columns,
    getRowId: (row) => String(row.id),
  });
  if (loans.isPending) return <Loading />;
  if (loans.error) return <LoadError title="Could not load the loans" error={loans.error} />;
  const data = loans.data;
  const active = data.loans.filter((l) => l.status === 'active');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} data-testid="debt-tab">
      <MacroStrip saveId={saveId} />
      <Panel
        title={`Loans · ${formatMoneyShort(data.debt_cents)} owed`}
        label="Loans"
        action={
          <Button h={44} onClick={() => setTaking(true)} data-testid="take-loan">
            Take a loan
          </Button>
        }
      >
        {data.loans.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0 }} data-testid="no-loans">
            No loans yet. Venture debt follows a priced round; a bank lends to a profitable
            scale-up.
          </p>
        ) : (
          <DataTable table={table} label="Loans" rowTestId="loan-row" />
        )}
      </Panel>
      {active.map((l) => (
        <BalanceChart key={l.id} loan={l} />
      ))}
      {taking && (
        <TakeLoanDialog saveId={saveId} offers={data.offers} onClose={() => setTaking(false)} />
      )}
      {repaying && (
        <RepayDialog
          saveId={saveId}
          loan={repaying}
          energy={data.repay_energy}
          onClose={() => setRepaying(null)}
        />
      )}
    </div>
  );
}

function BalanceChart({ loan }: { loan: Loan }) {
  const values = loan.schedule.map((p) => p.balance_after_cents);
  return (
    <Panel title={`${loan.lender}: balance over the term`} label={`${loan.lender} schedule`}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
        <svg
          viewBox="0 0 100 24"
          role="img"
          aria-label={`Balance from ${formatMoneyShort(loan.balance_cents)} to zero by ${loan.ends_label}`}
          style={{ width: 300, height: 72 }}
          data-testid={`loan-schedule-${loan.id}`}
        >
          <polyline
            points={rangeSparkPoints([loan.balance_cents, ...values])}
            fill="none"
            stroke="var(--tst-accent)"
            strokeWidth={1.5}
          />
        </svg>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {loan.schedule.length} payments left, the last in {loan.ends_label}.{' '}
          {loan.interest_only_months > 0 &&
            `Interest only for the first ${loan.interest_only_months} months, then equal principal. `}
          Paid so far: {formatMoneyShort(loan.interest_paid_cents)} interest,{' '}
          {formatMoneyShort(loan.principal_paid_cents)} principal.
        </span>
      </div>
    </Panel>
  );
}

function PaymentLine({ p }: { p: Payment | null | undefined }) {
  if (!p) return null;
  return (
    <span className="tst-num" data-testid="loan-first-payment">
      First month: {formatMoney(p.interest_cents)} interest + {formatMoney(p.principal_cents)}{' '}
      principal
    </span>
  );
}

function TakeLoanDialog({
  saveId,
  offers,
  onClose,
}: {
  saveId: string;
  offers: LoanTerms[];
  onClose: () => void;
}) {
  const [instrument, setInstrument] = useState(
    offers.find((o) => o.eligible)?.instrument ?? offers[0]?.instrument ?? 'venture_debt',
  );
  const offer = offers.find((o) => o.instrument === instrument) ?? offers[0];
  const [dollars, setDollars] = useState<number>(Math.floor((offer?.max_cents ?? 0) / 100));
  const terms = useMemo(() => ({ instrument, cents: dollars * 100 }), [instrument, dollars]);
  const [debounced] = useDebouncedValue(terms, PREVIEW_DEBOUNCE_MS);
  const preview = useLoanPreview(saveId, debounced.instrument, debounced.cents);
  const take = useTakeLoan(saveId);
  if (!offer) return null;
  const current = debounced === terms && !preview.isFetching;
  const problem = offer.problem ?? (current ? preview.data?.problem : null);
  return (
    <Modal opened onClose={onClose} title="Take a loan" size="lg">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="loan-dialog">
        <SegmentedControl
          value={instrument}
          onChange={(v) => {
            setInstrument(v);
            const o = offers.find((x) => x.instrument === v);
            setDollars(Math.floor((o?.max_cents ?? 0) / 100));
          }}
          data={offers.map((o) => ({ value: o.instrument, label: o.instrument_label }))}
          data-testid="loan-instrument"
        />
        <span data-testid="loan-eligibility">
          {offer.eligible
            ? `${offer.lender} will lend up to ${formatMoneyWhole(offer.max_cents)} at ${formatRateBp(offer.rate_bp)} a year over ${offer.term_months} months${offer.interest_only_months ? ` (${offer.interest_only_months} interest only)` : ''}.`
            : `Not offered now: ${offer.problem}.`}
          {offer.warrant_bp > 0 &&
            ` The lender takes warrants for ${(offer.warrant_bp / 100).toFixed(2)}% of the company.`}
        </span>
        <NumberInput
          label="Amount"
          prefix="$"
          thousandSeparator=","
          allowDecimal={false}
          allowNegative={false}
          value={dollars}
          onChange={(v) => setDollars(typeof v === 'number' ? v : 0)}
          classNames={{ input: 'tst-num' }}
          description={`${formatMoneyWhole(offer.min_cents)} to ${formatMoneyWhole(offer.max_cents)}`}
          inputWrapperOrder={['label', 'input', 'description', 'error']}
          disabled={!offer.eligible}
          data-testid="loan-amount"
        />
        <PaymentLine p={preview.data?.first_payment} />
        <span style={{ fontSize: 13 }}>Covenant: {offer.covenant}.</span>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          {offer.breach}
        </span>
        {problem && offer.eligible && (
          <Alert color="warn" data-testid="loan-problem">
            {problem}
          </Alert>
        )}
        {take.error && <Alert color="red">{take.error.message}</Alert>}
        <Button
          h={44}
          disabled={!offer.eligible || !current || Boolean(problem) || dollars <= 0}
          loading={take.isPending}
          onClick={() =>
            take.mutate({ instrument, amount_cents: dollars * 100 }, { onSuccess: onClose })
          }
          data-testid="sign-loan"
        >
          Sign · {offer.energy} energy
        </Button>
      </div>
    </Modal>
  );
}

function RepayDialog({
  saveId,
  loan,
  energy,
  onClose,
}: {
  saveId: string;
  loan: Loan;
  energy: number;
  onClose: () => void;
}) {
  const [dollars, setDollars] = useState<number>(loan.balance_cents / 100);
  const repay = useRepayLoan(saveId);
  const all = dollars * 100 >= loan.balance_cents;
  return (
    <Modal opened onClose={onClose} title={`Repay ${loan.lender}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} data-testid="repay-dialog">
        <span>
          Balance {formatMoney(loan.balance_cents)} at {formatRateBp(loan.rate_bp)}. Repaying early
          carries no fee.
        </span>
        <NumberInput
          label="Amount"
          prefix="$"
          thousandSeparator=","
          decimalScale={2}
          allowNegative={false}
          value={dollars}
          onChange={(v) => setDollars(typeof v === 'number' ? v : 0)}
          classNames={{ input: 'tst-num' }}
          data-testid="repay-amount"
        />
        {repay.error && <Alert color="red">{repay.error.message}</Alert>}
        <Button
          h={44}
          disabled={dollars <= 0}
          loading={repay.isPending}
          onClick={() =>
            repay.mutate(
              { loanId: loan.id, amountCents: all ? null : Math.round(dollars * 100) },
              { onSuccess: onClose },
            )
          }
          data-testid="confirm-repay"
        >
          {all ? 'Repay it all' : 'Repay'} · {energy} energy
        </Button>
      </div>
    </Modal>
  );
}
