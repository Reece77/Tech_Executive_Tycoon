// Attribute display rules from docs/wireframes.md. Ranges arrive from the API; this only
// chooses a color and a label for them.

export interface Range {
  min: number;
  max: number;
}

export type Tier = 1 | 2 | 3 | 4;

/** Color tier by range midpoint: 1-5, 6-10, 11-15, 16-20. */
export function attributeTier({ min, max }: Range): Tier {
  const mid = (min + max) / 2;
  if (mid >= 16) return 4;
  if (mid >= 11) return 3;
  if (mid >= 6) return 2;
  return 1;
}

/** "14–17" for a range, "14" for a known value. */
export function rangeText({ min, max }: Range): string {
  return min === max ? String(min) : `${min}–${max}`;
}

/** Morale bar color band: below 40 warn, 40-59 light grey, 60+ accent. */
export type MoraleBand = 'low' | 'mid' | 'high';

export function moraleBand(morale: number): MoraleBand {
  if (morale < 40) return 'low';
  if (morale < 60) return 'mid';
  return 'high';
}

/** Sort key for "top skills": highest midpoint first, then narrower range, then label. */
export function byStrength<T extends { label: string; range: Range }>(a: T, b: T): number {
  const mid = (r: Range) => r.min + r.max;
  return (
    mid(b.range) - mid(a.range) ||
    a.range.max - a.range.min - (b.range.max - b.range.min) ||
    a.label.localeCompare(b.label)
  );
}
