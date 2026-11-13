import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { setupGame } from './helpers.ts';

// M29 flows (formulas.md 42): (a) a new game's first unlock and the checklist ticking; (b) the
// palette jumping to a person; (c) the inbox's Needs you tab; (d) the launcher's single-port
// server opening the Main menu. Settings are shared by every save in the folder, so each flow
// that changes them puts the defaults back.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const DEFAULTS = { show_everything: false, guided_first_year: true, stop_on: 'major' };
const LAUNCHER_URL = `http://127.0.0.1:${process.env.TST_E2E_LAUNCHER_PORT ?? 5176}`;

test.afterEach(async ({ request }) => {
  await request.put('/api/settings/ui/onboarding', { data: DEFAULTS });
});

function saveOf(page: Page): string {
  return new URL(page.url()).pathname.split('/')[2];
}

test("(a) a new game's first unlock and the checklist ticking", async ({ page }) => {
  await setupGame(page, { company: `Unlock ${stamp}` });
  const save = saveOf(page);
  const nav = page.getByRole('navigation', { name: 'Game screens' });
  // stage-1 screens only
  await expect(nav.getByTestId('nav-products')).toBeVisible();
  await expect(nav.getByTestId('nav-products-hardware')).toHaveCount(0);
  await expect(nav.getByTestId('nav-products-fabs')).toHaveCount(0);
  await expect(page.getByTestId('nav-group-chain')).toHaveCount(0);

  await nav.getByRole('link', { name: /Overview/ }).click();
  const checklist = page.getByTestId('getting-started');
  await expect(checklist).toContainText('0 of 7');
  await expect(page.getByTestId('step-product_team')).toHaveAttribute('data-done', 'false');
  await expect(page.getByTestId('what-next')).toBeVisible();

  // A hardware product makes Hardware relevant: it unlocks with an inbox item and a toast.
  const created = await page.request.post(`/api/saves/${save}/products`, {
    data: { name: 'Gizmo', category: 'devices', segments: ['consumer'] },
  });
  expect(created.ok()).toBe(true);
  const products = await (await page.request.get(`/api/saves/${save}/products`)).json();
  const gizmo = (products as { product_id: number; name: string }[]).find(
    (p) => p.name === 'Gizmo',
  );
  expect(gizmo).toBeDefined();
  await page.request.post(`/api/saves/${save}/products/${gizmo?.product_id}/assign`, {
    data: { unit_id: null },
  });
  await page.reload();
  const toast = page.getByTestId('unlock-toast');
  await expect(toast).toHaveAttribute('data-key', 'hardware');
  await expect(toast).toContainText('Gizmo is a hardware product');
  await expect(nav.getByTestId('nav-products-hardware')).toBeVisible();
  await expect(page.getByTestId('step-product_team')).toHaveAttribute('data-done', 'true');
  await expect(checklist).toContainText('1 of 7');

  // its guide page, and the item in the inbox
  await toast.getByRole('link', { name: 'What it does' }).click();
  await expect(page.getByTestId('guide-page')).toContainText('Devices and servers');
  await expect(page.getByTestId('guide-status')).toContainText('Gizmo is a hardware product');
  await page.goto(`/game/${save}/inbox?tab=news`);
  await expect(page.getByTestId('inbox-item').filter({ hasText: 'New: Hardware' })).toHaveCount(1);

  // Show everything puts every screen in the side bar; dismissing hides the checklist.
  await page.goto(`/game/${save}/settings`);
  await page.getByTestId('setting-show-everything').click();
  await expect(nav.getByTestId('nav-products-fabs')).toBeVisible();
  await page.goto(`/game/${save}/overview`);
  await page.getByTestId('getting-started-dismiss').click();
  await expect(checklist).toHaveCount(0);
});

test('(b) the palette jumps to a person', async ({ page }) => {
  await setupGame(page, { company: `Palette ${stamp}` });
  const save = saveOf(page);
  const entries = (await (await page.request.get(`/api/saves/${save}/palette`)).json()).entries as {
    kind: string;
    label: string;
    path: string;
  }[];
  const founder = entries.find((e) => e.kind === 'person');
  expect(founder).toBeDefined();
  await page.keyboard.press('Control+k');
  const input = page.getByTestId('palette-input');
  await expect(input).toBeFocused();
  await input.fill(founder?.label.split(' ')[1] ?? '');
  await expect(page.getByTestId('palette-option').first()).toContainText(founder?.label ?? '');
  await input.press('Enter');
  await expect(page).toHaveURL(new RegExp(`/game/${save}/${founder?.path}$`));
  await expect(page.getByTestId('breadcrumbs')).toContainText(`People/${founder?.label}`);
  // a screen by name too, and the person is now a recent item
  await page.getByTestId('palette-open').click();
  await expect(page.getByTestId('palette-option').first()).toContainText(founder?.label ?? '');
  await page.getByTestId('palette-input').fill('cap table');
  await page.getByTestId('palette-input').press('Enter');
  await expect(page).toHaveURL(new RegExp(`/game/${save}/finance/captable$`));
});

test("(c) the inbox's Needs you tab", async ({ page }) => {
  const save = `m29-needs-${stamp}`;
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_event_save.py', saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
  await page.goto(`/game/${save}/overview`);
  await expect(page.getByTestId('overview-alerts')).toContainText('1 event to answer');
  await page.getByRole('link', { name: 'Open Needs you' }).click();
  await expect(page.getByTestId('inbox-tab-needs_you')).toHaveAttribute('aria-selected', 'true');
  const items = page.getByTestId('inbox-item');
  await expect(items).toHaveCount(1);
  await expect(items.first()).toContainText('has gone quiet');
  await page.getByTestId('inbox-tab-all').click();
  await expect.poll(() => items.count()).toBeGreaterThan(1);

  // Interruptions at critical only: the major event no longer stops Continue.
  await expect(page.getByTestId('continue')).toBeDisabled();
  await page.goto(`/game/${save}/settings`);
  await page.getByTestId('setting-stop-on').getByText('Critical events only').click();
  await expect(page.getByTestId('continue')).toBeEnabled();
  const date = await page.getByTestId('game-date').textContent();
  await page.getByTestId('continue').click();
  await expect(page.getByTestId('game-date')).not.toHaveText(date ?? '');
  await page.goto(`/game/${save}/inbox?tab=needs_you`);
  await expect(page.getByText('Nothing needs you right now.')).toBeVisible();
});

test("(d) the launcher's single-port server opens the Main menu", async ({ page, request }) => {
  const save = `m29-launch-${stamp}`;
  const made = await request.post('/api/saves', {
    data: { name: save, scenario: 'ex_big_tech_founders', company_name: 'Launchco' },
  });
  expect(made.ok()).toBe(true);
  await page.goto(`${LAUNCHER_URL}/`);
  await expect(page.getByRole('heading', { name: 'Tech Startup Tycoon' })).toBeVisible();
  const cont = page.getByTestId('continue-last');
  await expect(cont).toBeVisible();
  // Continue opens the save played last; deep links load from the same server
  await page.goto(`${LAUNCHER_URL}/game/${save}/overview`);
  await expect(page.getByTestId('game-shell')).toBeVisible();
  await expect(page.getByTestId('company-name')).toHaveText('Launchco');
  // Back up now, from the Saves screen
  await page.goto(`${LAUNCHER_URL}/`);
  await page.getByTestId(`backups-${save}`).click();
  await page.getByTestId('back-up-now').click();
  await expect(page.getByTestId('backed-up')).toBeVisible();
  await expect(page.getByTestId('backup-row').filter({ hasText: 'Backed up by you' })).toHaveCount(
    1,
  );
});
