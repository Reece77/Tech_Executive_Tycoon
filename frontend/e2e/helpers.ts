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

/** Answer every open major and critical event with its first choice through the API, as a
 * player must before Continue (23.1, M10b), and decline executives' proposals (M10c). Flows
 * that are not about events use this. */
export async function answerBlocking(page: Page, opts: { proposals?: boolean } = {}) {
  const save = new URL(page.url()).pathname.split('/')[2];
  const events = await (await page.request.get(`/api/saves/${save}/events`)).json();
  // A critical event first: the save is read only until it is answered (M23r), so another
  // event answered before it is refused (M27a's flow (a) found this).
  const critical = events.blocking_event_id as number | null;
  const ids = (events.blocking_event_ids as number[]).filter((id) => id !== critical);
  for (const id of critical ? [critical, ...ids] : ids) {
    await page.request.post(`/api/saves/${save}/events/${id}/choose`, { data: { choice: 'A' } });
  }
  // An executive's proposal blocks too (24.1, M10c): flows not about it decline it.
  const proposals =
    opts.proposals === false ? [] : ((events.blocking_proposal_ids ?? []) as number[]);
  for (const id of proposals) {
    await page.request.post(`/api/saves/${save}/scaleup/proposals/${id}/decline`);
  }
  // And a pitch (27.1, M13b).
  const pitches = opts.proposals === false ? [] : ((events.blocking_pitch_ids ?? []) as number[]);
  for (const id of pitches) {
    await page.request.post(`/api/saves/${save}/scaleup/pitches/${id}/decline`);
  }
  if ((events.blocking_event_ids as number[]).length || proposals.length || pitches.length) {
    await page.reload();
    if (opts.proposals !== false) await expect(page.getByTestId('continue-blocked')).toHaveCount(0);
  }
}

/** Press Continue and wait for that month to be played; open major and critical events are
 * answered first with their first choice (23.1, M10b).
 *
 * Waits on state, not on the date changing: after answerBlocking reloads the page the date
 * reads "…" until the overview loads, so "the date is no longer what it was" passed on the
 * page load alone and a Continue was counted that never ran (M15r; the M9 Europe launch
 * stayed "Localizing" and the next unanswered event hung the loop). */
export async function continueMonth(page: Page) {
  await answerBlocking(page);
  await pressContinue(page);
}

/** Press Continue as it stands (nothing answered first) and wait until that month is played:
 * its advance response, then the top bar showing the month it names. */
export async function pressContinue(page: Page) {
  const button = page.getByTestId('continue');
  await expect(button).toBeEnabled();
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        /^\/api\/saves\/[^/]+\/advance$/.test(new URL(r.url()).pathname),
    ),
    button.click(),
  ]);
  expect(response.ok(), `Continue was refused: ${response.status()}`).toBe(true);
  const played = (await response.json()) as { date_label: string };
  await expect(page.getByTestId('game-date')).toHaveText(played.date_label);
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

/**
 * Answer any open critical event with its first choice, through the API, as a player must
 * before Continue (M7a: early-days events move cash, so a short runway can turn critical in
 * flows that are not about events).
 */
export async function answerCritical(request: APIRequestContext, base: string) {
  // Since M10b (23.1) open major events block Continue too: answer every blocking event.
  type Events = { blocking_event_ids: number[] };
  const events = await api<Events>(request, 'GET', `${base}/events`);
  for (const id of events.blocking_event_ids) {
    await api(request, 'POST', `${base}/events/${id}/choose`, { choice: 'A' });
  }
}
