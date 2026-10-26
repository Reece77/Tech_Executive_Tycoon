// Inbox badges and filters. The API sends the template key as `kind`; this maps it to the
// wireframe's text labels (no icons) and to the People/Hiring/Products filters.

export type KindLabel =
  'Hire' | 'Search' | 'Scout' | 'Notice' | 'Declined' | 'Delegate' | 'Product';
export type InboxFilter = 'all' | 'unread' | 'people' | 'hiring' | 'products';
type Group = 'people' | 'hiring' | 'company' | 'products';

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
};

/** The message kinds a filter keeps, for the API (across every page); null keeps all. */
export function kindsFor(filter: InboxFilter): string[] | null {
  if (filter === 'all' || filter === 'unread') return null;
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

export function matchesFilter(item: { kind: string; read: boolean }, filter: InboxFilter): boolean {
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
