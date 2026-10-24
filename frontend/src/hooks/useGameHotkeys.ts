import { useEffect, useRef } from 'react';

// No hotkeys while typing. Space/Enter are also left alone on focused buttons and links, whose
// own activation already fires (handling both would advance twice); digits still jump there.
const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);
const ACTIVATING_TAGS = new Set(['BUTTON', 'A']);

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return TYPING_TAGS.has(target.tagName) || target.isContentEditable;
}

function isActivatingTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && ACTIVATING_TAGS.has(target.tagName);
}

/** Space/Enter -> Continue; 1-9 -> jump to the Nth left-nav screen. */
export function useGameHotkeys(onContinue: () => void, onJump: (index: number) => void) {
  const handlers = useRef({ onContinue, onJump });
  useEffect(() => {
    handlers.current = { onContinue, onJump };
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isTypingTarget(event.target)) return;
      if (event.key === ' ' || event.key === 'Enter') {
        if (isActivatingTarget(event.target)) return;
        event.preventDefault();
        handlers.current.onContinue();
      } else if (/^[1-9]$/.test(event.key)) {
        handlers.current.onJump(Number(event.key) - 1);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
