import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M17 flows: (a) the Commodities tab shows 2022's lithium spike on a 2023 save; (b) sign a
// lithium offtake and see it on the device cost breakdown; (c) a data centre in South and
// Southeast Asia shows a lower power cost than one in North America.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built by tools/e2e_m17_save.py while the API has them closed. */
function fixture(mode: string, save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m17_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) the Commodities tab shows the 2022 lithium spike on a 2023 save', async ({ page }) => {
  const save = `m17-tab-${STAMP}`;
  fixture('y2023', save);
  await page.goto(`/game/${save}/products/markets`);
  await page.getByTestId('category-commodities').click();
  await expect(page.getByTestId('commodity-row')).toHaveCount(12);
  await page.getByTestId('commodity-lithium_carbonate').click();
  const chart = page.getByTestId('commodity-chart');
  await expect(chart).toContainText('Lithium carbonate: price by month');
  await expect(page.getByTestId('commodity-peak')).toContainText('80,000 $/t (Nov 2022)');
  await expect(chart.getByRole('img')).toBeVisible();
});

test('(b) sign a lithium offtake and see it on the device cost breakdown', async ({ page }) => {
  const save = `m17-offtake-${STAMP}`;
  fixture('device2020', save);
  await page.goto(`/game/${save}/products/markets/commodities`);
  const form = page.getByTestId('offtake-form');
  await expect(form).toBeVisible();
  await page.getByTestId('offtake-volume').fill('20');
  await page.getByTestId('offtake-quote').click();
  await expect(page.getByTestId('offtake-quote-out')).toContainText('6,000–10,000');
  await page.getByTestId('offtake-sign').click();
  await expect(page.getByTestId('deal-row')).toHaveCount(1);
  await expect(page.getByTestId('deal-row')).toContainText('Lithium carbonate offtake with');
  await page.goto(`/game/${save}/products/hardware`);
  const line = page.getByTestId('commodity-line-lithium_carbonate');
  await expect(line).toBeVisible();
  await expect(page.getByTestId('commodity-hedged-lithium_carbonate')).toContainText('hedged');
});

test('(c) power costs less in South and Southeast Asia than in North America', async ({ page }) => {
  const save = `m17-power-${STAMP}`;
  fixture('power', save);
  await page.goto(`/game/${save}/products/infrastructure`);
  const rows = page.getByTestId('power-per-cu');
  await expect(rows).toHaveCount(2);
  // $200 a CU-month of GPU power in North America, x 0.85 in South and Southeast Asia (33.5)
  const texts = (await rows.allInnerTexts()).map((t) => t.split(' ')[0]).sort();
  expect(texts).toEqual(['$170', '$200']);
});
