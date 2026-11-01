import { expect, test, type APIRequestContext } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { api, continueMonth } from './helpers.ts';

// M5 flows: (a) open Competitors and a rival profile; (b) receive a scripted approach, counter
// it with a raise and see the answer at Continue; (c) poach a rival's key person through the
// new Recruitment channel.
test.describe.configure({ mode: 'serial' });

const SEED = 16;
const COMPS = `m5-comps-${Date.now()}`;
const APPROACH = `m5-approach-${Date.now()}`;

async function createSave(request: APIRequestContext, name: string) {
  await api(request, 'POST', '/saves', {
    name,
    company_name: 'Rival Watch',
    scenario: 'funded_spinout',
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
}

test('(a) open Competitors and a rival profile', async ({ page, request }) => {
  await createSave(request, COMPS);
  await api(request, 'POST', `/saves/${COMPS}/advance`);
  await page.goto(`/game/${COMPS}/overview`);
  await page.keyboard.press('8');
  await expect(page).toHaveURL(/\/competitors$/);
  await expect(page.getByTestId('rival-counts')).toContainText('23 established'); // 17 + M9's six regional incumbents
  const rows = page.getByTestId('rival-row');
  await expect(rows).toHaveCount(23);
  await expect(page.getByTestId('news-line').first()).toBeVisible();
  await page.getByRole('link', { name: 'Salesforce' }).click();
  await expect(page).toHaveURL(/\/competitors\/\d+$/);
  await expect(page.getByTestId('rival-name')).toContainText('Salesforce');
  await expect(page.getByTestId('style-chip').first()).toHaveText('Premium');
  await expect(page.getByTestId('rival-segment').first()).toBeVisible();
  await expect(page.getByTestId('key-person')).toHaveCount(8);
  await expect(page.getByTestId('poach-rival')).toContainText('Poach from Salesforce · 10 energy');
});

test('(b) counter a scripted approach and see the answer at Continue', async ({ page }) => {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_approach_save.py', saveDir, APPROACH],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
  await page.goto(`/game/${APPROACH}/competitors`);
  const panel = page.getByTestId('approach-panel');
  await expect(panel).toContainText('Zoho is trying to hire');
  await expect(page.getByTestId('approach-band')).toContainText(
    /likely to stay|might go|likely to go/,
  );
  await panel.getByTestId('counter-approach').click();
  const dialog = page.getByTestId('raise-dialog');
  await expect(dialog).toBeVisible();
  const offer = (await panel.textContent())?.match(/offered \$([\d,]+)/)?.[1] ?? '0';
  const double = String(Number(offer.replace(/,/g, '')) * 2);
  await dialog.getByTestId('raise-salary').fill(double);
  await expect(page.getByTestId('counter-band')).toContainText('likely to stay');
  await expect(dialog.getByTestId('confirm-raise')).toBeEnabled(); // the preview has settled
  await dialog.getByTestId('confirm-raise').click();
  await expect(dialog).toBeHidden();

  await continueMonth(page);
  await page.goto(`/game/${APPROACH}/inbox`);
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: /stays|is leaving for Zoho/ }),
  ).toHaveCount(1);
});

test('(c) poach a rival key person through the Recruitment channel', async ({ page, request }) => {
  await page.goto(`/game/${COMPS}/recruitment`);
  await page.getByTestId('channel-poach').click();
  await page.getByTestId('poach-rival-select').click();
  await page.getByRole('option', { name: 'Salesforce' }).click();
  const open = page.getByTestId('open-search');
  await expect(open).toContainText('Poach · 10 energy');
  await open.click();
  await expect(page.getByTestId('search-row').first()).toContainText('Poach from Salesforce');
  await continueMonth(page);
  const row = page.getByTestId('candidate-row').first();
  await expect(row).toBeVisible();
  const name = (await row.getByRole('link').first().textContent()) ?? '';
  await row.getByTestId('interview').click();
  await expect(row.getByTestId('offer')).toBeEnabled(); // the interview has saved
  await row.getByTestId('offer').click();
  const offerPanel = page.getByRole('complementary', { name: 'Make an offer' });
  const ask = Number(
    ((await offerPanel.getByText(/asks \$/).textContent()) ?? '')
      .replace(/.*asks \$/, '')
      .replace(/,/g, ''),
  );
  await offerPanel.getByTestId('offer-salary').fill(String(ask * 3));
  await expect(offerPanel.getByTestId('send-offer')).toBeEnabled();
  await offerPanel.getByTestId('send-offer').click();
  await expect(offerPanel).toBeHidden(); // the offer has saved
  await continueMonth(page);
  const people = await api<{ name: string }[]>(request, 'GET', `/saves/${COMPS}/people`);
  expect(people.map((p) => p.name)).toContain(name);
});
