import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M8 flows: (a) at stage 3, create a division, move a department into it and see its P&L
// tab; (b) appoint a CTO and see the estimated effect, then vacate it and see the penalty;
// (c) create a fintech product and launch one; (d) Competitors shows Stripe after Sep 2011.
test.describe.configure({ mode: 'serial' });

const SCALE = `m8-scale-${Date.now()}`;
const LATER = `m8-later-${Date.now()}`;

/** Saves built by tools/e2e_m8_save.py before the API opens them: a company at stage 3
 * (reaching $20M ARR on screen takes years) and one played to October 2011. */
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
      'tools/e2e_m8_save.py',
      args[0],
      saveDir,
      ...args.slice(1),
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) create a division, move a department into it and see its P&L', async ({ page }) => {
  fixture('stage3', SCALE);
  await page.goto(`/game/${SCALE}/org`);
  await page.getByTestId('new-division').click();
  await page.getByTestId('unit-name-input').fill('Platform');
  await page.getByTestId('preview-confirm').click();
  await expect(page.getByLabel('Division Platform')).toBeVisible();
  await page.getByLabel('Department Eng').click();
  await page.getByTestId('move-team').click();
  await page.getByRole('menuitem', { name: 'Under Platform' }).click();
  await page.getByTestId('preview-confirm').click();
  await expect(page.getByTestId('division-card')).toContainText('Platform');
  await continueMonth(page);
  await page.goto(`/game/${SCALE}/finance/divisions`);
  const statement = page.getByRole('table', { name: 'Division statement' });
  await expect(statement).toContainText('Platform');
  await expect(statement).toContainText('Shared services');
  await expect(statement).toContainText('Company');
});

test('(b) appoint a CTO, see the estimate, then vacate the seat', async ({ page }) => {
  await page.goto(`/game/${SCALE}/org`);
  await answerBlocking(page); // e.g. a key exit (23.3, M10b) would cover the screen
  const cto = page.getByTestId('seat-cto');
  await expect(cto.getByTestId('vacancy-penalty')).toContainText('−5%');
  await cto.getByTestId('appoint').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('exec level');
  // M8r: the salary to appoint at is shown and editable, prefilled with the exec rate.
  const salary = dialog.getByTestId('appoint-salary').first();
  await expect(salary).not.toHaveValue('');
  await expect(salary.locator('xpath=ancestor::div[1]/..')).toContainText('a year');
  await dialog.getByTestId('appoint-confirm').first().click();
  await expect(dialog).toBeHidden();
  await expect(cto).toContainText('(est.)');
  await expect(cto).toContainText('fit for CTO');
  await cto.getByTestId('remove-exec').click();
  await expect(cto.getByTestId('vacancy-penalty')).toBeVisible();
});

test('(c) create a fintech product and launch one', async ({ page }) => {
  await page.goto(`/game/${SCALE}/products`);
  await page.getByTestId('new-product').click();
  await page.getByTestId('new-product-name').fill('Payroll');
  await page.getByTestId('product-category').selectOption('fintech');
  await expect(page.getByTestId('category-note')).toContainText('Launch needs quality 30');
  await page.getByTestId('segment-smb').check();
  await page.getByTestId('create-product').click();
  await expect(page.getByTestId('product-name')).toHaveText('Payroll');
  await page.goto(`/game/${SCALE}/products`);
  await page.getByRole('link', { name: 'Ledger' }).first().click();
  await expect(page.getByTestId('product-name')).toHaveText('Ledger');
  await page.getByTestId('launch').click();
  await expect(page.getByTestId('launch')).toBeHidden();
});

test('(d) Competitors shows Stripe after September 2011', async ({ page }) => {
  fixture('advance', LATER, '21');
  await page.goto(`/game/${LATER}/competitors`);
  await expect(page.getByTestId('rival-link').filter({ hasText: 'Stripe' })).toBeVisible();
  await expect(page.getByTestId('rival-link').filter({ hasText: 'Square' })).toBeVisible();
});
