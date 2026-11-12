import { expect, test } from '@playwright/test';
import { setupGame } from './helpers.ts';

// M0 smoke test, on the M1c setup screen: Continue twice; the date reads "Mar 2010" and cash
// has dropped by two months of costs ($50,000 - 2 x ($500 base overhead + $600 office)).
test('create a game and continue two months', async ({ page }) => {
  const company = `Smoke ${Date.now()}`;
  // No mission chosen: allowed, and the API uses the founder's first two interests.
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(company);
  await expect(page.getByTestId('setup-summary')).toContainText(
    "mission: your founder's interests",
  );
  await page.getByTestId('interest-ai').click();
  await expect(page.getByTestId('start-game')).toBeDisabled(); // one of two is not allowed
  await page.getByTestId('interest-ai').click();
  await setupGame(page, { company, mission: [] });
  await page.keyboard.press('3');
  await expect(page.getByText('Company mission')).toBeVisible();
  await expect(page.getByTestId('person-row')).toHaveCount(1);
  await page.keyboard.press('1');

  await expect(page.getByTestId('game-date')).toHaveText('Jan 2010');
  await expect(page.getByTestId('company-name')).toHaveText(company);
  await expect(page.getByTestId('top-cash')).toHaveText('$50,000');
  await expect(page.getByTestId('energy')).toHaveText('60 / 60');

  const cont = page.getByTestId('continue');
  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
  await expect(page.getByTestId('top-cash')).toHaveText('$48,900');

  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
  // the side nav's link (an open event card may link Overview too, M23c)
  await page
    .getByRole('navigation', { name: 'Game screens' })
    .getByRole('link', { name: /Overview/ })
    .click();
  // $50,000 less two months of $1,100, give or take February's event, answered with its
  // first choice at Continue (M6): a minor event moves at most 1% of cash, $500.
  const dollars = async (id: string) =>
    Number(((await page.getByTestId(id).textContent()) ?? '').replace(/[^0-9-]/g, ''));
  await expect(page.getByTestId('kpi-cash')).toHaveText(/^\$[\d,]+$/);
  expect(Math.abs((await dollars('kpi-cash')) - 47_800)).toBeLessThanOrEqual(500);
  expect(Math.abs((await dollars('kpi-burn')) - 1_100)).toBeLessThanOrEqual(500);
  await expect(page.getByTestId('kpi-runway')).toHaveText(/^4[2-4] months$/);
});

test('Space advances one month; keys jump screens', async ({ page }) => {
  await setupGame(page, { company: `Keys ${Date.now()}` });
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2010');

  await page.locator('main').click({ position: { x: 5, y: 5 } });
  await page.keyboard.press('Space');
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');

  await page.keyboard.press('3');
  await expect(page).toHaveURL(/\/people$/);
  await page.keyboard.press('5');
  await expect(page).toHaveURL(/\/org$/); // live from M2b
  await page.keyboard.press('6');
  await expect(page).toHaveURL(/\/products$/); // live from M3b
  await page.keyboard.press('7');
  await expect(page).toHaveURL(/\/finance$/); // live from M4b
  await page.keyboard.press('8');
  await expect(page).toHaveURL(/\/competitors$/); // live from M5
  await page.keyboard.press('9');
  await expect(page).toHaveURL(/\/history$/); // live from M7b
  await page.keyboard.press('0');
  await expect(page).toHaveURL(/\/saves$/); // M7b

  // Reloading keeps the game: state lives in the save file, not the browser.
  await page.reload();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
});
