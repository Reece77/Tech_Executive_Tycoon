import { expect, test } from '@playwright/test';
import { setupGame } from './helpers.ts';

// M0 smoke test, on the M1c setup screen: Continue twice; the date reads "Mar 2010" and cash
// has dropped by two months of costs ($50,000 - 2 x ($500 base overhead + $600 office)).
test('create a game and continue two months', async ({ page }) => {
  const company = `Smoke ${Date.now()}`;
  await setupGame(page, { company });

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
  await expect(page.getByText('Arrives in M2.')).toBeVisible();

  // Reloading keeps the game: state lives in the save file, not the browser.
  await page.reload();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
});
