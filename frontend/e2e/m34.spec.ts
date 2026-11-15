import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M34 flows (formulas.md 48): (a) a designation warning arrives a year ahead; (b) settle an
// investigation with a commitment; (c) a scripted structural order after ignored warnings offers
// spin-off or sale. Saves come from tools/e2e_m34_save.py: Kestrel in January 2026 with a phone on
// its own OS and store holding 45% of Europe's device users.
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
      'tools/e2e_m34_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) a designation warning arrives a year ahead', async ({ page }) => {
  test.setTimeout(900_000);
  const save = `m34-warning-${stamp}`;
  tool('warning', save);
  tool('advance', save, '11'); // January to November 2026 played: the save is at December
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page); // December 2026 played: the year's designation test
  await page.goto(`/game/${save}/competitors/regulation`);
  const dma = page.getByTestId('test-row').filter({ hasText: 'Digital Markets Act' });
  await expect(dma).toContainText('warned Dec 2026');
  await expect(dma).not.toContainText('designated');
  await page.goto(`/game/${save}/inbox`);
  await expect(
    page.getByText(/designation under the Digital Markets Act is likely next year/).first(),
  ).toBeVisible();
});

test('(b) settle an investigation with a commitment', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m34-objections-${stamp}`;
  tool('objections', save);
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('charges Kestrel');
  await expect(modal).toContainText('statement of objections');
  await modal.getByTestId('event-choice').filter({ hasText: 'Settle' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'charges Kestrel' })).toHaveCount(0);
  await page.goto(`/game/${save}/competitors/regulation`);
  const row = page
    .getByTestId('case-row')
    .filter({ hasText: 'Kestrel' })
    .filter({ hasText: 'favouring its own apps' });
  await expect(row).toContainText('settled');
  const duty = page.getByTestId('duty-row').filter({ hasText: 'Kestrel' });
  await expect(duty.filter({ hasText: 'commitment' })).toHaveCount(1);
});

test('(c) a structural order after ignored warnings offers spin-off or sale', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m34-order-${stamp}`;
  tool('order', save);
  await page.goto(`/game/${save}/competitors/regulation`);
  await expect(page.getByTestId('breaches')).toContainText('no self-preferencing');
  await expect(page.getByTestId('warning-sign')).toHaveCount(6);
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('orders Kestrel to separate Kestrel OS');
  const choices = modal.getByTestId('event-choice');
  await expect(choices.filter({ hasText: 'Spin it off' })).toHaveCount(1);
  await choices.filter({ hasText: 'Sell it' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'orders Kestrel' })).toHaveCount(0);
  await page.goto(`/game/${save}/competitors/regulation`);
  await expect(page.getByTestId('orders')).toContainText('sold');
});
