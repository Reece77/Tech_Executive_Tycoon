import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, pressContinue } from './helpers.ts';

// M38 flows (formulas.md 49): (a) design and launch an EV with bought cells; (b) build a cell
// plant fed by the group's lithium and see the unit cost fall; (c) a subsidy's sourcing rule
// disqualifies a car with Chinese cells in the US. Saves come from tools/e2e_m38_save.py (Volta, a
// stage-4 integrator in January 2024 with a lithium converter; `ev` is the practice save pt-ev).
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
      'tools/e2e_m38_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function openCar(page: Page, save: string) {
  await page.goto(`/game/${save}/products/vehicles`);
  await expect(page.getByTestId('vehicles-regions')).toContainText('North America');
  await page.getByTestId('vehicle-car-row').first().getByRole('link').click();
  await expect(page.getByTestId('car-design')).toBeVisible();
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

test('(a) design and launch an EV with bought cells', async ({ page }) => {
  test.setTimeout(420_000);
  const save = `m38-car-${stamp}`;
  tool('car', save);
  await openCar(page, save);
  await choose(page, 'spec-chemistry', 'LFP');
  await choose(page, 'spec-cells', /LG Energy Solution/);
  await page.getByTestId('save-spec').click();
  await expect(page.getByTestId('car-summary')).toContainText('cells lges');
  await page.getByTestId('car-product-link').click();
  await page.getByTestId('launch').click();
  await answerBlocking(page);
  await pressContinue(page);
  await openCar(page, save);
  await expect(page.getByTestId('car-summary')).toContainText('live');
  await expect(page.getByTestId('car-cost-line').first()).toContainText('Battery pack');
});

test('(b) a cell plant on the group lithium lowers the unit cost', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m38-cells-${stamp}`;
  tool('selling', save);
  tool('advance', save, '1');
  await page.goto(`/game/${save}/products/vehicles`);
  const before = money((await page.getByTestId('vehicle-car-row').first().innerText()) ?? '');
  await choose(page, 'cell-plant-size', '250 MWh a month');
  await choose(page, 'cell-plant-chemistry', 'LFP');
  await page.getByTestId('build-cell-plant').click();
  await expect(page.getByTestId('cell-plant-row')).toHaveCount(1);
  tool('ripen', save);
  await openCar(page, save);
  await choose(page, 'spec-cells', 'Your own cell plants');
  await page.getByTestId('save-spec').click();
  await expect(page.getByTestId('car-summary')).toContainText('from your own plants');
  await answerBlocking(page);
  await pressContinue(page);
  await page.goto(`/game/${save}/products/vehicles`);
  await expect(page.getByTestId('cell-plant-row').first()).toContainText('live');
  const row = page.getByTestId('vehicle-car-row').first();
  const after = money(await row.innerText());
  expect(after).toBeLessThan(before);
});

test('(c) Chinese cells lose the US credit', async ({ page }) => {
  test.setTimeout(420_000);
  const save = `m38-us-${stamp}`;
  tool('selling', save);
  await openCar(page, save);
  const us = page.getByTestId('eligibility-row').filter({ hasText: 'US federal EV tax credit' });
  await expect(us).toContainText('not eligible');
  await expect(us).toContainText('foreign entity of concern');
  await choose(page, 'spec-cells', /LG Energy Solution/);
  await page.getByTestId('save-spec').click();
  await expect(us).toContainText('eligible');
  await expect(us).not.toContainText('not eligible');
});
