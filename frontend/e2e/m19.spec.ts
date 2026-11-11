import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M19 flows (formulas.md 35): (a) found a mining subsidiary and transfer a permitted project
// into it (then order the mine); (b) watch construction end, the ramp-up and first sales;
// (c) a price crash and care and maintenance; (d) a scripted accident's critical event. Saves
// come from tools/e2e_m19_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m19_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

test('(a) found a mining subsidiary and move a permitted project into it', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m19-found-${stamp}`;
  tool('holder', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('mines-link').click();
  await expect(page.getByTestId('quote-row')).toHaveCount(1);
  // M23c: founding a subsidiary is on the Group screen, linked from Mines
  await page.getByTestId('found-link').click();
  await expect(page.getByTestId('group-found')).toBeVisible();
  await page.getByTestId('found-name').fill('Ironbark Mining');
  await page.getByTestId('found-subsidiary').click();
  await expect(page.getByTestId('group-found-done')).toBeVisible();
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('company-row')).toHaveCount(2);
  await expect(page.getByTestId('companies-panel')).toContainText('Ironbark Mining');
  await page.getByTestId('asset-select').click();
  await page.getByRole('option', { name: /permitted/ }).click();
  await page.getByTestId('to-select').click();
  await page.getByRole('option', { name: 'Ironbark Mining' }).click();
  await page.getByTestId('transfer').click();
  await expect(page.getByTestId('quote-row')).toContainText('Ironbark Mining');
  await page.getByTestId('build-mine').click();
  await expect(page.getByTestId('mine-row')).toHaveCount(1);
  await expect(page.getByTestId('mine-status')).toContainText(/building/i);
  await expect(page.getByTestId('mine-capex')).toContainText("the study's estimate");
});

test('(b) a mine ends construction, ramps up and sells', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m19-ramp-${stamp}`;
  tool('building', save);
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-status')).toContainText(/building/i);
  await pressContinue(page);
  await pressContinue(page);
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-status')).toContainText(/producing/i);
  await expect(page.getByTestId('mine-capex')).toContainText('revised');
  await expect(page.getByTestId('mine-output')).toContainText('last month');
  await expect(page.getByTestId('month-row').first()).toContainText('$');
});

test('(c) a price crash, answered with care and maintenance', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m19-crash-${stamp}`;
  tool('crash', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('Your mine is losing money on every tonne');
  await expect(modal.locator('[data-choice="B"]')).toContainText('Hedge');
  await expect(modal.locator('[data-choice="C"]')).toContainText('Keep running');
  await modal.locator('[data-choice="A"]').click(); // care and maintenance
  await expect(modal).toBeHidden();
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-status')).toContainText(/care/i);
  await expect(page.getByTestId('restart')).toBeVisible();
});

test("(d) a scripted accident's critical event", async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m19-accident-${stamp}`;
  tool('accident', save);
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-event')).toContainText(/accident/i);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('A tailings dam has failed');
  await expect(modal.locator('[data-choice="A"]')).toContainText('investigate');
  await modal.locator('[data-choice="B"]').click(); // compensate
  await expect(modal).toBeHidden();
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-event')).toHaveCount(0);
});
