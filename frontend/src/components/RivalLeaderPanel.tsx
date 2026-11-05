// A rival's CEO on the Rival screen (M14b, formulas.md 29.4): their name, recent public
// statements, and the feud with your founder (score, the rivalry line and its causes). All
// public; never the rival's decision weights (29.6).
import { useRivalLeader, type RivalLeader } from '../hooks/press';
import { formatWhole } from '../lib/format';
import { signed, STATEMENT_KINDS } from '../lib/press';
import { Panel } from './ScreenState';
import { Term } from './Term';

const FEUD_MAX = 100;

export function RivalLeaderPanel({ saveId, rivalId }: { saveId: string; rivalId: number }) {
  const leader = useRivalLeader(saveId, rivalId);
  if (!leader.data) return null;
  return <RivalLeaderBody leader={leader.data} />;
}

export function RivalLeaderBody({ leader }: { leader: RivalLeader }) {
  const feud = leader.feud;
  const width = Math.max(0, Math.min(FEUD_MAX, feud.score));
  return (
    <Panel
      title="Their CEO"
      testId="rival-leader"
      style={{ display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'flex-start' }}
    >
      <div style={{ flex: '1 1 260px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <Term term="rival_ceo">
            <strong style={{ fontSize: 16 }} data-testid="rival-ceo">
              {leader.ceo ?? 'No CEO named'}
            </strong>
          </Term>
          <span className="tst-muted" style={{ fontSize: 12 }}>
            CEO of {feud.rival}
          </span>
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Term term="feud">
            <span style={{ fontSize: 13 }}>Feud</span>
          </Term>
          <span
            role="meter"
            aria-label="Feud"
            aria-valuemin={0}
            aria-valuemax={FEUD_MAX}
            aria-valuenow={feud.score}
            style={{
              position: 'relative',
              flex: '1 1 140px',
              height: 8,
              borderRadius: 4,
              background: 'var(--tst-grey-bg)',
              overflow: 'hidden',
            }}
          >
            <span
              style={{
                position: 'absolute',
                inset: 0,
                width: `${width}%`,
                background: feud.rivalry ? 'var(--tst-warn)' : 'var(--tst-tier-4)',
              }}
            />
          </span>
          <span className="tst-num" data-testid="feud-score" data-score={feud.score}>
            {formatWhole(feud.score)}
          </span>
          {feud.rivalry && (
            <Term term="rivalry">
              <span
                data-testid="feud-rivalry"
                style={{
                  color: 'var(--tst-bg)',
                  background: 'var(--tst-warn)',
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '.04em',
                  borderRadius: 4,
                  padding: '2px 6px',
                }}
              >
                Rivalry
              </span>
            </Term>
          )}
        </div>
        {feud.causes.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column' }} data-testid="feud-causes">
            {[...feud.causes].reverse().map((c, i) => (
              <span key={`${c.turn}-${i}`} style={{ fontSize: 12, display: 'flex', gap: 8 }}>
                <span className="tst-num tst-muted" style={{ flex: 'none' }}>
                  {c.label}
                </span>
                <span className="tst-num" style={{ flex: 'none' }}>
                  {signed(c.change)}
                </span>
                <span style={{ color: 'var(--tst-text-2)' }}>{c.cause}</span>
              </span>
            ))}
          </div>
        ) : (
          <span className="tst-muted" style={{ fontSize: 12 }}>
            No feud with your founder.
          </span>
        )}
      </div>
      <div style={{ flex: '2 1 360px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="tst-muted" style={{ fontSize: 12 }}>
          Recent statements
        </span>
        {leader.statements.length === 0 && (
          <span className="tst-muted" style={{ fontSize: 13 }}>
            Nothing said in public lately.
          </span>
        )}
        {leader.statements.map((s, i) => (
          <span
            key={i}
            style={{ fontSize: 13, display: 'flex', gap: 8 }}
            data-testid="rival-statement"
            data-kind={s.kind}
          >
            <span className="tst-num tst-muted" style={{ flex: 'none' }}>
              {s.label}
            </span>
            <span
              style={{
                flex: 'none',
                fontWeight: 600,
                color: s.kind === 'statement' ? 'var(--tst-text-2)' : 'var(--tst-warn)',
              }}
            >
              {STATEMENT_KINDS[s.kind] ?? s.kind}
            </span>
            <span style={{ fontStyle: 'italic' }}>&ldquo;{s.text}&rdquo;</span>
          </span>
        ))}
      </div>
    </Panel>
  );
}
