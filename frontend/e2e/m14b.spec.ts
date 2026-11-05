import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { answerBlocking, continueMonth } from './helpers.ts';

// M14b flows: (a) a launch press moment answered boldly with a Ship promise, kept; (b) a
// no-layoffs promise broken by a firing, its "You said..." reminder and the morale; (c) a
// rival CEO's jab answered by name, and the feud on the Rival screen; (d) Replace a poached
// engineer with a recruiter on staff.
test.describe.configure({ mode: 'serial' });

const STAMP = Date.now();

/** Saves built and edited by tools/e2e_m14b_save.py. */
function fixture(mode: string, save: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m14b_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

/** Open this month's press event from the inbox and answer it. */
async function answerPress(page: Page, save: string, title: string | RegExp, choice: string) {
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('inbox-item').filter({ hasText: title }).first().click();
  const card = page.getByTestId('event-card');
  await expect(card.getByTestId('press-note')).toContainText('B is bold');
  await card.locator(`[data-choice="${choice}"]`).click();
  await expect(card.getByTestId('event-answered')).toHaveText(`You chose ${choice}.`);
  return card;
}

/** Overview's average-morale tile as a number. */
async function avgMorale(page: Page): Promise<number> {
  return Number(await page.getByTestId('kpi-morale').textContent());
}

test('(a) a launch press moment: a bold answer, a Ship promise, kept', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m14b-ship-${STAMP}`;
  fixture('launch', save); // Forge launched last month; Anvil still in development
  const card = await answerPress(page, save, 'Forge is out', 'B');
  await expect(card.locator('[data-choice="B"]')).toContainText('Say Forge will lead the market');
  await card.getByTestId('press-promise-link').click();

  await expect(page).toHaveURL(/\/overview$/);
  const panel = page.getByTestId('promises-panel');
  await expect(panel.getByTestId('promise-count')).toContainText('0 of 3 open');
  await panel.getByTestId('promise-open').click();
  const dialog = page.getByTestId('promise-dialog');
  await expect(dialog).toContainText('0 of 3 promises open');
  await dialog.getByTestId('promise-kind').selectOption('ship');
  await dialog.getByTestId('promise-product').selectOption({ label: 'Anvil' });
  await dialog.getByTestId('promise-months').fill('3');
  await expect(dialog.getByTestId('promise-submit')).toContainText('2 energy');
  await dialog.getByTestId('promise-submit').click();
  await expect(dialog).toBeHidden();

  const row = panel.getByTestId('promise-row').filter({ hasText: 'ship Anvil' });
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId('promise-status')).toHaveAttribute('data-status', 'open');
  await expect(row.getByTestId('promise-progress')).toHaveText('Anvil: in development');
  await expect(row.getByTestId('promise-deadline')).toContainText('3 months');
  await expect(panel.getByTestId('promise-open')).toHaveCount(0); // one promise a moment

  // Months of development later: Anvil is ready, ships on time, and the promise is kept.
  fixture('ready', save);
  await page.goto(`/game/${save}/products`);
  await page.getByRole('link', { name: 'Anvil', exact: true }).first().click();
  await expect(page.getByTestId('launch-missing')).toHaveText('Ready to launch.');
  await page.getByTestId('launch').click();
  await expect(page.getByTestId('launch')).toHaveCount(0);
  await continueMonth(page);

  await page.goto(`/game/${save}/overview`);
  await expect(row.getByTestId('promise-status')).toHaveAttribute('data-status', 'kept');
  await expect(page.getByTestId('credibility-history')).toContainText('kept: ship Anvil');
  await expect(page.getByTestId('active-effects')).toContainText(
    /\+[\d.]+% brand target across the company for 11 months/,
  );
  await page.goto(`/game/${save}/inbox`);
  const kept = page.getByTestId('inbox-item').filter({ hasText: 'Promise kept: ship Anvil' });
  await kept.click();
  await expect(page.getByTestId('message-body')).toContainText('The brand and your credibility');
  await expect(page.getByTestId('view-promises')).toBeVisible();
});

test('(b) break a no-layoffs promise: the reminder and the morale', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m14b-layoffs-${STAMP}`;
  fixture('layoffs', save); // a launch press moment for Pipeline, twelve on the staff
  await answerPress(page, save, 'Pipeline is out', 'A'); // measured
  await page.goto(`/game/${save}/overview`);
  const panel = page.getByTestId('promises-panel');
  await panel.getByTestId('promise-open').click();
  const dialog = page.getByTestId('promise-dialog');
  await dialog.getByTestId('promise-kind').selectOption('no_layoffs');
  await expect(dialog).toContainText('Runs 12 months from now.');
  await dialog.getByTestId('promise-submit').click();
  await expect(dialog).toBeHidden();
  const row = panel.getByTestId('promise-row').filter({ hasText: 'make no layoffs' });
  await expect(row.getByTestId('promise-status')).toHaveAttribute('data-status', 'open');
  await expect(row.getByTestId('promise-progress')).toHaveText('no layoffs so far');
  const before = await avgMorale(page);

  // Fire the marketer.
  await page.goto(`/game/${save}/people`);
  const victim = page.getByTestId('person-row').filter({ hasText: 'Marketer' }).first();
  await victim.getByRole('link').first().click();
  await page.getByTestId('fire').click();
  await page.getByTestId('fire-confirm').click();
  await expect(page).toHaveURL(/\/people$/);

  await page.goto(`/game/${save}/overview`);
  await expect(row.getByTestId('promise-status')).toHaveAttribute('data-status', 'broken');
  await expect(page.getByTestId('credibility-history')).toContainText('broken: make no layoffs');
  const after = await avgMorale(page);
  expect(after).toBeLessThanOrEqual(before - 5); // the broken promise alone costs 5

  // The press does not forget: the reminder comes as a press moment.
  let reminder = false;
  for (let month = 0; month < 3 && !reminder; month += 1) {
    await answerBlocking(page); // this month's other events, never a reminder already shown
    const date = page.getByTestId('game-date');
    const was = await date.textContent();
    await page.getByTestId('continue').click();
    await expect(date).not.toHaveText(was ?? '');
    const events = await (await page.request.get(`/api/saves/${save}/events`)).json();
    reminder = (events.open as { title: string }[]).some((e) => e.title.includes('You said'));
  }
  expect(reminder).toBe(true);
  const card = await answerPress(page, save, 'You said', 'C');
  await expect(card).toContainText('promised to make no layoffs');
  await page.goto(`/game/${save}/overview`);
  expect(await avgMorale(page)).toBeLessThan(before);
});

test("(c) a rival CEO's jab, a bold answer by name, and the feud", async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m14b-jab-${STAMP}`;
  fixture('jab', save); // Salesforce's CEO jabbed at Kestrel last month
  await page.goto(`/game/${save}/inbox`);
  const statement = page.getByTestId('inbox-item').filter({ hasText: 'a public statement' });
  await statement.filter({ hasText: 'Salesforce' }).first().click();
  await expect(page.getByTestId('message-body')).toContainText('Kestrel');
  const rivalUrl = await page.getByTestId('view-rival').getAttribute('href');
  expect(rivalUrl).toMatch(/\/competitors\/\d+$/);

  const card = await answerPress(page, save, 'takes a swipe at Kestrel', 'B');
  const bold = card.locator('[data-choice="B"]');
  await expect(bold).toContainText(/Hit back at .+ by name/);
  const ceo = ((await bold.textContent()) ?? '')
    .replace(/^B\. Hit back at /, '')
    .replace(/ by name$/, '');

  await page.goto(rivalUrl ?? '/');
  const leader = page.getByTestId('rival-leader');
  await expect(leader.getByTestId('rival-ceo')).toHaveText(ceo);
  await expect(leader.getByTestId('rival-statement').first()).toHaveAttribute('data-kind', 'jab');
  const score = Number(await leader.getByTestId('feud-score').getAttribute('data-score'));
  expect(score).toBeGreaterThan(0);
  await expect(leader.getByTestId('feud-causes')).toContainText('a bold claim named them');
  await expect(leader.getByTestId('feud-rivalry')).toHaveCount(0); // short of a rivalry
});

test('(d) Replace a poached engineer with a recruiter on staff', async ({ page }) => {
  test.setTimeout(120_000);
  const save = `m14b-replace-${STAMP}`;
  fixture('poached', save); // a senior engineer accepted Salesforce's approach
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('inbox-item').filter({ hasText: 'Salesforce' }).first().click();
  await expect(page.getByRole('link', { name: 'Find a replacement' })).toBeVisible();
  const replaceInInbox = page.locator('[data-testid^="replace-"]');
  await expect(replaceInInbox).toHaveText('Replace');
  const id = ((await replaceInInbox.getAttribute('data-testid')) ?? '').replace('replace-', '');

  await page.goto(`/game/${save}/recruitment`);
  const panel = page.getByTestId('replace-panel');
  const row = panel.getByTestId('replace-row');
  await expect(row).toContainText('Poached');
  await expect(row).toContainText('Software engineer');
  await panel.getByTestId(`replace-${id}`).click();
  await expect(panel.getByTestId('replace-started')).toBeVisible();
  await expect(panel.getByTestId(`replace-${id}`)).toBeDisabled();
  await expect(panel.getByTestId('replace-problem')).toHaveAttribute(
    'title',
    /already being found/,
  );

  const poached = (await row.getByRole('link').first().textContent()) ?? '';
  const engineers = async () => {
    await page.goto(`/game/${save}/people`);
    await expect(page.getByTestId('person-row').first()).toBeVisible();
    return page
      .getByTestId('person-row')
      .filter({ hasText: 'Software engineer' })
      .evaluateAll((rows) => rows.map((r) => r.querySelector('a')?.textContent ?? ''));
  };
  const before = await engineers();
  expect(before).toContain(poached); // serving notice
  await continueMonth(page);
  await continueMonth(page);
  await page.goto(`/game/${save}/recruitment`);
  await expect(page.getByTestId('plan-status').first()).toContainText(/filled/i);
  const after = await engineers();
  // The poached engineer has gone and a new one has joined in their place.
  expect(after).not.toContain(poached);
  expect(after.filter((name) => !before.includes(name)).length).toBeGreaterThan(0);
  await expect(page.getByTestId('leadership-fit').first()).toHaveText(/★/);
});
