// Formatting for the Exploration screen (M18): grades and estimate ranges, display only.
import type { EstimateRange } from '../hooks/exploration';

/** A grade as the screen shows it: percent of ore, or parts per million. */
export function formatGrade(value: number, unit: string): string {
  if (unit === 'ppm') return `${Math.round(value * 1e6).toLocaleString()} ppm`;
  return `${(value * 100).toFixed(value < 0.01 ? 3 : 2)}%`;
}

export function formatRange(r: EstimateRange, fmt: (v: number) => string): string {
  return `${fmt(r.low)} – ${fmt(r.high)} (±${Math.round(r.pct * 100)}%)`;
}
