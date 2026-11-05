// Press, promises and leadership fit (M14b, formulas.md 29): labels and display formatting only.
// Every value comes from the API; nothing here judges a promise or computes a fit.

export type PromiseKind = 'ship' | 'beat' | 'research' | 'no_layoffs' | 'no_price_rise';

/** The promise kinds the dialog offers, in the spec's order (29.2), with what each needs. */
export const PROMISE_KINDS: {
  key: PromiseKind;
  label: string;
  timed: boolean; // a deadline the player picks; the others run 12 months
  product: 'in_development' | 'live' | null;
}[] = [
  { key: 'ship', label: 'Ship a product by a date', timed: true, product: 'in_development' },
  { key: 'beat', label: "Beat a rival's quality by a date", timed: true, product: 'live' },
  { key: 'research', label: 'Reach a research level by a date', timed: true, product: null },
  { key: 'no_layoffs', label: 'No layoffs for 12 months', timed: false, product: null },
  { key: 'no_price_rise', label: 'No price rise for 12 months', timed: false, product: 'live' },
];

export const PROMISE_LABELS: Record<string, string> = {
  ship: 'Ship',
  beat: 'Beat',
  research: 'Research',
  no_layoffs: 'No layoffs',
  no_price_rise: 'No price rise',
};

export const PROMISE_STATUS: Record<string, { label: string; color: string; background: string }> =
  {
    open: { label: 'Open', color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
    kept: { label: 'Kept', color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
    broken: { label: 'Broken', color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
  };

export const STATEMENT_KINDS: Record<string, string> = {
  statement: 'Statement',
  jab: 'Jab',
  answer: 'Answer',
};

/** "+5.0" / "−10.0": a credibility change as the API sent it. */
export function signed(change: number): string {
  const text = Math.abs(change).toFixed(1);
  return change < 0 ? `−${text}` : `+${text}`;
}

/** "★★–★★★★" for a 2–4 star range, "★★★" when the range is one value (29.5). */
export function starRange(low: number, high: number): string {
  const lo = '★'.repeat(Math.max(0, low));
  return low === high ? lo : `${lo}–${'★'.repeat(Math.max(0, high))}`;
}

/** "2–4 stars" for screen readers and tooltips. */
export function starWords(low: number, high: number): string {
  return low === high ? `${low} of 5 stars` : `${low}–${high} of 5 stars`;
}
