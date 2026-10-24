import { statusStyle, type Status } from '../lib/status';

/** Roster status: Founder, Active or Notice. */
export function StatusChip({ status }: { status: Status }) {
  return (
    <span
      data-status={status}
      style={{
        ...statusStyle(status),
        fontSize: 12,
        fontWeight: 600,
        borderRadius: 4,
        padding: '2px 8px',
      }}
    >
      {status}
    </span>
  );
}
