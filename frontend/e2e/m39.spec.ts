import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M39 flows (formulas.md 53): (a) automate a vehicle plant with robots and see its unit cost fall;
// (b) launch a robotaxi zone in a city whose region has approved driverless service; (c) a serious
// incident suspends a zone. Saves come from tools/e2e_m39_save.py (Kestrel, a stage-4 EV maker in
// January 2027 with L3 cars and a North American vehicle plant; `robotics` is the practice save
// pt-robotics, `taxi` adds L4, a robotaxi service and a Phoenix depot).
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
      'tools/e2e_m39_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function choose(page: Page, testId: string, option: string | RegExp) {
  await page.getByTestId(testId).click();
  await page.getByRole('option', { name: option }).click();
}

function money(text: string): number {
  const m = /\$([\d,]+(?:\.\d+)?)/.exec(text);
  if (!m) throw new Error(`no amount in ${text}`);
  return Number(m[1].replaceAll(',', ''));
}

async function openZone(page: Page, save: string) {
  await page.goto(`/game/${save}/products/mobility`);
  await expect(page.getByTestId('mobility-cities')).toContainText('Phoenix');
  await choose(page, 'zone-city', 'Phoenix');
  await choose(page, 'zone-size', /^small/);
  await page.getByTestId('open-zone').click();
  await expect(page.getByTestId('mobility-zone-row').first()).toContainText('under review');
}

test('(a) robots in a vehicle plant lower its cost a unit', async ({ page }) => {
  test.setTimeout(420_000);
  const save = `m39-plant-${stamp}`;
  tool('robotics', save);
  await page.goto(`/game/${save}/products/robotics`);
  const row = page.getByTestId('plant-automation-row').first();
  await expect(row).toContainText('north america');
  const cost = row.locator('[data-testid^="plant-unit-cost-"]');
  const before = money(await cost.innerText());
  await row.getByRole('button', { name: 'Install' }).click();
  await expect(row).toContainText('60%'); // the target level (robotics.automation.target_level)
  await expect.poll(async () => money(await cost.innerText())).toBeLessThan(before);
});

test('(b) a robotaxi zone opens in an approved city', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m39-taxi-${stamp}`;
  tool('taxi', save);
  await openZone(page, save);
  tool('permit', save);
  await page.goto(`/game/${save}/products/mobility`);
  const zone = page.getByTestId('mobility-zone-row').first();
  await expect(zone).toContainText('active');
  await zone.getByRole('button', { name: 'Add cars' }).click();
  await expect(zone).toContainText('50');
  tool('advance', save, '1');
  await page.goto(`/game/${save}/products/mobility`);
  await expect(page.getByTestId('mobility-zone-row').first()).toContainText('active');
  const rides = page.getByTestId('mobility-zone-row').first().locator('td').nth(4);
  await expect
    .poll(async () => Number((await rides.innerText()).replaceAll(',', '')))
    .toBeGreaterThan(0);
});

test('(c) a serious incident suspends the zone', async ({ page }) => {
  test.setTimeout(480_000);
  const save = `m39-incident-${stamp}`;
  tool('taxi', save);
  await openZone(page, save);
  tool('permit', save);
  await page.goto(`/game/${save}/products/mobility`);
  await page
    .getByTestId('mobility-zone-row')
    .first()
    .getByRole('button', { name: 'Add cars' })
    .click();
  await expect(page.getByTestId('mobility-zone-row').first()).toContainText('50');
  tool('incident', save);
  await page.goto(`/game/${save}/products/mobility`);
  await expect(page.getByTestId('mobility-zone-row').first()).toContainText('suspended until');
  await expect(page.getByTestId('robotaxi-incident').first()).toContainText('serious');
});
