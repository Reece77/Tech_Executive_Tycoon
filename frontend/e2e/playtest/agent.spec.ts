import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { continueMonth, setupGame } from '../helpers.ts';

// M7c sub-task 3: the agent plays a new game for 120 months through the browser, as a
// reasonable player would (docs/tasks/M7c-fixes-and-agent-playtest.md). Out of `make e2e`;
// run with `make playtest`. Actions go through the screens; the script reads the API only to
// decide (what a player would read off the screens) and to record each year's numbers.
// Every step is guarded: a failing step is written to the journal and the game goes on, so
// one bug cannot hide the rest. The journal and yearly numbers feed docs/playtests/agent-m7c.md.

const MONTHS = Number(process.env.PLAYTEST_MONTHS ?? 120);
const SEED = 7;
const SHOTS = resolve(process.cwd(), '../docs/playtests/agent-m7c');
const OUT = resolve(process.cwd(), 'test-results/playtest');
const SCREENSHOT_SCREENS = ['overview', 'people', 'products', 'finance/statements'] as const;
const EVERY_SCREEN = [
  'inbox',
  'overview',
  'people',
  'recruitment',
  'org',
  'products',
  'products/markets',
  'finance/statements',
  'finance/divisions',
  'finance/captable',
  'finance/fundraising',
  'finance/board',
  'competitors',
  'history/timeline',
  'history/charts',
  'history/storylines',
  'history/fame',
  'saves',
  'settings',
];
const HIRE_ORDER = [
  'Software engineer',
  'Software engineer',
  'Account executive',
  'Marketer',
  'Software engineer',
  'Product manager',
  'Designer',
  'Sales representative',
  'Software engineer',
  'DevOps engineer',
  'Finance manager',
  'Recruiter',
];
const ROUND_TARGETS: Record<string, string> = { seed: '2000000', a: '8000000', b: '25000000' };

type Journal = {
  month: number;
  date: string;
  step: string;
  note: string;
  ok: boolean;
}[];
type YearRow = Record<string, unknown>;

const journal: Journal = [];
const years: YearRow[] = [];
const serverErrors: string[] = [];
const consoleErrors: string[] = [];

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`);
  if (!res.ok()) throw new Error(`GET ${path}: ${res.status()}`);
  return (await res.json()) as T;
}

test('agent playtest: 120 months through the browser', async ({ page, request }) => {
  test.setTimeout(4 * 60 * 60 * 1000);
  await page.setViewportSize({ width: 1440, height: 900 });
  mkdirSync(SHOTS, { recursive: true });
  mkdirSync(OUT, { recursive: true });
  page.on('response', (r) => {
    if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300));
  });

  // The COO answers with the mock adapter (CLAUDE.md section 8); events use it too.
  const saveDir = process.env.TST_E2E_SAVE_DIR ?? '';
  writeFileSync(join(saveDir, 'llm_settings.json'), JSON.stringify({ adapter: 'mock' }));

  const save = await setupGame(page, {
    company: 'Agent Co',
    seed: SEED,
    scenario: 'ex_big_tech_founders',
  });
  let month = 0;
  const date = async () =>
    (await page
      .getByTestId('game-date')
      .textContent({ timeout: 2000 })
      .catch(() => null)) ?? '?';

  async function step(name: string, fn: () => Promise<unknown>) {
    try {
      const result = await fn();
      const note = typeof result === 'string' ? result : '';
      if (note) journal.push({ month, date: await date(), step: name, note, ok: true });
    } catch (err) {
      const note = String(err instanceof Error ? err.message : err)
        .split('\n')[0]
        .slice(0, 400);
      journal.push({ month, date: await date().catch(() => '?'), step: name, note, ok: false });
      await page.screenshot({ path: join(OUT, `fail-${month}-${name}.png`) }).catch(() => {});
    }
  }

  const go = async (path: string) => {
    await page.goto(`/game/${save}/${path}`);
    await expect(page.getByTestId('game-date')).not.toHaveText('…');
  };

  // --- Month 0: a product and the first search ---
  await step('first product', async () => {
    await go('products');
    await page.getByTestId('new-product').click();
    await page.getByTestId('new-product-name').fill('Pipeline');
    await page.getByTestId('product-category').selectOption('b2b_saas');
    await page.getByTestId('segment-smb').check();
    await page.getByTestId('segment-mid_market').check();
    await page.getByTestId('create-product').click();
    await expect(page.getByTestId('product-name')).toHaveText('Pipeline');
    await page.getByTestId('assign-unit').click();
    await page.getByTestId('assign-confirm').click();
    for (const [seg, price] of [
      ['smb', '40'],
      ['mid_market', '700'],
    ]) {
      await page.getByTestId(`price-input-${seg}`).fill(price);
      await page.getByTestId('set-price').click();
      await expect(page.getByTestId('price-preview')).toBeHidden();
    }
    return 'created Pipeline (B2B SaaS, SMB $40, mid-market $700), built by the company';
  });

  let savesDone = false;
  try {
    for (month = 0; month < MONTHS; month++) {
      const year = Math.floor(month / 12);
      await step('events', () => answerEvents(page, request, save));
      await step('funding', () => fundraise(page, request, save, go));
      await step('hiring', () => hire(page, request, save, go, targetHeadcount(month)));
      await step('launch', () => launchReady(page, request, save, go));
      if (month === 5) await step('recruiter plan', () => recruiterPlan(page, go));
      if (month >= 30 && !savesDone) {
        savesDone = true;
        await step('saves manager', () => savesManager(page, save));
      }
      const second = await api<{ product_id: number }[]>(request, `/saves/${save}/products`);
      if (second.length < 2 && month >= 24) {
        await step('second product', () => secondProduct(page, request, save, go));
      }
      await step('marketing', () => marketing(page, request, save, go));
      if (month % 12 === 11) {
        await step('every screen', () => everyScreen(page, go));
        await step('screenshots', () => screenshots(page, go, year));
        await step('coo', () => askCoo(page));
        years.push(await yearRow(request, save, year));
        writeFileSync(
          join(OUT, 'journal.json'),
          JSON.stringify({ save, journal, years, serverErrors, consoleErrors }, null, 2),
        );
      }
      // A quiet stretch: Holiday for up to 4 months in the middle of years 3-9.
      if (year >= 2 && month % 12 === 4) {
        const before = month;
        await step('holiday', () => holiday(page, save));
        const now = await api<{ turn: number }>(request, `/saves/${save}/overview`);
        month = Math.max(before, now.turn - 1);
        continue;
      }
      await step('continue', async () => {
        if (!page.url().includes(`/game/${save}`)) await page.goto(`/game/${save}/inbox`);
        await handleCritical(page, request, save);
        await continueMonth(page);
      });
      const state = await api<{ game_state: string }>(request, `/saves/${save}/overview`);
      if (state.game_state !== 'active') {
        journal.push({
          month,
          date: await date(),
          step: 'game over',
          note: state.game_state,
          ok: true,
        });
        break;
      }
    }
  } finally {
    writeFileSync(
      join(OUT, 'journal.json'),
      JSON.stringify({ save, journal, years, serverErrors, consoleErrors }, null, 2),
    );
  }
  expect(serverErrors, serverErrors.join('\n')).toEqual([]);
});

// --- Decisions -------------------------------------------------------------------------------

function targetHeadcount(month: number): number {
  return Math.min(40, 4 + Math.floor(month / 6) * 2); // grows while runway allows
}

type Overview = {
  turn: number;
  cash_cents: number;
  runway_months: number | null;
  headcount: number;
  avg_morale: number | null;
  arr_cents: number;
  stage: number;
  energy: { energy: number };
};

async function answerEvents(page: Page, request: APIRequestContext, save: string) {
  await handleCritical(page, request, save); // the critical one first: it blocks the rest
  type Ev = { event_id: number; status: string; title: string };
  const events = await api<{ open: (Ev & { severity: string })[] }>(
    request,
    `/saves/${save}/events`,
  );
  const notes: string[] = [];
  for (const e of events.open.filter((x) => x.severity !== 'critical')) {
    await page.goto(`/game/${save}/events/${e.event_id}`); // M7c deep link
    const card = page.getByTestId('event-card');
    await expect(card).toBeVisible();
    const choices = card.locator('[data-choice]');
    const n = await choices.count();
    if (n === 0) continue;
    // Read the choices: rotate between them by event, but skip a choice that costs cash
    // while the runway is short (a reasonable player's caution, not always the first).
    let pick = e.event_id % n;
    const o = await api<Overview>(request, `/saves/${save}/overview`);
    const tight = o.runway_months !== null && o.runway_months < 12;
    for (let k = 0; k < n && tight; k++) {
      const i = (e.event_id + k) % n;
      if (!/costs/.test((await choices.nth(i).textContent()) ?? '')) {
        pick = i;
        break;
      }
    }
    await choices.nth(pick).click();
    await expect(card.getByTestId('event-answered')).toBeVisible();
    notes.push(`${e.title}: ${await choices.nth(pick).getAttribute('data-choice')}`);
  }
  return notes.join('; ');
}

async function handleCritical(
  page: Page,
  request: APIRequestContext,
  save: string,
): Promise<string> {
  const events = await api<{ blocking_event_id: number | null }>(request, `/saves/${save}/events`);
  if (events.blocking_event_id == null) return '';
  await page.goto(`/game/${save}/inbox`);
  const modal = page.getByTestId('critical-modal');
  await expect(modal.getByTestId('event-card')).toBeVisible();
  // Read it: take the last choice when cash is the problem (often the cautious one), else A.
  const text = (await modal.textContent()) ?? '';
  const choices = modal.locator('[data-choice]');
  const pick = /cash|payroll|runway/i.test(text) ? (await choices.count()) - 1 : 0;
  await choices.nth(pick).click();
  await expect(modal.getByTestId('event-card')).toBeHidden();
  return `critical: ${await choices
    .nth(pick)
    .getAttribute('data-choice')
    .catch(() => '?')}`;
}

async function fundraise(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
) {
  type Rounds = {
    rounds: {
      status: string;
      series: string;
      term_sheets: { sheet_id: number; status: string; pre_money_cents: number }[];
    }[];
    next: { series: string | null; allowed: boolean };
  };
  const rounds = await api<Rounds>(request, `/saves/${save}/finance/rounds`);
  const open = rounds.rounds.find((r) => r.status === 'open');
  type Summary = { open_bridge_id: number | null };
  const summary = await api<Summary>(request, `/saves/${save}/finance/summary`);
  if (summary.open_bridge_id != null) {
    await go('finance/fundraising');
    await page.getByTestId('accept-bridge').click();
    return 'accepted a bridge from existing investors';
  }
  const o = await api<Overview>(request, `/saves/${save}/overview`);
  if (!open && !rounds.next.allowed) {
    if (o.runway_months === null || o.runway_months >= 9) return '';
    return raiseSafe(page, request, save, go);
  }
  await go('finance/fundraising');
  if (open) {
    // Compare the offers and take the best valuation (read off the term-sheet table).
    const offered = open.term_sheets.filter((t) => t.status === 'offered');
    if (offered.length === 0) return '';
    const best = offered.reduce((a, b) => (b.pre_money_cents > a.pre_money_cents ? b : a));
    const row = page
      .getByTestId('sheet-row')
      .nth(open.term_sheets.findIndex((t) => t.sheet_id === best.sheet_id));
    await row.getByTestId('preview-sheet').click();
    // A Series A's board nominee defaults to the most senior employee.
    await page.getByTestId('accept-sheet').click();
    await expect(page.getByTestId('open-round')).toContainText('closing at Continue');
    return `accepted the best of ${offered.length} ${open.series} term sheets`;
  }
  const start = page.getByTestId('start-round');
  if (!(await start.isVisible()) || !(await start.isEnabled())) return '';
  const series = rounds.next.series ?? 'seed';
  await page.getByTestId('round-target').fill(ROUND_TARGETS[series] ?? '25000000');
  await start.click();
  await expect(page.getByTestId('open-round')).toBeVisible();
  return `started a ${series} round`;
}

/** A SAFE when runway is short and no round is allowed: the largest cap the hint calls
 * likely (the player reads the hint, never the chance). */
async function raiseSafe(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
) {
  const safes = await api<{ open: boolean }>(request, `/saves/${save}/finance/safes`);
  if (safes.open) return '';
  await go('finance/fundraising');
  const raise = page.getByTestId('raise-safe');
  if (!(await raise.isVisible())) return '';
  await page.getByTestId('safe-amount').fill('1500000');
  for (const cap of ['20000000', '15000000', '10000000', '7000000', '5000000']) {
    await page.getByTestId('safe-cap').fill(cap);
    await page.waitForTimeout(600); // the hint is debounced
    const hint = await page.getByTestId('safe-hint').getAttribute('data-hint');
    if (hint === 'likely' && (await raise.isEnabled())) {
      await raise.click();
      return `raised a $1.5M SAFE at a $${Number(cap) / 1e6}M cap (read: likely)`;
    }
  }
  return 'no SAFE cap read as likely';
}

async function hire(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
  wanted: number,
) {
  const o = await api<Overview>(request, `/saves/${save}/overview`);
  if (o.headcount - 1 >= wanted) return '';
  if (o.runway_months !== null && o.runway_months < 10)
    return 'hiring paused: runway under 10 months';
  await go('recruitment');
  const searches = page.getByTestId('search-row');
  if ((await searches.count()) === 0) {
    const role = HIRE_ORDER[(o.headcount - 1) % HIRE_ORDER.length];
    await page.getByTestId('search-role').click();
    await page.getByRole('option', { name: role, exact: true }).click();
    await page.getByTestId('channel-job_post').click();
    await page.getByTestId('open-search').click();
    await expect(searches.first()).toBeVisible();
    return `opened a job post for ${role}`;
  }
  const ids = await searches.evaluateAll((rows) =>
    rows.map((r) => r.getAttribute('data-search-id') ?? ''),
  );
  type C = { candidacy: { pending_offer: unknown } | null };
  const pending = (await api<C[]>(request, `/saves/${save}/recruitment/candidates`)).filter(
    (c) => c.candidacy?.pending_offer,
  ).length;
  let room = wanted - (o.headcount - 1) - pending;
  for (const id of ids) {
    if (room <= 0) break;
    const row = page.locator(`[data-testid="search-row"][data-search-id="${id}"]`);
    if ((await row.count()) === 0) continue;
    await row.getByTestId('select-search').click();
    room -= await offerSome(page, room);
  }
  // Close the job post once the target is reached (it costs every month).
  return '';
}

/** Interview and offer 1.05x the ask to up to `limit` candidates of the selected search. */
async function offerSome(page: Page, limit: number): Promise<number> {
  const panel = page.getByRole('complementary', { name: 'Make an offer' });
  let made = 0;
  while (made < limit) {
    const row = page
      .getByTestId('candidate-row')
      .filter({ has: page.getByTestId('offer') })
      .first();
    if ((await row.count()) === 0) break;
    const offer = row.getByTestId('offer');
    if (await offer.isDisabled()) {
      const energy = Number(
        ((await page.getByTestId('energy').textContent()) ?? '0').split('/')[0],
      );
      if (energy < 8) break;
      await row.getByTestId('interview').click();
      await expect(offer).toBeEnabled();
    }
    await offer.click();
    await expect(panel).toBeVisible();
    const ask = Number(
      ((await panel.getByText(/asks \$/).textContent()) ?? '')
        .replace(/.*asks \$/, '')
        .replace(/,/g, ''),
    );
    if (ask > 0) await panel.getByTestId('offer-salary').fill(String(Math.round(ask * 1.05)));
    await panel.getByTestId('send-offer').click();
    await expect(panel).toBeHidden();
    made += 1;
  }
  return made;
}

async function launchReady(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
) {
  type P = { product_id: number; name: string; status: string; launch: { ready: boolean } };
  const products = await api<P[]>(request, `/saves/${save}/products`);
  const notes = [];
  for (const p of products) {
    if (p.status !== 'in_development' || !p.launch.ready) continue;
    await go(`products/${p.product_id}`);
    await page.getByTestId('launch').click();
    await expect(page.getByTestId('product-status')).toHaveText(/^Live/);
    notes.push(`launched ${p.name}`);
  }
  return notes.join('; ');
}

async function marketing(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
) {
  // $10,000 a month per product, or 15% of its revenue once that is more.
  type P = {
    product_id: number;
    status: string;
    marketing_budget_cents: number;
    mrr_cents: number;
  };
  const products = await api<P[]>(request, `/saves/${save}/products`);
  const notes = [];
  for (const p of products) {
    if (p.status === 'retired') continue;
    const want = Math.max(1_000_000, Math.round((p.mrr_cents * 0.15) / 100_000) * 100_000);
    if (Math.abs(want - p.marketing_budget_cents) < Math.max(200_000, want * 0.25)) continue;
    await go(`products/${p.product_id}`);
    await page.getByTestId('marketing-budget').fill(String(want / 100));
    await page.getByTestId('save-marketing').click();
    notes.push(`marketing ${p.product_id} to $${want / 100}`);
  }
  return notes.join('; ');
}

async function recruiterPlan(page: Page, go: (p: string) => Promise<void>) {
  await go('recruitment');
  await page.getByTestId('new-plan').click();
  const dialog = page.getByTestId('plan-dialog');
  await dialog.getByTestId('plan-role').selectOption({ label: 'Software engineer' });
  await dialog.getByTestId('plan-target').fill('3');
  await dialog.getByTestId('plan-channel-recruiter').check();
  await dialog.getByTestId('plan-ratio').fill('1.1');
  await dialog.getByTestId('save-plan').click();
  await expect(dialog).toBeHidden();
  return 'recruiter plan: 3 software engineers at 1.1x';
}

async function secondProduct(
  page: Page,
  request: APIRequestContext,
  save: string,
  go: (p: string) => Promise<void>,
) {
  const o = await api<Overview>(request, `/saves/${save}/overview`);
  if (o.arr_cents < 100_000_000 || o.headcount < 12) return '';
  await go('org');
  await page.getByTestId('new-team').click();
  await page.getByTestId('unit-name-input').fill('Forge team');
  await page.getByTestId('preview-confirm').click();
  // Move three software engineers from the company onto the new team.
  let moved = 0;
  for (let i = 0; i < 3; i++) {
    await go('org');
    const engineer = page
      .getByTestId('unit-panel')
      .locator('tr')
      .filter({ hasText: 'Software engineer' })
      .filter({ has: page.locator('[data-testid="move-to"]:enabled') })
      .first();
    if ((await engineer.count()) === 0) break;
    await engineer.getByTestId('move-to').click();
    await page.getByRole('menuitem', { name: 'Forge team' }).click();
    await page.getByTestId('preview-confirm').click();
    await expect(page.getByTestId('preview-confirm')).toBeHidden();
    moved++;
  }
  await go('products');
  await page.getByTestId('new-product').click();
  await page.getByTestId('new-product-name').fill('Forge');
  await page.getByTestId('product-category').selectOption('dev_tools');
  await page.getByTestId('segment-smb').check();
  await page.getByTestId('create-product').click();
  await expect(page.getByTestId('product-name')).toHaveText('Forge');
  await page.getByTestId('price-input-smb').fill('30');
  await page.getByTestId('set-price').click();
  await expect(page.getByTestId('price-preview')).toBeHidden();
  await page.getByTestId('assign-unit').click();
  const choose = page.getByTestId('assign-unit-select');
  if (await choose.isVisible()) {
    const option = choose.locator('option').filter({ hasText: 'Forge team' }).first();
    await choose.selectOption((await option.getAttribute('value')) ?? '');
  }
  await page.getByTestId('assign-confirm').click();
  await expect(page.getByTestId('assign-confirm')).toBeHidden();
  return `second product Forge (dev tools, SMB $30), built by the Forge team (${moved} engineers moved)`;
}

async function holiday(page: Page, save: string) {
  await page.goto(`/game/${save}/inbox`);
  await page.locator('body').click({ position: { x: 5, y: 5 } });
  await page.keyboard.press('h');
  const dialog = page.getByRole('dialog', { name: 'Go on holiday' });
  await expect(dialog).toBeVisible();
  await dialog.getByTestId('holiday-months').fill('4');
  await dialog.getByTestId('holiday-start').click();
  const done = page.getByTestId('holiday-done');
  await expect(done).toBeVisible({ timeout: 300_000 });
  return ((await done.textContent()) ?? '').replace(/\s+/g, ' ').slice(0, 200);
}

async function savesManager(page: Page, save: string) {
  await page.goto('/');
  const row = page.getByTestId('save-row').filter({ has: page.getByTestId(`backups-${save}`) });
  await row.getByTestId(`duplicate-${save}`).click();
  await page.getByTestId('duplicate-submit-name').fill('Agent side run');
  await page.getByTestId('duplicate-submit').click();
  await expect(page.getByTestId('save-row').filter({ hasText: 'Agent side run' })).toHaveCount(1);
  await row.getByTestId(`backups-${save}`).click();
  const backups = page.getByRole('dialog');
  await backups.getByTestId('backup-row').first().getByTestId('restore-backup').click();
  await expect(page.getByTestId('restored-notice')).toBeVisible();
  await page.goto(`/game/${save}/inbox`);
  return 'duplicated the save and restored its first backup as a new save';
}

async function everyScreen(page: Page, go: (p: string) => Promise<void>) {
  const slow: string[] = [];
  for (const path of EVERY_SCREEN) {
    const started = Date.now();
    await go(path);
    await expect(page.getByText('Something went wrong')).toHaveCount(0);
    if (Date.now() - started > 4000) slow.push(`${path} ${Date.now() - started} ms`);
  }
  return slow.length ? `slow screens: ${slow.join(', ')}` : '';
}

async function screenshots(page: Page, go: (p: string) => Promise<void>, year: number) {
  for (const screen of SCREENSHOT_SCREENS) {
    await go(screen);
    await page.waitForLoadState('networkidle');
    const name = `y${String(year + 1).padStart(2, '0')}-${screen.split('/')[0]}.png`;
    await page.screenshot({ path: join(SHOTS, name) });
  }
}

async function askCoo(page: Page) {
  await page.getByTestId('coo-button').click();
  const panel = page.getByTestId('coo-panel');
  await expect(panel).toBeVisible();
  await page.getByTestId('coo-question').fill('What should I worry about this year?');
  await page.getByTestId('coo-ask').click();
  await expect(panel.getByTestId('coo-answer').first()).toBeVisible();
  await page.keyboard.press('Escape');
  return '';
}

async function yearRow(request: APIRequestContext, save: string, year: number): Promise<YearRow> {
  const o = await api<Overview>(request, `/saves/${save}/overview`);
  type R = { rounds: { series: string; status: string }[] };
  const rounds = await api<R>(request, `/saves/${save}/finance/rounds`).catch(() => ({
    rounds: [],
  }));
  type P = { name: string; status: string; mrr_cents: number };
  const products = await api<P[]>(request, `/saves/${save}/products`);
  type T = { total: number };
  const events = await api<T>(
    request,
    `/saves/${save}/history/timeline?category=events&year=${2010 + year}&limit=1`,
  ).catch(() => ({ total: -1 }));
  return {
    year: 2010 + year,
    cash_cents: o.cash_cents,
    arr_cents: o.arr_cents,
    staff: o.headcount,
    avg_morale: o.avg_morale,
    stage: o.stage,
    rounds: rounds.rounds.filter((r) => r.status === 'closed').map((r) => r.series),
    products: products.map((p) => `${p.name} (${p.status})`),
    events: events.total,
  };
}
