import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth, pressContinue } from './helpers.ts';

// M27b flows (formulas.md 40.7): (a) automate a mining subsidiary's areas and Continue three
// months; (b) a supply cover shortfall gets a proposal above the limit and a contract under it;
// (c) a corporate-development pitch arrives as a proposal. Saves come from
// tools/e2e_m27b_save.py (`chain` is Reece's pt-auto-chain).
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const CHAIN = `pt-auto-chain-${stamp}`;
const CORP = `m27b-corp-${stamp}`;

function fixture(kind: 'chain' | 'corp', save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m27b_save.py', kind, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function giveFirst(page: Page, area: string) {
  await page.getByTestId(`owner-${area}`).click();
  await page.getByRole('option').first().click();
  await expect(
    page.getByTestId('area-row').filter({ has: page.getByTestId(`take-back-${area}`) }),
  ).toHaveCount(1);
}

async function settings(page: Page, area: string) {
  const row = page.getByTestId('area-row').filter({ has: page.getByTestId(`take-back-${area}`) });
  await row.getByRole('button', { name: 'Settings' }).click();
}

test('(a) automate a mining subsidiary and Continue three months', async ({ page }) => {
  fixture('chain', CHAIN);
  await page.goto(`/game/${CHAIN}/automation`);
  await page.getByTestId('automation-company').click();
  await page.getByRole('option', { name: /Minerals \(subsidiary\)/ }).click();
  await expect(
    page.getByTestId('area-row').filter({ hasText: 'Mines and refineries' }),
  ).toHaveCount(1);
  await expect(page.getByTestId('area-row').filter({ hasText: 'Pricing' })).toHaveCount(0);
  await page.getByTestId('automate-all').click();
  const dialog = page.getByRole('dialog', { name: 'Automate everything' });
  await expect(dialog.getByTestId('plan-row').first()).toBeVisible();
  await dialog.getByTestId('automate-confirm').click();
  await expect(dialog).toBeHidden();
  await expect(
    page.getByTestId('area-row').filter({ hasText: 'Mines and refineries' }),
  ).toContainText('Automated');
  for (let i = 0; i < 3; i++) await continueMonth(page);
  await page.goto(`/game/${CHAIN}/automation`);
  const digest = page.getByTestId('digest-panel');
  await expect(digest).toContainText('Your month');
  await expect(
    digest.getByTestId('digest-area').filter({ hasText: 'Minerals:' }).first(),
  ).toBeVisible();
});

test('(b) a supply shortfall: a proposal above the limit, a contract under it', async ({
  page,
}) => {
  await page.goto(`/game/${CHAIN}/automation`);
  await answerBlocking(page);
  await giveFirst(page, 'supply');
  await settings(page, 'supply');
  await page.getByTestId('limit-input').fill('0');
  await page.getByTestId('settings-save').click();
  await expect(page.getByTestId('settings-save')).toHaveCount(0);
  await pressContinue(page);
  await page.goto(`/game/${CHAIN}/org`);
  const proposal = page.getByTestId('exec-proposal').filter({ hasText: /offtake|contract/ });
  await expect(proposal.first().getByTestId('proposal-approve')).toBeVisible(); // waiting for you
  await page.goto(`/game/${CHAIN}/automation`);
  await answerBlocking(page); // declined: the shortfall is still there
  await settings(page, 'supply');
  await page.getByTestId('limit-input').fill('1000000000');
  await page.getByTestId('settings-save').click();
  await expect(page.getByTestId('settings-save')).toHaveCount(0);
  await pressContinue(page);
  await page.goto(`/game/${CHAIN}/automation`);
  const area = page.getByTestId('digest-area').filter({ hasText: 'Supply and commodities' });
  await expect(area.first()).toContainText(/signed a/);
});

test('(c) a corporate-development pitch arrives as a proposal', async ({ page }) => {
  fixture('corp', CORP);
  await page.goto(`/game/${CORP}/automation`);
  await answerBlocking(page);
  await giveFirst(page, 'corp_dev');
  await settings(page, 'corp_dev');
  await page.getByTestId('budget-input').fill('5000000');
  await page.getByTestId('settings-save').click();
  await expect(page.getByTestId('settings-save')).toHaveCount(0);
  await pressContinue(page);
  await page.goto(`/game/${CORP}/org`);
  const bid = page.getByTestId('exec-proposal').filter({ hasText: /bid \$/ });
  await expect(bid.first()).toContainText('displayed value');
  await expect(bid.first().getByTestId('proposal-approve')).toBeVisible();
});
