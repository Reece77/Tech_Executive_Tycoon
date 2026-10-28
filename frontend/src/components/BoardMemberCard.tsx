import { Button } from '@mantine/core';
import type { Director } from '../hooks/api';
import { labelText } from '../lib/finance';
import { formatWhole } from '../lib/format';
import { Sparkline } from './Sparkline';

function seatLabel(d: Director): string {
  if (d.kind === 'independent') return 'Independent seat';
  if (d.kind === 'investor') return `Investor seat · ${d.firm_name ?? ''}`;
  return 'Common seat';
}

/** A director who is not an employee (M4c): investor and independent directors are generated
 * people with no employee profile, so their name opens this card instead. */
export function BoardMemberCard({
  director: d,
  onClose,
}: {
  director: Director;
  onClose?: () => void;
}) {
  const history = d.history;
  return (
    <aside
      className="tst-panel"
      aria-label={`Board member ${d.name}`}
      data-testid="director-card"
      style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 440 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{d.name}</h3>
        {onClose && (
          <Button size="compact-sm" variant="subtle" onClick={onClose}>
            Close
          </Button>
        )}
      </div>
      {d.firm_name && <span style={{ fontSize: 14 }}>{d.firm_name}</span>}
      <div className="tst-row">
        <span>Seat</span>
        <span>{seatLabel(d)}</span>
      </div>
      <div className="tst-row">
        <span>On the board since</span>
        <span className="tst-num">{d.seated_label}</span>
      </div>
      {d.confidence !== null && d.confidence !== undefined && (
        <div className="tst-row">
          <span>Confidence</span>
          <span>
            <span className="tst-num">{formatWhole(d.confidence)}</span> · {labelText(d.label)}
          </span>
        </div>
      )}
      {d.confidence !== null && d.confidence !== undefined && history.length > 1 && (
        <div className="tst-row" style={{ borderBottom: 0 }}>
          <span>
            Last {history.length} month ends: {formatWhole(history[0] ?? 0)} →{' '}
            {formatWhole(history[history.length - 1] ?? 0)}
          </span>
          <Sparkline
            values={history}
            label={`${d.name}'s confidence over the last ${history.length} month ends`}
          />
        </div>
      )}
    </aside>
  );
}
