// Left navigation; keys 1-9 and 0 jump to these in order. Later screens show dimmed with their milestone.
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
  { path: 'products', label: 'Products', arrivesIn: null },
  { path: 'finance', label: 'Finance', arrivesIn: null },
  { path: 'competitors', label: 'Competitors', arrivesIn: null },
  { path: 'history', label: 'History', arrivesIn: null },
  { path: 'saves', label: 'Saves', arrivesIn: null }, // M7b, key 0
];

/** Where the top bar's "Answer ... first" link goes (Reece's playtest 3): the first event
 * that needs answering, else the Org screen for proposals and pitches, else the inbox. */
export function answerHref(saveId: string, blockingEventIds: readonly number[], proposals: number) {
  if (blockingEventIds.length > 0) return `/game/${saveId}/events/${blockingEventIds[0]}`;
  return proposals > 0 ? `/game/${saveId}/org` : `/game/${saveId}/inbox`;
}
