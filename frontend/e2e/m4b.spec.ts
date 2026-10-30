import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { api, continueMonth } from './helpers.ts';

// M4b flows: (a) raise a SAFE and see the answer at Continue; (b) start a seed, compare two
// term sheets' dilution previews, accept one, Continue, and see the cap table match the
// preview; (c) run out of cash in a scripted save, see the insolvency badge and the bridge,
// ignore it, and reach the game over screen. (a) and (b) share one save, in order.
test.describe.configure({ mode: 'serial' });

const SEED = 16; // several seed firms answer this garage (backend test_api_finance)
const SAVE = `m4b-${Date.now()}`;
const BROKE = `m4b-broke-${Date.now()}`;

async function createSave(request: APIRequestContext, name: string, scenario: string) {
  await api(request, 'POST', '/saves', {
    name,
    company_name: name.startsWith('m4b-broke') ? 'Broke Co' : 'Raise Co',
    scenario,
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
}

async function openFundraising(page: Page, save: string) {
  await page.goto(`/game/${save}/finance/fundraising`);
  await expect(page.getByRole('tab', { name: 'Fundraising' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
}

test('(a) raise a SAFE and see the answer at Continue', async ({ page, request }) => {
  await createSave(request, SAVE, 'garage_bootstrap');
  await openFundraising(page, SAVE);
  await page.getByTestId('safe-amount').fill('300000');
  await page.getByTestId('safe-cap').fill('1000000');
  // The hint band, never the probability (formulas.md 14.9).
  await expect(page.getByTestId('safe-hint')).toHaveAttribute('data-hint', 'likely');
  await expect(page.getByTestId('safe-hint')).toContainText('Likely');
  await expect(page.getByTestId('safe-hint')).not.toContainText('%');
  const raise = page.getByTestId('raise-safe');
  await expect(raise).toHaveText('Raise · 10 energy');
  await expect(raise).toBeEnabled();
  await raise.click();
  await expect(page.getByTestId('energy')).toHaveText('50 / 60');
  await expect(page.getByTestId('past-item').first()).toContainText('Waiting for answers');
  await expect(page.getByTestId('safe-blocked')).toContainText('answer your open SAFE');

  await continueMonth(page);
  const answer = page.getByTestId('past-item').first();
  await expect(answer).not.toContainText('Waiting for answers');
  await expect(answer).toContainText(/Outstanding|Declined/);

  // The answer is a Finance message in the inbox.
  await page.goto(`/game/${SAVE}/inbox`);
  await page.getByRole('button', { name: 'Finance', exact: true }).click();
  await expect(page.getByText(/SAFE filled|Nobody took your SAFE/).first()).toBeVisible();
});

/** The founder's "after" percentage in the open dilution preview, e.g. "36.67%". */
async function previewAfter(page: Page, row: number): Promise<{ own: string; fd: string }> {
  await page.getByTestId('sheet-row').nth(row).getByTestId('preview-sheet').click();
  const preview = page.getByTestId('dilution-preview');
  await expect(preview).toBeVisible();
  const own = (await preview.getByTestId('preview-founder-after').textContent()) ?? '';
  const sheetOwn =
    (await page.getByTestId('sheet-row').nth(row).getByTestId('sheet-own-after').textContent()) ??
    '';
  expect(own).toBe(sheetOwn); // the table and the preview agree
  const fdText = (await preview.getByText(/^[\d,]+ → [\d,]+$/).textContent()) ?? ''; // "10,000,000 → 24,545,454"
  return { own, fd: fdText.split('→')[1].trim() };
}

test('(b) start a seed, compare two term sheets, accept one and see the cap table match', async ({
  page,
}) => {
  await openFundraising(page, SAVE);
  await page.getByTestId('round-target').fill('1500000');
  const start = page.getByTestId('start-round');
  await expect(start).toHaveText('Start Seed · 15 energy');
  await start.click();
  await expect(page.getByTestId('open-round')).toContainText('Seed · open');
  await expect(page.getByTestId('raise-safe')).toBeDisabled(); // not while a round is open
  await expect(page.getByTestId('safe-blocked')).toHaveText('Not while a priced round is open.');

  await continueMonth(page);
  const rows = page.getByTestId('sheet-row');
  await expect(rows.nth(1)).toBeVisible(); // at least two term sheets to compare
  const first = await previewAfter(page, 0);
  const second = await previewAfter(page, 1);
  expect(first.own).not.toBe(second.own); // different valuations, different dilution

  await page.getByTestId('accept-sheet').click(); // the second sheet is the one shown
  await expect(page.getByTestId('open-round')).toContainText('closing at Continue');
  await continueMonth(page);

  await page.getByTestId('finance-tab-captable').click();
  await expect(page.getByTestId('cap-founder-pct')).toHaveText(second.own);
  await expect(page.getByTestId('cap-total-shares')).toHaveText(second.fd);
  await expect(page.getByTestId('kpi-founder')).toHaveText(second.own);
  await expect(page.getByTestId('ownership-event').last()).toContainText(second.own);
  await page.getByTestId('finance-tab-board').click();
  await expect(page.getByTestId('director-row')).toHaveCount(2); // the founder and the lead
});

type Candidate = {
  person_id: number;
  candidacy: { salary_expectation_cents: number; pending_offer: unknown } | null;
};
type Summary = { insolvent_months: number; open_bridge_id: number | null; game_state: string };

/** A funded spinout (a board that offers bridges) that hires far above asks, advanced through
 * the API until cash first falls below zero: the setup flow (c) is not about. */
async function goBroke(request: APIRequestContext) {
  const base = `/saves/${BROKE}`;
  await createSave(request, BROKE, 'funded_spinout');
  await api(request, 'POST', `${base}/recruitment/searches`, {
    role: 'software_engineer',
    channel: 'job_post',
  });
  for (let month = 0; month < 12; month++) {
    await api(request, 'POST', `${base}/advance`);
    const summary = await api<Summary>(request, 'GET', `${base}/finance/summary`);
    if (summary.insolvent_months > 0) return summary;
    const people = await api<unknown[]>(request, 'GET', `${base}/people`);
    const candidates = await api<Candidate[]>(request, 'GET', `${base}/recruitment/candidates`);
    for (const c of candidates.slice(0, Math.max(0, 5 - people.length))) {
      if (!c.candidacy || c.candidacy.pending_offer) continue;
      await api(request, 'POST', `${base}/recruitment/candidates/${c.person_id}/interview`);
      await api(request, 'POST', `${base}/recruitment/candidates/${c.person_id}/offer`, {
        salary_cents: c.candidacy.salary_expectation_cents * 40,
        equity_bp: 0,
      });
    }
  }
  throw new Error('the scripted company never ran out of cash');
}

test('(c) run out of cash, see the insolvency badge and bridge, ignore it, reach game over', async ({
  page,
  request,
}) => {
  const summary = await goBroke(request);
  expect(summary.open_bridge_id, 'the board offers a bridge').not.toBeNull();

  await page.goto(`/game/${BROKE}/overview`);
  const badge = page.getByTestId('insolvent-badge');
  await expect(badge).toBeVisible();
  await expect(badge).toContainText('bridge offered');
  await badge.click();
  await expect(page).toHaveURL(/\/finance\/fundraising$/);
  await expect(page.getByTestId('bridge-offer')).toBeVisible();
  await expect(page.getByTestId('bridge-amount')).toHaveText(/^\$[\d,]+$/);
  await expect(page.getByTestId('accept-bridge')).toHaveText('Accept the bridge · 5 energy');

  // Ignore it: Continue until the third month end below zero ends the game. A critical
  // event (the payroll crunch, M6) must be answered first; take its first choice.
  const date = page.getByTestId('game-date');
  const cont = page.getByTestId('continue');
  const critical = page.getByRole('dialog');
  for (let step = 0; step < 8 && !page.url().endsWith('/over'); step++) {
    if (await critical.isVisible()) {
      await critical.locator('[data-choice="A"]').click();
      await expect(critical).toBeHidden();
      continue;
    }
    const before = await date.textContent();
    await expect(cont).toBeEnabled();
    await cont.click();
    await expect
      .poll(
        async () =>
          page.url().endsWith('/over') ||
          (await date.textContent()) !== before ||
          (await critical.isVisible()),
      )
      .toBe(true);
    if (!page.url().endsWith('/over') && !(await critical.isVisible()))
      await expect(page.getByTestId('insolvent-badge')).toBeVisible();
  }
  await expect(page).toHaveURL(/\/over$/);
  await expect(page.getByTestId('over-kicker')).toContainText('Bankrupt');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Broke Co ran out of money');
  await expect(page.getByText(/bridge; it lapsed without an answer/)).toBeVisible();
  await expect(page.getByTestId('over-cash')).toHaveText(/^-\$/);
  await expect(page.getByTestId('over-timeline').first()).toBeVisible();

  // The save stays readable; Continue stays off.
  await page.getByRole('link', { name: /Statements/ }).click();
  await expect(page).toHaveURL(/\/finance\/statements$/);
  await expect(page.getByTestId('game-over-banner')).toBeVisible();
  await expect(page.getByTestId('continue')).toBeDisabled();
});
