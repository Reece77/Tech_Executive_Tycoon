import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M13 flows: (a) take a company public through the IPO chain and see the Stock tab; (b) miss
// guidance and see the price and the board react; (c) appoint a CEO, Holiday a year, and see
// the CEO's decisions.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built by tools/e2e_m13_save.py while the API has them closed. */
function fixture(mode: string, save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m13_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) take a company public through the chain and see the Stock tab', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m13-ipo-${STAMP}`;
  fixture('eligible', save);
  await page.goto(`/game/${save}/finance/fundraising`);
  const panel = page.getByTestId('ipo-panel');
  await expect(panel.getByTestId('ipo-problem')).toContainText('Eligible');
  await expect(page.getByTestId('finance-tab-stock')).toHaveCount(0); // not public yet
  await panel.getByTestId('bank-option-morgan_stanley').click();
  await expect(panel.getByTestId('hire-banks')).toContainText('10 energy');
  await panel.getByTestId('hire-banks').click();
  await expect(panel.getByTestId('ipo-step-banks')).toHaveAttribute('data-state', 'done');
  await expect(panel.getByTestId('ipo-step-filing')).toHaveAttribute('data-state', 'now');
  await expect(panel.getByTestId('ipo-offering')).toBeVisible();

  let sawPricing = false;
  for (let month = 0; month < 8; month += 1) {
    const status = await panel.getByTestId('ipo-status').getAttribute('data-status');
    if (status === 'listed') break;
    if (status === 'pricing') {
      // Pricing night is critical: the modal shows the event and the pricing card.
      const modal = page.getByRole('dialog');
      await expect(modal.getByTestId('pricing-card')).toBeVisible();
      await expect(modal.getByTestId('price-option-range')).toContainText('after fees');
      await expect(modal.getByTestId('price-option-pull')).toContainText('costs $');
      await expect(panel.getByTestId('ipo-demand')).toBeVisible();
      await modal.locator('[data-choice="A"]').click(); // price at the suggestion
      await expect(modal).toBeHidden();
      sawPricing = true;
    }
    await continueMonth(page); // answers the S-1 and roadshow events with their first choice
    await page.goto(`/game/${save}/finance/fundraising`);
    await expect(panel.getByTestId('ipo-status')).toBeVisible();
  }
  expect(sawPricing).toBe(true);
  await expect(panel.getByTestId('ipo-status')).toHaveAttribute('data-status', 'listed');
  await page.getByTestId('finance-tab-stock').click();
  await expect(page.getByTestId('stock-ticker')).toHaveText(/^[A-Z]{3,5}$/);
  await expect(page.getByTestId('stock-price')).toHaveText(/^\$[\d,]+\.\d\d$/);
  await expect(page.getByTestId('stock-chart')).toBeVisible();
  await expect(page.getByTestId('analysts-panel')).toBeVisible();
});

test('(b) miss guidance and see the price and board react', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m13-miss-${STAMP}`;
  fixture('miss', save); // this quarter guided 25% above the consensus
  await page.goto(`/game/${save}/finance/stock`);
  await expect(page.getByTestId('guidance-row')).toHaveCount(1);
  await expect(page.getByTestId('guidance-result')).toHaveCount(0); // not reported yet
  await expect(page.getByTestId('guidance-set')).toBeVisible();
  for (let i = 0; i < 3; i += 1) await continueMonth(page);
  await page.goto(`/game/${save}/finance/stock`);
  const result = page.getByTestId('guidance-result');
  await expect(result).toHaveAttribute('data-result', 'miss');
  await expect(result).toContainText('→'); // the price before and after the report
  await expect(page.locator('[data-testid="stock-mark"][data-mark="miss"]')).toHaveCount(1);
  await expect(page.getByTestId('price-drivers')).toContainText('last quarter: miss');
  await expect(page.getByTestId('board-line')).toBeVisible();
  // The quarterly report and the miss event reached the inbox.
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByText('Quarterly results: a miss').first()).toBeVisible();
  await expect(page.getByText('Kestrel missed its guidance').first()).toBeVisible();
});

test("(c) appoint a CEO, Holiday a year, and see the CEO's decisions", async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m13-ceo-${STAMP}`;
  fixture('listed', save);
  await page.goto(`/game/${save}/org`);
  const seat = page.getByTestId('ceo-seat');
  await expect(seat).toContainText('You');
  await seat.locator('[data-testid^="ceo-candidate-"]').first().click();
  await expect(seat.getByTestId('ceo-appoint')).toContainText('10 energy');
  await seat.getByTestId('ceo-appoint').click();
  await expect(seat.getByTestId('ceo-name')).toBeVisible();
  await expect(seat).toContainText('You are Chair');

  await page.keyboard.press('h');
  const dialog = page.getByRole('dialog', { name: 'Go on holiday' });
  await expect(dialog).toBeVisible();
  await dialog.getByTestId('holiday-months').fill('12');
  await dialog.getByText('Critical only').click();
  await dialog.getByTestId('holiday-start').click();
  const done = page.getByTestId('holiday-done');
  await expect(done).toContainText('Back from holiday after 12 months', { timeout: 150_000 });

  await page.goto(`/game/${save}/org`);
  await expect(seat.getByTestId('ceo-name')).toBeVisible();
  await expect(seat.getByTestId('ceo-decision').first()).toBeVisible();
  expect(await seat.getByTestId('ceo-decision').count()).toBeGreaterThan(1);
  await expect(seat.getByTestId('ceo-override').first()).toContainText('Override · 6');
});
