import { Alert } from '@mantine/core';
import { Link, Outlet, useLocation, useNavigate, useParams } from 'react-router';
import { LeftNav } from '../components/LeftNav';
import { ScreenErrorBoundary } from '../components/ScreenErrorBoundary';
import { TopBar } from '../components/TopBar';
import { useAdvance, useFinanceSummary, useOverview } from '../hooks/api';
import { useGameHotkeys } from '../hooks/useGameHotkeys';
import { NAV_ITEMS } from '../lib/nav';

export function GameLayout() {
  const { saveId = '' } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const overview = useOverview(saveId);
  const summary = useFinanceSummary(saveId);
  const advance = useAdvance(saveId);
  const ended = overview.data !== undefined && overview.data.game_state !== 'active';

  const onContinue = () => {
    if (overview.data && !advance.isPending && !ended) {
      advance.mutate(undefined, {
        // The month that ends the game opens the game over screen (ADR-0018).
        onSuccess: (next) => {
          if (next.game_state !== 'active') void navigate(`/game/${saveId}/over`);
        },
      });
    }
  };
  useGameHotkeys(onContinue, (index) => {
    const item = NAV_ITEMS[index];
    if (item) void navigate(`/game/${saveId}/${item.path}`);
  });

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopBar
        overview={overview.data}
        summary={summary.data}
        advancing={advance.isPending}
        onContinue={onContinue}
      />
      <div className="tst-shell-body">
        <LeftNav saveId={saveId} unread={overview.data?.unread_inbox ?? 0} />
        <main className="tst-main">
          {overview.error && (
            <Alert color="red" title="Could not load the game" role="alert">
              {overview.error.message}
            </Alert>
          )}
          {ended && (
            <Alert color="warn" title="The game is over" data-testid="game-over-banner">
              The save stays readable. <Link to={`/game/${saveId}/over`}>See how it ended</Link>.
            </Alert>
          )}
          {advance.error && (
            <Alert color="red" title="Turn failed" withCloseButton onClose={advance.reset}>
              {advance.error.message}
            </Alert>
          )}
          <ScreenErrorBoundary key={location.pathname}>
            <Outlet />
          </ScreenErrorBoundary>
        </main>
      </div>
    </div>
  );
}
