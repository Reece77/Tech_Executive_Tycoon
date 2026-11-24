// Words for talks (M49, formulas.md 61): kinds, statuses and people's flags as shown. Labels only.

export const TALK_KIND_LABEL: Record<string, string> = {
  interview: 'Interview',
  crisis: 'Press conference',
  one_to_one: 'One-to-one',
};

export const TALK_STATUS: Record<string, string> = {
  open: 'In progress',
  done: 'Over',
  skipped: 'Skipped: today’s outcome',
  lapsed: 'Lapsed at the month end',
  failed: 'Over, but its outcome could not be applied',
};

export const FLAG_LABEL: Record<string, string> = {
  unhappy: 'Unhappy',
  approached: 'Approached by a rival',
  seat: 'Executive seat',
};
