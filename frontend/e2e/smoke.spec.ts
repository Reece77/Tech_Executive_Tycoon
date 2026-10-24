import { expect, test } from '@playwright/test';

// M0 smoke test: create a game, press Continue twice, the date reads "Mar 2010" and cash has
// dropped by two months of costs ($50,000 - 2 x ($500 base overhead + $600 office)).
test('create a game and continue two months', async ({ page }) => {
  const company = `Smoke ${Date.now()}`;

  await page.goto('/');
  await page.getByTestId('company-name-input').fill(company);
  await page.getByRole('button', { name: 'Start game' }).click();

  await expect(page.getByTestId('game-date')).toHaveText('Jan 2010');
  await expect(page.getByTestId('company-name')).toHaveText(company);
  await expect(page.getByTestId('top-cash')).toHaveText('$50,000.00');
  await expect(page.getByTestId('kpi-runway')).toHaveText('Not burning');

  const cont = page.getByTestId('continue');
  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
  await expect(page.getByTestId('top-cash')).toHaveText('$48,900.00');

  await cont.click();
  await expect(page.getByTestId('game-date')).toHaveText('Mar 2010');
  await expect(page.getByTestId('top-cash')).toHaveText('$47,800.00');
  await expect(page.getByTestId('kpi-cash')).toHaveText('$47,800.00');
  await expect(page.getByTestId('kpi-burn')).toHaveText('$1,100.00');
  await expect(page.getByTestId('kpi-runway')).toHaveText('43 months');
});

test('Space advances one month; placeholders say when they arrive', async ({ page }) => {
  const company = `Keys ${Date.now()}`;
  await page.goto('/');
  await page.getByTestId('company-name-input').fill(company);
  await page.getByRole('button', { name: 'Start game' }).click();
  await expect(page.getByTestId('game-date')).toHaveText('Jan 2010');

  await page.locator('body').click({ position: { x: 600, y: 400 } });
  await page.keyboard.press('Space');
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');

  await page.keyboard.press('3'); // People
  await expect(page.getByText('Arrives in M1b.')).toBeVisible();

  // Reloading keeps the game: state lives in the save file, not the browser.
  await page.reload();
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
});
