import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M24 flows (formulas.md 32): (a) four months of spending all energy bring burnout's critical
// event and the energy cut; (b) after the IPO the founder sells shares, creates a foundation,
// gives, and December's first grants show their effect; (c) lobbying builds influence with
// an exposure word, and a scripted scandal arrives as a critical event; (d) the legacy score
// on the Game over screen. Saves come from tools/e2e_m24_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m24_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

async function founderTab(page: Page, save: string, tab: string) {
  await page.goto(`/game/${save}/people/1`);
  await expect(page.getByTestId('founder-life')).toBeVisible();
  await page.getByTestId('founder-tabs').getByText(tab, { exact: true }).click();
}

test('(a) four months at full energy: burnout, its event and the energy cut', async ({ page }) => {
  test.setTimeout(300_000); // four fixture edits and four months
  const save = `m24-burnout-${stamp}`;
  tool('fresh', save);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('stress')).toHaveText('20');
  for (let month = 0; month < 4; month++) {
    tool('drain', save);
    await page.reload();
    await expect(page.getByTestId('energy')).toHaveText(/^0 \//);
    await page.getByTestId('continue').click();
    await expect(page.getByTestId('stress')).toHaveText(String(20 + 16 * (month + 1)));
  }
  const meter = page.getByTestId('stress-meter');
  await expect(meter).toHaveAttribute('data-burnout', 'true');
  await expect(meter.getByTestId('burnout-flag')).toBeVisible();
  // The monthly budget is cut by 30% (about 42 of 60; event bonuses move it a point or two).
  await expect(page.getByTestId('energy-meter')).toHaveAttribute('title', /-30% while burnt out/);
  const max = Number(((await page.getByTestId('energy').textContent()) ?? '').split('/')[1]);
  expect(max).toBeLessThanOrEqual(45);
  await expect(page.getByTestId('continue-blocked')).toBeVisible();

  // A critical event opens as a modal over the screen.
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('You are running on empty');
  await expect(modal.getByTestId('burnout-note')).toContainText('Executive team panel');
  await modal.locator('[data-choice="A"]').click(); // take this month off
  await expect(modal).toBeHidden();
  await expect(page.getByTestId('energy')).toHaveText(/^0 \//);
});

test('(b) sell shares after the IPO, start a foundation, see its first grants', async ({
  page,
}) => {
  test.setTimeout(300_000); // the fixture plays the IPO chain to a December
  const save = `m24-giving-${stamp}`;
  tool('december', save);
  await founderTab(page, save, 'Personal');
  const shares = Number(
    ((await page.getByTestId('personal-shares').textContent()) ?? '0').replace(/,/g, ''),
  );
  expect(shares).toBeGreaterThan(0);
  await page.getByTestId('sell-shares-input').fill(String(Math.floor(shares / 20)));
  await page.getByTestId('sell-shares').click();
  await expect(page.getByTestId('personal-cash')).not.toHaveText('$0');
  await expect(page.getByTestId('personal-entry').first()).toContainText('Sold');

  await page.getByTestId('founder-tabs').getByText('Foundation', { exact: true }).click();
  await page.getByTestId('foundation-cause').selectOption('education');
  await page.getByTestId('foundation-create').click();
  await expect(page.getByTestId('foundation-name')).toContainText('Foundation');
  await page.getByTestId('foundation-gift-input').fill('1000000');
  await page.getByTestId('foundation-give').click();
  await expect(page.getByTestId('foundation-endowment')).toHaveText('$1,000,000');

  await continueMonth(page); // December's month end: the first grants
  await founderTab(page, save, 'Foundation');
  await expect(page.getByTestId('foundation-grants')).toHaveText('$50,000');
  await expect(page.getByTestId('foundation-effect')).toContainText('hiring appeal');
});

test('(c) lobbying builds influence and exposure; a scandal is a critical event', async ({
  page,
}) => {
  test.setTimeout(180_000);
  const save = `m24-lobby-${stamp}`;
  tool('fresh', save);
  await founderTab(page, save, 'Government affairs');
  const panel = page.getByTestId('government-panel');
  await panel.getByTestId('lobby-region').selectOption('north_america');
  await panel.getByTestId('lobby-monthly').fill('500000');
  await panel.getByTestId('lobby-set').click();
  const row = panel.getByTestId('influence-row').filter({ hasText: 'North America' });
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId('exposure-value')).toHaveText('low');

  await continueMonth(page);
  await founderTab(page, save, 'Government affairs');
  await expect(row.getByTestId('influence-value')).toHaveText('6.7'); // 3 x sqrt(5)
  await expect(row.getByTestId('exposure-value')).toHaveText(/low|medium|high/);

  tool('scandal', save);
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('continue').click();
  const modal = page.getByTestId('critical-modal');
  await expect(modal).toContainText('A lobbying story breaks');
  await expect(modal).toContainText('Apologize in public');
  await modal.locator('[data-choice="B"]').click(); // drop the lobbying firm
  await expect(modal).toBeHidden();
  await founderTab(page, save, 'Government affairs');
  await expect(panel.getByTestId('scandal-row')).toHaveCount(1);
  // Dropping the lobbying firm stops the region's lobbying (influence rebuilt a little in the
  // month the story broke, before the answer).
  await expect(row).toContainText('$0');
});

test('(d) the legacy score on the Game over screen', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m24-over-${stamp}`;
  tool('over', save);
  await page.goto(`/game/${save}/over`);
  const panel = page.getByTestId('legacy-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('legacy')).toHaveText(/^\d+$/);
  await expect(panel).toContainText('Best company score');
});
