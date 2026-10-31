// Finance display helpers (M4b). Formatting only: every value comes from the API.

import type { StatementPeriod } from '../hooks/api';

const shareFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const MINUS = '−'; // U+2212, the wireframes' minus sign

/** 22633308 -> "22,633,308". */
export function formatShares(shares: number): string {
  return shareFormat.format(shares);
}

/** A 0-1 fraction from the API as a percentage: 0.3976 -> "39.76%". */
export function formatFraction(fraction: number, digits = 2): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** The change between two API fractions in percentage points: "+4.89", "−15.29", "new". */
export function formatPointChange(before: number, after: number, isNew = false): string {
  if (isNew) return 'new';
  const points = (after - before) * 100;
  if (Math.abs(points) < 0.005) return '0.00';
  return `${points > 0 ? '+' : MINUS}${Math.abs(points).toFixed(2)}`;
}

/** Statement amounts in thousands of dollars, one decimal, minus sign for negatives:
 * -6050000 -> "−60.5". Rounding is display only. */
export function formatThousands(cents: number): string {
  const tenths = Math.round(Math.abs(cents) / 10_000);
  const text = `${shareFormat.format(Math.trunc(tenths / 10))}.${tenths % 10}`;
  return cents < 0 && tenths > 0 ? `${MINUS}${text}` : text;
}

/** A share price string from the API ("0.48936") as dollars: "$0.48936"; "0" -> "—". */
export function formatSharePrice(dollars: string | null | undefined): string {
  if (!dollars || Number(dollars) === 0) return '—';
  return `$${dollars}`;
}

/** Annual growth from the API (1.5 = 150% a year) as a whole percentage. */
export function formatGrowth(growth: number): string {
  return `${Math.round(growth * 100)}%`;
}

export const SERIES_TEXT: Record<string, string> = {
  seed: 'Seed',
  a: 'Series A',
  b: 'Series B',
};

const CLASS_TEXT: Record<string, string> = {
  common: 'Common',
  preferred_seed: 'Seed preferred',
  preferred_a: 'Series A preferred',
  preferred_b: 'Series B preferred',
  safe_conversion: 'Preferred (converted SAFE)',
  option_pool: 'Options',
};

/** A holder line's class in words; the pool and granted options read differently. */
export function shareClassText(shareClass: string, holderKind: string): string {
  if (holderKind === 'pool') return 'Unallocated';
  if (holderKind === 'options') return 'Options granted';
  return CLASS_TEXT[shareClass] ?? shareClass;
}

/** Bar colours on the cap table (wireframe: founder accent, investors light grey, granted
 * options green, the unallocated pool dark grey). */
export function holderColor(holder: { holder_kind: string; is_founder?: boolean }): string {
  if (holder.is_founder) return 'var(--tst-accent)';
  if (holder.holder_kind === 'options') return 'var(--tst-good)';
  if (holder.holder_kind === 'pool') return '#6b7686';
  return 'var(--tst-tier-2)';
}

/** Board confidence bands for bars: below 25 orange, 25-39 gold, 40+ accent (wireframes). */
export function confidenceColor(confidence: number, removalBelow = 25, warningBelow = 40): string {
  if (confidence < removalBelow) return 'var(--tst-warn)';
  if (confidence < warningBelow) return 'var(--tst-tier-4)';
  return 'var(--tst-accent)';
}

/** The API's confidence label with a capital: "losing patience" -> "Losing patience". */
export function labelText(label: string | null | undefined): string {
  if (!label) return '—';
  return label.charAt(0).toUpperCase() + label.slice(1);
}

/** The SAFE dialog's hint band (formulas.md 14.9), as the wireframe colours it. */
export const SAFE_HINTS: Record<
  string,
  { label: string; color: string; bg: string; border: string }
> = {
  likely: {
    label: 'Likely',
    color: 'var(--tst-good)',
    bg: 'var(--tst-good-bg)',
    border: '#2B5A3A',
  },
  uncertain: { label: 'Uncertain', color: 'var(--tst-tier-4)', bg: '#3A2F16', border: '#5A4A20' },
  unlikely: {
    label: 'Unlikely',
    color: 'var(--tst-warn)',
    bg: 'var(--tst-warn-bg)',
    border: '#6A4426',
  },
};

export const STATUS_TEXT: Record<string, string> = {
  pending: 'Waiting for answers',
  declined: 'Declined',
  outstanding: 'Outstanding: converts at the next round',
  converted: 'Converted',
  offered: 'Offered',
  accepted: 'Accepted: money arrives at Continue',
  lapsed: 'Lapsed',
  open: 'Open',
  closed: 'Closed',
  failed: 'No term sheets',
};

/** Seats by kind as "2 common · 2 investor · 1 independent" (zero kinds left out). */
export function seatsText(seats: Record<string, number>): string {
  return ['common', 'investor', 'independent']
    .filter((kind) => (seats[kind] ?? 0) > 0)
    .map((kind) => `${seats[kind]} ${kind}`)
    .join(' · ');
}

/** SVG polyline points for a 0-100 sparkline in a width x height box. */
export function sparkPoints(values: readonly number[], width = 100, height = 24): string {
  if (values.length === 0) return '';
  const step = values.length > 1 ? (width - 10) / (values.length - 1) : 0;
  return values
    .map(
      (v, i) =>
        `${(5 + i * step).toFixed(1)},${(height - 2 - (v / 100) * (height - 4)).toFixed(1)}`,
    )
    .join(' ');
}

/** One P&L line across the periods; costs are shown negative, as the wireframe does. */
export interface StatementLine {
  id: string;
  label: string;
  values: number[]; // cents per period, already signed for display
  total?: boolean;
  indent?: boolean;
}

type Pnl = StatementPeriod['profit_and_loss'];

/** Every account that appears in any period, in account order, with its label. */
function accounts(periods: readonly StatementPeriod[], pick: (p: Pnl) => Pnl['revenue']) {
  const labels = new Map<string, string>();
  for (const p of periods)
    for (const line of pick(p.profit_and_loss)) labels.set(line.account, line.label);
  return [...labels.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function amount(lines: Pnl['revenue'], account: string): number {
  return lines.find((l) => l.account === account)?.amount_cents ?? 0;
}

/** P&L rows: revenue, cost of revenue, gross margin, each operating expense, operating
 * expenses, interest and tax when any period has them, and the net result. */
export function pnlLines(periods: readonly StatementPeriod[]): StatementLine[] {
  const pnl = periods.map((p) => p.profit_and_loss);
  const lines: StatementLine[] = [
    { id: 'revenue', label: 'Revenue', values: pnl.map((p) => p.total_revenue_cents) },
  ];
  for (const [account, label] of accounts(periods, (p) => p.cost_of_revenue)) {
    lines.push({
      id: account,
      label: `${label} (cost of revenue)`,
      values: pnl.map((p) => -amount(p.cost_of_revenue, account)),
      indent: true,
    });
  }
  lines.push({
    id: 'gross',
    label: 'Gross margin',
    values: pnl.map((p) => p.gross_margin_cents),
    total: true,
  });
  for (const [account, label] of accounts(periods, (p) => p.operating_expenses)) {
    lines.push({
      id: account,
      label,
      values: pnl.map((p) => -amount(p.operating_expenses, account)),
      indent: true,
    });
  }
  lines.push({
    id: 'opex',
    label: 'Operating expenses',
    values: pnl.map((p) => -p.total_operating_expenses_cents),
    total: true,
  });
  if (pnl.some((p) => p.interest_cents !== 0)) {
    lines.push({ id: 'interest', label: 'Interest', values: pnl.map((p) => -p.interest_cents) });
  }
  if (pnl.some((p) => p.tax_cents !== 0)) {
    lines.push({ id: 'tax', label: 'Tax', values: pnl.map((p) => -p.tax_cents) });
  }
  lines.push({
    id: 'net',
    label: 'Net result',
    values: pnl.map((p) => p.net_result_cents),
    total: true,
  });
  return lines;
}

/** A holder's name, with "(you)" on the founder's line. */
export function holderName(h: { holder: string; is_founder?: boolean }): string {
  return h.is_founder ? `${h.holder} (you)` : h.holder;
}

/** A holder line's row id. The cap table keeps one line per round, so converted SAFEs from
 * two rounds share holder and class; the position keeps the ids unique (M7c playtest). */
export function capRowId(
  r: { holder_kind: string; holder: string; share_class: string },
  index: number,
): string {
  return `${r.holder_kind}:${r.holder}:${r.share_class}:${index}`;
}
