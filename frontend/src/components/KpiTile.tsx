import type { ReactNode } from 'react';
import { Explain } from './Explain';
import { Term } from './Term';

interface Props {
  label: string;
  term: string; // glossary id of the label (M7b): every KPI has a definition
  value: string;
  note?: string;
  warn?: boolean;
  hint?: string; // tooltip: what drives the number
  testId?: string;
  small?: boolean; // text values such as the mission
  drivers?: (value: ReactNode) => ReactNode; // wraps the value in its breakdown tooltip
  explain?: string; // M25: the Explain metric key, for the button beside the label
  explainEntity?: string | number;
}

export function KpiTile({
  label,
  term,
  value,
  note,
  warn,
  hint,
  testId,
  small,
  drivers,
  explain,
  explainEntity,
}: Props) {
  return (
    <div className="tst-panel" style={{ padding: '12px 16px', flex: '1 1 150px' }} title={hint}>
      <div className="tst-muted" style={{ fontSize: 12 }}>
        <Term term={term}>{label}</Term>
        {explain && <Explain metric={explain} entity={explainEntity} label={label} />}
      </div>
      <div
        className={small ? undefined : 'tst-num'}
        style={{
          fontSize: small ? 15 : 22,
          fontWeight: 600,
          paddingTop: small ? 4 : 0,
          color: warn ? 'var(--tst-warn)' : undefined,
        }}
        data-testid={drivers ? undefined : testId}
      >
        {drivers ? drivers(<span data-testid={testId}>{value}</span>) : value}
      </div>
      {note && (
        <div className="tst-muted" style={{ fontSize: 12 }}>
          {note}
        </div>
      )}
    </div>
  );
}
