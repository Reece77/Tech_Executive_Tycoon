import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M10 flows: (a) take venture debt after a round and see the schedule; (b) a scripted
// covenant breach raises the critical lender event; (c) the Market screen's macro strip shows
// 2022's rate rise.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built by tools/e2e_m10_save.py before the API opens them. */
function fixture(...args: string[]) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    [
      'run',
      '--project',
      'backend',
      'python',
      'tools/e2e_m10_save.py',
      args[0],
      saveDir,
      ...args.slice(1),
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) take venture debt after a round and see the schedule', async ({ page }) => {
  const save = `m10-debt-${STAMP}`;
  fixture('spinout', save);
  await page.goto(`/game/${save}/finance/debt`);
  await expect(page.getByTestId('no-loans')).toBeVisible();
  await page.getByTestId('take-loan').click();
  const dialog = page.getByTestId('loan-dialog');
  await expect(dialog.getByTestId('loan-eligibility')).toContainText('Silicon Valley Bank');
  await dialog.getByTestId('loan-amount').fill('400000');
  await expect(dialog.getByTestId('loan-first-payment')).toContainText('interest');
  await dialog.getByTestId('sign-loan').click();
  await expect(page.getByTestId('loan-row')).toHaveCount(1);
  await expect(page.getByTestId('loan-row')).toContainText('Silicon Valley Bank');
  await expect(page.locator('[data-testid^="loan-schedule-"]')).toBeVisible();
  await continueMonth(page);
  await page.goto(`/game/${save}/finance/debt`);
  await expect(page.getByTestId('loan-row')).toContainText('$400,000.00');
  await expect(page.getByTestId('covenant').first()).toHaveAttribute('data-holds', 'true');
});

test('(b) a scripted covenant breach raises the lender event', async ({ page }) => {
  const save = `m10-breach-${STAMP}`;
  fixture('breach', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByRole('dialog');
  await expect(modal).toContainText('Silicon Valley Bank says a covenant is broken');
  await expect(page.getByTestId('continue')).toBeDisabled();
  await expect(modal).toContainText('repays $100,000 of the balance from cash now');
  await modal.locator('[data-choice="C"]').click();
  await expect(modal).toBeHidden();
  await expect(page.getByTestId('continue')).toBeEnabled();
  await page.goto(`/game/${save}/finance/debt`);
  await expect(page.getByTestId('loan-row')).toContainText('$300,000.00');
  await expect(page.getByTestId('loan-row')).toContainText('Waived until');
});

test("(c) the Market screen's macro strip shows 2022's rate rise", async ({ page }) => {
  const save = `m10-2022-${STAMP}`;
  fixture('year', save, '2022');
  await page.goto(`/game/${save}/products/markets`);
  const strip = page.getByTestId('macro-strip');
  await expect(strip).toContainText('Dec 2022');
  await expect(strip.getByTestId('macro-base_rate-value')).toHaveText('4.10%');
  await expect(strip.getByTestId('macro-base_rate')).toContainText('+4.02 points on a year ago');
  await expect(strip.getByTestId('macro-downturn')).toHaveCount(0);
});
