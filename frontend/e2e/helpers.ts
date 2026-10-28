import { expect, type APIRequestContext, type Page } from '@playwright/test';

export interface SetupOptions {
  company: string;
  seed?: number;
  scenario?: string;
  mission?: string[]; // [] starts with no mission (the founder's interests)
}

/** Create a game through the setup screen with the default founder; lands on the Inbox. */
export async function setupGame(page: Page, opts: SetupOptions): Promise<string> {
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(opts.company);
  if (opts.scenario) await page.getByTestId(`scenario-${opts.scenario}`).click();
  if (opts.seed !== undefined) {
    await page.getByRole('button', { name: 'Set a seed (optional)' }).click();
    await page.getByTestId('seed-input').fill(String(opts.seed));
  }
  for (const key of opts.mission ?? ['ai', 'enterprise']) {
    await page.getByTestId(`interest-${key}`).click();
  }
  const start = page.getByTestId('start-game');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/game\/[^/]+\/inbox$/);
  return new URL(page.url()).pathname.split('/')[2];
}

/** Press Continue and wait for the date to move on. */
export async function continueMonth(page: Page) {
  const date = page.getByTestId('game-date');
  const before = await date.textContent();
  await page.getByTestId('continue').click();
  await expect(date).not.toHaveText(before ?? '');
}

/** Founder energy left this month, from the top bar ("52 / 60"). */
export async function energyLeft(page: Page): Promise<number> {
  return Number(((await page.getByTestId('energy').textContent()) ?? '0').split('/')[0]);
}

/**
 * Send an offer to every candidate in the selected search that has none pending,
 * interviewing first (offers need an interview, ADR-0016) while energy lasts.
 */
export async function offerToAll(page: Page, salaryMultiple = 1, interviewEnergy = 8) {
  const panel = page.getByRole('complementary', { name: 'Make an offer' });
  for (;;) {
    const row = page
      .getByTestId('candidate-row')
      .filter({ has: page.getByTestId('offer') })
      .first();
    if ((await row.count()) === 0) break;
    const offer = row.getByTestId('offer');
    if (await offer.isDisabled()) {
      await expect(offer).toHaveText('Interview first');
      if ((await energyLeft(page)) < interviewEnergy) break;
      const before = await energyLeft(page);
      await row.getByTestId('interview').click();
      await expect(page.getByTestId('energy')).not.toHaveText(`${before} / 60`);
      await expect(offer).toBeEnabled();
    }
    await offer.click();
    await expect(panel).toBeVisible();
    if (salaryMultiple !== 1) {
      const ask = Number(
        ((await panel.getByText(/asks \$/).textContent()) ?? '')
          .replace(/.*asks \$/, '')
          .replace(/,/g, ''),
      );
      await panel.getByTestId('offer-salary').fill(String(Math.round(ask * salaryMultiple)));
    }
    const send = panel.getByTestId('send-offer');
    await expect(send).toBeEnabled();
    await send.click();
    await expect(panel).toBeHidden();
  }
}

/** API calls through the Vite proxy, for setting up state a test is not about. */
export async function api<T>(
  request: APIRequestContext,
  method: 'GET' | 'POST',
  path: string,
  data?: unknown,
): Promise<T> {
  const res = await request.fetch(`/api${path}`, { method, data });
  expect(res.ok(), `${method} ${path}: ${res.status()} ${await res.text()}`).toBe(true);
  return (await res.json()) as T;
}
