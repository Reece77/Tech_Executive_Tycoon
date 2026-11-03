// Display helpers for the IPO, the Stock tab and the CEO seat (M13). Formatting only: every
// value comes from the API.
import type { GameEventOut } from '../hooks/api';
import { humanize } from './format';

/** A percentage the API sent, for display: 59.4999 -> "59.5%", 6.0 -> "6%". */
export function pctText(value: number, digits = 1): string {
  return `${value.toFixed(digits).replace(/\.0+$/, '')}%`;
}

/** The open IPO event, if any: during pricing it is the pricing decision (category public). */
export function openIpoEvent(events: GameEventOut[] | undefined): GameEventOut | undefined {
  return events?.find((e) => e.category === 'public' && e.status === 'open');
}

/** "cto" -> "CTO", "products" -> "Products": a CEO scope's label. */
export function scopeLabel(scope: string): string {
  return scope.length <= 3 ? scope.toUpperCase() : humanize(scope);
}
