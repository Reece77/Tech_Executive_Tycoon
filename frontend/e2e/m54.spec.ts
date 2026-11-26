import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M54 flows (formulas.md 64): (a) charter a bank from a fintech and take deposits; (b) a rate rise
// squeezes a high-beta bank's margin on the Bank screen; (c) hedge 80% of Europe's revenue and see
// the settlement. Saves come from tools/e2e_m54_save.py (Fin, a stage-4 fintech group: `bank` is the
// practice save pt-bank in January 2019 with a banking line and cash for a charter; `rates` January
// 2022 with a chartered bank at a deposit beta of 0.9; `currency` January 2024 with half its
// software revenue in Europe).
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
      'tools/e2e_m54_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

const percent = (text: string | null): number => Number((text ?? '').replace('%', ''));

test('(a) charter a bank from a fintech and take deposits', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m54-bank-${stamp}`;
  tool('bank', save);
  await page.goto(`/game/${save}/products/bank`);
  await expect(page.getByTestId('bank-none')).toBeVisible();
  await page.getByTestId('bank-charter').click();
  await expect(page.getByTestId('bank-status-north_america')).toContainText('decides in');
  tool('advance', save, '20');
  await page.goto(`/game/${save}/products/bank`);
  await expect(page.getByTestId('bank-north_america')).toContainText('chartered');
  await expect(page.getByTestId('bank-deposits-north_america')).not.toContainText('$0.00 (');
});

test("(b) a rate rise squeezes a high-beta bank's margin", async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m54-rates-${stamp}`;
  tool('rates', save);
  await page.goto(`/game/${save}/products/bank`);
  await expect(page.getByTestId('bank-beta-north_america')).toContainText('0.90');
  const before = percent(await page.getByTestId('bank-nim-month-north_america').textContent());
  expect(before).toBeGreaterThan(0);
  tool('advance', save, '12');
  await page.goto(`/game/${save}/products/bank`);
  const after = percent(await page.getByTestId('bank-nim-month-north_america').textContent());
  expect(after).toBeLessThan(before);
});

test("(c) hedge 80% of Europe's revenue and see the settlement", async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m54-currency-${stamp}`;
  tool('currency', save);
  await page.goto(`/game/${save}/finance/currency`);
  await expect(page.getByTestId('fx-unhedged-europe')).toContainText('100%');
  await page.getByTestId('programme-share').fill('80');
  await page.getByTestId('programme-set').click();
  await expect(page.getByTestId('programme-status')).toContainText('80% hedged 12 months ahead');
  tool('advance', save, '2');
  await page.goto(`/game/${save}/finance/currency`);
  await expect(page.getByTestId('hedge-row').first()).toBeVisible();
  await expect(page.getByTestId('currency-hedges')).toContainText('settled');
});
