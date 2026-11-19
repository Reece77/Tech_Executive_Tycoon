import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M44 flows (formulas.md 57): (a) bid on a cloud tender and win or lose it with a score band; (b) a
// component ban disqualifies a device bid; (c) defence work triggers a staff reaction event. Saves
// come from tools/e2e_m44_save.py (`defence` is the practice save pt-defence: Aegis, a stage-4
// cloud, AI and satellites group in January 2027 with cleared staff, a cleared US data centre,
// past performance, a Foxconn-assembled rugged device, and three tenders announced this month).
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
// One save for the three flows (each bids on its own tender): building it plays 2010-2026.
const save = `m44-defence-${stamp}`;
let built = false;

function ensureSave(): void {
  if (!built) tool('defence', save);
  built = true;
}

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
      'tools/e2e_m44_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function openTender(page: Page, save: string, title: string) {
  await page.goto(`/game/${save}/products/government`);
  const tenders = page.getByTestId('government-tenders');
  await expect(tenders).toContainText(title);
  await tenders.getByRole('button', { name: new RegExp(title) }).click();
  await expect(page.getByTestId('tender-detail')).toContainText(title);
}

async function bid(page: Page, product: string | RegExp) {
  const detail = page.getByTestId('tender-detail');
  await detail.getByTestId('bid-product').click();
  await page.getByRole('option', { name: product }).click();
  await detail.getByTestId('bid-submit').click();
  await expect(detail.getByTestId('bid-status')).toContainText('submitted');
}

test('(a) bid on a cloud tender and win or lose it with a score band', async ({ page }) => {
  test.setTimeout(900_000);
  ensureSave();
  const title = 'E2E: US civil cloud services';
  await openTender(page, save, title);
  await expect(page.getByTestId('tender-requirements')).toContainText('bidders from');
  await bid(page, /Aegis Cloud/);
  tool('award', save);
  await openTender(page, save, title);
  const status = page.getByTestId('bid-status');
  await expect(status).toContainText(/won|lost/);
  await expect(status.getByTestId('bid-band')).toContainText(/score band \d+-\d+/);
  await expect(page.getByTestId('tender-winners')).toContainText('Awarded to');
});

test('(b) a component ban disqualifies a device bid', async ({ page }) => {
  test.setTimeout(900_000);
  ensureSave();
  const title = 'E2E: US rugged and secure devices';
  await openTender(page, save, title);
  await expect(page.getByTestId('tender-requirements')).toContainText('Section 889');
  await expect(page.getByTestId('tender-unmet')).toContainText('Section 889');
  await bid(page, /Aegis Rugged/);
  tool('award', save);
  await openTender(page, save, title);
  const status = page.getByTestId('bid-status');
  await expect(status).toContainText('disqualified');
  await expect(status.getByTestId('bid-reasons')).toContainText('Section 889');
});

test('(c) defence work triggers a staff reaction event', async ({ page }) => {
  test.setTimeout(900_000);
  ensureSave();
  const title = 'E2E: US AI and analytics';
  await openTender(page, save, title);
  await bid(page, /Aegis Mind/);
  tool('award', save);
  tool('letter', save);
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('open letter against the defence contract');
  await modal.getByTestId('event-choice').filter({ hasText: 'ethics board' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'open letter' })).toHaveCount(0);
  await page.goto(`/game/${save}/products/government`);
  await expect(page.getByTestId('government-record')).toContainText('1 staff letters');
});
