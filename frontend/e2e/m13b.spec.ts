import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M13b flows (formulas.md 27): (a) a CPO with authority pitches a new product; approve it
// and see the team and its hiring plan; (b) Holiday with a spend limit: the cheaper pitch
// goes ahead and is reported, the dearer one waits; (c) pull an era forward and see the
// arrival item and the chart marker. Saves come from tools/e2e_m13b_save.py and
// tools/e2e_m11_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(script: string, args: string[]): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', `tools/${script}`, args[0], saveDir, args[1]],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

test('(a) a CPO pitches a new product; approving builds its team and plan', async ({ page }) => {
  const save = `m13b-cpo-${stamp}`;
  tool('e2e_m13b_save.py', ['cpo', save]);
  await page.goto(`/game/${save}/org`);
  await expect(page.getByTestId('continue-blocked')).toContainText('1 proposal or pitch');
  const pitch = page.getByTestId('exec-pitch').first();
  await expect(pitch).toContainText('a new');
  await expect(pitch).toContainText('in 24 months');
  await pitch.getByTestId('pitch-approve').click();
  await expect(pitch.getByTestId('pitch-status')).toContainText('approved');
  await expect(page.getByTestId('continue-blocked')).toHaveCount(0);
  await expect(page.getByTestId('seat-record')).toContainText('1 made');
  await page.goto(`/game/${save}/products`);
  await expect(page.getByTestId('product-row')).toHaveCount(2); // Pipeline and the new one
  await page.goto(`/game/${save}/recruitment`);
  await expect(
    page.getByTestId('plan-row').filter({ hasText: 'Software engineer' }).first(),
  ).toBeVisible();
});

test('(b) on Holiday the small pitch goes ahead and the big one waits', async ({ page }) => {
  const save = `m13b-holiday-${stamp}`;
  const out = tool('e2e_m13b_save.py', ['holiday', save]);
  const limit = Number(/limit=(\d+)/.exec(out)?.[1]);
  expect(limit).toBeGreaterThan(0);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('game-date')).not.toHaveText('…');
  await page.keyboard.press('h');
  const dialog = page.getByRole('dialog', { name: 'Go on holiday' });
  await dialog.getByTestId('holiday-months').fill('1');
  await dialog.getByTestId('pitch-limit-default').click(); // untick: set a limit
  await dialog.getByTestId('pitch-limit').fill(String(limit));
  await dialog.getByTestId('holiday-start').click();
  await expect(page.getByTestId('holiday-done')).toBeVisible({ timeout: 30_000 });
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByText(/went ahead:/).first()).toBeVisible();
  await page.goto(`/game/${save}/org`);
  const pitches = page.getByTestId('exec-pitch');
  await expect(pitches.filter({ hasText: 'auto approved' })).toHaveCount(1);
  await expect(pitches.filter({ has: page.getByTestId('pitch-approve') })).toHaveCount(1);
});

test('(c) pull an era forward: the arrival item and the chart marker', async ({ page }) => {
  const save = `m13b-era-${stamp}`;
  tool('e2e_m11_save.py', ['ahead', save]);
  await page.goto(`/game/${save}/products`);
  await continueMonth(page);
  await page.goto(`/game/${save}/inbox`);
  const item = page.getByTestId('inbox-item').filter({ hasText: 'Transformers has arrived' });
  await expect(item).toHaveCount(1);
  await expect(item.locator('[data-kind="Critical"]')).toHaveCount(1);
  await page.goto(`/game/${save}/products/markets/ai_models`);
  await expect(page.getByTestId('market-size')).toContainText('Market size');
  await expect(page.getByTestId('market-era-marks')).toContainText('Transformers');
  await expect(page.getByTestId('market-era-marks')).toContainText('You');
});
