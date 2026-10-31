import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M7c flows: (a) answer an event, follow its History link and see its card with the choice
// taken; (b) a deep link to an inbox message opens it; (c) fire someone and open their
// Former employee profile from History. Saves come from tools/e2e_event_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function makeSave(name: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_event_save.py', saveDir, name],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) follow a History event link and see the event card', async ({ page }) => {
  const save = `m7c-event-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('inbox-item').filter({ hasText: 'has gone quiet' }).click();
  const card = page.getByTestId('event-card');
  await card.locator('[data-choice="B"]').click();
  await expect(card.getByTestId('event-answered')).toHaveText('You chose B.');
  await page.goto(`/game/${save}/history/timeline`);
  await page.getByTestId('history-event-link').first().click();
  await expect(page).toHaveURL(/\/inbox\/\d+$/);
  await expect(page.getByTestId('event-card')).toBeVisible();
  await expect(page.getByTestId('event-card').getByTestId('event-answered')).toHaveText(
    'You chose B.',
  );
});

test('(b) a deep link opens that message', async ({ page }) => {
  const save = `m7c-deep-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/inbox`);
  const last = page.getByTestId('inbox-item').last();
  const title = (await last.textContent()) ?? '';
  await last.click();
  await expect(page).toHaveURL(/\/inbox\/\d+$/);
  const url = page.url();
  await page.goto(`/game/${save}/overview`);
  await page.goto(url);
  await expect(page.getByTestId('message-title')).not.toHaveText('');
  expect(title).toContain((await page.getByTestId('message-title').textContent()) ?? '-');
});

test('(c) a former employee opens a read-only profile from History', async ({ page }) => {
  const save = `m7c-former-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/people`);
  await page.getByTestId('person-row').nth(1).getByRole('link').first().click(); // not the founder
  const name = (await page.getByTestId('profile-name').textContent()) ?? '';
  await page.getByTestId('fire').click();
  await page.getByTestId('fire-confirm').click();
  await expect(page).toHaveURL(/\/people$/);
  await page.goto(`/game/${save}/history/timeline`);
  await page.getByTestId('history-person-link').filter({ hasText: name }).first().click();
  await expect(page.getByTestId('former-badge')).toHaveText('Former employee');
  await expect(page.getByTestId('profile-name')).toHaveText(name);
  await expect(page.getByTestId('former-summary')).toContainText('Let go');
});
