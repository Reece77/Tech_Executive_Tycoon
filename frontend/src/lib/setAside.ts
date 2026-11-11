// Setting a critical decision aside (M23c, playtest 5): the player closes the critical modal to
// look around read only, with a banner back to it; Continue stays blocked until it is answered.
// While it is set aside, the client refuses every request that would change the game, except
// answering the event itself and the read-only POSTs (previews, quotes, inbox marks, Explain).
import { useSyncExternalStore } from 'react';
import { api } from '../api/client';

const KEY = (saveId: string) => `tst.setAside.${saveId}`;
const listeners = new Set<() => void>();
const memory = new Map<string, number>();

function read(saveId: string): number | null {
  try {
    const raw = window.sessionStorage.getItem(KEY(saveId));
    if (raw !== null) return Number(raw);
  } catch {
    // storage blocked: fall back to memory
  }
  return memory.get(saveId) ?? null;
}

function write(saveId: string, eventId: number | null) {
  if (eventId === null) memory.delete(saveId);
  else memory.set(saveId, eventId);
  try {
    if (eventId === null) window.sessionStorage.removeItem(KEY(saveId));
    else window.sessionStorage.setItem(KEY(saveId), String(eventId));
  } catch {
    // storage blocked: memory holds it
  }
  listeners.forEach((l) => l());
}

export function setAside(saveId: string, eventId: number) {
  write(saveId, eventId);
}

export function returnToDecision(saveId: string) {
  write(saveId, null);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The critical event the player set aside, if it is still the one blocking. */
export function useSetAside(saveId: string, blockingEventId: number | null): boolean {
  const stored = useSyncExternalStore(subscribe, () => read(saveId));
  return blockingEventId !== null && stored === blockingEventId;
}

// --- The read-only guard -------------------------------------------------------------------

let readOnly = false;

/** Turn the guard on while a critical decision is set aside (GameLayout keeps it in step). */
export function setReadOnly(on: boolean) {
  readOnly = on;
}

/** Requests that change nothing, or that answer the decision: allowed while looking around. */
const ALLOWED: readonly RegExp[] = [
  /\/events\/\d+\/choose$/,
  /-preview$/,
  /\/preview$/,
  /\/quote$/,
  /\/hint$/,
  /\/inbox\//,
  /\/explain\/[^/]+\/ask$/,
  /\/coo\/ask$/,
  /^\/api\/settings\/ui\//,
  /^\/api\/profile\//,
  /^\/api\/meta\//,
];

export function allowedWhileReadOnly(method: string, pathname: string): boolean {
  if (method.toUpperCase() === 'GET') return true;
  return ALLOWED.some((re) => re.test(pathname));
}

export const READ_ONLY_MESSAGE =
  'You are looking around read only while a critical decision waits. Answer it first (the banner at the top takes you back).';

let installed = false;

/** Install the guard on the API client once. */
export function installReadOnlyGuard() {
  if (installed) return;
  installed = true;
  api.use({
    onRequest({ request }) {
      if (!readOnly) return undefined;
      const { pathname } = new URL(request.url, window.location.origin);
      if (allowedWhileReadOnly(request.method, pathname)) return undefined;
      return new Response(
        JSON.stringify({ code: 'read_only', message: READ_ONLY_MESSAGE, retryable: false }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      );
    },
  });
}
