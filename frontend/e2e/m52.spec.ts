import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M52 (formulas.md 66): the editor and sandbox. (a) "The EV maker" opened in the editor, its
// cash doubled, saved as a custom scenario and started: the game has the doubled cash; (b) that
// scenario exported and imported back under another name; (c) a save over after December 2069
// continued in sandbox and played a year. (a) and (b) run in order.

const stamp = Date.now();

function tool(mode: string, save: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m52_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

test.describe.serial('a custom scenario', () => {
  const slug = `ev-double-${stamp}`;

  test("(a) double the EV maker's cash, save it and start it", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto('/');
    await page.getByTestId('scenario-editor-link').click();
    await page.getByTestId('editor-start').selectOption('ev_maker');
    await page.getByTestId('editor-open-button').click();
    await expect(page.getByTestId('editor-label')).toHaveValue('The EV maker');
    const cash = page.getByTestId('editor-cash');
    const before = Number((await cash.inputValue()).replace(/[^0-9]/g, ''));
    expect(before).toBeGreaterThan(0);
    await cash.fill(String(before * 2));
    await page.getByTestId('editor-save-as-name').fill(slug);
    const saveAs = page.getByTestId('editor-save-as');
    await expect(saveAs).toBeEnabled();
    await saveAs.click();
    await expect(page.getByTestId('editor-message')).toHaveText(`Saved as ${slug}`);
    await page.getByTestId('editor-game-company').fill(`Volt ${stamp}`);
    await page.getByTestId('editor-start-game-button').click();
    await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/, { timeout: 180_000 });
    const save = new URL(page.url()).pathname.split('/')[2];
    await expect(page.getByTestId('game-date')).toHaveText('Jan 2016');
    const overview = await (await page.request.get(`/api/saves/${save}/overview`)).json();
    expect(overview.cash_cents).toBe(before * 2 * 100);
    await expect(page.getByTestId('top-cash')).toContainText('$');
    const saves = await (await page.request.get('/api/saves')).json();
    expect(saves.find((s: { save_id: string }) => s.save_id === save).mode).toBe('custom');
  });

  test('(b) export the scenario and import it back', async ({ page }, info) => {
    await page.goto(`/editor?custom=${slug}`);
    await expect(page.getByTestId('editor-label')).toHaveValue('The EV maker');
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId('editor-export').click(),
    ]);
    expect(download.suggestedFilename()).toBe(`${slug}.yaml`);
    const text = readFileSync(await download.path(), 'utf8');
    expect(text).toContain('format: 1');
    const copy = join(info.outputDir, `shared-${stamp}.yaml`);
    writeFileSync(copy, text);
    await page.getByTestId('editor-import-file').setInputFiles(copy);
    await expect(page.getByTestId('editor-message')).toHaveText(`Imported shared-${stamp}`);
    await page.goto('/scenarios');
    const rows = page.getByTestId('custom-row');
    await expect(rows.filter({ hasText: `shared-${stamp}.yaml` })).toBeVisible();
    await expect(rows.filter({ hasText: `${slug}.yaml` })).toBeVisible();
    const cards = await (await page.request.get('/api/scenarios/custom')).json();
    const hashes = cards
      .filter((c: { slug: string }) => c.slug === slug || c.slug === `shared-${stamp}`)
      .map((c: { sha256: string }) => c.sha256);
    expect(hashes).toHaveLength(2);
    expect(hashes[0]).toBe(hashes[1]); // the same canonical text
  });
});

test('(c) continue a 2069 save in sandbox and advance a year', async ({ page }) => {
  test.setTimeout(240_000);
  const save = `m52-2069-${stamp}`;
  tool('end2069', save);
  await page.goto(`/game/${save}/over`);
  await expect(page.getByTestId('sandbox-continue')).toBeVisible();
  await page.getByTestId('continue-sandbox').click();
  await expect(page).toHaveURL(new RegExp(`/game/${save}/overview$`));
  const campaign = await (await page.request.get(`/api/saves/${save}/campaign`)).json();
  expect(campaign.length).toBe('endless');
  expect(campaign.end_label).toBe('no end');
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2070');
  for (let i = 0; i < 12; i++) await continueMonth(page);
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2071');
});
