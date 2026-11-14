import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M31 flows (formulas.md 44): (a) launch an own OS on a device line and see its catalogue index;
// (b) a removal arrives as a critical event and complying restores the listing; (c) set the own
// store's fee and see developer share respond over a year. Saves come from
// tools/e2e_m31_save.py (`platform` is the practice save pt-platform: a device maker in January
// 2026 with 20% of its region's users on Android, its own OS ready to launch).
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
      'tools/e2e_m31_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) launch an own OS on a device line and see its catalogue index', async ({ page }) => {
  test.setTimeout(300_000);
  const save = `m31-platform-${stamp}`;
  tool('platform', save);
  await page.goto(`/game/${save}/products`);
  await page.getByRole('link', { name: 'Kestrel OS' }).first().click();
  await page.getByTestId('launch').click();
  await expect(page.getByTestId('launch')).toHaveCount(0);
  await page.goto(`/game/${save}/competitors/platforms`);
  await expect(page.getByTestId('own-platform')).toContainText('Kestrel OS');
  const line = page.getByTestId('device-lines').locator('[data-testid^="device-line-"]').first();
  await expect(line).toContainText('runs Android');
  await line.locator('[data-testid^="device-platform-"]').click();
  await page.getByRole('option', { name: 'Kestrel OS' }).click();
  await line.locator('[data-testid^="switch-platform-"]').click();
  await expect(line).toContainText('runs Kestrel OS');
  await expect(page.getByTestId('own-platform')).toContainText('catalogue');
  await expect(page.getByTestId('platform-row').filter({ hasText: 'Kestrel OS' })).toHaveCount(1);
});

test('(b) a removal arrives as a critical event and complying restores the listing', async ({
  page,
}) => {
  test.setTimeout(300_000);
  const save = `m31-removal-${stamp}`;
  tool('removal', save);
  await page.goto(`/game/${save}/competitors/platforms`);
  const app = page.locator('[data-testid^="platform-app-"]').filter({ hasText: 'Kestrel Chat' });
  await expect(app).toContainText('removed');
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('removes Kestrel Chat');
  await modal.getByTestId('event-choice').filter({ hasText: 'Comply' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'removes Kestrel Chat' })).toHaveCount(0);
  await page.goto(`/game/${save}/competitors/platforms`);
  await expect(app).toBeVisible();
  await expect(app).not.toContainText('removed');
});

test("(c) the own store's fee moves developer share over a year", async ({ page }) => {
  test.setTimeout(300_000);
  const save = `m31-fee-${stamp}`;
  tool('os_live', save);
  await page.goto(`/game/${save}/competitors/platforms`);
  const own = page.getByTestId('own-platform');
  await expect(own).toBeVisible();
  const before = await own.textContent();
  await page.getByTestId('own-fee-input').fill('10');
  await page.getByTestId('save-rules').click();
  await expect(page.getByTestId('own-fee-input')).toHaveValue('10');
  tool('advance', save, '12');
  await page.reload();
  await expect(own).toBeVisible();
  const after = await own.textContent();
  expect(after).not.toEqual(before);
  const share = /North America [\d.]+% users, ([\d.]+)% developers/;
  const was = Number(share.exec(before ?? '')?.[1] ?? '0'); // no users yet: none
  const now = Number(share.exec(after ?? '')?.[1] ?? '0');
  expect(now).toBeGreaterThan(was);
});
