import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M20 flows (formulas.md 36): (a) build a silicon smelter where power is cheap and compare its
// unit cost with Europe's; (b) a wafer plant supplying the group's chips at transfer price;
// (c) China's 2021 power curb on an East Asian smelter; (d) a gallium recovery line supplying
// the group's chips through the December 2024 gallium ban. Saves come from
// tools/e2e_m20_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m20_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

/** The first dollar amount in a text, as a number. */
function dollars(text: string | null): number {
  const m = /\$([\d,]+(?:\.\d+)?)/.exec(text ?? '');
  if (!m) throw new Error(`no amount in ${text}`);
  return Number(m[1].replaceAll(',', ''));
}

/** Both dollar amounts of "$X ... against $Y". */
function pair(text: string | null): [number, number] {
  const all = [...(text ?? '').matchAll(/\$([\d,]+(?:\.\d+)?)/g)].map((m) =>
    Number(m[1].replaceAll(',', '')),
  );
  if (all.length < 2) throw new Error(`no pair in ${text}`);
  return [all[0], all[1]];
}

async function pick(page: Page, testId: string, option: string | RegExp) {
  await page.getByTestId(testId).click();
  await page.getByRole('option', { name: option }).click();
}

test('(a) a silicon smelter where power is cheap costs less than one in Europe', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const save = `m20-smelter-${stamp}`;
  tool('smelter', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('refineries-link').click();
  await pick(page, 'recipe-select', /Silicon smelter: Quartz to silicon metal/);
  await pick(page, 'build-region', 'Europe');
  await expect(page.getByTestId('quote-power')).toContainText('×1.50');
  const europe = dollars(await page.getByTestId('quote-unit-cost').textContent());
  await pick(page, 'build-region', 'South and Southeast Asia');
  await expect(page.getByTestId('quote-power')).toContainText('×0.85');
  const cheap = dollars(await page.getByTestId('quote-unit-cost').textContent());
  expect(cheap).toBeLessThan(europe);
  await page.getByTestId('build-refinery').click();
  await expect(page.getByTestId('plant-row')).toHaveCount(1);
  await expect(page.getByTestId('plant-status')).toContainText('building');
  await expect(page.getByTestId('plant-status')).toContainText('estimated');
});

test('(b) a wafer plant supplies the group’s chips at transfer price', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m20-wafers-${stamp}`;
  tool('wafers', save);
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page);
  await page.goto(`/game/${save}/products/refineries`);
  await answerBlocking(page);
  const row = page.getByTestId('supply-row').first();
  await expect(row).toContainText('300 mm silicon wafer');
  await expect(row).toContainText('Forge SoC');
  const [transfer, market] = pair(await row.textContent());
  expect(transfer).toBeLessThan(market);
  await expect(page.getByTestId('plant-outputs')).toContainText('group');
  await page.goto(`/game/${save}/finance/group`);
  await expect(page.getByTestId('chain-wafer')).toContainText('Forge SoC');
  await expect(page.getByTestId('chain-chip')).toContainText('Forge SoC');
});

test('(c) the 2021 power curb hits an East Asian smelter', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m20-curb-${stamp}`;
  tool('curb', save);
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page);
  await page.goto(`/game/${save}/products/refineries`);
  await answerBlocking(page);
  await expect(page.getByTestId('plant-curb')).toContainText('60.0%');
  await expect(page.getByTestId('plant-curb')).toContainText('Oct 2021');
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByText('Power curb: Silicon smelter #1, East Asia').first()).toBeVisible();
});

test('(d) a gallium recovery line supplies the chips through a ban', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m20-gallium-${stamp}`;
  tool('gallium', save);
  await page.goto(`/game/${save}/inbox`);
  await continueMonth(page); // December 2024: the SoC's first month of use
  await continueMonth(page); // January 2025: inside the ban, the line supplies it
  await page.goto(`/game/${save}/products/refineries`);
  await answerBlocking(page);
  const row = page.getByTestId('supply-row').filter({ hasText: 'Gallium' });
  await expect(row).toHaveCount(1);
  const [own, market] = pair(await row.textContent());
  expect(own).toBeLessThan(market);
  await pick(page, 'deal-good', 'Gallium');
  await expect(page.getByTestId('deals-panel')).toContainText(/allocation (?!100)\d+\.\d%/);
});
