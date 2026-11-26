import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M51 (formulas.md 63): scenarios and challenges. (a) The crash started from the new-game
// screen and failed at its deadline; (b) the Bootstrapped challenge refuses a funding round with
// its reason; (c) the result appears as a best result on the Scenarios screen, kept in the
// app-wide results file rather than the save. (a) and (c) run in order.

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

async function startNew(page: Page, company: string) {
  await page.getByTestId('company-name-input').fill(company);
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  const start = page.getByTestId('start-game');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/, { timeout: 60_000 });
  return new URL(page.url()).pathname.split('/')[2];
}

test.describe.serial('the crash', () => {
  const company = `Crash ${stamp}`;

  test('(a) start "The crash" from the Scenarios screen and fail it', async ({ page }) => {
    test.setTimeout(150_000);
    await page.goto('/');
    await page.getByTestId('scenarios-link').click();
    await expect(page.getByTestId('scenario-row').filter({ hasText: 'The crash' })).toBeVisible();
    await page.getByTestId('scenario-play-the_crash').click();
    await expect(page.getByTestId('historical-the_crash')).toHaveAttribute('aria-pressed', 'true');
    const save = await startNew(page, company);
    await expect(page.getByTestId('game-date')).toHaveText('Jan 2008');
    tool('e2e_m51_save.py', ['deadline', save]); // to December 2009 without playing between
    await page.goto(`/game/${save}/overview`);
    await expect(page.getByTestId('game-date')).toHaveText('Dec 2009');
    await answerBlocking(page);
    await page.getByTestId('continue').click();
    await expect(page).toHaveURL(/\/over$/, { timeout: 60_000 });
    await expect(page.getByTestId('scenario-result')).toHaveAttribute('data-result', 'failure');
    await expect(page.getByTestId('scenario-score')).toContainText('Company score');
    await expect(page.getByTestId('scenario-parts')).toContainText('Value');
  });

  test('(c) the result is the best on the Scenarios screen', async ({ page }) => {
    await page.goto('/scenarios');
    const best = page.getByTestId('scenario-best-the_crash');
    await expect(best).toBeVisible();
    await expect(best).toContainText(/Lost|Won/);
    await expect(page.getByTestId('scenario-row').filter({ hasText: 'The crash' })).toContainText(
      /hard|medium|easy/,
    );
  });
});

test('(b) the Bootstrapped challenge refuses a funding round', async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto('/new');
  await page.getByTestId('challenge-bootstrapped').check();
  const save = await startNew(page, `Bootstrap ${stamp}`);
  await page.goto(`/game/${save}/finance/fundraising`);
  const start = page.getByTestId('start-round');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByText('Refused by the Bootstrapped challenge')).toBeVisible();
  await continueMonth(page); // the game goes on
});
