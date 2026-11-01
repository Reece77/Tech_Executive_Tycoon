import { LoadError, Loading } from './ScreenState';
import { useMacro, type Macro } from '../hooks/api';
import { rangeSparkPoints } from '../lib/finance';

const SERIES: Record<string, (m: Macro['months'][number]) => number> = {
  base_rate: (m) => m.base_rate,
  climate: (m) => m.climate,
  confidence: (m) => m.confidence,
  ai_index: (m) => m.ai_index,
};

/** The four macro indicators with the last two years as sparklines (M10, wireframes: the
 * Finance Debt tab and the Market screen share it). */
export function MacroStrip({ saveId }: { saveId: string }) {
  const macro = useMacro(saveId);
  if (macro.isPending) return <Loading />;
  if (macro.error) return <LoadError title="Could not load the economy" error={macro.error} />;
  const m = macro.data;
  return (
    <section
      className="tst-panel"
      aria-label="Macro economy"
      data-testid="macro-strip"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
        <h2 className="tst-ptitle" style={{ margin: 0 }}>
          The economy · {m.current.label}
        </h2>
        {m.downturn && (
          <span
            className="tst-chip"
            style={{ color: 'var(--tst-warn)', fontWeight: 600 }}
            data-testid="macro-downturn"
          >
            Downturn under way
          </span>
        )}
        {m.after_history && (
          <span className="tst-muted" style={{ fontSize: 12 }}>
            Real history ended {m.history_ends_label}; the economy now moves in cycles.
          </span>
        )}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: 12,
        }}
      >
        {m.indicators.map((i) => {
          const pick = SERIES[i.key];
          const values = pick ? m.months.map(pick) : [];
          return (
            <div
              key={i.key}
              data-testid={`macro-${i.key}`}
              style={{ display: 'flex', flexDirection: 'column', gap: 2 }}
            >
              <span className="tst-muted" style={{ fontSize: 13 }}>
                {i.label}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  className="tst-num"
                  style={{ fontSize: 18 }}
                  data-testid={`macro-${i.key}-value`}
                >
                  {i.display}
                </span>
                {values.length > 1 && (
                  <svg
                    viewBox="0 0 100 24"
                    role="img"
                    aria-label={`${i.label} over the last ${values.length} months`}
                    style={{ width: 100, height: 24 }}
                  >
                    <polyline
                      points={rangeSparkPoints(values)}
                      fill="none"
                      stroke="var(--tst-accent)"
                      strokeWidth={2}
                    />
                  </svg>
                )}
              </div>
              <span className="tst-muted" style={{ fontSize: 12 }}>
                {i.context}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
