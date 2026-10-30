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

test('(c) search History for a hired person and open their profile', async ({ page, request }) => {
  const save = `m7b-history-${stamp}`;
  makeSave(save); // three engineers hired through the normal actions
  type Person = { person_id: number; name: string; is_founder: boolean };
  const people = (await (await request.get(`/api/saves/${save}/people`)).json()) as Person[];
  const hire = people.find((p) => !p.is_founder);
  if (!hire) throw new Error('the fixture hires three engineers');
  await page.goto(`/game/${save}/inbox`);
  await page.keyboard.press('9');
  await expect(page).toHaveURL(/\/history$/);
  await expect(page.getByTestId('history-search')).toBeVisible();
  await page.keyboard.press('/');
  await expect(page.getByTestId('history-search')).toBeFocused();
  await page.keyboard.type(hire.name.split(' ')[1]);
  const row = page
    .getByTestId('history-row')
    .filter({ hasText: `${hire.name} accepted your offer` });
  await expect(row).toHaveCount(1);
  await expect(page.getByTestId('history-count')).toContainText('match');
  await row.getByTestId('history-person-link').click();
  await expect(page).toHaveURL(new RegExp(`/people/${hire.person_id}$`));
  await expect(page.getByRole('heading', { name: hire.name })).toBeVisible();
});

test('(d) hover a top-bar number and see its breakdown', async ({ page }) => {
  const save = `m7b-tooltip-${stamp}`;
  makeSave(save); // two months played with three engineers on the payroll
  await page.goto(`/game/${save}/people`);
  await page.getByTestId('top-cash').hover();
  const tip = page.getByRole('tooltip');
  await expect(tip).toContainText("Last month's change in cash");
  await expect(tip.getByTestId('breakdown')).toContainText('Payroll');
  await expect(tip).toContainText(/Cash (rose|fell) \$[\d,.]+ in Feb 2010/);
  await page.mouse.move(0, 0);
  await page.getByTestId('top-runway').hover();
  await expect(page.getByRole('tooltip')).toContainText('Projected net burn');
  // Definitions: column headers have their glossary text.
  await page.mouse.move(0, 0);
  await page.getByRole('table', { name: 'Roster' }).getByText('Morale', { exact: true }).hover();
  await expect(page.getByRole('tooltip')).toContainText('How happy the person is');
});

test('(e) save a People view, reload, and find it still selected', async ({ page }) => {
  const save = `m7b-views-${stamp}`;
  const other = `m7b-views-other-${stamp}`;
  makeSave(save);
  makeSave(other);
  const view = `Pay review ${stamp}`;
  await page.goto(`/game/${save}/people`);
  const roster = page.getByRole('table', { name: 'Roster' });
  await expect(roster.getByRole('columnheader', { name: 'Age', exact: true })).toBeVisible();
  const menu = page.getByTestId('views-people.overview');
  await menu.click();
  await page.getByTestId('column-age').click(); // hide Age
  await page.keyboard.press('Escape');
  await expect(roster.getByRole('columnheader', { name: 'Age', exact: true })).toHaveCount(0);
  await expect(menu).toContainText('(changed)');
  await menu.click();
  await page.getByTestId('view-save-as').click();
  await page.getByTestId('view-name').fill(view);
  await page.getByTestId('view-save').click();
  await expect(menu).toHaveText(`View: ${view} ▾`);

  await page.reload();
  await expect(page.getByTestId('views-people.overview')).toHaveText(`View: ${view} ▾`);
  await expect(roster.getByRole('columnheader', { name: 'Age', exact: true })).toHaveCount(0);

  // Views are shared by every save (saves/ui_settings.json), and Default brings Age back.
  await page.goto(`/game/${other}/people`);
  await expect(page.getByTestId('views-people.overview')).toHaveText(`View: ${view} ▾`);
  await page.getByTestId('views-people.overview').click();
  await page.getByTestId('view-option').filter({ hasText: 'Default' }).click();
  await page.keyboard.press('Escape');
  await expect(roster.getByRole('columnheader', { name: 'Age', exact: true })).toBeVisible();
  // ? lists every shortcut.
  await page.locator('main').click({ position: { x: 5, y: 5 } });
  await page.keyboard.press('?');
  await expect(page.getByTestId('shortcut-list')).toContainText('Go on holiday');
});
