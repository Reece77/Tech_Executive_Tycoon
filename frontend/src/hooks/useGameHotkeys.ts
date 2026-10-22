import { useEffect, useRef } from 'react';

// Keys are ignored while typing, and on focused buttons/links, whose own Space/Enter
// activation already fires (handling both would advance twice).
const IGNORE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A']);

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return IGNORE_TAGS.has(target.tagName) || target.isContentEditable;
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
