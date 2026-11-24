import { Link } from 'react-router';
import { useMeetings } from '../hooks/meetings';
import { KpiTile } from './KpiTile';

/** Credibility (29.3, M48 59.2) on the company and market screens, with the way to this
 * month's meetings. */
export function CredibilityTile({ saveId }: { saveId: string }) {
  const q = useMeetings(saveId);
  if (!q.data) return null;
  const due = q.data.available.filter((a) => a.available && a.kind !== 'investor_day');
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
      <KpiTile
        term="credibility"
        label="Credibility"
        value={q.data.credibility.toFixed(0)}
        note="Kept and broken promises, guidance and commitments"
        testId="kpi-credibility"
      />
      <Link
        to={`/game/${saveId}/finance/meetings`}
        data-testid="meetings-link"
        style={{ fontSize: 13 }}
      >
        {due.length
          ? `This month: ${due.map((a) => (a.kind === 'board' ? 'board meeting' : 'earnings call')).join(' and ')}`
          : 'Meetings'}
      </Link>
    </div>
  );
}
