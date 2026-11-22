import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M43 flow: the conglomerate view and the January letter on a 2039 save with at least four
// industries (full_integrator's chain group: software, devices, chips, mining and materials).
// The save comes from tools/e2e_m43_save.py (a few minutes: thirty years played).
test.describe.configure({ mode: 'serial', timeout: 900_000 });

const stamp = Date.now();
const FORBIDDEN = ['potential', 'true_', 'hidden_', 'current_ability'];

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m43_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32', timeout: 840_000 },
  ).toString();
}

test('the conglomerate view and the letter to shareholders on a 2039 group', async ({ page }) => {
  const save = `m43-group-${stamp}`;
  tool('group', save);
  const response = await page.request.get(`/api/saves/${save}/conglomerate`);
  const body = await response.text();
  for (const word of FORBIDDEN) expect(body).not.toContain(word);
  const data = JSON.parse(body);
  expect(data.industries.length).toBeGreaterThanOrEqual(4);

  await page.goto(`/game/${save}/finance/conglomerate`);
  await expect(page.getByTestId('conglomerate-tab')).toBeVisible();
  await expect(page.getByTestId('conglomerate-industry')).toHaveCount(data.industries.length);
  await expect(page.getByTestId('conglomerate-company').first()).toBeVisible();
  await expect(page.getByTestId('conglomerate-allocation-row').first()).toBeVisible();
  await expect(page.getByTestId('conglomerate-capital-year').first()).toBeVisible();
  await expect(page.getByTestId('letter-text')).toContainText('Dear shareholders');

  // the letter is kept in History
  const timeline = await (
    await page.request.get(`/api/saves/${save}/history/timeline?search=Letter`)
  ).json();
  expect(timeline.rows.map((r: { title: string }) => r.title)).toContain(
    'Letter to shareholders, 2038',
  );
  await page.goto(`/game/${save}/history/timeline`);
  await page.getByTestId('history-search').fill('Letter to shareholders');
  await expect(page.getByText('Letter to shareholders, 2038').first()).toBeVisible();
});
