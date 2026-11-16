// M35a: start each run with an empty server-error log (e2e/server-errors.ts reads it after).
import { rmSync } from 'node:fs';

export default function clearServerErrors(): void {
  const file = process.env.TST_E2E_ERROR_LOG;
  if (file) rmSync(file, { force: true });
}
