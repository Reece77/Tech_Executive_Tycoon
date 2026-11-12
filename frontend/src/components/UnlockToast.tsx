import { CloseButton } from '@mantine/core';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useUnlocks, type System } from '../hooks/onboarding';

// Unlock toasts (M29, 42.1): a screen that opened this month says what it is, why it opened
// and links to its guide page; shown once per screen in this browser session.

const SHOW_MS = 15_000;
const seenKey = (saveId: string) => `tst.unlock-toasts.${saveId}`;

function seen(saveId: string): Set<string> {
  try {
    return new Set(JSON.parse(window.sessionStorage.getItem(seenKey(saveId)) ?? '[]') as string[]);
  } catch {
    return new Set();
  }
}

function remember(saveId: string, keys: Iterable<string>) {
  try {
    const all = seen(saveId);
    for (const k of keys) all.add(k);
    window.sessionStorage.setItem(seenKey(saveId), JSON.stringify([...all]));
  } catch {
    // a convenience only
  }
}

export function UnlockToasts({ saveId }: { saveId: string }) {
  const data = useUnlocks(saveId).data;
  const [shown, setShown] = useState<System[]>([]);
  const marked = useRef(new Set<string>());

  useEffect(() => {
    if (!data) return;
    const already = seen(saveId);
    const fresh = data.systems.filter(
      (s) => data.fresh.includes(s.key) && !already.has(s.key) && !marked.current.has(s.key),
    );
    if (fresh.length === 0) return;
    for (const s of fresh) marked.current.add(s.key);
    remember(
      saveId,
      fresh.map((s) => s.key),
    );
    setShown((cur) => [...cur, ...fresh]);
    const keys = new Set(fresh.map((s) => s.key));
    const timer = setTimeout(() => setShown((cur) => cur.filter((s) => !keys.has(s.key))), SHOW_MS);
    return () => clearTimeout(timer);
  }, [data, saveId]);

  if (shown.length === 0) return null;
  return (
    <div
      style={{
        position: 'fixed',
        left: 16,
        bottom: 16,
        zIndex: 400,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 340,
      }}
      aria-live="polite"
    >
      {shown.map((s) => (
        <div
          key={s.key}
          className="tst-panel"
          role="status"
          data-testid="unlock-toast"
          data-key={s.key}
          style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 14px' }}
        >
          <div style={{ flex: 1 }}>
            <div className="tst-muted" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              New screen
            </div>
            <div style={{ fontWeight: 600 }}>{s.label}</div>
            <div className="tst-muted" style={{ fontSize: 13 }}>
              Open because {s.reason ?? 'you opened it'}.{' '}
              <Link to={`/game/${saveId}/guide/${s.key}`}>What it does</Link>
            </div>
          </div>
          <CloseButton
            size="sm"
            aria-label={`Close the ${s.label} notice`}
            onClick={() => setShown((cur) => cur.filter((x) => x.key !== s.key))}
          />
        </div>
      ))}
    </div>
  );
}
