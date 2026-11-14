import { Link } from 'react-router';
import { Panel } from './ScreenState';
import { useOwnerRecord } from '../hooks/automation';

/**
 * An area owner's record on their profile (M27b sub-task 10, formulas.md 40.3): the areas they
 * run, decisions and missteps this year, proposals and their outcomes, pitches hit or missed,
 * their areas' latest KPIs and recent lines. Outcomes only: never a score or a draw.
 */
export function OwnerRecordPanel({ saveId, personId }: { saveId: string; personId: number }) {
  const record = useOwnerRecord(saveId, personId);
  const r = record.data;
  if (!r) return null;
  const any = r.areas.length > 0 || r.decisions_year > 0 || r.proposals > 0 || r.recent.length > 0;
  if (!any) return null;
  return (
    <Panel title="Areas they run" testId="owner-record">
      <div style={{ fontSize: 13 }}>
        {r.areas.length > 0 ? r.areas.join(', ') : 'No area now'} ·{' '}
        <Link to={`/game/${saveId}/automation`}>Automation</Link>
      </div>
      <div
        className="tst-muted"
        style={{ fontSize: 13, marginTop: 4 }}
        data-testid="owner-record-counts"
      >
        {r.decisions_year} decision{r.decisions_year === 1 ? '' : 's'} this year
        {r.mistakes_year ? ` (${r.mistakes_year} missteps)` : ''} · {r.proposals} proposal
        {r.proposals === 1 ? '' : 's'}: {r.proposals_approved} approved, {r.proposals_declined}{' '}
        declined, {r.proposals_expired} expired · pitches {r.pitches_hit} hit, {r.pitches_missed}{' '}
        missed
      </div>
      {(r.kpis ?? []).length > 0 && (
        <ul style={{ margin: '6px 0' }} className="tst-muted">
          {(r.kpis ?? []).map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
      )}
      {r.recent.length > 0 && (
        <ul style={{ margin: '6px 0' }}>
          {r.recent.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
