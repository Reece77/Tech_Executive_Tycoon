import type { Era } from '../hooks/api';
import { Term } from './Term';

/** The era timeline (M11, formulas.md 21.4): arrived eras with who caused them, the next era
 * of each domain with its threshold against your level, then later eras (no dates). */
export function EraTimeline({ eras }: { eras: Era[] }) {
  return (
    <ol
      data-testid="era-timeline"
      style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}
    >
      {eras.map((e) => (
        <li
          key={e.key}
          data-testid={`era-${e.key}`}
          data-status={e.status}
          style={{
            display: 'grid',
            gridTemplateColumns: '170px 1fr',
            gap: 8,
            padding: '6px 8px',
            borderLeft: `3px solid ${
              e.status === 'arrived'
                ? 'var(--tst-good)'
                : e.status === 'next'
                  ? 'var(--tst-accent)'
                  : 'var(--tst-rule)'
            }`,
            background: e.status === 'next' ? 'var(--tst-gold-bg)' : undefined,
          }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>
              <Term term="research.era">{e.label}</Term>
            </div>
            <div className="tst-muted" style={{ fontSize: 12 }}>
              {e.domain_label}
            </div>
          </div>
          <div style={{ fontSize: 13 }}>
            {e.status === 'arrived' ? (
              <span data-testid="era-arrived">
                Arrived {e.arrived}
                {e.on_schedule
                  ? ', on schedule'
                  : `, ${e.months_early} months early (${e.caused_by ?? 'a rival'})`}
              </span>
            ) : (
              <span>
                <Term term="research.threshold">Threshold</Term>{' '}
                <span className="tst-num">{e.threshold.toFixed(1)}</span>; your level{' '}
                <span className="tst-num">{e.your_level.toFixed(1)}</span>
                {e.status === 'next' && (
                  <span className="tst-muted">
                    {' '}
                    · <Term term="research.first_mover">First mover</Term>: {e.first_mover_reward}
                  </span>
                )}
              </span>
            )}
            <div className="tst-muted" style={{ fontSize: 12 }}>
              {e.accelerates}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
