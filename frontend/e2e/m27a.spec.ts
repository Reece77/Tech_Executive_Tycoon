import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M27a flows (formulas.md 40): (a) Automate everything on pt-auto and Continue three months,
// then read the digest; (b) a one-off proposal stops a holiday and is approved; (c) take an
// area back; (d) "Can't automate yet" names how to fix it. Saves come from
// tools/e2e_m27a_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const AUTO = `pt-auto-${stamp}`;
const CFO = `m27a-cfo-${stamp}`;

function fixture(kind: 'auto' | 'cfo', save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m27a_save.py', kind, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) automate everything, Continue three months, read the digest', async ({ page }) => {
  fixture('auto', AUTO);
  await page.goto(`/game/${AUTO}/automation`);
  await expect(page.getByTestId('area-row')).toHaveCount(12);
  await page.getByTestId('automate-all').click();
  const dialog = page.getByRole('dialog', { name: 'Automate everything' });
  await expect(dialog.getByTestId('plan-row').first()).toBeVisible();
  await dialog.getByTestId('automate-confirm').click();
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId('area-row').filter({ hasText: 'Automated' }).first()).toBeVisible();
  for (let i = 0; i < 3; i++) await continueMonth(page); // the digest never blocks Continue
  await page.goto(`/game/${AUTO}/automation`);
  const digest = page.getByTestId('digest-panel');
  await expect(digest).toContainText('Your month');
  await expect(digest.getByTestId('digest-area').first()).toBeVisible();
  await digest.getByTestId('digest-open').click();
  await expect(page.getByTestId('working-pane')).toContainText('Your month');
  await page.goto(`/game/${AUTO}/overview`);
  await expect(page.getByTestId('latest-digest')).toContainText('Your month');
});

test('(c) take an area back from its screen header', async ({ page }) => {
  await page.goto(`/game/${AUTO}/recruitment`);
  await answerBlocking(page);
  const header = page.getByTestId('run-by');
  await expect(header).toContainText('Hiring: run by');
  await page.getByTestId('header-take-back-hiring').click();
  await expect(page.getByTestId('header-take-back-hiring')).toHaveCount(0);
  await page.goto(`/game/${AUTO}/automation`);
  await expect(page.getByTestId('area-row').filter({ hasText: 'Hiring' })).toContainText(
    'Manage myself',
  );
});

test("(d) Can't automate yet names how to fix it", async ({ page }) => {
  fixture('cfo', CFO);
  await page.goto(`/game/${CFO}/automation`);
  await expect(page.getByTestId('cant-press')).toContainText(
    'hire a senior communications manager or fill the CMO seat',
  );
});

test('(b) a one-off proposal stops a holiday and is approved', async ({ page }) => {
  await page.goto(`/game/${CFO}/automation`);
  await page.getByTestId('owner-treasury').click();
  await page.getByRole('option').first().click();
  await expect(page.getByTestId('area-row').filter({ hasText: 'Treasury' })).toContainText(
    'Automated',
  );
  await page.goto(`/game/${CFO}/inbox`);
  await answerBlocking(page);
  await expect(page.getByTestId('game-date')).not.toHaveText('…');
  await page.keyboard.press('h');
  const dialog = page.getByRole('dialog', { name: 'Go on holiday' });
  await dialog.getByTestId('holiday-months').fill('6');
  await dialog.getByTestId('holiday-start').click();
  await expect(page.getByTestId('holiday-done')).toBeVisible({ timeout: 60_000 });
  await page.goto(`/game/${CFO}/org`);
  const proposal = page.getByTestId('exec-proposal').first();
  await expect(proposal).toContainText('seed round');
  await proposal.getByTestId('proposal-approve').click();
  await expect(proposal).toContainText('approved');
});
