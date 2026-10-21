import { Alert, AppShell } from '@mantine/core';
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
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 200, breakpoint: 'xs' }}
      padding="md"
      styles={{
        main: { background: 'var(--tst-bg)' },
        header: { background: 'var(--tst-surface)', borderColor: 'var(--tst-border)' },
        navbar: { background: 'var(--tst-surface)', borderColor: 'var(--tst-border)' },
      }}
    >
      <AppShell.Header>
        <TopBar overview={overview.data} advancing={advance.isPending} onContinue={onContinue} />
      </AppShell.Header>
      <AppShell.Navbar>
        <LeftNav saveId={saveId} />
      </AppShell.Navbar>
      <AppShell.Main>
        {advance.error && (
          <Alert color="red" mb="md" title="Turn failed" withCloseButton onClose={advance.reset}>
            {advance.error.message}
          </Alert>
        )}
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
