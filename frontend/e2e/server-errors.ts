// M35a: e2e fails on any server error. Both API servers in playwright.config.ts write every
// unhandled exception and 5xx response to TST_ERROR_LOG (backend/tst/api/error_log.py); this
// global teardown reads that file after the run and throws (failing the run) on any line the
// allow-list below does not name. Add an entry only for an error a flow means to cause, with
// the reason.
import { existsSync, readFileSync } from 'node:fs';

export interface ServerError {
  method: string;
  path: string;
  status: number;
  error: string | null;
  where: string | null;
}

interface Allowed {
  path: RegExp;
  error?: RegExp;
  reason: string;
}

// Intended server errors: none today. M35a fixed the two main's logs showed (the M&A screen of
// a founded subsidiary, an event naming someone who had left).
export const ALLOWED: Allowed[] = [];

export function unlisted(errors: ServerError[], allowed: Allowed[] = ALLOWED): ServerError[] {
  return errors.filter(
    (e) =>
      !allowed.some(
        (a) => a.path.test(e.path) && (a.error === undefined || a.error.test(e.error ?? '')),
      ),
  );
}

export function readErrors(file: string): ServerError[] {
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf-8')
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => JSON.parse(line) as ServerError);
}

export default function checkServerErrors(): void {
  const file = process.env.TST_E2E_ERROR_LOG;
  if (!file) return;
  const bad = unlisted(readErrors(file));
  if (bad.length === 0) return;
  const lines = bad.map(
    (e) =>
      `  ${e.method} ${e.path} -> ${e.status} ${e.error ?? ''}${e.where ? ` at ${e.where}` : ''}`,
  );
  throw new Error(
    `The server logged ${bad.length} error(s) no flow means to cause ` +
      `(allow-list: e2e/server-errors.ts):\n${lines.join('\n')}`,
  );
}
