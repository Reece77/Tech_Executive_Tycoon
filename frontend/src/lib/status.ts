export type Status = 'Founder' | 'Active' | 'Notice';

const STYLES: Record<Status, { color: string; background: string }> = {
  Founder: { color: 'var(--tst-text-2)', background: 'var(--tst-grey-bg)' },
  Active: { color: 'var(--tst-good)', background: 'var(--tst-good-bg)' },
  Notice: { color: 'var(--tst-warn)', background: 'var(--tst-warn-bg)' },
};

export function statusStyle(status: Status) {
  return STYLES[status];
}

/** Roster status from the API's founder flag and employment status ("active" | "notice"). */
export function statusOf(person: {
  is_founder: boolean;
  employment: { status: string } | null;
}): Status {
  if (person.is_founder) return 'Founder';
  return person.employment?.status === 'notice' ? 'Notice' : 'Active';
}
