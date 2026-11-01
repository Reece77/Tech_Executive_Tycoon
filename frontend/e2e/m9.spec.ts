import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M9 flows: (a) lease a Berlin office, move a team there, and see costs and market rates
// change; (b) launch a product in Europe and see it go live after 3 months; (c) search for
// engineers in Bangalore and see city and salary on candidates.
test.describe.configure({ mode: 'serial' });

const GEO = `m9-geo-${Date.now()}`;

/** A save built by tools/e2e_m9_save.py: four engineers in a "Platform" team and a live
 * B2B SaaS product. */
function fixture(name: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m9_save.py', 'geo', saveDir, name],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) lease a Berlin office, move a team there, see costs and rates change', async ({
  page,
}) => {
  fixture(GEO);
  // An engineer's market rate in the HQ's flexible space: a senior engineer's $115,000.
  await page.goto(`/game/${GEO}/people`);
  const engineer = page.getByRole('row').filter({ hasText: 'Software engineer' }).first();
  await expect(engineer.getByTestId('person-city')).toHaveText('San Francisco');
  await engineer.getByRole('link').first().click();
  await expect(page.getByText('Market rate', { exact: true })).toBeVisible();
  await expect(page.locator('body')).toContainText('$115,000');
  const profile = page.url();
  await page.goto(`/game/${GEO}/org`);
  await page.getByTestId('offices-link').click();
  await expect(page.getByTestId('cities-panel')).toContainText('Bangalore');
  await expect(page.getByTestId('office-row').first()).toContainText('$3,000'); // 5 x $600
  await page.getByTestId('lease-open').click();
  await page.getByTestId('lease-city').click();
  await page.getByRole('option', { name: /^Berlin/ }).click();
  await page.getByTestId('lease-seats').click();
  await page.getByRole('option', { name: '50 seats', exact: true }).click();
  // 50 seats x $600 x 0.45 x 0.75 a month, and three months' rent to fit out (19.9).
  await expect(page.getByTestId('lease-preview')).toContainText('$10,125 a month');
  await expect(page.getByTestId('lease-preview')).toContainText('$30,375');
  await page.getByTestId('lease-confirm').click();
  await expect(page.getByTestId('office-row')).toHaveCount(2);
  await page.getByTestId('move-unit').click();
  await page.getByRole('option', { name: 'Platform' }).click();
  await page.getByTestId('move-office').click();
  await page.getByRole('option', { name: 'Berlin' }).click();
  await page.getByTestId('move-confirm').click();
  const berlin = page.getByTestId('office-row').nth(1);
  await expect(berlin).toContainText('4 / 50 seats');
  await expect(berlin).toContainText('Platform');
  await page.goto(`/game/${GEO}/people`);
  await expect(page.getByTestId('person-city').filter({ hasText: 'Berlin' })).toHaveCount(4);
  // The same engineer now works in Berlin: $115,000 x 0.65.
  await page.goto(profile);
  await expect(page.locator('body')).toContainText('$74,750');
});

test('(b) launch a product in Europe and see it go live after 3 months', async ({ page }) => {
  await page.goto(`/game/${GEO}/products`);
  await page.getByRole('link', { name: 'Pipeline' }).first().click();
  const regions = page.getByTestId('regions-panel');
  await expect(regions.getByTestId('region-status-north_america')).toHaveText('Home');
  await expect(regions.getByTestId('region-status-europe')).toHaveText('Not launched');
  await regions.getByTestId('launch-europe').click();
  await expect(page.getByRole('dialog')).toContainText('$40,000');
  await page.getByTestId('launch-confirm').click();
  await expect(regions.getByTestId('region-status-europe')).toContainText('Localizing until');
  for (let i = 0; i < 3; i += 1) await continueMonth(page);
  await page.goto(`/game/${GEO}/products`);
  await page.getByRole('link', { name: 'Pipeline' }).first().click();
  await expect(page.getByTestId('regions-panel').getByTestId('region-status-europe')).toContainText(
    'Live since',
  );
});

test('(c) search for engineers in Bangalore and see city and salary', async ({ page }) => {
  await page.goto(`/game/${GEO}/recruitment`);
  await page.getByTestId('search-city').click();
  await page.getByRole('option', { name: 'Bangalore' }).click();
  await page.getByTestId('channel-job_post').click();
  await page.getByTestId('open-search').click();
  await continueMonth(page);
  await page.goto(`/game/${GEO}/recruitment`);
  const cities = page.getByTestId('candidate-city');
  await expect(cities.filter({ hasText: 'Bangalore' }).first()).toBeVisible();
  const row = page.getByRole('row').filter({ hasText: 'Bangalore' }).first();
  await expect(row).toContainText('$');
});
