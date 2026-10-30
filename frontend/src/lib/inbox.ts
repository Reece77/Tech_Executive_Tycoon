// Inbox badges and filters. The API sends the template key as `kind`; this maps it to the
// wireframe's text labels (no icons) and to the People/Hiring/Products filters.

export type KindLabel =
  | 'Hire'
  | 'Search'
  | 'Scout'
  | 'Notice'
  | 'Declined'
  | 'Delegate'
  | 'Product'
  | 'Finance'
  | 'News'
  | 'Event'
  | 'Critical';
export type InboxFilter =
  'all' | 'unread' | 'people' | 'hiring' | 'products' | 'finance' | 'archived';
type Group = 'people' | 'hiring' | 'company' | 'products' | 'finance';

const KINDS: Record<string, { label: KindLabel; group: Group }> = {
  candidates_arrived: { label: 'Search', group: 'hiring' },
  offer_accepted: { label: 'Hire', group: 'hiring' },
  offer_declined: { label: 'Declined', group: 'hiring' },
  tag_revealed: { label: 'Scout', group: 'people' },
  resigned: { label: 'Notice', group: 'people' },
  retired: { label: 'Notice', group: 'people' },
  employee_left: { label: 'Notice', group: 'people' },
  fired: { label: 'Notice', group: 'people' },
  culture_carrier_left: { label: 'Notice', group: 'people' },
  out_of_cash: { label: 'Notice', group: 'company' },
  // M2a/M2b: hiring plans and the org
  plan_activity: { label: 'Delegate', group: 'hiring' },
  plan_filled: { label: 'Delegate', group: 'hiring' },
  plan_paused: { label: 'Delegate', group: 'hiring' },
  unit_leader_left: { label: 'Notice', group: 'people' },
  // M3: products
  product_launched: { label: 'Product', group: 'products' },
  first_customer: { label: 'Product', group: 'products' },
  arr_milestone: { label: 'Product', group: 'products' },
  sales_capacity_limited: { label: 'Product', group: 'products' },
  product_rotting: { label: 'Product', group: 'products' },
  // M4: finance (SAFE answers, term sheets, closings, the board, insolvency and bridges)
  safe_filled: { label: 'Finance', group: 'finance' },
  safe_declined: { label: 'Finance', group: 'finance' },
  term_sheets_arrived: { label: 'Finance', group: 'finance' },
  no_term_sheets: { label: 'Finance', group: 'finance' },
  round_lapsed: { label: 'Finance', group: 'finance' },
  round_closed: { label: 'Finance', group: 'finance' },
  board_meeting: { label: 'Finance', group: 'finance' },
  board_warning: { label: 'Finance', group: 'finance' },
  founder_removed: { label: 'Finance', group: 'finance' },
  board_seat_empty: { label: 'Finance', group: 'finance' },
  // M5: rivals
  market_news: { label: 'News', group: 'company' },
  rival_approach: { label: 'News', group: 'people' },
  poach_accepted: { label: 'Notice', group: 'people' },
  poach_declined: { label: 'News', group: 'people' },
  rival_failed: { label: 'News', group: 'company' },
  nominee_left: { label: 'Finance', group: 'finance' },
  insolvent: { label: 'Finance', group: 'finance' },
  bridge_offered: { label: 'Finance', group: 'finance' },
  bridge_lapsed: { label: 'Finance', group: 'finance' },
  bridge_funded: { label: 'Finance', group: 'finance' },
  bankrupt: { label: 'Finance', group: 'finance' },
  stage_from_funding: { label: 'Finance', group: 'finance' },
  // M6: events (the card opens in the message panel)
  event: { label: 'Event', group: 'company' },
  critical_event: { label: 'Critical', group: 'company' },
};

/** The Finance tab a finance message opens (M4b). */
const FINANCE_TAB: Record<string, string> = {
  board_meeting: 'board',
  board_warning: 'board',
  founder_removed: 'board',
  board_seat_empty: 'board',
  nominee_left: 'board',
  round_closed: 'captable',
  stage_from_funding: 'captable',
  bankrupt: 'statements',
};

export function financeTab(kind: string): string {
  return FINANCE_TAB[kind] ?? 'fundraising';
}

/** The message kinds a filter keeps, for the API (across every page); null keeps all. */
export function kindsFor(filter: InboxFilter): string[] | null {
  if (filter === 'all' || filter === 'unread' || filter === 'archived') return null;
  return Object.keys(KINDS).filter((kind) => KINDS[kind].group === filter);
}

/** "51–100 of 342" for one inbox page. */
export function pageRange(offset: number, shown: number, total: number): string {
  if (total === 0) return '0 of 0';
  return `${offset + 1}–${offset + shown} of ${total}`;
}

export function kindLabel(kind: string): KindLabel {
  return KINDS[kind]?.label ?? 'Notice'; // a template added without a label here
}

export function matchesFilter(
  item: { kind: string; read: boolean; archived?: boolean },
  filter: InboxFilter,
): boolean {
  if (filter === 'archived') return Boolean(item.archived);
  if (item.archived) return false; // archived items show only under Archived (M4c)
  switch (filter) {
    case 'all':
      return true;
    case 'unread':
      return !item.read;
    default:
      return KINDS[item.kind]?.group === filter;
  }
}

/** First sentence of a body, for the one-line preview. */
export function preview(body: string): string {
  const end = body.search(/[.!?](\s|$)/);
  return end === -1 ? body : body.slice(0, end + 1);
}
