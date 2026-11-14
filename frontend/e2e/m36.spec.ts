import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M36 flows (formulas.md 45): (a) a new game with a partner and two children, and family time
// set on the Family screen; (b) a child of 18 educated at a top university, their ranges
// narrowing; (c) a succession to an heir makes them the player, and the adviser comments on
// the next proposal. Saves for (b) and (c) come from tools/e2e_m36_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m36_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

async function widths(page: Page): Promise<number> {
  const texts = await page
    .getByTestId('family-member')
    .first()
    .getByTestId('member-skill-range')
    .allTextContents();
  return texts.reduce((sum, t) => {
    const [lo, hi] = t.split('-').map(Number);
    return sum + (hi - lo);
  }, 0);
}

test('(a) a new game with a partner and two children; family time', async ({ page }) => {
  const company = `Hearth ${stamp}`;
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(company);
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  await page.getByTestId('family-setting').selectOption('children');
  await page.getByTestId('family-child-age-0').fill('6');
  await page.getByTestId('family-add-child').click();
  await page.getByTestId('family-child-age-1').fill('3');
  await page.getByTestId('start-game').click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/);
  const save = new URL(page.url()).pathname.split('/')[2];

  await page.goto(`/game/${save}/people/family`);
  await expect(page.getByTestId('family-screen')).toBeVisible();
  await expect(page.getByTestId('family-member')).toHaveCount(2);
  await expect(page.getByTestId('partner-name')).not.toBeEmpty();
  await expect(page.getByTestId('family-time')).toHaveText('10');
  await page.getByTestId('family-time-input').fill('14');
  await page.getByTestId('family-time-save').click();
  await expect(page.getByTestId('family-time')).toHaveText('14');
});

test('(b) a child of 18 at a top university: their ranges narrow', async ({ page }) => {
  const save = `m36-teen-${stamp}`;
  tool('teen', save);
  await page.goto(`/game/${save}/people/family`);
  await expect(page.getByTestId('family-member')).toHaveCount(1);
  const before = await widths(page);
  expect(before).toBeGreaterThan(0);
  await page
    .locator('[data-testid="educate-choice"][data-stage="university"][data-tier="top"]')
    .click();
  await expect(page.getByTestId('family-member').first()).toContainText('Top university');
  await expect.poll(() => widths(page)).toBeLessThan(before);
});

test('(c) succession to an heir; the adviser comments on the next proposal', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m36-heir-${stamp}`;
  tool('heir', save);
  await page.goto(`/game/${save}/people/1?tab=family`);
  await expect(page.getByTestId('founder-family-tab')).toBeVisible();
  const select = page.getByTestId('succession-heir-select');
  const heir = (await select.locator('option:checked').textContent()) ?? '';
  expect(heir).not.toBe('');
  await page.getByTestId('succession-hand-over').click();
  await expect(page.getByTestId('succession-confirm-text')).toContainText(heir);
  await page.getByTestId('succession-confirm').click();

  await page.goto(`/game/${save}/people/family`);
  await expect(page.getByTestId('family-head')).toContainText(heir);
  await expect(page.getByTestId('adviser-panel')).toBeVisible();

  tool('proposal', save);
  const events = await (await page.request.get(`/api/saves/${save}/events`)).json();
  for (const id of (events.blocking_proposal_ids ?? []) as number[]) {
    await page.request.post(`/api/saves/${save}/scaleup/proposals/${id}/decline`);
  }
  for (const id of (events.blocking_event_ids ?? []) as number[]) {
    await page.request.post(`/api/saves/${save}/events/${id}/choose`, { data: { choice: 'A' } });
  }
  await page.reload();
  await pressContinue(page);
  await page.goto(`/game/${save}/people/family`);
  const opinion = page.getByTestId('adviser-opinion').first();
  await expect(opinion).toContainText('lease');
  await expect(opinion).toHaveAttribute('data-stance', /support|oppose/);
});
