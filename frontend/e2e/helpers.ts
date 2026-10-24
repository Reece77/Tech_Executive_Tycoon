import { expect, type APIRequestContext, type Page } from '@playwright/test';

export interface SetupOptions {
  company: string;
  seed?: number;
  scenario?: string;
  mission?: [string, string];
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

/** Send an offer to every candidate in the selected search that has none pending. */
export async function offerToAll(page: Page, salaryMultiple = 1) {
  const panel = page.getByRole('complementary', { name: 'Make an offer' });
  for (;;) {
    const offer = page.getByTestId('candidate-row').getByTestId('offer').first();
    if ((await offer.count()) === 0) break;
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
