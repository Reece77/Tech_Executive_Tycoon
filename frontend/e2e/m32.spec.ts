import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, pressContinue } from './helpers.ts';

// M32 flows (formulas.md 46): (a) sign a PPA for a data centre; (b) build a solar-with-storage
// plant behind a fab's meter and see the queue skipped; (c) a grid outage costs wafers and is
// shown. Saves come from tools/e2e_m32_save.py (`power` is the practice save pt-power: a stage-4
// integrator in January 2027 with a fab and two data centres in congested regions).
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(...args: string[]): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const [mode, save, ...rest] = args;
  execFileSync(
    'uv',
    [
      'run',
      '--project',
      'backend',
      'python',
      'tools/e2e_m32_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) sign a PPA for a data centre', async ({ page }) => {
  test.setTimeout(420_000);
  const save = `m32-ppa-${stamp}`;
  tool('power', save);
  await page.goto(`/game/${save}/products/power`);
  await expect(page.getByTestId('power-regions')).toContainText('North America');
  await page.getByTestId('ppa-mwh').fill('5000');
  await expect(page.getByTestId('ppa-quote')).toContainText('take-or-pay');
  await page.getByTestId('sign-ppa').click();
  await expect(page.getByTestId('power-ppa-row')).toHaveCount(1);
  await expect(page.getByTestId('power-ppa-row').first()).toContainText('active');
  await answerBlocking(page);
  await pressContinue(page);
  await page.goto(`/game/${save}/products/power`);
  const na = page.getByTestId('power-region-row').filter({ hasText: 'North America' });
  await expect(na).toContainText('PPA');
  await expect(page.getByTestId('power-cost-north_america')).toBeVisible();
});

test('(b) build solar with storage behind a fab and skip the queue', async ({ page }) => {
  test.setTimeout(420_000);
  const save = `m32-btm-${stamp}`;
  tool('fab', save);
  await page.goto(`/game/${save}/products/power`);
  await page.getByTestId('plant-type').click();
  await page.getByRole('option', { name: 'Solar with storage' }).click();
  await page.getByTestId('plant-size').click();
  await page.getByRole('option', { name: '500 MW' }).click();
  await page.getByTestId('plant-site').click();
  await page.getByRole('option', { name: /Behind the meter/ }).click();
  await expect(page.getByTestId('plant-quote')).toContainText('behind the meter: no queue');
  await page.getByTestId('build-plant').click();
  const row = page.getByTestId('power-plant-row').first();
  await expect(row).toContainText('Solar with storage');
  await expect(row).toContainText(/fab/i);
  await expect(page.getByTestId('power-queue')).toContainText('Nothing is waiting');
  // a grid-tied plant joins the queue instead
  await page.getByTestId('plant-site').click();
  await page.getByRole('option', { name: 'On the grid' }).click();
  await expect(page.getByTestId('plant-quote')).toContainText('grid queue');
});

test('(c) a grid outage costs wafers and is shown', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m32-outage-${stamp}`;
  tool('outage', save);
  tool('until_outage', save);
  await page.goto(`/game/${save}/products/power`);
  await expect(page.getByTestId('power-outage-list')).toContainText('Africa grid went down');
  await expect(page.getByTestId('power-wafers-lost')).toContainText('wafer starts lost');
});
