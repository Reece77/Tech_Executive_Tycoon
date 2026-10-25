// Org display helpers: labels and text for values the API sends. No game values computed here.

export type UnitKind = 'company' | 'department' | 'team';

export const UNIT_KIND_LABELS: Record<UnitKind, string> = {
  company: 'Company',
  department: 'Department',
  team: 'Team',
};

export const MANAGER_LABELS: Record<string, string> = {
  strong: 'Strong',
  fine: 'Fine',
  stretched: 'Stretched',
};

export const POLICY_LABELS: Record<string, string> = { office: 'Office', remote: 'Remote' };

export const FOCUS_LABELS: Record<string, string> = {
  current: 'Best now',
  potential: 'Spot potential',
};

export const CHANNEL_LABELS: Record<string, string> = {
  any: 'Any',
  job_post: 'Job post',
  recruiter: 'Recruiter',
  network: 'Network',
};

/** "Office", or "Office (inherited)" when the unit has no policy of its own. */
export function policyText(own: string | null, effective: string): string {
  const label = POLICY_LABELS[effective] ?? effective;
  return own === null ? `${label} (inherited)` : label;
}

/** A morale change from a preview: +3, −2 (true minus sign), 0. */
export function signed(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const text = Math.abs(rounded).toFixed(1).replace(/\.0$/, '');
  if (rounded > 0) return `+${text}`;
  if (rounded < 0) return `−${text}`;
  return '0';
}
