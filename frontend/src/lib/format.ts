// Display formatting only. Money arrives from the API as integer cents.

const groupFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** 4800000 -> "$48,000.00"; -150 -> "-$1.50". Integer math, so no float rounding. */
export function formatMoney(cents: number): string {
  if (!Number.isSafeInteger(cents)) {
    throw new RangeError(`formatMoney expects integer cents, got ${cents}`);
  }
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  const dollars = Math.trunc(abs / 100);
  const rest = abs % 100;
  return `${sign}$${groupFormat.format(dollars)}.${String(rest).padStart(2, '0')}`;
}

/** Compact form for chart axes: 4800000 -> "$48k", 150000000 -> "$1.5M". */
export function formatMoneyShort(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const dollars = Math.abs(cents) / 100;
  if (dollars >= 1_000_000) return `${sign}$${trim(dollars / 1_000_000)}M`;
  if (dollars >= 1_000) return `${sign}$${trim(dollars / 1_000)}k`;
  return `${sign}$${trim(dollars)}`;
}

function trim(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '');
}

/** Runway in months from the API; null means the company is not burning cash. */
export function formatRunway(months: number | null): string {
  if (months === null) return 'Not burning';
  return `${months} month${months === 1 ? '' : 's'}`;
}

/** Whole dollars for tiles and tables: 25140000 -> "$251,400" (half-cent rounding is display only). */
export function formatMoneyWhole(cents: number): string {
  if (!Number.isSafeInteger(cents)) {
    throw new RangeError(`formatMoneyWhole expects integer cents, got ${cents}`);
  }
  const sign = cents < 0 ? '-' : '';
  const dollars = Math.round(Math.abs(cents) / 100);
  return `${sign}$${groupFormat.format(dollars)}`;
}

/** Basis points as a percentage, by integer math: 50 -> "0.50%", 1000 -> "10.00%". */
export function formatBpPercent(bp: number): string {
  const sign = bp < 0 ? '-' : '';
  const abs = Math.abs(Math.trunc(bp));
  return `${sign}${Math.trunc(abs / 100)}.${String(abs % 100).padStart(2, '0')}%`;
}

/** A ratio from the API: 1.0438 -> "1.04×". */
export function formatRatio(ratio: number): string {
  return `${ratio.toFixed(2)}×`;
}

/** 1 -> "1 month", 4 -> "4 months". */
export function formatMonths(months: number): string {
  return `${months} month${months === 1 ? '' : 's'}`;
}

/** Morale and other 0-100 floats are shown as whole numbers. */
export function formatWhole(value: number): string {
  return String(Math.round(value));
}

/** "senior" -> "Senior", "job_post" -> "Job post". */
export function humanize(key: string): string {
  const text = key.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}
