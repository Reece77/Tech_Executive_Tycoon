import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M16 flows (formulas.md 31): (a) form a holding company on an eligible fixture and see the
// Group screen; (b) sell 30% of a subsidiary and see NCI in the consolidated statements; (c)
// spin off a subsidiary and see it become a listed rival; (d) an unfair transfer price raises
// a minority complaint. Saves come from tools/e2e_m16_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string, ...args: string[]): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    [
      'run',
      '--project',
      'backend',
      'python',
      'tools/e2e_m16_save.py',
      mode,
      saveDir,
      save,
      ...args,
    ],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

test('(a) form a holding company and see the Group screen', async ({ page }) => {
  test.setTimeout(240_000); // the fixture lists the company through the IPO chain
  const save = `m16-form-${stamp}`;
  tool('eligible', save);
  await page.goto(`/game/${save}/finance/group`);
  const gate = page.getByTestId('group-gate');
  await expect(gate).toContainText('Form a holding company');
  await expect(page.getByTestId('group-row')).toHaveCount(3); // the company and two brands
  await gate.getByTestId('group-form').click();
  await expect(gate).toBeHidden();
  const rows = page.getByTestId('group-row');
  await expect(rows).toHaveCount(4);
  await expect(rows.first()).toContainText('Kestrel Holdings');
  await expect(rows.first()).toContainText('Holding company');
  await expect(rows.nth(1)).toContainText('Operating company');
  await expect(rows.nth(1)).toContainText('100.00%');
  await expect(rows.nth(1)).toContainText('Consolidated');
  // The company switcher scopes the statements to one company of the group.
  await page.getByTestId('finance-tab-statements').click();
  const switcher = page.getByTestId('company-switcher');
  await expect(switcher).toBeVisible();
  await expect(switcher.locator('option')).toHaveCount(4);
  await switcher.selectOption({ index: 1 }); // the operating company
  await expect(page).toHaveURL(/company=1/);
});

test('(b) sell 30% of a subsidiary and see NCI in the consolidated statements', async ({
  page,
}) => {
  test.setTimeout(240_000);
  const save = `m16-sell-${stamp}`;
  tool('formed', save);
  await page.goto(`/game/${save}/finance/group`);
  const brand = page.getByTestId('group-row').nth(2);
  await expect(brand).toContainText('Subsidiary');
  await brand.getByTestId('group-pct').fill('30');
  await brand.getByTestId('group-sell').click();
  await expect(brand).toContainText('70.00%');
  tool('advance', save); // the sale's month closes
  await page.goto(`/game/${save}/finance/statements`);
  await expect(page.getByText('Non-controlling interest').first()).toBeVisible();
});

test('(c) spin off a subsidiary and see it become a listed rival', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m16-spin-${stamp}`;
  tool('formed', save);
  await page.goto(`/game/${save}/finance/group`);
  const rows = page.getByTestId('group-row');
  await expect(rows).toHaveCount(4);
  const brand = rows.nth(3);
  const href = (await brand.getByTestId('group-entity-link').getAttribute('href')) ?? '';
  const id = /company=(\d+)/.exec(href)?.[1];
  expect(id).toBeTruthy();
  await brand.getByTestId('group-spin').click();
  await expect(rows).toHaveCount(3);
  await expect(page.getByTestId('group-personal-stake')).toContainText('in your own name');
  await page.goto(`/game/${save}/competitors/${id}`);
  await expect(page.getByTestId('target-value')).toContainText('Market cap');
});

test('(d) an unfair transfer price raises a minority complaint', async ({ page }) => {
  test.setTimeout(300_000); // the fixture plays the months it takes
  const save = `m16-complaint-${stamp}`;
  tool('complaint', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('Minority shareholders complain about transfer prices');
  await modal.locator('[data-choice="A"]').click(); // move the prices to market
  await expect(modal).toBeHidden();
  await page.goto(`/game/${save}/finance/group`);
  await expect(page.getByTestId('group-complaint')).toBeVisible(); // until the month end
  await expect(page.getByTestId('group-flow')).toContainText('unfair');
});
