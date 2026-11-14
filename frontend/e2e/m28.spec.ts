import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M28 flows (formulas.md 41.7, 41.4): (a) open a rival miner's company page from a contract;
// (b) filter World news by good; (c) a rival's bid for a cheap listed player arrives as a
// critical event. Saves come from tools/e2e_m28_save.py (`world` is the practice save
// pt-world: a listed integrator in January 2027 with a lithium converter and an Albemarle
// offtake).
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m28_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

const worldSave = `m28-world-${stamp}`;

test("(a) a rival miner's company page from a contract", async ({ page }) => {
  test.setTimeout(240_000);
  tool('world', worldSave);
  await page.goto(`/game/${worldSave}/products/markets/commodities`);
  const deal = page.getByTestId('deal-row').filter({ hasText: 'Albemarle' });
  await expect(deal).toHaveCount(1);
  await deal.getByTestId('company-link').click();
  await expect(page).toHaveURL(/\/competitors\/\d+$/);
  await expect(page.getByTestId('rival-name')).toContainText('Albemarle');
  const company = page.getByTestId('world-company');
  await expect(company).toContainText('A chain company in United States');
  await expect(page.getByTestId('company-executives')).toContainText('CEO');
  await expect(page.getByTestId('facility-row').first()).toContainText('Lithium carbonate');
  await expect(page.getByTestId('company-financials')).toContainText('Revenue');
});

test('(b) World news filtered by good', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(`/game/${worldSave}/competitors`);
  await page.getByTestId('world-news-link').click();
  await expect(page).toHaveURL(/\/competitors\/world-news$/);
  const items = page.getByTestId('news-item');
  await expect(items.first()).toBeVisible();
  const all = await items.count();
  await page.getByTestId('news-filter-good').click();
  await page.getByRole('option', { name: 'Lithium carbonate' }).click();
  await expect(page).toHaveURL(/good=lithium_carbonate/);
  await expect(items.first()).toContainText('Lithium carbonate');
  const lithium = await items.count();
  expect(lithium).toBeGreaterThan(0);
  expect(lithium).toBeLessThan(all);
  for (const text of await items.allTextContents()) expect(text).toContain('Lithium carbonate');
});

test('(c) a bid for a cheap listed player arrives as a critical event', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m28-bid-${stamp}`;
  tool('bid', save);
  await page.goto(`/game/${save}/overview`);
  await continueMonth(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('A buyer has approached');
  await page.goto(`/game/${save}/competitors/world-news?kind=bid`);
  await expect(page.getByTestId('news-item').first()).toContainText('unsolicited approach');
});
