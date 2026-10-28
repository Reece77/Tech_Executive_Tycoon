import { useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { LoadError, Loading, Panel } from '../../components/ScreenState';
import { StatementTable } from '../../components/StatementTable';
import {
  useOverview,
  useStatements,
  type Overview,
  type StatementPeriod,
  type StatementPeriodKind,
} from '../../hooks/api';
import { formatMoneyShort, formatMoneyWhole } from '../../lib/format';
import { formatThousands } from '../../lib/finance';

const PERIODS: { key: StatementPeriodKind; label: string }[] = [
  { key: 'month', label: 'Month' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'year', label: 'Year' },
];
const SHOWN = 12; // periods side by side (M4b brief)

function Row({
  label,
  cents,
  strong,
  last,
  testId,
}: {
  label: string;
  cents: number;
  strong?: boolean;
  last?: boolean;
  testId?: string;
}) {
  return (
    <div
      className="tst-row"
      style={{ fontWeight: strong ? 600 : undefined, borderBottom: last ? 0 : undefined }}
    >
      <span>{label}</span>
      <span
        className="tst-num"
        style={{ color: cents < 0 ? 'var(--tst-warn)' : undefined }}
        data-testid={testId}
      >
        {formatThousands(cents)}
      </span>
    </div>
  );
}

function BalanceSheet({ period: p }: { period: StatementPeriod }) {
  const b = p.balance_sheet;
  return (
    <Panel title={`Balance sheet · end of ${p.label}`} style={{ flex: '1 1 300px' }}>
      {b.assets.map((l) => (
        <Row key={l.account} label={l.label} cents={l.amount_cents} />
      ))}
      <Row label="Total assets" cents={b.total_assets_cents} strong testId="bs-assets" />
      {b.liabilities.length === 0 ? (
        <Row label="SAFEs outstanding" cents={0} />
      ) : (
        b.liabilities.map((l) => <Row key={l.account} label={l.label} cents={l.amount_cents} />)
      )}
      <Row label="Total liabilities" cents={b.total_liabilities_cents} strong />
      {b.paid_in_equity.map((l) => (
        <Row key={l.account} label={`${l.label} paid in`} cents={l.amount_cents} />
      ))}
      <Row label="Accumulated result" cents={b.accumulated_result_cents} />
      <Row
        label="Liabilities and equity"
        cents={b.total_liabilities_and_equity_cents}
        strong
        last
        testId="bs-total"
      />
    </Panel>
  );
}

function CashFlow({ period: p }: { period: StatementPeriod }) {
  const f = p.cash_flow;
  return (
    <Panel title={`Cash flow · ${p.label}`} style={{ flex: '1 1 300px' }}>
      <Row label="Operating" cents={f.operating_cents} />
      {f.investing_cents !== 0 && <Row label="Investing" cents={f.investing_cents} />}
      <Row label="Financing (SAFEs and rounds)" cents={f.financing_cents} />
      <Row label="Change in cash" cents={f.change_in_cash_cents} strong />
      <div className="tst-row" style={{ borderBottom: 0 }}>
        <span className="tst-muted">
          Burn this {p.first_turn === p.last_turn ? 'month' : 'period'}
        </span>
        <span className="tst-num" data-testid="cf-burn">
          {formatThousands(f.burn_cents)}
        </span>
      </div>
      <p className="tst-muted" style={{ margin: '8px 0 0', fontSize: 12 }}>
        Runway is cash divided by this month&apos;s projected net burn. It shows
        &ldquo;Profitable&rdquo; once revenue covers costs.
      </p>
    </Panel>
  );
}

/** Cash and monthly burn at each month end, on separate scales. */
export function CashBurnChart({ history }: { history: Overview['history'] }) {
  if (history.length === 0) {
    return (
      <p className="tst-muted" style={{ margin: 0, fontSize: 14 }}>
        No month has closed yet.
      </p>
    );
  }
  const last = history[history.length - 1];
  return (
    <div
      role="img"
      aria-label={`Cash and monthly burn, ${history[0].date_label} to ${last.date_label}; now ${formatMoneyWhole(last.cash_cents)} cash and ${formatMoneyWhole(last.monthly_burn_cents)} burn`}
    >
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={history} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--tst-rule)" vertical={false} />
          <XAxis
            dataKey="date_label"
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(label: string) => label.split(' ')[0]}
          />
          <YAxis
            yAxisId="cash"
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(v: number) => formatMoneyShort(v)}
            width={56}
          />
          <YAxis
            yAxisId="burn"
            orientation="right"
            stroke="var(--tst-muted)"
            fontSize={11}
            fontFamily="var(--tst-font-mono)"
            tickFormatter={(v: number) => formatMoneyShort(v)}
            width={52}
          />
          <Tooltip
            formatter={(v) => formatMoneyWhole(Number(v))}
            contentStyle={{
              background: 'var(--tst-panel)',
              border: '1px solid var(--tst-border)',
              fontFamily: 'var(--tst-font-mono)',
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            yAxisId="cash"
            type="linear"
            dataKey="cash_cents"
            name="Cash"
            stroke="var(--tst-accent)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="burn"
            type="linear"
            dataKey="monthly_burn_cents"
            name="Monthly burn (own scale)"
            stroke="var(--tst-warn)"
            strokeWidth={2}
            strokeDasharray="4 3"
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StatementsTab({ saveId }: { saveId: string }) {
  const [period, setPeriod] = useState<StatementPeriodKind>('month');
  const statements = useStatements(saveId, period);
  const overview = useOverview(saveId);
  if (statements.isPending || overview.isPending) return <Loading />;
  if (statements.error || overview.error) {
    return (
      <LoadError title="Could not load the statements" error={statements.error ?? overview.error} />
    );
  }
  const periods = statements.data.periods.slice(-SHOWN);
  const latest = periods.at(-1);
  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <div role="group" aria-label="Period" className="tst-toggle">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              type="button"
              aria-pressed={period === p.key}
              onClick={() => setPeriod(p.key)}
              data-testid={`period-${p.key}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <span className="tst-muted" style={{ fontSize: 13 }}>
          In thousands of dollars · the books reconcile every month
          {periods.some((p) => !p.complete) ? ' · * period still in progress' : ''}
        </span>
      </div>
      {latest === undefined ? (
        <Panel title="Profit and loss">
          <p className="tst-muted" style={{ margin: 0 }}>
            No month has closed yet. Press Continue to play the first month.
          </p>
        </Panel>
      ) : (
        <>
          <section
            aria-label="Profit and loss"
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            <h2 className="tst-ptitle" style={{ margin: 0 }}>
              Profit and loss
            </h2>
            <StatementTable periods={periods} />
          </section>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
            <BalanceSheet period={latest} />
            <CashFlow period={latest} />
            <Panel title="Cash and burn, last 12 months" style={{ flex: '1 1 340px' }}>
              <CashBurnChart history={overview.data.history} />
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
