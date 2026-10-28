import { Button } from '@mantine/core';
import type { Learned } from '../hooks/api';
import { humanize } from '../lib/format';
import { AttributeRange } from './AttributeRange';

const ACTION_TEXT: Record<string, string> = {
  interview: 'Interview',
  reference_check: 'References',
  scout: 'Scouting',
};

/** What one interview, reference check or scout taught (M4c). Values come from the API's
 * before and after ranges; this only lays them out. */
export function LearnedCard({
  learned,
  interestLabel,
  focus,
}: {
  learned: Learned;
  interestLabel?: (key: string) => string;
  focus?: readonly string[]; // the role's key skills; other skills are only counted
}) {
  const shown = learned.ranges.filter(
    (r) => r.group === 'personality' || !focus || focus.includes(r.key),
  );
  const others = learned.ranges.length - shown.length;
  const potentialMoved = learned.potential_before !== learned.potential_after;
  const nothing =
    learned.ranges.length === 0 &&
    !potentialMoved &&
    learned.interests === null &&
    learned.tags.length === 0;
  return (
    <div
      data-testid="learned-card"
      data-person-id={learned.person_id}
      style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <span style={{ fontWeight: 600 }}>
        {learned.name}{' '}
        <span className="tst-muted" style={{ fontWeight: 400, fontSize: 12 }}>
          · {ACTION_TEXT[learned.action] ?? humanize(learned.action)}
        </span>
      </span>
      {nothing && (
        <span className="tst-muted" style={{ fontSize: 13 }}>
          Nothing new: what you knew already held up.
        </span>
      )}
      {shown.length > 0 && (
        <table className="tst-table" aria-label={`What narrowed for ${learned.name}`}>
          <tbody>
            {shown.map((r) => (
              <tr key={r.key} data-testid="learned-range">
                <td style={{ fontSize: 13 }}>{r.label}</td>
                <td>
                  <AttributeRange range={r.before} label={`${r.label} before`} />
                </td>
                <td className="tst-muted" aria-hidden>
                  →
                </td>
                <td>
                  <AttributeRange range={r.after} label={`${r.label} now`} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {others > 0 && (
        <span className="tst-muted" style={{ fontSize: 12 }}>
          and {others} other skill{others === 1 ? '' : 's'} narrowed
        </span>
      )}
      <span style={{ fontSize: 13 }} data-testid="learned-potential">
        Potential:{' '}
        {potentialMoved ? (
          <>
            <span className="tst-muted">{learned.potential_before}</span> →{' '}
            <strong>{learned.potential_after}</strong>
          </>
        ) : (
          <span className="tst-muted">still {learned.potential_after}</span>
        )}
      </span>
      {learned.interests !== null && (
        <span style={{ fontSize: 13 }}>
          Interests: {learned.interests.map((k) => interestLabel?.(k) ?? humanize(k)).join(', ')}
          {learned.work_style ? ` · works as a ${humanize(learned.work_style).toLowerCase()}` : ''}
        </span>
      )}
      {learned.tags.map((t) => (
        <span key={t.key} style={{ fontSize: 13, color: 'var(--tst-link)' }}>
          Noticed: {t.text}
        </span>
      ))}
    </div>
  );
}

export function LearnedPanel({
  learned,
  interestLabel,
  focus,
  onClose,
}: {
  learned: Learned[];
  interestLabel?: (key: string) => string;
  focus?: readonly string[];
  onClose: () => void;
}) {
  return (
    <aside
      className="tst-panel"
      aria-label="What you learned"
      data-testid="learned-panel"
      style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>What you learned</h2>
        <Button size="compact-sm" variant="subtle" onClick={onClose}>
          Close
        </Button>
      </div>
      {learned.length === 0 ? (
        <span className="tst-muted" style={{ fontSize: 13 }}>
          No candidates to learn about.
        </span>
      ) : (
        learned.map((l) => (
          <LearnedCard key={l.person_id} learned={l} interestLabel={interestLabel} focus={focus} />
        ))
      )}
    </aside>
  );
}
