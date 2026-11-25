import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M53 flows (formulas.md 62): (a) win a mid-band auction; (b) build 5G in a region and see coverage
// grow; (c) a ban forces replacing Huawei equipment. Saves come from tools/e2e_m53_save.py (Nova, a
// stage-4 devices and chips group: `telecom` is the practice save pt-telecom in January 2018 with
// the UK's April 2018 mid-band auction announced; `network` January 2020 with US spectrum and a
// mobile line; `huawei` December 2025 with 2,500 North American sites on Huawei radios).
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
      'tools/e2e_m53_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) win a mid-band auction', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m53-auction-${stamp}`;
  tool('telecom', save);
  await page.goto(`/game/${save}/products/telecom`);
  const auction = page.getByTestId('telecom-auctions').locator('[data-testid^="auction-"]').first();
  await expect(auction).toContainText('UK 2018 auction');
  await expect(auction).toContainText('mid band');
  const id = (await auction.getAttribute('data-testid'))?.replace('auction-', '') ?? '';
  await page.getByTestId(`bid-blocks-${id}`).fill('2');
  await page.getByTestId(`bid-limit-${id}`).fill('5000000000');
  await page.getByTestId(`bid-submit-${id}`).click();
  await expect(page.getByTestId(`bid-registered-${id}`)).toContainText('Registered: 2 blocks');
  tool('advance', save, '4');
  await page.goto(`/game/${save}/products/telecom`);
  await expect(page.getByTestId(`auction-result-${id}`)).toContainText('you 2');
  await expect(page.getByTestId('licence-row').first()).toContainText('United Kingdom');
});

test('(b) build 5G in a region and see coverage grow', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m53-network-${stamp}`;
  tool('network', save);
  await page.goto(`/game/${save}/products/telecom`);
  await expect(page.getByTestId('coverage-north_america')).toContainText('0%');
  await page.getByTestId('build-region').click();
  await page.getByRole('option', { name: 'North America' }).click();
  await page.getByTestId('build-generation').click();
  await page.getByRole('option', { name: '5G' }).click();
  await page.getByTestId('build-vendor').click();
  await page.getByRole('option', { name: 'Ericsson' }).click();
  await page.getByTestId('build-sites').click();
  await page.getByRole('option', { name: '2,500' }).click();
  await page.getByTestId('build-towers').click();
  await expect(page.getByTestId('radio-row').first()).toContainText('5G, Ericsson');
  tool('advance', save, '13');
  await page.goto(`/game/${save}/products/telecom`);
  await expect(page.getByTestId('coverage-north_america')).not.toContainText('0% ·');
  await expect(page.getByTestId('coverage-north_america')).toContainText('5G');
});

test('(c) a ban forces replacing Huawei equipment', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m53-huawei-${stamp}`;
  tool('huawei', save);
  await page.goto(`/game/${save}/products/telecom`);
  await expect(page.getByTestId('telecom-bans')).toContainText('US restrictions on Huawei');
  const row = page.getByTestId('radio-row').first();
  await expect(row).toContainText('Huawei');
  await expect(row).toContainText('to replace, 0 done');
  await row.getByRole('button', { name: 'Rip and replace' }).click();
  await expect(page.getByTestId('radio-row')).toHaveCount(2);
  await expect(page.getByTestId('radio-row').nth(1)).toContainText('Ericsson');
  tool('advance', save, '7');
  await page.goto(`/game/${save}/products/telecom`);
  const banned = page.getByTestId('radio-row').first();
  await expect(banned).toContainText('2,500 done');
  await expect(banned).not.toContainText('dark');
});
