import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M26 flows (formulas.md 37): (a) join a rival startup's round and see the stake; (b) back a
// former employee's new startup; (c) buy shares of a listed rival from its page and receive a
// dividend at the quarter's end; (d) a scripted insider trade leads to an investigation.
// Saves come from tools/e2e_m26_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string[] {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m26_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  )
    .toString()
    .trim()
    .split('\n');
}

async function investments(page: Page, save: string) {
  await page.goto(`/game/${save}/people/1`);
  await expect(page.getByTestId('founder-life')).toBeVisible();
  await page.getByTestId('founder-tabs').getByText('Investments', { exact: true }).click();
  await expect(page.getByTestId('investments')).toBeVisible();
}

test("(a) join a rival startup's round and see the stake", async ({ page }) => {
  test.setTimeout(240_000); // the fixture plays months until a round opens
  const save = `m26-round-${stamp}`;
  const [, startup] = tool('rounds', save);
  await investments(page, save);
  await expect(page.getByTestId('inv-cash')).toHaveText('$5,000,000');
  await page.getByTestId(`round-amount-${startup}`).fill('100000');
  await page.getByTestId(`round-invest-${startup}`).click();
  const stake = page.getByTestId('angel-stake');
  await expect(stake).toHaveCount(1);
  await expect(stake).toContainText('open');
  await expect(stake).toContainText('$100,000');
  await expect(page.getByTestId('inv-cash')).toHaveText('$4,900,000');
  // The Rival page shows the stake too (information rights).
  await page.goto(`/game/${save}/competitors/${startup}`);
  await expect(page.getByTestId('personal-invest').getByTestId('my-stake')).toHaveText(/%$/);
});

test("(b) back a former employee's new startup", async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m26-back-${stamp}`;
  const [, person] = tool('leaver', save);
  await investments(page, save);
  const panel = page.getByTestId('back-panel');
  await expect(panel.getByTestId('back-founder')).toContainText('Ada Leaver');
  await expect(panel.getByTestId('back-founder')).toContainText('(known)');
  await panel.getByTestId('back-founder').selectOption(person);
  await panel.getByTestId('back-amount').fill('1000000');
  await panel.getByTestId('back-startup').click();
  const stake = page.getByTestId('angel-stake');
  await expect(stake).toHaveCount(1);
  await expect(stake).toContainText('$1,000,000');
  await expect(page.getByTestId('inv-cash')).toHaveText('$4,000,000');
  await continueMonth(page);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('inbox-item').filter({ hasText: 'You backed' })).toHaveCount(1);
});

test('(c) buy shares of a listed rival and receive a dividend', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m26-dividend-${stamp}`;
  const [, rival] = tool('dividend', save);
  await page.goto(`/game/${save}/competitors/${rival}`);
  const panel = page.getByTestId('personal-invest');
  await panel.getByTestId('buy-shares-count').fill('10000');
  await panel.getByTestId('buy-shares').click();
  await expect(panel.getByTestId('my-shares')).toHaveText(/^10,?000$/);
  await continueMonth(page); // March: the quarter's end pays the dividend
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('inbox-item').filter({ hasText: 'Dividend from' })).toHaveCount(1);
  await page.goto(`/game/${save}/people/1`);
  await page.getByTestId('founder-tabs').getByText('Personal', { exact: true }).click();
  await expect(page.getByTestId('personal-entry').filter({ hasText: 'Dividend from' })).toHaveCount(
    1,
  );
});

test('(d) a scripted insider trade leads to an investigation', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m26-insider-${stamp}`;
  tool('insider', save);
  await investments(page, save);
  const trade = page.getByTestId('trade');
  await expect(trade).toHaveCount(1);
  await expect(trade.getByTestId('trade-notes')).toHaveText('in a sensitive window');
  await expect(page.getByTestId('investments')).not.toContainText('risk');
  await continueMonth(page); // the regulator's investigation opens at this month's end
  await page.goto(`/game/${save}/inbox`);
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: 'Regulators investigate' }),
  ).toHaveCount(1);
  await investments(page, save);
  await expect(page.getByTestId('trade').getByTestId('trade-notes')).toContainText(
    'under investigation',
  );
});
