import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M12a flows: (a) build a general data centre and see it complete and take your products'
// compute; (b) sell spare capacity and see Cloud hosting customers arrive; (c) a scripted
// understaffed data centre has an outage event.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built or edited by tools/e2e_m12a_save.py while the API has them closed. */
function fixture(mode: string, save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m12a_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) build a general data centre; it completes and serves your products', async ({ page }) => {
  const save = `m12a-build-${STAMP}`;
  fixture('product', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('infrastructure-link').click();
  await expect(page.getByTestId('no-facilities')).toBeVisible();
  await page.getByTestId('build-open').click();
  await expect(page.getByTestId('build-preview')).toContainText('Capex (paid over 12 months)');
  await expect(page.getByTestId('build-delay')).toContainText('none');
  await page.getByTestId('build-confirm').click();
  await expect(page.getByTestId('facility-row')).toHaveCount(1);
  await expect(page.getByTestId('build-progress')).toContainText('ready Jan 2011');
  fixture('ripen', save);
  await continueMonth(page);
  await answerBlocking(page);
  await page.goto(`/game/${save}/products/infrastructure`);
  const row = page.getByTestId('facility-row');
  await expect(row.getByTestId('use-text')).toContainText('your products');
  await expect(row.getByTestId('use-text')).not.toContainText('your products 0 ');
  await expect(row.getByTestId('cost-per-used')).toContainText('spot $1,000');
});

test('(b) sell spare capacity and see Cloud hosting customers arrive', async ({ page }) => {
  const save = `m12a-cloud-${STAMP}`;
  fixture('cloud', save);
  await page.goto(`/game/${save}/products/infrastructure`);
  await expect(page.getByTestId('staff-text')).toHaveText('10 of 10');
  await page.getByTestId('cloud-start').click();
  await expect(page.getByTestId('cloud-customers')).toBeVisible();
  fixture('brand', save);
  for (let i = 0; i < 2; i += 1) {
    await continueMonth(page);
    await answerBlocking(page);
  }
  await page.goto(`/game/${save}/products/infrastructure`);
  await expect(page.getByTestId('cloud-customers')).not.toHaveText('0');
  await expect(page.getByTestId('use-text')).not.toContainText('sold 0 ');
});

test('(c) an understaffed data centre has an outage event', async ({ page }) => {
  const save = `m12a-outage-${STAMP}`;
  fixture('outage', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByRole('dialog');
  await expect(modal).toContainText('A data centre outage took Pipeline down');
  await expect(page.getByTestId('continue')).toBeDisabled();
  await modal.locator('[data-choice="B"]').click();
  await expect(modal).toBeHidden();
  await page.goto(`/game/${save}/products/infrastructure`);
  await expect(page.getByTestId('cloud-outages')).toHaveCount(0); // not selling: no cloud panel
  await expect(page.getByTestId('staff-text')).toHaveText('0 of 3');
});
