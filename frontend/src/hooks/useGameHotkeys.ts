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

export interface ExtraHotkeys {
  onHoliday?: () => void; // H (M7b)
  onHelp?: () => void; // ? shows every shortcut (M7b)
}

/** The search box of the table on screen (M7b: `/` focuses it). */
export const TABLE_SEARCH_ATTR = 'data-table-search';

/** Focus the first table search box on the page; false if there is none. */
export function focusTableSearch(): boolean {
  const box = document.querySelector<HTMLElement>(`[${TABLE_SEARCH_ATTR}]`);
  if (!box) return false;
  box.focus();
  return true;
}

/** Space/Enter -> Continue; 1-9 and 0 -> jump to the Nth left-nav screen; H -> Holiday;
 *  / -> the table search; ? -> the shortcut list. */
export function useGameHotkeys(
  onContinue: () => void,
  onJump: (index: number) => void,
  extra: ExtraHotkeys = {},
) {
  const handlers = useRef({ onContinue, onJump, extra });
  useEffect(() => {
    handlers.current = { onContinue, onJump, extra };
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isTypingTarget(event.target)) return;
      if (event.key === ' ' || event.key === 'Enter') {
        if (isActivatingTarget(event.target)) return;
        event.preventDefault();
        handlers.current.onContinue();
      } else if (/^[0-9]$/.test(event.key)) {
        handlers.current.onJump((Number(event.key) + 9) % 10); // 1-9, then 0 for the tenth
      } else if (event.key === 'h' || event.key === 'H') {
        handlers.current.extra.onHoliday?.();
      } else if (event.key === '/') {
        if (focusTableSearch()) event.preventDefault();
      } else if (event.key === '?') {
        handlers.current.extra.onHelp?.();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
