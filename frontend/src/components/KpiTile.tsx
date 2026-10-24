interface Props {
  label: string;
  value: string;
  note?: string;
  warn?: boolean;
  hint?: string; // tooltip: what drives the number
  testId?: string;
  small?: boolean; // text values such as the mission
}

export function KpiTile({ label, value, note, warn, hint, testId, small }: Props) {
  return (
    <div className="tst-panel" style={{ padding: '12px 16px', flex: '1 1 150px' }} title={hint}>
      <div className="tst-muted" style={{ fontSize: 12 }}>
        {label}
      </div>
      <div
        className={small ? undefined : 'tst-num'}
        style={{
          fontSize: small ? 15 : 22,
          fontWeight: 600,
          paddingTop: small ? 4 : 0,
          color: warn ? 'var(--tst-warn)' : undefined,
        }}
        data-testid={testId}
      >
        {value}
      </div>
      {note && (
        <div className="tst-muted" style={{ fontSize: 12 }}>
          {note}
        </div>
      )}
    </div>
  );
}
