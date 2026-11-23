import { expect, test } from '@playwright/test';
import { continueMonth } from './helpers.ts';

// M50 (formulas.md 60, ADR-0024): a campaign begun in January 2008 from the new-game screen,
// played through Q4 2008, shows the venture climate freezing after Lehman's failure (60.2):
// x 1.05 in the spring of 2008, x 0.52 by December (macro_history.yaml's monthly climate).
test('start in 2008, play through Q4 2008, see the venture climate freeze', async ({ page }) => {
  test.setTimeout(240_000); // twelve months played through the UI
  const company = `Crisis ${Date.now()}`;
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(company);
  await page.getByTestId('start-year').selectOption('2008');
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  const start = page.getByTestId('start-game');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/);
  const save = new URL(page.url()).pathname.split('/')[2];
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2008');

  await page.goto(`/game/${save}/finance/debt`);
  await expect(page.getByTestId('macro-climate-value')).toHaveText('x 1.05');
  for (let month = 0; month < 12; month++) await continueMonth(page);
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2009');
  // December 2008's climate is the last month played: rounds are scarce and cheap
  await page.goto(`/game/${save}/finance/debt`);
  const value = await page.getByTestId('macro-climate-value').textContent();
  expect(Number((value ?? '').replace('x ', ''))).toBeLessThanOrEqual(0.6);

  const campaign = await (await page.request.get(`/api/saves/${save}/campaign`)).json();
  expect(campaign.end_label).toBe('Dec 2037'); // 360 months from January 2008
});
