import { Alert } from '@mantine/core';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate, useParams } from 'react-router';
import { AchievementToasts } from '../components/AchievementToast';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { RunBy } from '../components/RunBy';
import { CommandPalette } from '../components/CommandPalette';
import { CooPanel } from '../components/CooPanel';
import { CriticalEventModal, SetAsideBanner } from '../components/EventCard';
import { HolidayDialog, HolidayStrip } from '../components/Holiday';
import { LeftNav } from '../components/LeftNav';
import { ScreenErrorBoundary } from '../components/ScreenErrorBoundary';
import { ShortcutHelp } from '../components/ShortcutHelp';
import { TopBar } from '../components/TopBar';
import { UnlockToasts } from '../components/UnlockToast';
import { useAdvance, useEvents, useFinanceSummary, useHoliday, useOverview } from '../hooks/api';
import { useContinueUntil } from '../hooks/modes';
import { usePalette } from '../hooks/onboarding';
import { useGameHotkeys } from '../hooks/useGameHotkeys';
import { answerHref, NAV_ITEMS } from '../lib/nav';
import { usePaletteHotkey } from '../lib/palette';
import { pushRecent } from '../lib/recent';
import { installReadOnlyGuard, setReadOnly, useSetAside } from '../lib/setAside';

installReadOnlyGuard();

export function GameLayout() {
  const { saveId = '' } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const overview = useOverview(saveId);
  const summary = useFinanceSummary(saveId);
  const advance = useAdvance(saveId);
  const until = useContinueUntil(saveId); // M15b (30.5)
  const ended = overview.data !== undefined && overview.data.game_state !== 'active';
  const events = useEvents(saveId);
  // Open major and critical events block Continue until answered (23.1, M10b); a critical
  // one also opens as a modal (M6).
  const blocking = events.data?.blocking_event_ids.length ?? 0;
  const proposals =
    (events.data?.blocking_proposal_ids.length ?? 0) + // M10c (24.1)
    (events.data?.blocking_pitch_ids?.length ?? 0); // M13b (27.1): pitches block too
  const blocked = blocking + proposals > 0;
  // M23c: a critical decision set aside makes the game read only until it is answered.
  const aside = useSetAside(saveId, events.data?.blocking_event_id ?? null);
  useEffect(() => {
    setReadOnly(aside);
    return () => setReadOnly(false);
  }, [aside]);
  const holiday = useHoliday(saveId);
  const away = holiday.data?.status === 'running';
  const [holidayOpen, setHolidayOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [cooOpen, setCooOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false); // M29 (42.4): Ctrl+K
  usePaletteHotkey(useCallback(() => setPaletteOpen(true), []));
  // Recent items (42.4): a person, product or rival page visited goes first in the palette.
  const palette = usePalette(saveId);
  const names = useMemo(
    () => new Map((palette.data?.entries ?? []).map((e) => [e.path, e] as const)),
    [palette.data],
  );
  const here = location.pathname.replace(`/game/${saveId}/`, '');
  useEffect(() => {
    const entry = names.get(here);
    if (entry) pushRecent(saveId, { label: entry.label, path: entry.path, kind: entry.kind });
  }, [here, names, saveId]);
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
  const onContinueUntil = () => {
    if (overview.data && !advance.isPending && !until.isPending && !ended && !blocked && !away) {
      until.mutate(undefined, {
        onSuccess: (out) => {
          if (out.stopped_for === 'game_over') void navigate(`/game/${saveId}/over`);
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
    <div className="tst-shell" data-testid="game-shell">
      <TopBar
        overview={overview.data}
        summary={summary.data}
        advancing={advance.isPending}
        blocking={blocking}
        proposals={proposals}
        eventsHref={answerHref(saveId, events.data?.blocking_event_ids ?? [], proposals)}
        away={away}
        onContinue={onContinue}
        onContinueUntil={onContinueUntil}
        untilRunning={until.isPending}
        onHoliday={onHoliday}
        onCoo={() => setCooOpen(true)}
      />
      {cooOpen && <CooPanel saveId={saveId} onClose={() => setCooOpen(false)} />}
      <AchievementToasts saveId={saveId} />
      <UnlockToasts saveId={saveId} />
      <CommandPalette saveId={saveId} opened={paletteOpen} onClose={() => setPaletteOpen(false)} />
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
      {!ended && !away && <SetAsideBanner saveId={saveId} />}
      <div className="tst-shell-body">
        <LeftNav
          saveId={saveId}
          unread={overview.data?.unread_inbox ?? 0}
          onSearch={() => setPaletteOpen(true)}
        />
        <main className="tst-main" data-testid="working-pane">
          <Breadcrumbs saveId={saveId} />
          <RunBy />
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
          {until.data && !until.isPending && (
            <Alert
              color="blue"
              title={`Played ${until.data.months_played} month${until.data.months_played === 1 ? '' : 's'}, to ${until.data.date_label}`}
              withCloseButton
              onClose={until.reset}
              data-testid="continue-until-stopped"
            >
              Stopped: {until.data.stopped_label}
            </Alert>
          )}
          {until.error && (
            <Alert color="red" title="Continue until failed" withCloseButton onClose={until.reset}>
              {until.error.message}
            </Alert>
          )}
          {advance.error && (
            <Alert color="red" title="Turn failed" withCloseButton onClose={advance.reset}>
              {advance.error.message}
            </Alert>
          )}
          {/* A new screen resets the boundary; opening another message (/inbox/:id, M7c) does
              not, so the inbox keeps its folder filter. */}
          <ScreenErrorBoundary key={location.pathname.replace(/\/inbox\/\d+$/, '/inbox')}>
            <Outlet />
          </ScreenErrorBoundary>
        </main>
      </div>
    </div>
  );
}
