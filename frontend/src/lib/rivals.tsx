// Rival chips and tags (M5 wireframes): style colours, the startup chip, news tags.

const STYLE_COLORS: Record<string, { color: string; background: string }> = {
  aggressive: { color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
  fast_follower: { color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
  premium: { color: 'var(--tst-tier-4)', background: 'var(--tst-gold-bg)' },
  cost_leader: { color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
};

const TAG_COLORS: Record<string, string> = {
  Price: 'var(--tst-warn)',
  Push: 'var(--tst-link)',
  Enter: 'var(--tst-teal)',
  Cut: 'var(--tst-text-2)',
  Approach: 'var(--tst-warn)',
  Launch: 'var(--tst-good)',
  Funding: 'var(--tst-tier-4)',
  Founded: 'var(--tst-purple)',
  Failed: 'var(--tst-text-2)',
};

const chip = {
  fontSize: 11,
  fontWeight: 600,
  padding: '2px 6px',
  borderRadius: 4,
  whiteSpace: 'nowrap',
} as const;

export function StyleChip({ personality, label }: { personality: string; label: string }) {
  return (
    <span style={{ ...chip, ...(STYLE_COLORS[personality] ?? {}) }} data-testid="style-chip">
      {label}
    </span>
  );
}

export function StartupChip() {
  return (
    <span style={{ ...chip, color: 'var(--tst-purple)', background: 'var(--tst-purple-bg)' }}>
      Startup
    </span>
  );
}

export function MoveTag({ tag }: { tag: string }) {
  return (
    <span
      style={{
        ...chip,
        color: TAG_COLORS[tag] ?? 'var(--tst-text-2)',
        border: '1px solid currentColor',
        flex: 'none',
      }}
    >
      {tag}
    </span>
  );
}
