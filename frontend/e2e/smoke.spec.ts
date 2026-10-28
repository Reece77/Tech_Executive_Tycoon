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
  await expect(page.getByTestId('energy')).toHaveText('100 / 100');

  const cont = page.getByTestId('continue');
  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
  await expect(page.getByTestId('top-cash')).toHaveText('$48,900');

  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
  await page.getByRole('link', { name: /Overview/ }).click();
  await expect(page.getByTestId('kpi-cash')).toHaveText('$47,800');
  await expect(page.getByTestId('kpi-burn')).toHaveText('$1,100');
  await expect(page.getByTestId('kpi-runway')).toHaveText('43 months');
});

test('Space advances one month; keys jump screens; later screens say when they arrive', async ({
  page,
}) => {
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
  await expect(page.getByText('Arrives in M5.')).toBeVisible();

  // Reloading keeps the game: state lives in the save file, not the browser.
  await page.reload();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
});
