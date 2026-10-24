import { Link, useParams } from 'react-router';
import { CashChart } from '../components/CashChart';
import { KpiTile } from '../components/KpiTile';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { useOverview, type Overview } from '../hooks/api';
import { formatMoneyWhole, formatRunway, formatWhole } from '../lib/format';

// Phase-6 memo labels (backend/tst/sim/hiring/phases.py) as the wireframe words them.
const COST_LABELS: Record<string, string> = {
  'Base overhead': 'Overhead',
  'Job posts': 'Job posts',
};

export function OverviewScreen() {
  const { saveId = '' } = useParams();
  const { data, error, isPending } = useOverview(saveId);

  if (isPending) return <Loading />;
  if (error) return <LoadError title="Could not load the overview" error={error} />;

  const lastMonth = data.history.at(-1)?.date_label ?? null;
  const month = data.date_label.split(' ')[0];
  return (
    <>
      <ScreenTitle>Overview</ScreenTitle>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 12,
        }}
      >
        <KpiTile
          label="Cash"
          value={formatMoneyWhole(data.cash_cents)}
          note={lastMonth ? `End of ${lastMonth.split(' ')[0]}` : 'Starting cash'}
          hint="Balance of the cash account"
          testId="kpi-cash"
        />
        <KpiTile
          label="Monthly burn"
          value={formatMoneyWhole(data.monthly_burn_cents)}
          note={`${lastMonth ? `${lastMonth.split(' ')[0]}; ` : ''}${month} projected ${formatMoneyWhole(data.month_total_cents)}`}
          hint="Net cash spent in the last closed month"
          testId="kpi-burn"
        />
        <KpiTile
          label="Runway"
          value={formatRunway(data.runway_months)}
          warn={data.runway_low}
          note={lastMonth ? `At ${lastMonth.split(' ')[0]}'s burn` : 'No month closed yet'}
          hint="Whole months of cash left at the last month's burn"
          testId="kpi-runway"
        />
        <KpiTile
          label="Headcount"
          value={String(data.team.headcount)}
          note={data.team.on_notice ? `${data.team.on_notice} on notice` : 'Including you'}
          testId="kpi-headcount"
        />
        <KpiTile
          label="Monthly payroll"
          value={formatMoneyWhole(data.team.payroll_cents)}
          note="Salaries and benefits"
          hint="This month, at the current team"
          testId="kpi-payroll"
        />
        <KpiTile
          label="Average morale"
          value={data.team.avg_morale === null ? 'n/a' : formatWhole(data.team.avg_morale)}
          note="Employees, not the founder"
          testId="kpi-morale"
        />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>
        <Panel title="Cash at month end" style={{ flex: '2 1 480px' }}>
          <CashChart history={data.history} />
        </Panel>
        <CostsPanel overview={data} month={month} />
      </div>
      <Panel
        title="Latest in your inbox"
        label="Latest messages"
        action={
          <Link to={`/game/${saveId}/inbox`} style={{ fontSize: 13, textDecoration: 'none' }}>
            Open inbox
          </Link>
        }
      >
        {data.latest_inbox.length === 0 ? (
          <p className="tst-muted" style={{ margin: 0, fontSize: 14 }}>
            Nothing yet.
          </p>
        ) : (
          data.latest_inbox.map((m) => (
            <Link
              key={m.item_id}
              to={`/game/${saveId}/inbox?item=${m.item_id}`}
              className="tst-row"
              style={{ textDecoration: 'none', color: 'var(--tst-text-2)' }}
            >
              <span style={m.read ? undefined : { fontWeight: 600, color: 'var(--tst-text)' }}>
                {m.title}
              </span>
              <span className="tst-num tst-muted" style={{ fontSize: 12, flex: 'none' }}>
                {m.date_label}
              </span>
            </Link>
          ))
        )}
      </Panel>
    </>
  );
}

function CostsPanel({ overview, month }: { overview: Overview; month: string }) {
  const label = (text: string) =>
    text === 'Office'
      ? `Office (${overview.team.headcount} ${overview.team.headcount === 1 ? 'person' : 'people'})`
      : (COST_LABELS[text] ?? text);
  return (
    <Panel
      title={`${month} costs (projected)`}
      label="This month's costs"
      style={{ flex: '1 1 280px', display: 'flex', flexDirection: 'column' }}
    >
      {overview.month_costs.map((c) => (
        <div key={c.account} className="tst-row" data-testid={`cost-${c.account}`}>
          <span style={{ color: 'var(--tst-text-2)' }}>{label(c.label)}</span>
          <span className="tst-num">{formatMoneyWhole(c.amount_cents)}</span>
        </div>
      ))}
      {overview.month_paid.map((c, i) => (
        <div key={`paid-${i}`} className="tst-row" data-testid="cost-paid">
          <span style={{ color: 'var(--tst-text-2)' }}>{c.label} (paid)</span>
          <span className="tst-num">{formatMoneyWhole(c.amount_cents)}</span>
        </div>
      ))}
      <div className="tst-row" style={{ borderBottom: 0, fontWeight: 600 }}>
        <span>Total</span>
        <span className="tst-num" data-testid="cost-total">
          {formatMoneyWhole(overview.month_total_cents)}
        </span>
      </div>
      <p className="tst-muted" style={{ margin: '8px 0 0', fontSize: 12 }}>
        No revenue yet. Products arrive in M3.
      </p>
    </Panel>
  );
}
