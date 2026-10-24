import { Alert } from '@mantine/core';
import { Outlet, useNavigate, useParams } from 'react-router';
import { LeftNav } from '../components/LeftNav';
import { TopBar } from '../components/TopBar';
import { useAdvance, useOverview } from '../hooks/api';
import { useGameHotkeys } from '../hooks/useGameHotkeys';
import { NAV_ITEMS } from '../lib/nav';

export function GameLayout() {
  const { saveId = '' } = useParams();
  const navigate = useNavigate();
  const overview = useOverview(saveId);
  const advance = useAdvance(saveId);

  const onContinue = () => {
    if (overview.data && !advance.isPending) advance.mutate();
  };
  useGameHotkeys(onContinue, (index) => {
    const item = NAV_ITEMS[index];
    if (item) void navigate(`/game/${saveId}/${item.path}`);
  });

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopBar overview={overview.data} advancing={advance.isPending} onContinue={onContinue} />
      <div className="tst-shell-body">
        <LeftNav saveId={saveId} unread={overview.data?.unread_inbox ?? 0} />
        <main className="tst-main">
          {overview.error && (
            <Alert color="red" title="Could not load the game" role="alert">
              {overview.error.message}
            </Alert>
          )}
          {advance.error && (
            <Alert color="red" title="Turn failed" withCloseButton onClose={advance.reset}>
              {advance.error.message}
            </Alert>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
