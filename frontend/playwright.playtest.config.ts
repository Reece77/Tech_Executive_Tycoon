import { defineConfig } from '@playwright/test';
import base from './playwright.config';

// The M7c agent playtest (e2e/playtest): 120 months through the browser, on demand only
// (`make playtest`), with the same servers as `make e2e`.
export default defineConfig({
  ...base,
  testDir: 'e2e/playtest',
  testIgnore: [],
  use: {
    ...base.use,
    viewport: { width: 1440, height: 900 },
    actionTimeout: 15_000, // a missing element fails its step instead of hanging the run
    navigationTimeout: 30_000,
  },
});
