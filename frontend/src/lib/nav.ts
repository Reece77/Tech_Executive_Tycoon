// Left navigation; keys 1-9 jump to these in order. Later screens show dimmed with their milestone.
export interface NavItem {
  path: string;
  label: string;
  arrivesIn: string | null; // null = live now
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: 'inbox', label: 'Inbox', arrivesIn: null },
  { path: 'overview', label: 'Overview', arrivesIn: null },
  { path: 'people', label: 'People', arrivesIn: null },
  { path: 'recruitment', label: 'Recruitment', arrivesIn: null },
  { path: 'org', label: 'Org', arrivesIn: null },
  { path: 'products', label: 'Products', arrivesIn: 'M3' },
  { path: 'finance', label: 'Finance', arrivesIn: 'M4' },
  { path: 'competitors', label: 'Competitors', arrivesIn: 'M5' },
  { path: 'history', label: 'History', arrivesIn: 'M7' },
];
