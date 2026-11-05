import { starRange, starWords } from '../lib/press';

/** Leadership fit as a star range from revealed values (M14b, 29.5): a range while any of
 * leadership, mentoring, communication or temperament is still unrevealed. */
export function LeadershipFit({ low, high }: { low?: number; high?: number }) {
  const lo = low ?? 1;
  const hi = high ?? 5;
  return (
    <span
      data-testid="leadership-fit"
      data-low={lo}
      data-high={hi}
      title={`Leadership fit ${starWords(lo, hi)}`}
      aria-label={`Leadership fit ${starWords(lo, hi)}`}
      style={{
        color: 'var(--tst-tier-4)',
        fontSize: 12,
        letterSpacing: '-0.05em',
        whiteSpace: 'nowrap',
      }}
    >
      {starRange(lo, hi)}
    </span>
  );
}
