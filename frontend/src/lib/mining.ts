// Formatting for the Mines screen (M19): tonnages, prices a tonne or a pound, display only.

export function formatTonnes(t: number | null | undefined): string {
  if (t === null || t === undefined) return '—';
  if (t >= 1e6) return `${(t / 1e6).toFixed(2)} Mt`;
  if (t >= 1e4) return `${Math.round(t / 1000).toLocaleString()} kt`;
  return `${Math.round(t).toLocaleString()} t`;
}

export function formatPerTonne(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return '—';
  return `$${Math.round(usd).toLocaleString()}/t`;
}

export function formatPerPound(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return '—';
  return `$${usd.toFixed(2)}/lb`;
}

export function formatShare(x: number): string {
  return `${Math.round(x * 100)}%`;
}

const LB_PER_T = 2204.62; // unit conversion only

/** A price a tonne shown a pound (copper is quoted a pound). */
export function formatTonneAsPound(usdPerT: number): string {
  return formatPerPound(usdPerT / LB_PER_T);
}
