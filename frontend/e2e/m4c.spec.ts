import { expect, test, type APIRequestContext } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { api, continueMonth } from './helpers.ts';

// M4c flows: (a) interview a candidate and see what it taught, then references sharpen the
// personality columns; (b) at a Series A, choose the board nominee and open an investor
// director's card; (c) mark everything read, archive read items and find them again.
test.describe.configure({ mode: 'serial' });

const SEED = 16;
const HIRING = `m4c-hiring-${Date.now()}`;
const RAISE = `m4c-raise-${Date.now()}`;

async function createSave(request: APIRequestContext, name: string, scenario: string) {
  await api(request, 'POST', '/saves', {
    name,
    company_name: 'Learn Co',
    scenario,
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
}

test('(a) interview a candidate and see what you learned', async ({ page, request }) => {
  await createSave(request, HIRING, 'ex_big_tech_founders');
  await api(request, 'POST', `/saves/${HIRING}/recruitment/searches`, {
    role: 'software_engineer',
    channel: 'job_post',
  });
  await api(request, 'POST', `/saves/${HIRING}/advance`);
  await page.goto(`/game/${HIRING}/recruitment`);
  const row = page.getByTestId('candidate-row').first();
  await expect(row).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Personality' })).toBeVisible();
  const loyaltyBefore = (await row.getByTitle(/^Loyalty:/).textContent()) ?? '';

  await row.getByTestId('interview').click();
  const panel = page.getByTestId('learned-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('learned-card')).toContainText('Interview');
  await expect(panel.getByTestId('learned-range').first()).toBeVisible();
  await expect(panel.getByTestId('learned-potential')).toContainText('Potential:');
  await expect(panel).toContainText('Interests:');
  await expect(page.getByTestId('energy')).toHaveText('52 / 60'); // a new month's 60, less the interview's 8

  await row.getByTestId('references').click();
  await expect(panel.getByTestId('learned-card')).toContainText('References');
  await expect(panel.getByTestId('learned-range').first()).toBeVisible();
  // References narrow personality: the table's Loyalty column is now as the panel says.
  const loyalty = panel.getByTestId('learned-range').filter({ hasText: 'Loyalty' });
  if ((await loyalty.count()) > 0) {
    await expect(row.getByTitle(/^Loyalty:/)).not.toHaveText(loyaltyBefore);
  }
  await expect(page.getByTestId('energy')).toHaveText('48 / 60'); // references 4
});

/** A funded spinout with four engineers at $2M ARR, ready for a Series A: built by
 * tools/e2e_series_a_save.py before the API opens it (reaching $1M ARR on screen takes about
 * fifteen months, and the flow is not about that). */
function readyForSeriesA() {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_series_a_save.py', saveDir, RAISE],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(b) at a Series A, choose the nominee and open a director card', async ({
  page,
  request,
}) => {
  readyForSeriesA();
  const people = await api<{ person_id: number; name: string; is_founder: boolean }[]>(
    request,
    'GET',
    `/saves/${RAISE}/people`,
  );
  const staff = people.filter((p) => !p.is_founder);
  expect(staff.length, 'the spinout hired at twice the ask').toBeGreaterThanOrEqual(2);

  await page.goto(`/game/${RAISE}/finance/fundraising`);
  await page.getByTestId('round-target').fill('6000000');
  const start = page.getByTestId('start-round');
  await expect(start).toHaveText('Start Series A · 15 energy');
  await start.click();
  await expect(page.getByTestId('open-round')).toContainText('Series A · open');
  await continueMonth(page);
  await page.getByTestId('sheet-row').first().getByTestId('preview-sheet').click();
  const preview = page.getByTestId('dilution-preview');
  await expect(preview).toBeVisible();
  const select = preview.getByTestId('nominee-select');
  await expect(select).toHaveValue(/most senior/);
  await select.click();
  const options = page.getByRole('option');
  await expect(options).toHaveCount(staff.length);
  const chosen = ((await options.last().textContent()) ?? '').split(' · ')[0];
  await options.last().click();
  await expect(select).toHaveValue(new RegExp(`^${chosen}`));
  await page.getByTestId('accept-sheet').click();
  await expect(page.getByTestId('open-round')).toContainText('closing at Continue');
  await continueMonth(page);

  await page.getByTestId('finance-tab-board').click();
  const rows = page.getByTestId('director-row');
  await expect(rows).toHaveCount(4); // two common, two investor
  // The nominee is an employee: their name opens their profile.
  const nominee = rows.filter({ hasText: 'your nominee' });
  await expect(nominee.getByRole('link', { name: chosen })).toBeVisible();
  // Investor directors are not employees: their name opens a card, not a dead profile link.
  const investor = rows.filter({ hasText: 'Investor' }).first();
  await investor.getByTestId('director-name').click();
  const card = page.getByTestId('director-card');
  await expect(card).toBeVisible();
  await expect(card).toContainText('Investor seat');
  await expect(card).toContainText('On the board since');
  await expect(card).toContainText('Confidence');
  await nominee.getByRole('link', { name: chosen }).click();
  await expect(page.getByTestId('profile-name')).toHaveText(chosen);
});

test('(c) mark all read, archive read items and find them again', async ({ page }) => {
  await page.goto(`/game/${HIRING}/inbox`);
  const items = page.getByTestId('inbox-item');
  await expect(items.first()).toBeVisible();
  const count = await items.count();
  await page.getByTestId('inbox-read-all').click();
  await expect(page.getByTestId('inbox-unread')).toContainText('0 unread');
  await page.getByTestId('inbox-archive-read').click();
  await expect(items).toHaveCount(0);
  await expect(page.getByText('Archived messages are under Archived')).toBeVisible();

  await page.getByRole('button', { name: 'Archived', exact: true }).click();
  await expect(items).toHaveCount(count);
  await items.first().click();
  await page.getByTestId('inbox-unarchive').click();
  await expect(items).toHaveCount(count - 1);
  await page.getByRole('button', { name: 'All', exact: true }).click();
  await expect(items).toHaveCount(1);
  await items.first().click();
  await page.getByTestId('inbox-archive').click();
  await expect(items).toHaveCount(0);
});
