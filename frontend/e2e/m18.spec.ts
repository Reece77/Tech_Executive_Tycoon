import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth, pressContinue } from './helpers.ts';

// M18 flows (formulas.md 34): (a) a desk study, a licence and a survey on a fixture; (b) drill
// 20 holes and watch the grade range narrow; (c) a protest during permitting with its
// choices; (d) sell a project to a supplier. Saves come from tools/e2e_m18_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m18_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

function pct(text: string | null): number {
  const m = /±(\d+)%/.exec(text ?? '');
  if (!m) throw new Error(`no range in ${text}`);
  return Number(m[1]);
}

test('(a) a desk study, a licence and a survey', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m18-desk-${stamp}`;
  tool('explorer', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('exploration-link').click();
  await expect(page.getByTestId('explorer-line')).toContainText('3 geologists');
  await page.getByTestId('region-select').click();
  await page.getByRole('option', { name: 'Latin America' }).click();
  await page.getByTestId('commodity-select').click();
  await page.getByRole('option', { name: 'Copper' }).click();
  await page.getByTestId('desk-study').click();
  await expect(page.getByTestId('explorer-line')).toContainText('1 busy');
  await continueMonth(page);
  await continueMonth(page); // a desk study takes two months
  await page.goto(`/game/${save}/products/exploration`);
  await page.getByTestId('region-select').click();
  await page.getByRole('option', { name: 'Latin America' }).click();
  await page.getByTestId('commodity-select').click();
  await page.getByRole('option', { name: 'Copper' }).click();
  const high = page.locator('[data-band="high"][data-held="false"]');
  await expect(high.first()).toBeVisible();
  await high.first().click(); // licence it
  await expect(page.getByTestId('project-row')).toHaveCount(1);
  await page.getByTestId('stage-survey').click();
  await expect(page.getByTestId('project-facts')).toContainText(/survey running/i);
});

test('(b) drill 20 holes and watch the grade range narrow', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m18-drill-${stamp}`;
  tool('sampled', save);
  await page.goto(`/game/${save}/products/exploration`);
  await expect(page.getByTestId('sample-range')).toContainText('±');
  await page.getByTestId('holes-input').fill('20');
  await page.getByTestId('drill').click();
  const widths: number[] = [];
  for (let month = 0; month < 5; month++) {
    await pressContinue(page);
    await page.goto(`/game/${save}/products/exploration`);
    widths.push(pct(await page.getByTestId('grade-range').textContent()));
  }
  await expect(page.getByTestId('hole-row')).toHaveCount(20);
  expect(widths[widths.length - 1]).toBeLessThan(widths[0]);
  for (let i = 1; i < widths.length; i++) expect(widths[i]).toBeLessThanOrEqual(widths[i - 1]);
});

test('(c) a protest during permitting, with its choices', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m18-protest-${stamp}`;
  tool('protest', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('A community blockade at the exploration camp');
  await expect(modal.locator('[data-choice="A"]')).toBeVisible();
  await expect(modal.locator('[data-choice="B"]')).toContainText('benefit agreement');
  await expect(modal.locator('[data-choice="C"]')).toContainText('Push on');
  await modal.locator('[data-choice="B"]').click(); // the benefit agreement
  await expect(modal).toBeHidden();
  await page.goto(`/game/${save}/products/exploration`);
  await expect(page.getByTestId('permit-status')).toContainText('benefit agreement signed');
});

test('(d) sell a project to a supplier', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m18-sell-${stamp}`;
  tool('permitted', save);
  await page.goto(`/game/${save}/products/exploration`);
  await expect(page.getByTestId('permit-status')).toContainText('granted');
  await expect(page.getByTestId('sale-quote')).toContainText('would pay');
  await page.getByTestId('sell').click();
  await expect(page.getByTestId('sale-quote')).toContainText('sold to');
});
