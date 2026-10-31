import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router';
import { OverviewTip } from '../components/Term';
import { CashChart } from '../components/CashChart';
import { KpiTile } from '../components/KpiTile';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { useOverview, type Overview, type OverviewBreakdowns } from '../hooks/api';
import { formatMoneyShort, formatMoneyWhole, formatRunway, formatWhole } from '../lib/format';
import { formatFraction } from '../lib/finance';
import { pct, MANAGER_LABELS } from '../lib/org';

// Phase-6 memo labels (backend/tst/sim/hiring/phases.py) as the wireframe words them.
const COST_LABELS: Record<string, string> = {
  'Base overhead': 'Overhead',
  'Job posts': 'Job posts',
};

/** Last round, post-money, the founder's ownership and the board's mood (M4b). */
function FundingTile({ saveId, funding: f }: { saveId: string; funding: Overview['funding'] }) {
  const parts = [
    f.post_money_cents === null ? null : `${formatMoneyShort(f.post_money_cents)} post-money`,
    `you own ${formatFraction(f.founder_fraction)}`,
    f.board_label ? `board ${f.board_label}` : null,
    f.safes_outstanding > 0
      ? `${f.safes_outstanding} SAFE${f.safes_outstanding === 1 ? '' : 's'} to convert`
      : null,
  ].filter(Boolean);
  return (
    <Link
      to={`/game/${saveId}/finance/captable`}
      style={{ display: 'flex', textDecoration: 'none', color: 'inherit' }}
      data-testid="kpi-funding-link"
    >
      <KpiTile
        term="kpi.funding"
        label="Funding"
        value={
          f.last_round_label
            ? `${f.last_round_label}, ${f.last_round_date_label ?? ''}`
            : 'No priced round'
        }
        small
        note={parts.join(' · ')}
        hint="Your last priced round, its post-money valuation, your share of the company and the board's confidence"
        testId="kpi-funding"
      />
    </Link>
  );
}

export function OverviewScreen() {
  const { saveId = '' } = useParams();
  const tip = (which: keyof OverviewBreakdowns, title: string) => (value: ReactNode) => (
    <OverviewTip saveId={saveId} which={which} title={title}>
      {value}
    </OverviewTip>
  );
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
          term="kpi.cash"
          drivers={tip('cash', "Last month's change in cash")}
          label="Cash"
          value={formatMoneyWhole(data.cash_cents)}
          note={lastMonth ? `End of ${lastMonth.split(' ')[0]}` : 'Starting cash'}
          testId="kpi-cash"
        />
        <KpiTile
          term="kpi.burn"
          drivers={tip('burn', 'Burn by cost line')}
          label="Monthly burn"
          value={formatMoneyWhole(data.monthly_burn_cents)}
          note={`${lastMonth ? `${lastMonth.split(' ')[0]}; ` : ''}${month} projected ${formatMoneyWhole(data.month_net_burn_cents)}`}
          testId="kpi-burn"
        />
        <KpiTile
          term="kpi.runway"
          drivers={tip('runway', 'Runway')}
          label="Runway"
          value={formatRunway(data.runway_months)}
          warn={data.runway_low}
          note={`At ${month}'s costs`}
          testId="kpi-runway"
        />
        <KpiTile
          term="kpi.mrr"
          drivers={tip('mrr', 'MRR by product')}
          label="MRR"
          value={formatMoneyWhole(data.mrr_cents)}
          note={lastMonth ? `Revenue in ${lastMonth.split(' ')[0]}` : 'No month closed yet'}
          testId="kpi-mrr"
        />
        <KpiTile
          term="kpi.arr"
          drivers={tip('arr', 'ARR by product')}
          label="ARR"
          value={formatMoneyShort(data.arr_cents)}
          note={
            data.stage_since_label
              ? `Stage ${data.stage} since ${data.stage_since_label}`
              : '12 × MRR; stage 2 from $1M'
          }
          testId="kpi-arr"
        />
        <KpiTile
          term="kpi.headcount"
          drivers={tip('headcount', 'Staff by unit')}
          label="Headcount"
          value={String(data.team.headcount)}
          note={data.team.on_notice ? `${data.team.on_notice} on notice` : 'Including you'}
          testId="kpi-headcount"
        />
        <KpiTile
          term="kpi.payroll"
          label="Monthly payroll"
          value={formatMoneyWhole(data.team.payroll_cents)}
          note="Salaries and benefits"
          hint="This month, at the current team"
          testId="kpi-payroll"
        />
        <KpiTile
          term="kpi.avg_morale"
          drivers={tip('avg_morale', 'Average morale terms')}
          label="Average morale"
          value={data.team.avg_morale === null ? 'n/a' : formatWhole(data.team.avg_morale)}
          note="Employees, not the founder"
          testId="kpi-morale"
        />
        <FundingTile saveId={saveId} funding={data.funding} />
        {data.org && (
          <KpiTile
            term="kpi.org"
            label="Org"
            value={`${data.org.units} ${data.org.units === 1 ? 'unit' : 'units'}`}
            warn={data.org.managers_over_span > 0}
            note={`${data.org.managers_over_span} over span · managers ${
              data.org.manager_label
                ? (MANAGER_LABELS[data.org.manager_label] ?? '').toLowerCase()
                : 'n/a'
            }`}
            hint="Departments and teams; managers with more reports than they handle well; the average manager"
            testId="kpi-org"
          />
        )}
        {data.support && (
          <KpiTile
            term="kpi.support"
            label="Support coverage"
            value={`${data.support.support_staff} of ${data.support.needed}`}
            warn={data.support.pools_short > 0}
            note={
              data.support.pools_short > 0
                ? `${data.support.pools_short} short · output ${pct(data.support.output_effect_pct)}`
                : 'Covered'
            }
            hint="Finance, recruiting and operations staff and executives against one per 15 staff"
            testId="kpi-support"
          />
        )}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>
        <Panel title="Cash and revenue at month end" style={{ flex: '2 1 480px' }}>
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
      title={`${month} revenue and costs (projected)`}
      label="This month's costs"
      style={{ flex: '1 1 280px', display: 'flex', flexDirection: 'column' }}
    >
      <div className="tst-row" data-testid="month-revenue">
        <span style={{ color: 'var(--tst-text-2)' }}>Revenue (at today&apos;s customers)</span>
        <span className="tst-num" style={{ color: 'var(--tst-good)' }}>
          {formatMoneyWhole(overview.month_revenue_cents)}
        </span>
      </div>
      <h3 className="tst-ptitle" style={{ margin: '12px 0 0' }}>
        Costs
      </h3>
      {overview.month_costs.map((c) => (
        <div key={`${c.account}-${c.label}`} className="tst-row" data-testid={`cost-${c.account}`}>
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
        <span>Total costs</span>
        <span className="tst-num" data-testid="cost-total">
          {formatMoneyWhole(overview.month_total_cents)}
        </span>
      </div>
      {overview.month_revenue_cents === 0 && (
        <p className="tst-muted" style={{ margin: '8px 0 0', fontSize: 12 }}>
          No revenue yet: launch a product to start selling.
        </p>
      )}
    </Panel>
  );
}
