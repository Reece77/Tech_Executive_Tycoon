import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M7b flows: (a) a Holiday stops on a major event and the summary appears; (b) rename,
// duplicate and restore a save; (c) search History for a hire and open their profile;
// (d) a top-bar number's breakdown; (e) a saved People view survives a reload; (f) ask the
// COO with the mock adapter.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function makeSave(name: string, flag?: '--critical' | '--queued') {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const args = ['run', '--project', 'backend', 'python', 'tools/e2e_event_save.py', saveDir, name];
  if (flag) args.push(flag);
  execFileSync('uv', args, {
    cwd: resolve(process.cwd(), '..'),
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
}

test('(a) a 6-month Holiday stops on a major event and the summary appears', async ({ page }) => {
  const save = `m7b-holiday-${stamp}`;
  makeSave(save, '--queued'); // next month brings a known major event
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('game-date')).not.toHaveText('…');
  await page.keyboard.press('h');
  const dialog = page.getByRole('dialog', { name: 'Go on holiday' });
  await expect(dialog).toBeVisible();
  await dialog.getByTestId('holiday-months').fill('6');
  await expect(dialog.getByText('Major and critical')).toBeVisible();
  await dialog.getByTestId('holiday-start').click();
  const done = page.getByTestId('holiday-done');
  await expect(done).toContainText('an event needs your answer', { timeout: 30_000 });
  await expect(done).toContainText('after 1 month');
  await done.getByTestId('holiday-summary-link').click();
  await expect(page.getByTestId('message-title')).toHaveText('While you were away: 1 month');
  await expect(page.getByTestId('message-body')).toContainText('Cash:');
  await expect(page.getByTestId('continue')).toBeEnabled();
});
