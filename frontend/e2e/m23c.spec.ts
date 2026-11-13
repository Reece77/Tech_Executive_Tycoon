import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M23c flows (playtest 5): (a) the top bar and side nav stay put while the working pane
// scrolls, wide and narrow; (b) a critical event set aside to look around read only, and
// answered later; (c) a block's licence asks first; (d) the commodity planning view. Saves come
// from the v3 fixture tools.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(file: string, mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', `tools/${file}`, mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

/** Scroll the working pane to its end; the page itself must not scroll. */
async function scrollPane(page: Page) {
  const pane = page.getByTestId('working-pane');
  await pane.evaluate((el) => el.scrollTo(0, el.scrollHeight));
  await expect.poll(() => pane.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(await page.locator('html').evaluate((el) => el.scrollTop)).toBe(0); // the page itself never scrolls
}

test('(a) the top bar and side nav stay visible while the working pane scrolls', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const save = `m23c-shell-${stamp}`;
  tool('e2e_m18_save.py', 'sampled', save);
  for (const size of [
    { width: 1280, height: 720 },
    { width: 390, height: 760 },
  ]) {
    await page.setViewportSize(size);
    await page.goto(`/game/${save}/products/exploration`);
    await expect(page.getByTestId('projects-panel')).toBeVisible();
    await scrollPane(page);
    await expect(page.getByTestId('continue')).toBeInViewport();
    await expect(page.getByTestId('game-date')).toBeInViewport();
    await expect(page.getByRole('navigation', { name: 'Game screens' })).toBeInViewport();
  }
});

test('(b) a critical event set aside to look around read only, and answered later', async ({
  page,
}) => {
  test.setTimeout(240_000);
  const save = `m23c-aside-${stamp}`;
  tool('e2e_m19_save.py', 'crash', save);
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('Your mine is losing money on every tonne');
  // the card links the mine it is about
  await expect(modal.getByTestId('event-link').first()).toContainText(/mine #\d+/);
  await modal.getByTestId('set-aside').click();
  await expect(modal).toBeHidden();
  const banner = page.getByTestId('set-aside-banner');
  await expect(banner).toContainText('Critical decision waiting');
  await expect(page.getByTestId('continue-blocked')).toBeVisible();
  // browse any screen: the banner stays, and follows its link to the mine
  await page
    .getByRole('navigation', { name: 'Game screens' })
    .getByRole('link', { name: /People/ })
    .click(); // M29: a group is titled People too
  await expect(banner).toBeVisible();
  await banner.getByRole('link', { name: /mine #\d+/ }).click();
  await expect(page).toHaveURL(/products\/mines\?mine=\d+/);
  await expect(page.getByTestId('mine-status')).toContainText(/producing/i);
  // read only: an action is refused until the decision is answered
  await page.getByTestId('care').click();
  await expect(page.getByTestId('mines-error')).toContainText('read only');
  await expect(page.getByTestId('mine-status')).toContainText(/producing/i);
  // back to the decision, and answer it
  await banner.getByTestId('back-to-decision').click();
  await expect(modal.locator('[data-choice="A"]')).toBeVisible();
  await modal.locator('[data-choice="A"]').click(); // care and maintenance
  await expect(modal).toBeHidden();
  await expect(banner).toHaveCount(0);
  await page.goto(`/game/${save}/products/mines`);
  await expect(page.getByTestId('mine-status')).toContainText(/care/i);
});

test('(c) a block licence asks first: cost, term and what you get', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m23c-licence-${stamp}`;
  tool('e2e_m18_save.py', 'explorer', save);
  await page.goto(`/game/${save}/products/exploration`);
  await expect(page.getByTestId('project-row')).toHaveCount(0);
  const free = page.locator('[data-held="false"]').first();
  await free.click();
  const dialog = page.getByRole('dialog', { name: 'Licence this block?' });
  await expect(dialog.getByTestId('licence-fee')).toContainText('$');
  await expect(dialog.getByTestId('licence-term')).toContainText('years, renewable');
  await dialog.getByTestId('licence-cancel').click();
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId('project-row')).toHaveCount(0); // nothing bought
  await free.click();
  await page.getByTestId('licence-confirm').click();
  await expect(page.getByTestId('project-row')).toHaveCount(1);
  // a greyed-out stage says how to unlock it
  await expect(page.getByTestId('stage-how')).toContainText('How:');
});

test('(d) the commodity planning view: need, drivers and cover', async ({ page }) => {
  test.setTimeout(180_000);
  const save = `m23c-plan-${stamp}`;
  tool('e2e_m20_save.py', 'wafers', save);
  await page.goto(`/game/${save}/products`);
  await pressContinue(page); // a month of production to plan from
  await page.goto(`/game/${save}/products/markets/commodities`);
  const plan = page.getByTestId('plan-panel');
  await expect(plan).toBeVisible();
  await expect(plan.getByTestId('plan-row').first()).toBeVisible();
  await expect(plan.getByTestId('plan-row').first()).toContainText('Forge');
  await expect(plan.getByTestId('plan-month')).toHaveCount(12);
});
