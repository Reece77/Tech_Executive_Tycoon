import { Alert } from '@mantine/core';
import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate, useParams } from 'react-router';
import { CriticalEventModal } from '../components/EventCard';
import { HolidayDialog, HolidayStrip } from '../components/Holiday';
import { LeftNav } from '../components/LeftNav';
import { ScreenErrorBoundary } from '../components/ScreenErrorBoundary';
import { ShortcutHelp } from '../components/ShortcutHelp';
import { TopBar } from '../components/TopBar';
import { useAdvance, useEvents, useFinanceSummary, useHoliday, useOverview } from '../hooks/api';
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
  const events = useEvents(saveId);
  // An open critical event blocks Continue until answered (M6, ADR-0006 amended).
  const blocked = events.data?.blocking_event_id != null;
  const holiday = useHoliday(saveId);
  const away = holiday.data?.status === 'running';
  const [holidayOpen, setHolidayOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const canHoliday = overview.data !== undefined && !ended && !blocked && !away;

  const onContinue = () => {
    if (overview.data && !advance.isPending && !ended && !blocked && !away) {
      advance.mutate(undefined, {
        // The month that ends the game opens the game over screen (ADR-0018).
        onSuccess: (next) => {
          if (next.game_state !== 'active') void navigate(`/game/${saveId}/over`);
        },
      });
    }
  };
  const onHoliday = () => {
    if (canHoliday && !advance.isPending) setHolidayOpen(true);
  };
  useGameHotkeys(
    onContinue,
    (index) => {
      const item = NAV_ITEMS[index];
      if (item) void navigate(`/game/${saveId}/${item.path}`);
    },
    { onHoliday, onHelp: () => setHelpOpen(true) },
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopBar
        overview={overview.data}
        summary={summary.data}
        advancing={advance.isPending}
        blocked={blocked}
        away={away}
        onContinue={onContinue}
        onHoliday={onHoliday}
      />
      <HolidayStrip saveId={saveId} />
      {holidayOpen && holiday.data && (
        <HolidayDialog
          saveId={saveId}
          holiday={holiday.data}
          onClose={() => setHolidayOpen(false)}
        />
      )}
      {helpOpen && <ShortcutHelp onClose={() => setHelpOpen(false)} />}
      {!ended && !away && <CriticalEventModal saveId={saveId} />}
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
