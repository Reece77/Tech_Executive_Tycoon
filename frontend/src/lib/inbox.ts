// Inbox badges and filters. The API sends the template key as `kind`; this maps it to the
// wireframe's text labels (no icons) and to the People/Hiring filters.

export type KindLabel = 'Hire' | 'Search' | 'Scout' | 'Notice' | 'Declined' | 'Month';
export type InboxFilter = 'all' | 'unread' | 'people' | 'hiring';

const KINDS: Record<string, { label: KindLabel; group: 'people' | 'hiring' | 'company' }> = {
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
};

export function kindLabel(kind: string): KindLabel {
  return KINDS[kind]?.label ?? 'Month';
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
