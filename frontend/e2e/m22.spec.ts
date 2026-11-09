import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M22 flows (formulas.md 39): (a) the World screen in October 2022 shows the new chip rules;
// (b) launch a compliant accelerator variant and keep China sales; (c) a gallium ban raises a
// chip's cost; (d) a licence request approved with high influence. Saves come from
// tools/e2e_m22_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m22_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

/** The gallium row's price premium, as a percentage. */
async function galliumPremium(page: Page): Promise<number> {
  const row = page.getByTestId('supply-row').filter({ hasText: /LatticeGallium/ });
  await expect(row).toHaveCount(1);
  const text = (await row.textContent()) ?? '';
  const m = /\+(\d+)%/.exec(text);
  if (!m) throw new Error(`no premium in ${text}`);
  return Number(m[1]);
}

test('(a) the World screen in October 2022 shows the new chip rules', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m22-chips-a-${stamp}`;
  tool('chips', save);
  await page.goto(`/game/${save}/competitors`);
  await page.getByTestId('world-link').click();
  await expect(page.getByTestId('tension')).toContainText('75/100');
  const rule = page
    .getByTestId('rule-row')
    .filter({ hasText: 'US advanced computing and semiconductor rules' });
  await expect(rule).toContainText('In force');
  await expect(rule).toContainText('China');
  await expect(page.getByTestId('exposure-row')).toContainText('east_asia: 55% closed');
  // October 2023's update is not announced yet
  await expect(page.getByTestId('rules-panel')).not.toContainText('Update to the October 2022');
});

test('(b) a compliant accelerator variant keeps China sales', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m22-chips-b-${stamp}`;
  tool('chips', save);
  await page.goto(`/game/${save}/competitors/world`);
  await page.getByTestId('launch-variant').click();
  const row = page.getByTestId('exposure-row');
  await expect(row).toContainText('as variant');
  await expect(page.getByTestId('variant-row')).toContainText('Compliant variant of Accel');
  await continueMonth(page);
  await page.goto(`/game/${save}/competitors/world`);
  await expect(page.getByTestId('exposure-row')).toContainText('as variant');
});

test('(c) a gallium ban raises a chip’s cost', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m22-gallium-${stamp}`;
  tool('gallium', save);
  await page.goto(`/game/${save}/competitors/world`);
  const licensing = await galliumPremium(page); // November 2024: China's licensing
  await continueMonth(page);
  await page.goto(`/game/${save}/competitors/world`);
  await expect(page.getByTestId('rules-panel')).toContainText(
    'China bans gallium, germanium and antimony exports to the US',
  );
  const ban = await galliumPremium(page); // December 2024: the ban to the US
  expect(ban).toBeGreaterThan(licensing);
});

test('(d) a licence request is approved with high influence', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m22-influence-${stamp}`;
  tool('influence', save);
  await page.goto(`/game/${save}/competitors/world`);
  await page.getByTestId('request-licence').click();
  await expect(page.getByTestId('licence-row')).toContainText('pending');
  for (let i = 0; i < 3; i++) await continueMonth(page);
  await page.goto(`/game/${save}/competitors/world`);
  await expect(page.getByTestId('licence-row')).toContainText('approved');
  await expect(page.getByTestId('exposure-row')).not.toContainText('closed');
});
