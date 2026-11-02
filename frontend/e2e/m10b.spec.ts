import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M10b flows (formulas.md 23): (a) answer an event, see it archive and its modifier on the
// active-effects panel; (b) a major event blocks Continue until answered; (c) a one-engineer
// product shows "team too small" with the maintenance line; (d) set a regional price and see
// it shown. Saves come from tools/e2e_event_save.py and tools/e2e_m9_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function run(tool: string, args: (dir: string) => string[]) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync('uv', ['run', '--project', 'backend', 'python', tool, ...args(saveDir)], {
    cwd: resolve(process.cwd(), '..'),
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
}

test('(a) answer an event, see it archive and its modifier on the active effects', async ({
  page,
}) => {
  const save = `m10b-mod-${stamp}`;
  run('tools/e2e_event_save.py', (dir) => [dir, save, '--modifier']);
  await page.goto(`/game/${save}/inbox`);
  const item = page.getByTestId('inbox-item').filter({ hasText: 'shortlisted for an award' });
  await item.click();
  const card = page.getByTestId('event-card');
  await expect(card).toContainText('morale target across the company for 3 months');
  await card.locator('[data-choice="A"]').click();
  await expect(card.getByTestId('event-answered')).toHaveText('You chose A.');
  await page.goto(`/game/${save}/inbox`);
  await expect(item).toHaveCount(0); // archived
  await page.getByRole('button', { name: 'Archived', exact: true }).click();
  await expect(item).toHaveCount(1);
  await page.goto(`/game/${save}/overview`);
  const effects = page.getByTestId('active-effects');
  await expect(effects).toContainText('+1% morale target across the company');
  await expect(effects).toContainText('3 months left');
});

test('(b) a major event blocks Continue until answered', async ({ page }) => {
  const save = `m10b-major-${stamp}`;
  run('tools/e2e_event_save.py', (dir) => [dir, save]);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('continue')).toBeDisabled();
  await expect(page.getByTestId('continue-blocked')).toHaveText('Answer 1 event first');
  await page.getByTestId('inbox-item').filter({ hasText: 'has gone quiet' }).click();
  await page.getByTestId('event-card').locator('[data-choice="A"]').click();
  await expect(page.getByTestId('continue')).toBeEnabled();
  await expect(page.getByTestId('continue-blocked')).toHaveCount(0);
});

test('(c) a one-engineer product shows "team too small" with the maintenance line', async ({
  page,
}) => {
  const save = `m10b-small-${stamp}`;
  run('tools/e2e_m9_save.py', (dir) => ['small', dir, save]);
  await page.goto(`/game/${save}/products`);
  await page.getByRole('link', { name: 'Pipeline' }).first().click();
  const strength = page.getByTestId('product-team-strength');
  await expect(strength).toContainText('Below 1.5 Pipeline slips; full speed at 6');
  await expect(strength).toContainText('Add about 1 builder to stop the slide');
  await continueMonth(page);
  await page.goto(`/game/${save}/products`);
  await page.getByRole('link', { name: 'Pipeline' }).first().click();
  await expect(page.getByText('Falling: the team is too small')).toBeVisible();
});

test('(d) set a regional price and see it shown', async ({ page }) => {
  const save = `m10b-region-${stamp}`;
  run('tools/e2e_m9_save.py', (dir) => ['geo', dir, save]);
  await page.goto(`/game/${save}/products`);
  await page.getByRole('link', { name: 'Pipeline' }).first().click();
  const regions = page.getByTestId('regions-panel');
  await regions.getByTestId('launch-europe').click();
  await page.getByTestId('launch-confirm').click();
  await expect(regions.getByTestId('region-status-europe')).toContainText('Localizing until');
  await regions.getByTestId('prices-europe').click();
  const dialog = page.getByRole('dialog');
  await dialog.getByTestId('region-price-smb').fill('39');
  await dialog.getByRole('button', { name: 'Set' }).click();
  await expect(dialog).toContainText('now $39');
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('regional-price-europe-smb')).toContainText('$39');
  await expect(regions).toContainText('$39');
});
