import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, setupGame } from './helpers.ts';

// M25 flows: (a) Explain on churn shows the breakdown and a template explanation (the LLM is
// off); (b) launching a first product shows its achievement toast; (c) a mod made in the Data
// editor halves a rival's starting brand, and a new game started with it shows the change on
// the Rival screen; (d) a modded save shows its flag and earns no achievements.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const MOD = `half-sf-${stamp}`;

function tool(mode: string, name: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m25_save.py', mode, saveDir, name],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) Explain on churn: the breakdown and a template explanation', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m25-live-${stamp}`;
  tool('live', save);
  await page.goto(`/game/${save}/products/1`);
  await answerBlocking(page); // a critical event's modal would cover the screen
  await expect(page.getByTestId('product-churn')).toContainText('%');
  await page.getByTestId('explain-churn-1').first().click();
  const panel = page.getByTestId('explain-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('explain-item').first()).toContainText('SMB');
  await expect(page.getByTestId('explain-template')).toContainText(/^Churn (rose|fell|held)/);
  // Ask why with the LLM off: the chief of staff gives the template explanation.
  await page.getByTestId('explain-question').fill('Why did churn move?');
  await page.getByTestId('explain-ask').click();
  const template = await page.getByTestId('explain-template').innerText();
  await expect(page.getByTestId('explain-answer')).toContainText(template.slice(0, 40));
});

test('(b) launching a first product shows its achievement toast', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m25-ready-${stamp}`;
  tool('ready', save); // also starts a fresh profile
  await page.goto(`/game/${save}/products/1`);
  await answerBlocking(page);
  await page.getByTestId('launch').click();
  const toast = page.locator('[data-testid="achievement-toast"][data-key="first_launch"]');
  await expect(toast).toBeVisible();
  await expect(toast).toContainText('Ship it');
  await page.goto('/achievements');
  const row = page.getByTestId('achievement-row').filter({ hasText: 'Ship it' });
  await expect(row).toContainText('Earned');
  await expect(
    page.getByTestId('achievement-row').filter({ hasText: '???' }).first(),
  ).toBeVisible();
});

test('(c) a mod halves a rival brand and a new game shows it', async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto('/');
  await page.getByTestId('data-editor-link').click();
  await page.getByTestId('mod-name-input').fill(MOD);
  await page.getByTestId('mod-description-input').fill('Salesforce at half brand');
  await page.getByTestId('editor-file-incumbents.yaml').click();
  const form = page.getByTestId('editor-form-incumbents.yaml');
  await form.getByText('companies').first().click(); // open the list
  await page.getByTestId('open-companies/@name=Salesforce').click();
  await form.getByText('products').first().click();
  await page.getByTestId('open-companies/@name=Salesforce/products/@name=Sales Cloud').click();
  const brand = page.getByTestId(
    'field-companies/@name=Salesforce/products/@name=Sales Cloud/brand',
  );
  await expect(brand).toHaveValue('80');
  await brand.fill('40');
  await page.getByTestId('mod-save').click();
  await expect(page.getByTestId('mod-saved')).toContainText('1 changed value');

  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(`Modded ${stamp}`);
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  await page.getByTestId('mod-select').click();
  await page.getByRole('option', { name: new RegExp(MOD) }).click();
  await page.getByTestId('start-game').click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/);
  const save = new URL(page.url()).pathname.split('/')[2];
  await page.goto(`/game/${save}/competitors`);
  await page.getByTestId('rival-link').filter({ hasText: 'Salesforce' }).first().click();
  const salesCloud = page.getByTestId('rival-segment').filter({ hasText: 'Sales Cloud' }).first();
  await expect(salesCloud.locator('td').nth(4)).toHaveText('40'); // the brand column; base 80
});

test('(d) a modded save is flagged and earns no achievements', async ({ page }) => {
  test.setTimeout(120_000);
  const save = await setupGame(page, { company: `Flagged ${stamp}` }); // a plain game first
  const saves = await (await page.request.get('/api/saves')).json();
  const plain = saves.find((s: { save_id: string }) => s.save_id === save);
  expect(plain.mod_name).toBeNull();
  const modded = saves.find(
    (s: { mod_name: string | null; company_name: string }) =>
      s.mod_name === MOD && s.company_name === `Modded ${stamp}`,
  );
  expect(modded).toBeTruthy();
  await page.goto('/');
  await expect(page.getByTestId(`save-mod-${modded.save_id}`)).toContainText(MOD);
  const ach = await (await page.request.get(`/api/saves/${modded.save_id}/achievements`)).json();
  expect(ach.eligible).toBe(false);
  expect(ach.reason).toContain('Modded');
  await page.goto(`/game/${modded.save_id}/history/fame`);
  await expect(page.getByTestId('fame-modded')).toContainText(MOD);
  // Playing on earns nothing: no achievement names the modded save.
  await page.request.post(`/api/saves/${modded.save_id}/advance`);
  const profile = await (await page.request.get('/api/profile/achievements')).json();
  expect(
    profile.achievements.filter((a: { save: string | null }) => a.save === modded.save_id),
  ).toEqual([]);
});

test('(e) spoiler fields show only behind the toggle (PM ruling 2026-11-08)', async ({ page }) => {
  await page.goto('/mods');
  await page.getByTestId('editor-file-incumbents.yaml').click();
  const form = page.getByTestId('editor-form-incumbents.yaml');
  await form.getByText('companies').first().click();
  await page.getByTestId('open-companies/@name=Salesforce').click();
  const cash = page.getByTestId('field-companies/@name=Salesforce/cash_months');
  await expect(page.getByTestId('field-companies/@name=Salesforce/stage')).toBeVisible();
  await expect(cash).toHaveCount(0); // off by default
  await page.getByTestId('spoiler-toggle').check();
  const shown = page.getByTestId('editor-form-incumbents.yaml');
  await shown.getByText('companies').first().click();
  await page.getByTestId('open-companies/@name=Salesforce').click();
  await expect(page.getByTestId('field-companies/@name=Salesforce/cash_months')).toBeVisible();
});
