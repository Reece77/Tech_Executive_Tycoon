// Left navigation. Only Overview is live in M0; the rest show when they arrive.
export interface NavItem {
  path: string;
  label: string;
  arrivesIn: string | null; // null = live now
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: 'inbox', label: 'Inbox', arrivesIn: 'M1b' },
  { path: 'overview', label: 'Overview', arrivesIn: null },
  { path: 'people', label: 'People', arrivesIn: 'M1b' },
  { path: 'recruitment', label: 'Recruitment', arrivesIn: 'M1b' },
  { path: 'org', label: 'Org', arrivesIn: 'M2' },
  { path: 'products', label: 'Products', arrivesIn: 'M3' },
  { path: 'finance', label: 'Finance', arrivesIn: 'M4' },
  { path: 'competitors', label: 'Competitors', arrivesIn: 'M5' },
  { path: 'history', label: 'History', arrivesIn: 'M7' },
];
