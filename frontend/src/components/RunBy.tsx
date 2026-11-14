import { Button } from '@mantine/core';
import { Link, useLocation, useParams } from 'react-router';
import { useAutomation, useTakeBackArea } from '../hooks/automation';

/** "Run by <name> (<role>) · Take back" on every screen whose area is automated (40.8). */
export function RunBy() {
  const { saveId = '' } = useParams();
  const location = useLocation();
  const auto = useAutomation(saveId);
  const takeBack = useTakeBackArea(saveId);
  const here = location.pathname.replace(`/game/${saveId}/`, '').replace(/\/\d+$/, '');
  const owned = (auto.data?.areas ?? []).filter(
    (a) => a.status === 'automated' && a.owner && a.screen === here,
  );
  if (owned.length === 0) return null;
  return (
    <div
      className="tst-muted"
      style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 13, marginBottom: 8 }}
      data-testid="run-by"
    >
      {owned.map((a) => (
        <span key={a.area}>
          {a.label}: run by {a.owner?.name}
          {a.owner?.role ? ` (${a.owner.role})` : ''} ·{' '}
          <Button
            size="compact-xs"
            variant="subtle"
            disabled={takeBack.isPending}
            onClick={() => takeBack.mutate(a.area)}
            data-testid={`header-take-back-${a.area}`}
          >
            Take back
          </Button>{' '}
          · <Link to={`/game/${saveId}/automation`}>Automation</Link>
        </span>
      ))}
    </div>
  );
}
