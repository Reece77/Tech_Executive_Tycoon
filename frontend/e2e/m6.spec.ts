import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M6 flows: (a) answer an event and see its effect; (b) a scripted critical event blocks
// Continue until answered, and its follow-up arrives next month; (c) switch to offline
// templates in Settings and receive a template event. Saves come from tools/e2e_event_save.py.
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

async function cash(page: Page): Promise<number> {
  const text = (await page.getByTestId('top-cash').textContent()) ?? '0';
  return Number(text.replace(/[^0-9-]/g, ''));
}

test('(a) answer an event and see its effect', async ({ page }) => {
  const save = `m6-event-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/inbox`);
  await expect(page.getByTestId('events-header')).toContainText('1 event to answer');
  await page.getByTestId('inbox-item').filter({ hasText: 'has gone quiet' }).click();
  const card = page.getByTestId('event-card');
  await expect(card).toBeVisible();
  await expect(card).toContainText(/costs about \$/);
  const before = await cash(page);
  await card.locator('[data-choice="B"]').click();
  await expect(card.getByTestId('event-answered')).toHaveText('You chose B.');
  await expect.poll(() => cash(page)).toBeLessThan(before);
  await expect(page.getByTestId('events-header')).toContainText('No events to answer');
});

test('(b) a critical event blocks Continue until answered', async ({ page }) => {
  const save = `m6-critical-${stamp}`;
  makeSave(save, '--critical');
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByRole('dialog');
  await expect(modal).toContainText('Payroll is at risk');
  await expect(page.getByTestId('continue')).toBeDisabled();
  await expect(page.getByTestId('continue-blocked')).toHaveText('Answer the critical event first');
  await page.keyboard.press('Escape'); // the modal cannot be dismissed
  await expect(modal).toBeVisible();
  await modal.locator('[data-choice="A"]').click();
  await expect(modal).toBeHidden();
  await expect(page.getByTestId('continue')).toBeEnabled();
  await continueMonth(page);
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: 'The morning after the payroll scare' }),
  ).toHaveCount(1);
});

test('(c) offline templates in Settings, then a template event', async ({ page }) => {
  const save = `m6-offline-${stamp}`;
  makeSave(save, '--queued');
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('settings-button').click();
  await expect(page).toHaveURL(/\/settings$/);
  await page.getByTestId('adapter-choice').getByText('Offline templates').click();
  await page.getByTestId('save-settings').click();
  await expect(page.getByTestId('adapter-in-use')).toHaveText('Offline templates');
  await page.reload();
  await expect(page.getByTestId('adapter-in-use')).toHaveText('Offline templates');
  await continueMonth(page);
  await page.goto(`/game/${save}/inbox`);
  await page
    .getByTestId('inbox-item')
    .filter({ hasText: 'The morning after the payroll scare' })
    .click();
  await expect(page.getByTestId('event-card')).toContainText('Written by a template');
});
