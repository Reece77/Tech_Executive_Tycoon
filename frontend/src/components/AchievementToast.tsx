import { CloseButton } from '@mantine/core';
import { useEffect, useRef, useState } from 'react';
import { useMarkSeen, useSaveAchievements, type Achievement } from '../hooks/profile';

// Achievement toasts (M25 section 2): each newly earned achievement shows once, bottom right,
// and is marked seen in the profile as it appears.

const SHOW_MS = 12_000; // how long a toast stays before it fades on its own
const MAX_SHOWN = 3; // toasts at once; the rest are counted on a last line

export function AchievementToasts({ saveId }: { saveId: string }) {
  const data = useSaveAchievements(saveId).data;
  const markSeen = useMarkSeen();
  const [shown, setShown] = useState<Achievement[]>([]);
  const marked = useRef(new Set<string>());
  const unseen = data?.unseen;

  useEffect(() => {
    const fresh = (unseen ?? []).filter((a) => !marked.current.has(a.key));
    if (fresh.length === 0) return;
    for (const a of fresh) marked.current.add(a.key);
    setShown((s) => [...s, ...fresh]);
    markSeen.mutate(fresh.map((a) => a.key));
    const keys = new Set(fresh.map((a) => a.key));
    const timer = setTimeout(() => setShown((s) => s.filter((a) => !keys.has(a.key))), SHOW_MS);
    return () => clearTimeout(timer);
    // markSeen is stable enough; the effect runs when new achievements arrive
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unseen]);

  if (shown.length === 0) return null;
  return (
    <div
      style={{
        position: 'fixed',
        right: 16,
        bottom: 16,
        zIndex: 400,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 340,
        pointerEvents: 'none', // never in the way of a click on the screen beneath
      }}
      aria-live="polite"
    >
      {shown.slice(0, MAX_SHOWN).map((a) => (
        <div
          key={a.key}
          className="tst-panel"
          role="status"
          data-testid="achievement-toast"
          data-key={a.key}
          style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 14px' }}
        >
          <div style={{ flex: 1 }}>
            <div className="tst-muted" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              Achievement
            </div>
            <div style={{ fontWeight: 600 }}>{a.title}</div>
            <div className="tst-muted" style={{ fontSize: 12 }}>
              {a.description}
            </div>
          </div>
          <CloseButton
            style={{ pointerEvents: 'auto' }}
            size="sm"
            aria-label="Dismiss"
            onClick={() => setShown((s) => s.filter((x) => x.key !== a.key))}
          />
        </div>
      ))}
      {shown.length > MAX_SHOWN && (
        <div className="tst-panel tst-muted" style={{ padding: '6px 14px', fontSize: 12 }}>
          +{shown.length - MAX_SHOWN} more: see Achievements on the main menu
        </div>
      )}
    </div>
  );
}
