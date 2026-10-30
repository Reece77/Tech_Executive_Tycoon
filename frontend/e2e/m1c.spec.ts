import { expect, test, type Page } from '@playwright/test';
import { answerCritical, api, continueMonth, offerToAll, setupGame } from './helpers.ts';

const SEED = 11;

async function moraleByName(page: Page): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  for (const row of await page.getByTestId('person-row').all()) {
    const value = row.getByTestId('morale-value');
    if ((await value.count()) === 0) continue; // the founder shows n/a
    out.set((await row.locator('td').first().innerText()).trim(), Number(await value.innerText()));
  }
  return out;
}

test('(a) set up a game with a custom founder and mission', async ({ page }) => {
  await page.goto('/new');
  await page.getByTestId('company-name-input').fill(`Kestrel ${Date.now()}`);
  await page.getByRole('button', { name: 'Hard', exact: true }).click();
  await page.getByTestId('scenario-funded_spinout').click();
  await expect(page.getByTestId('scenario-funded_spinout')).toContainText('$900,000');

  await page.getByTestId('first-name').fill('Reece');
  await page.getByTestId('last-name').fill('Founder');
  await page.getByTestId('age').fill('34');
  await page.getByTestId('background-salesperson').click();
  await expect(page.getByTestId('points-left')).toHaveText('0');
  await expect(page.getByTestId('skill-value-sales')).toHaveText('16'); // 5 + 8 + 3 bonus

  // Move one point from legal to data: still balanced, values come from the preview.
  await page.getByRole('button', { name: 'Add a point to Data' }).click();
  await expect(page.getByTestId('points-left')).toHaveText('-1');
  await expect(page.getByTestId('founder-errors')).toBeVisible();
  await expect(page.getByTestId('start-game')).toBeDisabled();
  await page.getByRole('button', { name: 'Remove a point from Legal' }).click();
  await expect(page.getByTestId('points-left')).toHaveText('0');
  await expect(page.getByTestId('skill-value-data')).toHaveText('6');
  await expect(page.getByTestId('founder-errors')).toBeHidden();

  await page.getByTestId('preset-hustler').click();
  await expect(page.getByTestId('start-game')).toBeDisabled(); // no mission yet
  await page.getByTestId('interest-ai').click();
  await page.getByTestId('interest-enterprise').click();
  await page.getByTestId('interest-climate').click(); // a third is ignored
  await expect(page.getByTestId('interest-climate')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByTestId('setup-summary')).toContainText(
    'Salesperson · Hustler · AI and Enterprise',
  );

  await page.getByTestId('start-game').click();
  await expect(page).toHaveURL(/\/inbox$/);
  await expect(page.getByTestId('top-cash')).toHaveText('$900,000');

  await page.keyboard.press('3');
  await expect(page.getByText('AI · Enterprise')).toBeVisible();
  const founder = page.getByTestId('person-row').first();
  await expect(founder).toContainText('Reece Founder');
  await expect(founder).toContainText('Founder');
  await expect(founder).toContainText('n/a');
  await founder.getByRole('link', { name: 'Reece Founder' }).click();
  await expect(page.getByTestId('profile-name')).toHaveText('Reece Founder');
  await expect(page.getByTestId('attr-sales')).toContainText('16');
  await expect(page.getByTestId('attr-data')).toContainText('6');
  await expect(page.getByText('Age 34')).toBeVisible();
});

test('(b) job post, interview, offer at the ask, hire, payroll', async ({ page }) => {
  test.setTimeout(60_000); // a batch of interviews, one round trip each; rivals made each slower (M5)
  await setupGame(page, { company: `Hiring ${Date.now()}`, seed: SEED });
  await page.keyboard.press('4');
  await expect(page.getByTestId('channel-job_post')).toHaveAttribute('aria-checked', 'true');
  await page.getByTestId('open-search').click();
  await expect(page.getByTestId('energy')).toHaveText('55 / 60');
  await expect(page.getByTestId('search-row')).toContainText('pending');

  await continueMonth(page);
  await expect(page.getByTestId('game-date')).toHaveText('Feb 2010');
  const rows = page.getByTestId('candidate-row');
  await expect(rows.first()).toBeVisible();
  await expect(rows.first()).toContainText('Interview to learn');
  // Offers need an interview first (ADR-0016).
  await expect(rows.first().getByTestId('offer')).toBeDisabled();
  await expect(rows.first().getByTestId('offer')).toHaveText('Interview first');

  await rows.first().getByTestId('interview').click();
  await expect(page.getByTestId('energy')).toHaveText('52 / 60'); // energy resets each month
  await expect(rows.first()).toContainText('Interviewed');
  await expect(rows.first()).not.toContainText('Interview to learn');
  await expect(rows.first().getByTestId('offer')).toBeEnabled();

  // Preview at the ask: ratio 1.00x and the 85% floor, then send.
  await rows.first().getByTestId('offer').click();
  const panel = page.getByRole('complementary', { name: 'Make an offer' });
  await expect(panel).toContainText('1.00× their ask');
  await expect(panel).toContainText('(85%) they always decline');
  await expect(panel.getByTestId('offer-hint')).toContainText(
    'Based only on what you have learned',
  );
  await panel.getByTestId('send-offer').click();
  await expect(rows.first().getByTestId('offer-pending')).toHaveText(
    'Offer pending · answer in Mar 2010',
  );
  // Offers are a coin flip; offer the rest at their ask too so the seeded game hires someone.
  await offerToAll(page);

  await continueMonth(page);
  await page.keyboard.press('3');
  const staff = page.getByTestId('person-row');
  await expect(staff.first()).toBeVisible();
  expect(await staff.count()).toBeGreaterThan(1);
  await expect(staff.filter({ hasText: 'Active' }).first()).toBeVisible();

  await page.keyboard.press('2');
  await expect(page.getByTestId('kpi-payroll')).not.toHaveText('$0');
  await expect(page.getByTestId('cost-6000_salaries')).toBeVisible();
  await expect(page.getByTestId('stage')).toHaveText('Stage 1 · Garage startup');
  await page.keyboard.press('1');
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: 'accepted your offer' }).first(),
  ).toBeVisible();
});

test('(c) fire someone: severance and the morale dip', async ({ page, request }) => {
  const save = `fire-${Date.now()}`;
  const base = `/saves/${save}`;
  await api(request, 'POST', '/saves', {
    name: save,
    company_name: 'Fire Co',
    scenario: 'ex_big_tech_founders',
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
  await api(request, 'POST', `${base}/recruitment/searches`, {
    role: 'software_engineer',
    channel: 'job_post',
  });
  await api(request, 'POST', `${base}/advance`);
  type Candidate = { person_id: number; candidacy: { salary_expectation_cents: number } };
  const candidates = await api<Candidate[]>(request, 'GET', `${base}/recruitment/candidates`);
  for (const c of candidates.slice(0, 7)) {
    // 7 interviews of 8 energy fit in the month's 60 (M4c)
    await api(request, 'POST', `${base}/recruitment/candidates/${c.person_id}/interview`);
    await api(request, 'POST', `${base}/recruitment/candidates/${c.person_id}/offer`, {
      salary_cents: Math.round(c.candidacy.salary_expectation_cents * 1.5),
      equity_bp: 0,
    });
  }
  await api(request, 'POST', `${base}/advance`);
  await answerCritical(request, base); // seven hires at 1.5x can leave a short runway

  await page.goto(`/game/${save}/people`);
  await expect(page.getByTestId('person-row').nth(2)).toBeVisible(); // founder + at least two
  const before = await moraleByName(page);
  const headcount = await page.getByTestId('person-row').count();
  const [victim] = before.keys();

  await page.getByRole('link', { name: victim }).click();
  await page.getByTestId('fire').click();
  const confirm = page.getByTestId('fire-confirm-text');
  await expect(confirm).toContainText('Severance of $');
  await expect(confirm).toContainText("everyone else's morale will drop by at least 3 points");
  const severance = ((await confirm.innerText()).match(/\$[\d,]+/) ?? [''])[0];
  await page.getByTestId('fire-confirm').click();

  await expect(page).toHaveURL(/\/people$/);
  await expect(page.getByTestId('person-row')).toHaveCount(headcount - 1);
  const after = await moraleByName(page);
  expect(after.has(victim)).toBe(false);
  for (const [name, morale] of after) {
    expect(morale, name).toBeLessThanOrEqual(Math.max((before.get(name) ?? 0) - 3, 0) + 1);
  }

  await page.keyboard.press('2');
  await expect(page.getByTestId('cost-paid')).toHaveText(`Severance (paid)${severance}`);
  await page.keyboard.press('1');
  await expect(page.getByTestId('inbox-item').filter({ hasText: 'was let go' })).toBeVisible();
});

test('ten hires within six turns using all three channels', async ({ page }) => {
  test.setTimeout(180_000);
  await setupGame(page, {
    company: `Ten ${Date.now()}`,
    seed: SEED,
    scenario: 'ex_big_tech_founders',
  });
  const channels = ['network', 'recruiter', 'job_post'] as const;

  for (let turn = 0; turn < 6; turn++) {
    await page.keyboard.press('4');
    await expect(page.getByTestId('open-search')).toBeVisible();
    if (turn < 2) {
      // Open each channel (the job post stays open; the others run one batch each).
      for (const channel of turn === 0 ? channels : (['network', 'recruiter'] as const)) {
        const searches = await page.getByTestId('search-row').count();
        await page.getByTestId(`channel-${channel}`).click();
        await page.getByTestId('open-search').click();
        await expect(page.getByTestId('search-row')).toHaveCount(searches + 1);
      }
    }
    // Go by search id, re-finding each row: searches close and the list reorders as we go.
    const ids = await page
      .getByTestId('search-row')
      .evaluateAll((rows) => rows.map((r) => r.getAttribute('data-search-id') ?? ''));
    for (const id of ids) {
      const row = page.locator(`[data-testid="search-row"][data-search-id="${id}"]`);
      if ((await row.count()) === 0) continue;
      await row.getByTestId('select-search').click();
      await expect(row.getByTestId('select-search')).toHaveAttribute('aria-pressed', 'true');
      await offerToAll(page, 1.3);
    }
    await continueMonth(page);
    await page.keyboard.press('3');
    await expect(page.getByTestId('person-row').first()).toBeVisible();
    if ((await page.getByTestId('person-row').count()) >= 11) break;
  }
  await expect(page.getByTestId('game-date')).not.toHaveText('Aug 2010');
  expect(await page.getByTestId('person-row').count()).toBeGreaterThanOrEqual(11);
});
