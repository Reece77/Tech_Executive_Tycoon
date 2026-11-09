import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M21 flows (formulas.md 38): (a) the node timeline shows TSMC's N5 in 2020; (b) build a
// mature-node fab and see a fab's yield climb; (c) a leading-edge fab waits for its EUV tools;
// (d) a fab sells its spare starts as slots to rival designers. Saves come from
// tools/e2e_m21_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m21_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

/** The first percentage in a text, as a number. */
function percent(text: string | null): number {
  const m = /(\d+)%/.exec(text ?? '');
  if (!m) throw new Error(`no percentage in ${text}`);
  return Number(m[1]);
}

/** A "Mon YYYY" date in a text, as a month count. */
function month(text: string | null, which = 0): number {
  const names = 'JanFebMarAprMayJunJulAugSepOctNovDec';
  const all = [
    ...(text ?? '').matchAll(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})/g),
  ];
  if (all.length <= which) throw new Error(`no month in ${text}`);
  const [, mon, year] = all[which];
  return Number(year) * 12 + names.indexOf(mon) / 3;
}

async function pick(page: Page, testId: string, option: string | RegExp) {
  await page.getByTestId(testId).click();
  await page.getByRole('option', { name: option }).click();
}

test('(a) the node timeline shows TSMC’s N5 in 2020', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m21-nodes-${stamp}`;
  tool('nodes', save);
  await page.goto(`/game/${save}/products/markets/nodes`);
  const n5 = page.getByTestId('node-n5');
  await expect(n5).toContainText('5 nm');
  await expect(n5).toContainText('Apr 2020');
  await expect(n5).toContainText('TSMC (Apr 2020)');
  await expect(page.getByTestId('node-edge')).toContainText('Leading edge 5 nm');
  await expect(page.getByTestId('node-a16')).toContainText('expected 2026-2027');
  await expect(page.getByTestId('foundries')).toContainText('GlobalFoundries');
});

test('(b) build a mature-node fab; a fab’s yield climbs', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m21-mature-${stamp}`;
  tool('mature', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('fabs-link').click();
  await pick(page, 'fab-node', '28/32 nm');
  await pick(page, 'fab-size', '10,000 starts');
  await expect(page.getByTestId('fab-quote')).toContainText('24 months');
  await page.getByTestId('build-fab').click();
  await expect(page.getByTestId('fab-row')).toHaveCount(2);
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page); // the first fab starts production
  await page.goto(`/game/${save}/products/fabs`);
  await answerBlocking(page);
  await expect(page.getByTestId('fab-status')).toContainText('in production');
  const first = percent(await page.getByTestId('fab-yield').textContent());
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page);
  await continueMonth(page);
  await page.goto(`/game/${save}/products/fabs`);
  await answerBlocking(page);
  const later = percent(await page.getByTestId('fab-yield').textContent());
  expect(later).toBeGreaterThan(first);
  await expect(page.getByTestId('fab-history')).toContainText('Yield curve');
});

test('(c) a leading-edge fab waits for its EUV tools', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m21-euv-${stamp}`;
  tool('euv', save);
  await page.goto(`/game/${save}/products/fabs`);
  await pick(page, 'fab-node', /^5 nm$/);
  await pick(page, 'fab-size', '100,000 starts');
  const quote = page.getByTestId('fab-quote');
  await expect(quote).toContainText('36 months');
  await expect(quote).toContainText('50 EUV tools');
  await page.getByTestId('build-fab').click();
  await expect(page.getByTestId('fab-row')).toHaveCount(1);
  await expect(page.getByTestId('fab-tools')).toContainText('50 tools, arriving');
  const status = await page.getByTestId('fab-status').textContent();
  // ordered January 2021: construction ends January 2024; it is ready only after the tools
  expect(month(status)).toBeGreaterThan(2024 * 12);
});

test('(d) a fab sells its spare starts as slots to rival designers', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m21-slots-${stamp}`;
  tool('slots', save);
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page);
  await page.goto(`/game/${save}/products/fabs`);
  await answerBlocking(page);
  await expect(page.getByTestId('fab-use')).toContainText('foundry slots');
  await expect(page.getByTestId('fab-customers')).toContainText('NVIDIA');
  await expect(page.getByTestId('fab-revenue')).not.toContainText('$0 this month');
});
