import { Link, useParams } from 'react-router';
import { useRelationships, useTeamMood } from '../hooks/api';
import { Panel } from './ScreenState';

const LABEL_COLOR: Record<string, string> = {
  close: 'var(--tst-good)',
  good: 'var(--tst-good)',
  neutral: 'var(--tst-text-2)',
  strained: 'var(--tst-warn)',
  hostile: 'var(--tst-warn)',
};

/** The profile's Relationships panel (M6): unit-mates and manager links with a label,
 * never a number (formulas.md 16.9). */
export function RelationshipsPanel({ saveId, personId }: { saveId: string; personId: number }) {
  const rels = useRelationships(saveId, personId);
  if (!rels.data || rels.data.length === 0) return null;
  return (
    <Panel title="Relationships">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rels.data.map((r) => (
          <div
            key={r.person_id}
            style={{ display: 'flex', gap: 8, fontSize: 13 }}
            data-testid="relationship"
          >
            <Link to={`/game/${saveId}/people/${r.person_id}`}>{r.name}</Link>
            <span className="tst-muted">{r.link}</span>
            <span style={{ marginLeft: 'auto', color: LABEL_COLOR[r.label] }}>{r.label}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/** The org unit panel's "Team mood" line (M6): strained or hostile pairs in the unit. */
export function TeamMoodLine({ unitId }: { unitId: number | null }) {
  const { saveId = '' } = useParams();
  const mood = useTeamMood(saveId, unitId);
  if (!mood.data) return null;
  return (
    <div style={{ fontSize: 13 }} data-testid="team-mood">
      <span className="tst-muted">Team mood: </span>
      <span style={{ color: mood.data.pairs.length ? 'var(--tst-warn)' : undefined }}>
        {mood.data.line}
      </span>
    </div>
  );
}
