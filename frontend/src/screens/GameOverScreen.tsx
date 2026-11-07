import { Link, Navigate, useParams } from 'react-router';
import { ExitChoicePanel } from '../components/ExitChoicePanel';
import { KpiTile } from '../components/KpiTile';
import { LoadError, Loading } from '../components/ScreenState';
import { Sparkline } from '../components/Sparkline';
import { useGameOver, useOverview, type GameOver } from '../hooks/api';
import { formatMoneyWhole, formatMonths } from '../lib/format';
import { formatFraction } from '../lib/finance';

const LINKS = [
  { label: 'Statements', path: 'finance/statements' },
  { label: 'Cap table', path: 'finance/captable' },
  { label: 'Inbox', path: 'inbox' },
  { label: 'People', path: 'people' },
];

function headline(g: GameOver): { kicker: string; title: string; text: string } {
  if (g.game_state === 'scenario_done') {
    // M15b (30.3): a historical scenario judged, early on success or at its deadline
    const won = g.scenario_result === 'success';
    return {
      kicker: `Scenario ${won ? 'won' : 'lost'} · ${g.ended_label ?? ''}`,
      title: `${g.scenario_label ?? 'Scenario'}: ${won ? 'goal reached' : 'goal missed'}`,
      text: `The goal: ${g.scenario_goal ?? ''} by ${g.scenario_deadline_label ?? ''}. ${
        won ? `${g.company_name} did it.` : `${g.company_name} did not get there in time.`
      }`,
    };
  }
  if (g.game_state === 'exit' || g.game_state === 'retired') {
    // M14 (28.6): the company was sold; M15b: then retired
    return {
      kicker: `${g.game_state === 'retired' ? 'Retired' : 'Exit'} · ${g.ended_label ?? ''}`,
      title: `You sold ${g.company_name} to ${g.exit_buyer ?? 'a buyer'}`,
      text: `The buyer paid ${formatMoneyWhole(g.exit_price_cents ?? 0)} for every share. Your stake came to ${formatMoneyWhole(g.exit_proceeds_cents ?? 0)}.`,
    };
  }
  if (g.game_state === 'founder_removed') {
    const voted = g.directors.filter((d) => d.voted).length;
    return {
      kicker: `Removed by the board · ${g.ended_label ?? ''}`,
      title: `The board removed you as CEO of ${g.company_name}`,
      text: `${voted} of ${g.directors.length} investor and independent directors had lost confidence for long enough to vote you out, and together they held a majority of the board.`,
    };
  }
  const bridge =
    g.bridge_offered_cents === null || g.bridge_offered_cents === undefined
      ? ''
      : g.bridge_lapsed
        ? ` Your investors offered a ${formatMoneyWhole(g.bridge_offered_cents)} bridge; it lapsed without an answer.`
        : ` Your investors' bridge did not keep cash above zero.`;
  return {
    kicker: `Bankrupt · ${g.ended_label ?? ''}`,
    title: `${g.company_name} ran out of money`,
    text: `Cash stayed below zero at three month ends in a row, ${g.insolvent_from_label ?? ''} to ${g.ended_label ?? ''}.${bridge}`,
  };
}

/** How the game ended (M4b, ADR-0018): no nav; the save stays readable through the links. */
export function GameOverScreen() {
  const { saveId = '' } = useParams();
  const overview = useOverview(saveId);
  const over = useGameOver(saveId);
  if (overview.isPending || over.isPending) return <Loading />;
  if (overview.error || over.error) {
    return <LoadError title="Could not load the game" error={overview.error ?? over.error} />;
  }
  const g = over.data;
  if (g.game_state === 'active') return <Navigate to={`/game/${saveId}/overview`} replace />;
  const h = headline(g);
  const o = overview.data;
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 24,
          padding: '12px 20px',
          background: 'var(--tst-panel)',
          borderBottom: '1px solid var(--tst-border)',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 16, fontWeight: 700 }}>{g.company_name}</span>
          <span className="tst-muted" style={{ fontSize: 12 }}>
            Stage {o.stage} · {o.stage_label}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 28,
            marginLeft: 'auto',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="tst-ptitle" style={{ margin: 0, fontSize: 11, fontWeight: 400 }}>
              Date
            </span>
            <span className="tst-num" style={{ fontSize: 15 }}>
              {g.ended_label}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="tst-ptitle" style={{ margin: 0, fontSize: 11, fontWeight: 400 }}>
              Cash
            </span>
            <span
              className="tst-num"
              style={{ fontSize: 15, color: g.cash_cents < 0 ? 'var(--tst-warn)' : undefined }}
              data-testid="over-cash"
            >
              {formatMoneyWhole(g.cash_cents)}
            </span>
          </div>
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: 'var(--tst-bg)',
              background: 'var(--tst-warn)',
              borderRadius: 4,
              padding: '4px 10px',
            }}
          >
            Game over
          </span>
          <Link
            to="/new"
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: 'var(--tst-bg)',
              background: 'var(--tst-accent)',
              borderRadius: 8,
              padding: '12px 24px',
              minHeight: 44,
              boxSizing: 'border-box',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            New game
          </Link>
        </div>
      </header>
      <main
        style={{
          flex: 1,
          width: '100%',
          maxWidth: 980,
          margin: '0 auto',
          padding: '40px 24px',
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
          gap: 22,
        }}
        data-testid="game-over"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--tst-warn)',
              textTransform: 'uppercase',
              letterSpacing: '.08em',
            }}
            data-testid="over-kicker"
          >
            {h.kicker}
          </span>
          <h1 style={{ margin: 0, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}>{h.title}</h1>
          <p style={{ margin: 0, fontSize: 16, lineHeight: 1.6, color: 'var(--tst-text-2)' }}>
            {h.text}
          </p>
          {g.scenario_result && (
            <span
              data-testid="scenario-result"
              data-result={g.scenario_result}
              style={{
                alignSelf: 'flex-start',
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 4,
                padding: '4px 10px',
                color: 'var(--tst-bg)',
                background:
                  g.scenario_result === 'success' ? 'var(--tst-good)' : 'var(--tst-warn)',
              }}
            >
              {g.scenario_label}: {g.scenario_result === 'success' ? 'success' : 'failure'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <KpiTile
            term="kpi.lasted"
            label="Lasted"
            value={formatMonths(g.months_lasted)}
            note={`${g.founded_label} to ${g.ended_label ?? ''}`}
            testId="over-lasted"
          />
          <KpiTile
            term="kpi.arr_at_end"
            label="ARR at the end"
            value={formatMoneyWhole(g.arr_cents)}
            note={`${g.live_products} live product${g.live_products === 1 ? '' : 's'}, ${g.customers} customers`}
            testId="over-arr"
          />
          <KpiTile
            term="kpi.peak_headcount"
            label="Peak headcount"
            value={String(g.peak_headcount)}
            note={`${g.final_headcount} at the end`}
            testId="over-headcount"
          />
          <KpiTile
            term="kpi.founder_owned"
            label="You owned"
            value={formatFraction(g.founder_fraction, 1)}
            note={g.funding_summary ?? 'with no outside money'}
            testId="over-ownership"
          />
        </div>
        {g.can_found_again && <ExitChoicePanel saveId={saveId} over={g} />}
        {g.game_state === 'founder_removed' && g.directors.length > 0 && (
          <section className="tst-panel" aria-label="The directors">
            <h2 className="tst-ptitle">The directors</h2>
            {g.directors.map((d) => (
              <div key={d.name} className="tst-row" style={{ alignItems: 'center' }}>
                <span>
                  {d.name}
                  {d.firm_name ? ` · ${d.firm_name}` : ' · independent'}
                  {d.voted ? ' · voted to remove you' : ''}
                </span>
                <span style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <Sparkline
                    values={d.history}
                    label={`${d.name}'s confidence over the last months`}
                  />
                  <span className="tst-num">
                    {d.confidence === null || d.confidence === undefined
                      ? '—'
                      : Math.round(d.confidence)}
                  </span>
                </span>
              </div>
            ))}
          </section>
        )}
        <section className="tst-panel" aria-label="The last six months">
          <h2 className="tst-ptitle">The last six months</h2>
          {g.timeline.length === 0 ? (
            <p className="tst-muted" style={{ margin: 0 }}>
              No finance news in the last six months.
            </p>
          ) : (
            g.timeline.map((t, i) => (
              <div
                key={`${t.turn}-${t.template}-${i}`}
                className="tst-row"
                style={{ borderBottom: i === g.timeline.length - 1 ? 0 : undefined }}
                data-testid="over-timeline"
              >
                <span className="tst-num">{t.date_label}</span>
                <span
                  style={{
                    color: t.critical ? 'var(--tst-warn)' : 'var(--tst-text-2)',
                    textAlign: 'right',
                  }}
                >
                  {t.title}
                </span>
              </div>
            ))
          )}
        </section>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="tst-muted" style={{ fontSize: 13 }}>
            The save is kept and stays readable.
          </span>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 10,
            }}
          >
            {LINKS.map((l) => (
              <Link
                key={l.path}
                to={`/game/${saveId}/${l.path}`}
                className="tst-panel"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  minHeight: 44,
                  boxSizing: 'border-box',
                  textDecoration: 'none',
                  color: 'var(--tst-text)',
                  fontSize: 15,
                }}
              >
                {l.label} <span aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
