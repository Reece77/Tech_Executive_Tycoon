import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M15b flows (formulas.md 30): (a) a Sandbox start in 2018 with no rivals sees the 2018
// world; (b) "Survive 2022" played to its deadline succeeds and shows the result screen;
// (c) January's rankings arrive as news and on the Rankings screen; (d) Continue until stops
// at a pitch. Saves come from tools/e2e_m15b_save.py.
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

test('(a) a Sandbox start in 2018 with no rivals sees the 2018 world', async ({ page }) => {
  test.setTimeout(180_000); // the world plays 2010-2017 before the start (30.2)
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(`Sandy ${stamp}`);
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  await page.getByTestId('mode-kind').getByText('Sandbox').click();
  await page.getByTestId('sandbox-year').fill('2018');
  await page.getByTestId('sandbox-rivals').click();
  await page.getByRole('option', { name: 'No rivals' }).click();
  const start = page.getByTestId('start-game');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/, { timeout: 150_000 });
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2018');
  const save = new URL(page.url()).pathname.split('/')[2];
  const rivals = await (await page.request.get(`/api/saves/${save}/rivals`)).json();
  expect(rivals.rivals.length).toBeGreaterThan(0);
  expect(rivals.rivals.every((r: { failed: boolean }) => r.failed)).toBe(true); // none left
  await page.goto(`/game/${save}/competitors`);
  await expect(page.getByTestId('rival-counts')).toContainText('0 startups alive');
  await page.goto(`/game/${save}/products/research`);
  await expect(page.getByTestId('era-transformers')).toHaveAttribute('data-status', 'arrived');
  await expect(page.getByTestId('era-cloud_native')).toHaveAttribute('data-status', 'arrived');
});

test('(b) Survive 2022 to its deadline: the scenario result screen', async ({ page }) => {
  const save = `m15b-survive-${stamp}`;
  tool('e2e_m15b_save.py', ['deadline', save]);
  await page.goto(`/game/${save}/overview`);
  await expect(page.getByTestId('game-date')).toHaveText('Dec 2023');
  await answerBlocking(page);
  await page.getByTestId('continue').click();
  await expect(page).toHaveURL(/\/over$/, { timeout: 60_000 });
  await expect(page.getByTestId('over-kicker')).toContainText('Scenario won');
  await expect(page.getByTestId('scenario-result')).toHaveAttribute('data-result', 'success');
  await expect(page.getByTestId('game-over')).toContainText('Still solvent');
});

test('(c) January rankings arrive as news and on the Rankings screen', async ({ page }) => {
  const save = `m15b-rankings-${stamp}`;
  tool('e2e_m15b_save.py', ['december', save]);
  await page.goto(`/game/${save}/overview`);
  await expect(page.getByTestId('game-date')).toHaveText('Dec 2010');
  await continueMonth(page);
  await page.goto(`/game/${save}/inbox`);
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: 'The 2011 industry rankings' }),
  ).toHaveCount(1);
  await page.goto(`/game/${save}/competitors`);
  await page.getByTestId('rankings-link').click();
  await expect(page.getByRole('heading', { name: /Rankings 2011/ })).toBeVisible();
  await expect(
    page.getByTestId('rankings-revenue').getByTestId('ranking-row').first(),
  ).toBeVisible();
  await expect(page.getByTestId('rankings-innovative')).toBeVisible();
});

test('(d) Continue until stops at a pitch', async ({ page }) => {
  const save = `m15b-until-${stamp}`;
  tool('e2e_m15b_save.py', ['pitch', save]);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('game-date')).not.toHaveText('…');
  await page.getByTestId('continue-until').click();
  const stopped = page.getByTestId('continue-until-stopped');
  await expect(stopped).toBeVisible({ timeout: 60_000 });
  await expect(stopped).toContainText('a pitch above your auto-approve limit waits for you');
  await expect(page.getByTestId('continue-blocked')).toContainText('pitch');
});
