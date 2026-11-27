import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// The smoke test runs its own API (fresh save folder) and Vite server on spare ports, so it
// never touches saves/ or a running `make dev`.
const API_PORT = Number(process.env.TST_E2E_API_PORT ?? 8765); // overridable to run beside `make playtest`
const WEB_PORT = Number(process.env.TST_E2E_WEB_PORT ?? 5175);
// M29 (42.5): the launcher serves the built front end and the API on one port.
const LAUNCHER_PORT = Number(process.env.TST_E2E_LAUNCHER_PORT ?? 5176);
// Kept in the environment so test workers (which load this file again) see the same folder;
// the M4c flow edits a save there with tools/e2e_set_arr.py.
process.env.TST_E2E_SAVE_DIR ??= mkdtempSync(join(tmpdir(), 'tst-e2e-'));
const saveDir = process.env.TST_E2E_SAVE_DIR;
// M35a: both API servers log every unhandled exception and 5xx response here; the global
// teardown fails the run on any the allow-list does not name (e2e/server-errors.ts).
process.env.TST_E2E_ERROR_LOG ??= join(saveDir, 'server-errors.jsonl');
const errorLog = process.env.TST_E2E_ERROR_LOG;

// PLAYWRIGHT_CHANNEL=msedge (or chrome) uses an installed browser instead of downloading
// Playwright's Chromium with `pnpm exec playwright install chromium`.
const channel = process.env.PLAYWRIGHT_CHANNEL;
// PLAYWRIGHT_CHROMIUM_PATH points at an installed Chromium whose version differs from the
// pinned Playwright's (cloud sessions).
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;

export default defineConfig({
  testDir: 'e2e',
  testIgnore: ['playtest/**'], // the agent playtest runs on demand: make playtest (M7c)
  fullyParallel: false,
  workers: 1,
  // M59: e2e/shard-reporter.ts splits `--shard=N/T` runs by measured file time (CI's four
  // `e2e (shard N/4)` jobs); without --shard it only records file times when asked to.
  reporter: [['list'], ['./e2e/shard-reporter.ts']],
  globalSetup: './e2e/server-errors-setup.ts',
  globalTeardown: './e2e/server-errors.ts',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel,
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
  ],
  webServer: [
    {
      command: `uv run uvicorn tst.api.app:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/api/meta/scenarios`,
      // No API key: events are written by templates, never by Claude (CLAUDE.md section 8).
      env: {
        TST_SAVE_DIR: saveDir,
        TST_ERROR_LOG: errorLog,
        ANTHROPIC_API_KEY: '',
        TST_ANTHROPIC_API_KEY: '',
        // M47: conversations on the mock adapter (never Claude), so e2e/m47.spec.ts can show the
        // cap switching them to template mode; events keep their templates
        TST_CONVERSATION_ADAPTER: 'mock',
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // The launcher as the shortcut runs it, without installing or opening a browser; it
      // builds frontend/dist first when that is missing or stale.
      command: `uv run --project backend python tools/launcher.py --no-browser --skip-install --port ${LAUNCHER_PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${LAUNCHER_PORT}/api/meta/scenarios`,
      env: {
        TST_SAVE_DIR: saveDir,
        TST_ERROR_LOG: errorLog,
        ANTHROPIC_API_KEY: '',
        TST_ANTHROPIC_API_KEY: '',
      },
      reuseExistingServer: false,
      timeout: 300_000,
    },
    {
      command: `pnpm exec vite --port ${WEB_PORT} --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { TST_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
