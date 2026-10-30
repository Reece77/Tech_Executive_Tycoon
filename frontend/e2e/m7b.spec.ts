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

test('(b) rename, duplicate and restore a save, and find the restored copy', async ({
  page,
  request,
}) => {
  const save = `m7b-saves-${stamp}`;
  makeSave(save); // played two months; no backup yet
  // A periodic backup comes every 12 months; play to it through the API.
  for (let i = 0; i < 10; i++) {
    const events = await (await request.get(`/api/saves/${save}/events`)).json();
    if (events.blocking_event_id !== null) {
      await request.post(`/api/saves/${save}/events/${events.blocking_event_id}/choose`, {
        data: { choice: 'A' },
      });
    }
    expect((await request.post(`/api/saves/${save}/advance`)).ok()).toBe(true);
  }
  await page.goto('/');
  const row = page.getByTestId('save-row').filter({ hasText: save });
  await expect(row).toHaveCount(1);
  await row.getByTestId(`rename-${save}`).click();
  await page.getByTestId('rename-submit-name').fill(`Main run ${stamp}`);
  await page.getByTestId('rename-submit').click();
  const renamed = page.getByTestId('save-row').filter({ hasText: `Main run ${stamp}` });
  await expect(renamed).toContainText('Kestrel');

  await renamed.getByTestId(`duplicate-${save}`).click();
  await page.getByTestId('duplicate-submit-name').fill(`Side run ${stamp}`);
  await page.getByTestId('duplicate-submit').click();
  await expect(page.getByTestId('save-row').filter({ hasText: `Side run ${stamp}` })).toHaveCount(
    1,
  );

  await renamed.getByTestId(`backups-${save}`).click();
  const backups = page.getByRole('dialog');
  await expect(backups).toContainText('The original save is never changed');
  await backups.getByTestId('backup-row').first().getByTestId('restore-backup').click();
  await expect(page.getByTestId('restored-notice')).toContainText('Kestrel (restored, Jan 2011)');
  const restored = page.getByTestId('save-row').filter({ hasText: 'Kestrel (restored, Jan 2011)' });
  await expect(restored.first()).toBeVisible();
  await page.getByTestId('restored-notice').getByRole('link', { name: 'Open it' }).click();
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2011');
  await page.keyboard.press('0');
  await expect(page).toHaveURL(/\/saves$/);
  // The restored copy plays on; the original stays where it was.
  await page.getByTestId('continue').click();
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2011');
  await expect(page.getByTestId('save-row').filter({ hasText: `Main run ${stamp}` })).toContainText(
    'Jan 2011',
  );
});
