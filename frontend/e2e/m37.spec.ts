import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M37 flows (formulas.md 52): (a) a standard game's December 2039 summary offers to continue,
// and continuing plays on in dynasty mode; (b) a dynasty game shows a post-2039 era arriving.
// Saves come from tools/e2e_m37_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m37_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

test('(a) the December 2039 summary offers to continue in dynasty mode', async ({ page }) => {
  const save = `m37-end-${stamp}`;
  tool('end', save);
  await page.goto(`/game/${save}/overview`);
  await expect(page).toHaveURL(new RegExp(`/game/${save}/over$`));
  await expect(page.getByTestId('over-kicker')).toContainText('Campaign summary');
  await expect(page.getByTestId('campaign-end')).toBeVisible();
  await page.getByTestId('continue-dynasty').click();
  await expect(page).toHaveURL(new RegExp(`/game/${save}/overview$`));
  const campaign = await (await page.request.get(`/api/saves/${save}/campaign`)).json();
  expect(campaign.length).toBe('dynasty');
  expect(campaign.end_label).toBe('Dec 2069');
});

test('(b) a dynasty game shows a post-2039 era arriving', async ({ page }) => {
  const save = `m37-era-${stamp}`;
  tool('era', save);
  await page.goto(`/game/${save}/products/research`);
  const era = page.getByTestId('era-fusion_power');
  await expect(era).toBeVisible();
  await expect(era.getByTestId('era-arrived')).toBeVisible();
});
