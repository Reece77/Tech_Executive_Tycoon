// The command palette's matching and hotkey (M29, 42.4).
import { useEffect } from 'react';

export interface Option {
  key: string;
  label: string;
  detail: string;
  kind: string;
  path: string;
}

/** Options matching every word of the query, screens first, best (prefix) matches first. */
export function matchOptions(options: readonly Option[], query: string): Option[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const scored = options
    .map((o) => {
      const hay = `${o.label} ${o.detail}`.toLowerCase();
      if (!words.every((w) => hay.includes(w))) return null;
      const label = o.label.toLowerCase();
      const score = (label.startsWith(words[0]) ? 0 : 2) + (o.kind === 'screen' ? 0 : 1);
      return { o, score };
    })
    .filter((x): x is { o: Option; score: number } => x !== null);
  scored.sort((a, b) => a.score - b.score || a.o.label.localeCompare(b.o.label));
  return scored.map((x) => x.o);
}

/** Ctrl+K and Cmd+K open the palette, even while typing elsewhere. */
export function usePaletteHotkey(onOpen: () => void) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        onOpen();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onOpen]);
}
