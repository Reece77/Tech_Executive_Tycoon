import { moraleBand } from '../lib/attr';
import { formatWhole } from '../lib/format';

const COLORS = { low: 'var(--tst-warn)', mid: 'var(--tst-tier-2)', high: 'var(--tst-accent)' };

interface Props {
  morale: number | null; // null: not tracked (the founder in M1)
  width?: number; // bar width in px; omit to fill the row
  height?: number;
  large?: boolean;
}

/** Morale 0-100: the number is always shown beside the bar. */
export function MoraleBar({ morale, width, height = 6, large = false }: Props) {
  if (morale === null) {
    return <span className="tst-muted">n/a</span>;
  }
  const band = moraleBand(morale);
  const pct = Math.max(0, Math.min(100, morale));
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: large ? 10 : 8 }}>
      <span
        className="tst-num"
        style={{ minWidth: 22, fontSize: large ? 17 : undefined }}
        data-testid="morale-value"
      >
        {formatWhole(morale)}
      </span>
      <span
        role="meter"
        aria-label="Morale"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(morale)}
        style={{
          display: 'block',
          flex: width === undefined ? 1 : undefined,
          width,
          minWidth: 40,
          height,
          background: 'var(--tst-track)',
          borderRadius: height / 2,
        }}
      >
        <span
          data-band={band}
          style={{
            display: 'block',
            width: `${pct}%`,
            height,
            borderRadius: height / 2,
            background: COLORS[band],
          }}
        />
      </span>
    </span>
  );
}
