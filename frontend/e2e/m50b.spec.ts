import { expect, test } from '@playwright/test';
import { continueMonth } from './helpers.ts';

// M50b (formulas.md 60.4-60.7): a campaign begun in January 2000 from the new-game screen
// ("Dot-com 2000"), advanced into 2001. The venture climate is the bubble's (x 1.80, the
// bounds' top) in January 2000, and the campaign's standard end is December 2029.
test('start a Dot-com 2000 game and advance into 2001', async ({ page }) => {
  test.setTimeout(300_000); // thirteen months played through the UI
  const company = `Bubble ${Date.now()}`;
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(company);
  await page.getByTestId('start-year').selectOption('2000');
  for (const key of ['ai', 'enterprise']) await page.getByTestId(`interest-${key}`).click();
  const start = page.getByTestId('start-game');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/);
  const save = new URL(page.url()).pathname.split('/')[2];
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2000');

  await page.goto(`/game/${save}/finance/debt`);
  await expect(page.getByTestId('macro-climate-value')).toHaveText('x 1.80');
  for (let month = 0; month < 13; month++) await continueMonth(page);
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2001');

  const campaign = await (await page.request.get(`/api/saves/${save}/campaign`)).json();
  expect(campaign.end_label).toBe('Dec 2029'); // 360 months from January 2000
});
