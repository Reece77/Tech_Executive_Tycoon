import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M16 flows (formulas.md 31): (a) form a holding company on an eligible fixture and see the
// Group screen. Saves come from tools/e2e_m16_save.py.
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
