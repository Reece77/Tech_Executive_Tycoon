import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M14 flows (formulas.md 28): (a) diligence then a friendly offer for a startup, integrate
// it and see its people join; (b) buy a startup as a brand, set a directive and see the
// consolidated P&L; (c) a deal over 50% combined share is blocked and the remedy offered;
// (d) accept a takeover bid and see the exit ending. Saves come from tools/e2e_m14_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(args: string[]): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m14_save.py', args[0], saveDir, args[1]],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

function target(out: string): number {
  return Number(/target=(\d+)/.exec(out)?.[1]);
}

/** Bid what the panel shows (the counter if there is one, else the range's top). */
async function offer(page: Page, mode: 'integrate' | 'brand') {
  if (mode === 'brand') await page.getByTestId('offer-mode').getByText('Keep as a brand').click();
  const counter = page.getByTestId('target-counter');
  const value = (await counter.count())
    ? await counter.textContent()
    : await page.getByTestId('target-value').textContent();
  const amounts = (value ?? '').match(/\$[\d,]+/g) ?? [];
  const dollars = Number((amounts.at(-1) ?? '$0').replace(/[$,]/g, ''));
  await page.getByTestId('offer-price').fill(String(dollars));
  await page.getByTestId('make-offer').click();
  await expect(page.getByTestId('offer-answer').first()).toBeVisible();
}

test('(a) diligence, a friendly offer for a startup, then its people join', async ({ page }) => {
  const save = `m14-startup-${stamp}`;
  const id = target(tool(['startup', save]));
  await page.goto(`/game/${save}/competitors/${id}`);
  await expect(page.getByTestId('target-value')).toContainText('Estimated value');
  await page.getByTestId('start-diligence').click();
  await expect(page.getByTestId('diligence-status')).toContainText('Under way');
  await continueMonth(page);
  await continueMonth(page);
  await page.goto(`/game/${save}/competitors/${id}`);
  await expect(page.getByTestId('diligence-status')).toContainText('Findings');
  for (let i = 0; i < 2 && !(await page.getByTestId('deal-status').count()); i += 1) {
    await offer(page, 'integrate'); // the first answer may be a counter
  }
  await expect(page.getByTestId('deal-status')).toContainText('Accepted');
  const before = await (await page.request.get(`/api/saves/${save}/people`)).json();
  await continueMonth(page);
  await page.goto(`/game/${save}/finance/deals`);
  await expect(page.getByTestId('acquisition-row')).toContainText('Integrated');
  const after = await (await page.request.get(`/api/saves/${save}/people`)).json();
  expect(after.length).toBeGreaterThan(before.length); // its key people joined
});

test('(b) a startup kept as a brand, a directive, the consolidated P&L', async ({ page }) => {
  const save = `m14-brand-${stamp}`;
  const id = target(tool(['startup', save]));
  await page.goto(`/game/${save}/competitors/${id}`);
  for (let i = 0; i < 2 && !(await page.getByTestId('deal-status').count()); i += 1) {
    await offer(page, 'brand');
  }
  await expect(page.getByTestId('deal-status')).toContainText('Accepted');
  await continueMonth(page); // closes
  await continueMonth(page); // the first consolidated month
  await page.goto(`/game/${save}/finance/deals`);
  const row = page.getByTestId('brand-row');
  await expect(row).toHaveCount(1);
  await row.getByText('Harvest').click();
  await expect
    .poll(async () => {
      const mna = await (await page.request.get(`/api/saves/${save}/mna`)).json();
      return mna.subsidiaries[0].directive;
    })
    .toBe('harvest');
  await page.goto(`/game/${save}/finance/statements`);
  await expect(page.getByTestId('subsidiary-columns')).toBeVisible();
  await expect(page.getByText('consolidated with your brands')).toBeVisible();
});

test('(c) over half a market is blocked and the remedy offered', async ({ page }) => {
  const save = `m14-blocked-${stamp}`;
  const id = target(tool(['blocked', save]));
  await page.goto(`/game/${save}/competitors/${id}`);
  for (let i = 0; i < 2 && !(await page.getByTestId('deal-status').count()); i += 1) {
    await offer(page, 'integrate');
  }
  await expect(page.getByTestId('deal-status')).toContainText('Blocked');
  await page.goto(`/game/${save}/finance/deals`);
  await expect(page.getByTestId('open-deal-status')).toHaveText('Blocked');
  await expect(page.getByTestId('accept-remedy')).toContainText('divest');
});

test('(d) accept a takeover bid: the exit ending', async ({ page }) => {
  const save = `m14-exit-${stamp}`;
  tool(['exit', save]);
  await page.goto(`/game/${save}/overview`);
  const modal = page.getByRole('dialog');
  for (let i = 0; i < 6; i += 1) {
    await expect(modal).toBeVisible();
    const title = (await modal.textContent()) ?? '';
    await modal.locator('[data-choice="A"]').click(); // "Accept and sell" for the offer
    if (title.includes('names a price')) break;
    await expect(modal).toBeHidden();
    await page.reload();
  }
  await page.goto(`/game/${save}/over`);
  await expect(page.getByTestId('over-kicker')).toContainText('Exit');
  await expect(page.getByTestId('game-over')).toContainText('You sold');
  await expect(page.getByTestId('game-over')).toContainText('Your stake came to');
});
