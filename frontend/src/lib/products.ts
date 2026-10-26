// Product display helpers: labels and number text for values the API sends (M3b).
// No game value is computed here; fractions arrive from the API and are only formatted.

const countFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const MINUS = '−'; // U+2212, as the wireframes print negatives

/** A 0-1 fraction as a percentage: 0.0242 -> "2.4%". */
export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** A change as a signed percentage: 0.068 -> "+6.8%", -0.17 -> "−17.0%". */
export function formatSignedPercent(fraction: number, digits = 1): string {
  const text = Math.abs(fraction * 100).toFixed(digits);
  if (Number(text) === 0) return `${text}%`;
  return `${fraction < 0 ? MINUS : '+'}${text}%`;
}

/** Customers are stored as floats and shown rounded: 2949.6 -> "2,950". */
export function formatCount(value: number): string {
  return countFormat.format(Math.round(value));
}

/** New or lost customers in a month; small sales-led numbers keep one decimal. */
export function formatFlow(value: number, sign: '+' | '-'): string {
  const abs = Math.abs(value);
  const text = abs > 0 && abs < 10 ? abs.toFixed(1).replace(/\.0$/, '') : formatCount(abs);
  if (text === '0') return '0';
  return `${sign === '+' ? '+' : MINUS}${text}`;
}

/** Quality, features, brand and price scores: whole numbers. */
export function formatScore(value: number): string {
  return String(Math.round(value));
}

/** Appeal keeps one decimal, as in the market tables. */
export function formatAppeal(value: number): string {
  return value.toFixed(1);
}

export type ProductStatus = 'in_development' | 'live' | 'sunset' | 'retired';

const CHIP_STYLES: Record<string, { color: string; background: string }> = {
  live: { color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
  in_development: { color: 'var(--tst-link)', background: 'var(--tst-accent-bg)' },
  sunset: { color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
  retired: { color: 'var(--tst-text-2)', background: 'var(--tst-grey-bg)' },
};

export function lifecycleStyle(status: string) {
  return CHIP_STYLES[status] ?? CHIP_STYLES.retired;
}

/** "Live · growth", "Live · mature", "Live", "In development", "Sunset". */
export function lifecycleText(p: { status: string; lifecycle_label: string }): string {
  if (p.status !== 'live') return p.lifecycle_label;
  const label = p.lifecycle_label.toLowerCase();
  return label === 'live' ? 'Live' : `Live · ${label}`;
}

export const PACE_LABELS: Record<string, string> = {
  fast: 'Fast',
  steady: 'Steady',
  slow: 'Slow',
};

/** Development pace from the API, or "No team" when nobody builds it. */
export function paceText(pace: string, builders: number): string {
  if (builders === 0) return 'No team';
  return PACE_LABELS[pace] ?? pace;
}

export const REACH_TEXT: Record<string, string> = {
  self_serve: 'Self-serve: brand brings customers',
  sales: 'Needs salespeople',
};

/** "quality 25%, price 35%, brand 15% and features 25%" from a segment's appeal weights. */
export function weightsText(w: {
  quality: number;
  price: number;
  brand: number;
  features: number;
}): string {
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return `quality ${pct(w.quality)}, price ${pct(w.price)}, brand ${pct(w.brand)} and features ${pct(w.features)}`;
}

/** What a segment's customers are called. */
export function customerNoun(countsUsers: boolean): string {
  return countsUsers ? 'users' : 'customers';
}

export const BRAND_TREND_TEXT: Record<string, string> = {
  rising: 'and rising',
  falling: 'and falling',
  steady: 'and holding',
};
