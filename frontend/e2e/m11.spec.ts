import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M11 flows: (a) assign a unit to an AI project and see the lead grow; (b) a scripted lead
// past the Transformers threshold brings the era early, with the news and the first-mover
// note; (c) license in from a rival and see the level change.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

/** A save built by tools/e2e_m11_save.py: six data scientists in an "AI lab" team. */
function fixture(mode: 'lab' | 'ahead' | 'rival', name: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m11_save.py', mode, saveDir, name],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

const aiLead = (page: import('@playwright/test').Page) =>
  page.getByTestId('domain-row').filter({ hasText: /^AI/ }).getByRole('cell').nth(2);

test('(a) assign a unit to an AI project and see the lead grow', async ({ page }) => {
  const save = `m11-lab-${stamp}`;
  fixture('lab', save);
  await page.goto(`/game/${save}/products`);
  await page.getByTestId('research-link').click();
  await expect(page.getByTestId('levels-panel')).toContainText('Software platform');
  await expect(aiLead(page)).toHaveText('0.0');
  await page.getByTestId('project-open').click();
  await page.getByTestId('project-domain').click();
  await page.getByRole('option', { name: 'AI', exact: true }).click();
  await page.getByTestId('project-confirm').click();
  const row = page.getByTestId('project-row');
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('AI lab');
  await expect(row).toContainText('100%');
  await continueMonth(page);
  await page.goto(`/game/${save}/products/research`);
  await expect(aiLead(page)).not.toHaveText('0.0');
  const lead = Number(await aiLead(page).innerText());
  expect(lead).toBeGreaterThan(1);
});

test('(b) a lead past the Transformers threshold brings the era early', async ({ page }) => {
  const save = `m11-ahead-${stamp}`;
  fixture('ahead', save);
  await page.goto(`/game/${save}/products/research`);
  await expect(page.getByTestId('era-transformers')).toHaveAttribute('data-status', 'later');
  await continueMonth(page);
  await page.goto(`/game/${save}/products/research`);
  const era = page.getByTestId('era-transformers');
  await expect(era).toHaveAttribute('data-status', 'arrived');
  await expect(era).toContainText('months early (You)');
  await page.goto(`/game/${save}/inbox`);
  await page.getByText('Transformers has arrived').first().click();
  await expect(page.locator('body')).toContainText('pulled forward by your research');
  await expect(page.locator('body')).toContainText('First-mover head start');
  await page.goto(`/game/${save}/products/markets`);
  await expect(page.getByTestId('market-eras').getByTestId('era-transformers')).toContainText(
    'months early (You)',
  );
});

test('(c) license in from a rival and see the level change', async ({ page }) => {
  const save = `m11-rival-${stamp}`;
  fixture('rival', save);
  await page.goto(`/game/${save}/products/research`);
  await page.getByTestId('rival-domain').click();
  await page.getByRole('option', { name: 'Devices' }).click();
  // exactly IBM, not M12a's IBM SoftLayer
  const ibm = page
    .getByTestId('rival-lead-row')
    .filter({ has: page.getByRole('cell', { name: 'IBM', exact: true }) });
  await expect(ibm).toBeVisible();
  const devices = page.getByTestId('domain-row').filter({ hasText: /^Devices/ });
  await expect(devices.getByRole('cell').nth(2)).toHaveText('0.0');
  await ibm.getByTestId('license-in-open').click();
  await page.getByTestId('license-points').fill('5');
  await expect(page.getByTestId('license-terms')).toContainText('a point');
  await page.getByTestId('license-confirm').click();
  await expect(devices.getByRole('cell').nth(2)).toHaveText('5.0');
  await expect(page.getByTestId('license-row')).toContainText('From IBM');
});
