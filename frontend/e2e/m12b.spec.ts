import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M12b flows: (a) launch a device on a contract and see its unit cost and gross margin;
// (b) build a plant and see it take over from the contract; (c) design an AI accelerator and
// see a GPU data centre's capex fall.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built or edited by tools/e2e_m12b_save.py while the API has them closed. */
function fixture(mode: string, save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m12b_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) launch a device on a contract; see its unit cost and gross margin', async ({ page }) => {
  const save = `m12b-device-${STAMP}`;
  fixture('device', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('hardware-link').click();
  const panel = page.getByTestId('manufacturing-panel');
  await expect(panel.getByTestId('needs-source')).toBeVisible();
  await page.getByTestId('cm-open').click();
  await page.getByTestId('cm-sign').click();
  await expect(page.getByTestId('hw-contract-row')).toHaveCount(1);
  await expect(page.getByTestId('hw-contract-row')).toContainText('Foxconn in Shenzhen');
  await page.goto(`/game/${save}/products`);
  await page.getByText('Pebble Phone').first().click();
  await page.getByTestId('launch').click();
  const unit = page.getByTestId('unit-cost');
  // 26.7's $233 with the BOM's commodities at January 2010's spot (M17, formulas.md 33.2)
  await expect(unit).toContainText('$232.54');
  await expect(page.getByTestId('gross-margin')).toContainText('27%');
  await continueMonth(page);
  await answerBlocking(page);
  await page.goto(`/game/${save}/products/hardware`);
  await expect(page.getByTestId('units-sold')).not.toContainText(/^Sold last month\s*0$/);
  await expect(page.getByTestId('source-row').first()).toContainText('Foxconn');
});

test('(b) build a plant; it takes over from the contract', async ({ page }) => {
  const save = `m12b-plant-${STAMP}`;
  fixture('live_device', save);
  await page.goto(`/game/${save}/products/hardware`);
  await expect(page.getByTestId('no-plants')).toBeVisible();
  await page.getByTestId('plant-open').click();
  await expect(page.getByTestId('plant-quote')).toContainText('paid over 12 months');
  await page.getByTestId('plant-build').click();
  await expect(page.getByTestId('plant-row')).toHaveCount(1);
  await expect(page.getByTestId('plant-progress')).toContainText('ready Jan 2011');
  fixture('plant_ready', save);
  await continueMonth(page);
  await answerBlocking(page);
  await page.goto(`/game/${save}/products/hardware`);
  await expect(page.getByTestId('plant-use')).not.toContainText('yours 0 ');
  const plantSource = page.getByTestId('source-row').filter({ hasText: 'Assembly plant' });
  await expect(plantSource).not.toContainText('made 0 ');
});

test('(c) design an AI accelerator; a GPU data centre costs less', async ({ page }) => {
  const save = `m12b-chip-${STAMP}`;
  fixture('chip', save);
  const preview = async () =>
    (
      await (
        await page.request.get(
          `/api/saves/${save}/infrastructure/build-preview?kind=data_centre_gpu&units=500`,
        )
      ).json()
    ).capex_cents as number;
  const before = await preview();
  await page.goto(`/game/${save}/products/hardware`);
  await page.getByTestId('wafer-open').click();
  await page.getByTestId('wafer-sign').click();
  await expect(page.getByTestId('chip-row')).toContainText('50 wafers a month');
  await page.goto(`/game/${save}/products`);
  await page.getByText('Kestrel TPU').first().click();
  await page.getByTestId('launch').click();
  await page.goto(`/game/${save}/products/hardware`);
  await expect(page.getByTestId('gpu-capex')).toContainText('GPU data-centre capex ×0.');
  const after = await preview();
  expect(after).toBeLessThan(before * 0.8);
});
