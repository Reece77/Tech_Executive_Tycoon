/** A leader's direct reports against their comfortable span, from the API's ManagerOut. */
export function SpanBadge({
  reports,
  limit,
  over,
}: {
  reports: number;
  limit: number;
  over: boolean;
}) {
  return (
    <span
      className="tst-num"
      data-testid="span-badge"
      data-over={over ? 'true' : 'false'}
      style={{
        fontSize: 12,
        fontWeight: over ? 600 : 400,
        color: over ? 'var(--tst-warn)' : 'var(--tst-good)',
        background: over ? 'var(--tst-warn-bg)' : 'var(--tst-good-bg)',
        borderRadius: 4,
        padding: '2px 8px',
      }}
    >
      {reports} / {limit} reports{over ? ' · over span' : ''}
    </span>
  );
}
