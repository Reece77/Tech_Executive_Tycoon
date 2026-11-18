import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M40 flows (formulas.md 56): (a) design a vehicle and launch a satellite; (b) a launch failure with
// the player's own satellites aboard arrives as a critical event; (c) broadband coverage opens a
// region once a shell is complete. Saves come from tools/e2e_m40_save.py (Halcyon, a stage-4 chip
// and devices group in January 2026; `launcher` adds a launch line, a launch site, a broadband line,
// a satellite plant and a North American licence; `shell` a one-shell constellation 40 satellites
// short of complete).
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
      'tools/e2e_m40_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) design a vehicle and launch a satellite', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m40-launch-${stamp}`;
  tool('launcher', save);
  await page.goto(`/game/${save}/products/space`);
  await expect(page.getByTestId('space-vehicles')).toContainText('no launch vehicle');
  await page.getByTestId('design-vehicle').click();
  await expect(page.getByTestId('vehicle-row').first()).toContainText('Halcyon Lift');
  const plan = page.getByTestId('plan-constellation');
  await plan.getByLabel('Constellation name').fill('Halcyon Ring');
  await plan.getByLabel('Broadband line').click();
  await page.getByRole('option', { name: 'Halcyon Net' }).click();
  await plan.getByLabel('Vehicle').click();
  await page.getByRole('option', { name: 'Halcyon Lift' }).click();
  await plan.getByRole('button', { name: 'Plan constellation' }).click();
  await expect(page.getByTestId('constellation').first()).toContainText('Halcyon Ring');
  tool('advance', save, '1');
  await page.goto(`/game/${save}/products/space`);
  const launch = page.getByTestId('launch-row').first();
  await expect(launch).toContainText('Halcyon Lift');
  await expect(launch).toContainText('Halcyon Ring');
  await expect(launch.locator('td').nth(3)).not.toHaveText('0');
});

test('(b) a launch failure with own satellites aboard is a critical event', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m40-failure-${stamp}`;
  tool('shell', save);
  tool('failure', save);
  tool('advance', save, '1');
  await page.goto(`/game/${save}/events`);
  await expect(page.getByText(/satellites/i).first()).toBeVisible();
  await page.goto(`/game/${save}/products/space`);
  await expect(page.getByTestId('launch-row').first()).toContainText('Failure');
});

test('(c) coverage opens a region once a shell is complete', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m40-shell-${stamp}`;
  tool('shell', save);
  await page.goto(`/game/${save}/products/space`);
  await expect(page.getByTestId('coverage').first()).toContainText('nothing yet');
  await expect(page.getByTestId('shell-0')).not.toContainText('complete');
  tool('advance', save, '1');
  await page.goto(`/game/${save}/products/space`);
  await expect(page.getByTestId('shell-0')).toContainText('complete');
  await expect(page.getByTestId('coverage').first()).toContainText('north america');
});
