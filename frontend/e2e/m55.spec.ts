import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M55 flows (formulas.md 65): (a) green-light a series with a creative lead and see its audience
// at release; (b) overrule a lead and see the morale warning; (c) launch an ad tier and see ad
// revenue on the Streaming screen. Saves come from tools/e2e_m55_save.py (Reel, a stage-3
// consumer-apps group: `media` is the practice save pt-media in January 2016 with creative leads
// on offer; `stream` January 2023 with a live video service).
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(...args: string[]): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const [mode, save, ...rest] = args;
  execFileSync(
    'uv',
    [
      'run',
      '--project',
      'backend',
      'python',
      'tools/e2e_m55_save.py',
      mode,
      saveDir,
      save,
      ...rest,
    ],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

async function signAndGreenlight(page: import('@playwright/test').Page, save: string) {
  await page.goto(`/game/${save}/products/studio`);
  await page.getByTestId('studio-offers').locator('[data-testid^="sign-"]').first().click();
  await expect(page.getByTestId('lead-row')).toHaveCount(1);
  await page.getByTestId('greenlight-name').fill('Harbour Lights');
  await page.getByTestId('greenlight-lead').click();
  await page.getByRole('option').first().click();
  await page.getByTestId('greenlight-submit').click();
  await expect(page.getByTestId('slate-row').first()).toContainText('Harbour Lights');
}

test('(a) green-light a series with a creative lead and see its audience at release', async ({
  page,
}) => {
  test.setTimeout(600_000);
  const save = `m55-series-${stamp}`;
  tool('media', save);
  await signAndGreenlight(page, save);
  await expect(page.getByTestId('slate-row').first()).toContainText('0 of 14 months');
  tool('advance', save, '15');
  await page.goto(`/game/${save}/products/studio`);
  const row = page.getByTestId('released-row').first();
  await expect(row).toContainText('Harbour Lights');
  await expect(row.locator('[data-testid^="audience-"]')).toContainText('M of ');
  await expect(row.locator('[data-testid^="audience-"]')).toContainText('expected');
});

test('(b) overrule a lead and see the morale warning', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m55-overrule-${stamp}`;
  tool('media', save);
  await signAndGreenlight(page, save);
  await page.getByTestId('slate-row').first().locator('[data-testid^="overrule-"]').click();
  await expect(page.getByTestId('slate-row').first()).toContainText('1');
  await page.goto(`/game/${save}/inbox`);
  await expect(
    page.getByText(/Morale warning: .* is unhappy about Harbour Lights/).first(),
  ).toBeVisible();
});

test('(c) launch an ad tier and see ad revenue on the Streaming screen', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m55-adtier-${stamp}`;
  tool('stream', save);
  await page.goto(`/game/${save}/products/streaming`);
  const service = page.locator('[data-testid^="service-"]').first();
  await expect(service).toContainText('Reel Stream');
  const id = ((await service.getAttribute('data-testid')) ?? '').replace('service-', '');
  await expect(page.getByTestId(`ad-revenue-${id}`)).toContainText('ad revenue $0');
  await page.getByTestId(`ad-tier-${id}`).click(); // controlled: checked once the save answers
  await expect(page.getByTestId(`ad-tier-${id}`)).toBeChecked();
  tool('advance', save, '2');
  await page.goto(`/game/${save}/products/streaming`);
  await expect(page.getByTestId(`ad-revenue-${id}`)).not.toContainText('ad revenue $0');
});

test('(d) the Games and Social screens open', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m55-screens-${stamp}`;
  tool('stream', save);
  await page.goto(`/game/${save}/products/games`);
  await expect(page.getByTestId('games-titles')).toContainText('No games yet');
  await page.goto(`/game/${save}/products/social`);
  await expect(page.getByTestId('social-ads')).toContainText('North America');
  await expect(page.getByTestId('social-apps')).toContainText('Reel Moments');
});
