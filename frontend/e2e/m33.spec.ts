import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M33 flows (formulas.md 47): (a) order high-NA tools and see the queue's range; (b) prepay the
// order to move up; (c) start the lithography programme and see its first stage. One save from
// tools/e2e_m33_save.py (`litho` is the practice save pt-litho: a stage-5 chip group in January
// 2030 with two fabs and a lithography lab), used by the three flows in turn.
test.describe.configure({ mode: 'serial' });

const save = `m33-litho-${Date.now()}`;

function tool(...args: string[]): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const [mode, name, ...rest] = args;
  execFileSync(
    'uv',
    [
      'run',
      '--project',
      'backend',
      'python',
      'tools/e2e_m33_save.py',
      mode,
      saveDir,
      name,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

const firstMonths = (text: string | null): number => Number((text ?? '').match(/(\d+)/)?.[1]);

test.beforeAll(() => {
  test.setTimeout(900_000); // 2010-2029 played by the engine
  tool('litho', save);
});

test('(a) order high-NA tools and see the queue range', async ({ page }) => {
  await page.goto(`/game/${save}/products/equipment`);
  await expect(page.getByTestId('equipment-generations')).toContainText('High-NA EUV');
  await page.getByTestId('equipment-generation-select').click();
  await page.getByRole('option', { name: 'High-NA EUV (EXE)' }).click();
  await page.getByTestId('equipment-tools').locator('input').fill('10');
  await page.getByTestId('equipment-order').click();
  const row = page.getByTestId('equipment-order-row');
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('High-NA EUV');
  await expect(page.getByTestId('equipment-lead')).toContainText('months');
});

test('(b) prepay the order to move up the queue', async ({ page }) => {
  await page.goto(`/game/${save}/products/equipment`);
  const lead = page.getByTestId('equipment-lead');
  await expect(lead).toContainText('months');
  const before = firstMonths(await lead.textContent());
  await page.getByTestId('equipment-prepay').click();
  await expect(page.getByTestId('equipment-order-row')).toContainText('prepaid');
  const after = firstMonths(await lead.textContent());
  expect(after).toBeLessThanOrEqual(before);
});

test('(c) start the lithography programme and see its first stage', async ({ page }) => {
  await page.goto(`/game/${save}/products/equipment`);
  const status = page.getByTestId('litho-status-litho_1');
  await expect(status).toContainText('open');
  await page.getByTestId('litho-start-litho_1').click();
  await expect(status).toContainText('running');
  await expect(status).toContainText('expected to end');
});
