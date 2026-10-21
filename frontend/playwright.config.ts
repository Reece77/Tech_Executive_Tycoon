import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// The smoke test runs its own API (fresh save folder) and Vite server on spare ports, so it
// never touches saves/ or a running `make dev`.
const API_PORT = 8765;
const WEB_PORT = 5175;
const saveDir = mkdtempSync(join(tmpdir(), 'tst-e2e-'));

// PLAYWRIGHT_CHANNEL=msedge (or chrome) uses an installed browser instead of downloading
// Playwright's Chromium with `pnpm exec playwright install chromium`.
const channel = process.env.PLAYWRIGHT_CHANNEL;

export default defineConfig({
  testDir: 'e2e',
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
      env: { TST_SAVE_DIR: saveDir },
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
