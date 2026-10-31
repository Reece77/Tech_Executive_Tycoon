import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// The smoke test runs its own API (fresh save folder) and Vite server on spare ports, so it
// never touches saves/ or a running `make dev`.
const API_PORT = Number(process.env.TST_E2E_API_PORT ?? 8765); // overridable to run beside `make playtest`
const WEB_PORT = Number(process.env.TST_E2E_WEB_PORT ?? 5175);
// Kept in the environment so test workers (which load this file again) see the same folder;
// the M4c flow edits a save there with tools/e2e_set_arr.py.
process.env.TST_E2E_SAVE_DIR ??= mkdtempSync(join(tmpdir(), 'tst-e2e-'));
const saveDir = process.env.TST_E2E_SAVE_DIR;

// PLAYWRIGHT_CHANNEL=msedge (or chrome) uses an installed browser instead of downloading
// Playwright's Chromium with `pnpm exec playwright install chromium`.
const channel = process.env.PLAYWRIGHT_CHANNEL;

export default defineConfig({
  testDir: 'e2e',
  testIgnore: ['playtest/**'], // the agent playtest runs on demand: make playtest (M7c)
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel } }],
  webServer: [
    {
      command: `uv run uvicorn tst.api.app:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/api/meta/scenarios`,
      // No API key: events are written by templates, never by Claude (CLAUDE.md section 8).
      env: { TST_SAVE_DIR: saveDir, ANTHROPIC_API_KEY: '', TST_ANTHROPIC_API_KEY: '' },
      reuseExistingServer: false,
      timeout: 60_000,
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
