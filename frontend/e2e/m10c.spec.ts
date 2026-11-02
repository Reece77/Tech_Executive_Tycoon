import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M10c flows (formulas.md 24): (a) give the CRO authority and see a seller hiring plan opened
// when capacity limits sales; (b) a CFO proposal blocks Continue and approving it opens the
// round; (c) a quarterly report arrives. Saves come from tools/e2e_m10c_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const CRO = `m10c-cro-${stamp}`;
const CFO = `m10c-cfo-${stamp}`;

function fixture(kind: 'cro' | 'cfo', save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m10c_save.py', kind, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function giveAuthority(page: Page, seat: string) {
  const row = page.getByTestId(`seat-${seat}`);
  await row.getByTestId('authority').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Guardrails');
  await dialog.getByTestId('authority-on').click();
  await expect(dialog).toBeHidden();
  await expect(row.getByTestId('authority')).toHaveText('Authority on');
}

test('(a) give the CRO authority and see a seller plan opened', async ({ page }) => {
  fixture('cro', CRO);
  await page.goto(`/game/${CRO}/org`);
  await giveAuthority(page, 'cro');
  await continueMonth(page);
  await page.goto(`/game/${CRO}/org`);
  await expect(page.getByTestId('exec-decision').first()).toContainText('(CRO)');
  await expect(page.getByTestId('exec-decisions')).toContainText('account executive');
  await page.goto(`/game/${CRO}/recruitment`);
  await expect(page.getByTestId('plan-row').filter({ hasText: 'Account executive' })).toHaveCount(
    1,
  );
});

test('(b) a CFO proposal blocks Continue and approving it opens the round', async ({ page }) => {
  fixture('cfo', CFO);
  await page.goto(`/game/${CFO}/org`);
  await giveAuthority(page, 'cfo');
  const date = page.getByTestId('game-date');
  const before = await date.textContent();
  await page.getByTestId('continue').click();
  await expect(date).not.toHaveText(before ?? '');
  await page.goto(`/game/${CFO}/org`);
  await answerBlocking(page, { proposals: false }); // a critical event's modal would cover it
  await expect(page.getByTestId('continue-blocked')).toContainText('1 proposal');
  await expect(page.getByTestId('continue')).toBeDisabled();
  const proposal = page.getByTestId('exec-proposal').first();
  await expect(proposal).toContainText('seed round');
  await proposal.getByTestId('proposal-approve').click();
  await expect(proposal).toContainText('approved');
  await expect(page.getByTestId('continue-blocked')).toHaveCount(0);
  await page.goto(`/game/${CFO}/finance/fundraising`);
  await expect(page.getByTestId('open-round')).toContainText('Seed · open');
});

test('(c) a quarterly report arrives', async ({ page }) => {
  await page.goto(`/game/${CFO}/org`);
  for (let i = 0; i < 3; i++) {
    if ((await page.getByTestId('exec-report').count()) > 0) break;
    await answerBlocking(page);
    await continueMonth(page);
    await page.goto(`/game/${CFO}/org`);
  }
  const report = page.getByTestId('exec-report').first();
  await expect(report).toContainText('CFO');
  await report.locator('summary').click();
  await expect(report).toContainText('Q1 2010');
  await page.goto(`/game/${CFO}/inbox`);
  await expect(page.getByTestId('inbox-item').filter({ hasText: 'CFO report' })).toHaveCount(1);
});
