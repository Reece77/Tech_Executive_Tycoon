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

/** Compact form for chart axes: 4800000 -> "$48k", 150000000 -> "$1.5M", 191000000000 ->
 * "$1.9B". */
export function formatMoneyShort(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const dollars = Math.abs(cents) / 100;
  if (dollars >= 1_000_000_000) return `${sign}$${trim(dollars / 1_000_000_000)}B`;
  if (dollars >= 1_000_000) return `${sign}$${trim(dollars / 1_000_000)}M`;
  if (dollars >= 1_000) return `${sign}$${trim(dollars / 1_000)}k`;
  return `${sign}$${trim(dollars)}`;
}

function trim(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '');
}

/** Runway in months from the API; null means profitable: this month's revenue covers
 * its projected costs (formulas.md 14.1). */
export function formatRunway(months: number | null): string {
  if (months === null) return 'Profitable';
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

/** Typed dollars to integer cents by string math: "$1,000.5" -> 100050; invalid -> 0. */
export function parseDollars(text: string): number {
  const digits = text.replace(/[$,\s]/g, '');
  if (!/^\d+(\.\d{1,2})?$/.test(digits)) return 0;
  const [whole, frac = ''] = digits.split('.');
  return Number(whole) * 100 + Number(frac.padEnd(2, '0'));
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

/** "38.2 MB", "640 KB": a file size (M7b saves). */
export function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1000))} KB`;
}

/** A wall-clock time from the API (ISO, UTC) in the player's locale: "30 Oct 2026, 14:02". */
export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
