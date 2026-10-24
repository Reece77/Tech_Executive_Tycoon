import { kindLabel, type KindLabel } from '../lib/inbox';

const STYLES: Record<KindLabel, { color: string; background: string }> = {
  Hire: { color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
  Search: { color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
  Scout: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)' },
  Notice: { color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
  Declined: { color: 'var(--tst-text-2)', background: 'var(--tst-grey-bg)' },
  Month: { color: 'var(--tst-text-2)', background: 'var(--tst-grey-bg)' },
};

/** Inbox message kind as a text badge (no icons). `kind` is the API's template key. */
export function KindBadge({ kind }: { kind: string }) {
  const label = kindLabel(kind);
  return (
    <span
      data-kind={label}
      style={{
        ...STYLES[label],
        flex: 'none',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '.04em',
        textTransform: 'uppercase',
        padding: '2px 6px',
        borderRadius: 4,
        height: 16,
        lineHeight: '16px',
      }}
    >
      {label}
    </span>
  );
}
