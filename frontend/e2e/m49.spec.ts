import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { continueMonth } from './helpers.ts';

// M49 flows (formulas.md 61): (a) a launch interview with a bold claim; (b) a recall press
// conference; (c) a one-to-one that keeps a poached engineer; (d) a broken promotion promise.
// The saves come from tools/e2e_m49_save.py (`talks`: stage-3 Quill in Jan 2019, two engineers
// approached by rivals and a class I recall of Quill Glucose last month; `launch`: the same with
// Quill Watch's launch press event open; `due`: a save's open promised promotions fall due
// now). The API server runs conversations on the mock adapter (TST_CONVERSATION_ADAPTER,
// playwright.config.ts), never Claude; the flows play in template mode.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const talksSave = `m49-talks-${stamp}`;
const launchSave = `m49-launch-${stamp}`;
const built = new Map<string, string>();

function tool(mode: string, name: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m49_save.py', mode, saveDir, name],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

/** Build a save once; returns the tool's output (the approached people's ids as JSON). */
function ensure(name: string, mode: string): string {
  const out = built.get(name) ?? tool(mode, name);
  built.set(name, out);
  return out;
}

function approached(name: string): number[] {
  const out = ensure(name, 'talks');
  const line = out.trim().split('\n').pop() ?? '{}';
  return (JSON.parse(line) as { approached: number[] }).approached;
}

async function conversationSettings(page: Page, body: Record<string, unknown>) {
  const current = await (await page.request.get('/api/settings/llm')).json();
  const res = await page.request.put('/api/settings/llm', {
    data: {
      adapter: current.adapter,
      monthly_budget_cents: current.budget_cents,
      model_events: current.model_events,
      model_story: current.model_story,
      ...body,
    },
  });
  expect(res.ok()).toBeTruthy();
}

/** Answer every question with the given template moves until the talk is over. */
async function answerAll(page: Page, moves: string[]) {
  await expect(page.getByTestId('talk-mode')).toContainText('Template mode');
  while (await page.getByTestId('talk-send').isVisible()) {
    const before = await page.getByTestId('talk-answer').count();
    for (const m of moves) await page.getByTestId(`talk-move-${m}`).click();
    await page.getByTestId('talk-send').click();
    await expect(page.getByTestId('talk-answer')).toHaveCount(before + 1);
  }
  await expect(page.getByTestId('talk-status')).toContainText('Over');
  await expect(page.getByTestId('talk-effects')).toBeVisible();
}

test('(a) a launch interview with a bold claim', async ({ page }) => {
  test.setTimeout(300_000);
  ensure(launchSave, 'launch');
  await page.goto(`/game/${launchSave}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  const events = await (await page.request.get(`/api/saves/${launchSave}/events`)).json();
  const press = (events.open as { event_id: number; template_id: string }[]).find(
    (e) => e.template_id === 'press_launch',
  );
  expect(press, 'the launch press event is open').toBeTruthy();
  await page.goto(`/game/${launchSave}/events/${press?.event_id}`);
  await expect(page.getByTestId('event-card')).toBeVisible();
  await page.getByTestId('event-take-interview').click();
  await expect(page.getByTestId('press-room')).toBeVisible();
  await expect(page.getByTestId('talk-room')).toBeVisible();
  await expect(page.getByTestId('talk-subject')).toContainText('Quill Watch');
  await expect(page.getByTestId('talk-counterpart')).toContainText('stance');
  await answerAll(page, ['bold_claim']);
  await expect(page.getByTestId('talk-effects')).toContainText('a bold answer');
  await expect(page.getByTestId('press-row')).toHaveCount(1);
  // The interview answered the press event (bold is its B).
  await page.goto(`/game/${launchSave}/events/${press?.event_id}`);
  await expect(page.getByTestId('event-answered')).toContainText('B');
  await expect(page.getByTestId('event-take-interview')).toHaveCount(0);
});

test('(b) a recall press conference', async ({ page }) => {
  test.setTimeout(300_000);
  approached(talksSave);
  await page.goto(`/game/${talksSave}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  await page.goto(`/game/${talksSave}/press`);
  await expect(page.getByTestId('press-room')).toBeVisible();
  await expect(page.getByTestId('press-slot-recall')).toContainText('Quill Glucose');
  await page.getByTestId('press-take-recall').click();
  await expect(page.getByTestId('talk-subject')).toContainText('recall');
  await answerAll(page, ['apologise', 'take_responsibility']);
  await expect(page.getByTestId('talk-effects')).toContainText('brand');
  await expect(page.getByTestId('talk-effects')).toContainText(/beloved/i);
  await expect(page.getByTestId('press-view-recall')).toBeVisible();
});

test('(c) a one-to-one that keeps a poached engineer', async ({ page }) => {
  test.setTimeout(300_000);
  const [engineer] = approached(talksSave);
  await page.goto(`/game/${talksSave}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  // The People screen flags them and offers the talk.
  await page.goto(`/game/${talksSave}/people`);
  await expect(page.getByTestId('person-flag-approached')).toHaveCount(2);
  await expect(page.getByTestId('people-one-to-one')).toHaveCount(2);
  await page.goto(`/game/${talksSave}/people/${engineer}`);
  const name = (await page.getByTestId('profile-name').textContent()) ?? '';
  await expect(page.getByTestId('one-to-one')).toContainText('Approached by');
  await page.getByTestId('one-to-one-open').click();
  await expect(page.getByTestId('talk-room')).toBeVisible();
  await expect(page.getByTestId('talk-approached')).toBeVisible();
  await answerAll(page, ['offer_raise', 'listen', 'praise']);
  await expect(page.getByTestId('talk-effect').first()).toBeVisible();
  // Once held, not again this month.
  await expect(page.getByTestId('one-to-one-open')).toBeDisabled();
  await expect(page.getByTestId('one-to-one-note')).toContainText('Already held this month');
  await continueMonth(page);
  await page.goto(`/game/${talksSave}/people`);
  await expect(page.getByTestId('person-row').filter({ hasText: name })).toHaveCount(1);
  await page.goto(`/game/${talksSave}/people/${engineer}`);
  await expect(page.getByTestId('profile-name')).toHaveText(name);
  await expect(page.getByTestId('former-badge')).toHaveCount(0);
});

test('(d) a broken promotion promise', async ({ page }) => {
  test.setTimeout(300_000);
  const poached = approached(talksSave);
  await page.goto(`/game/${talksSave}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  const list = await (await page.request.get(`/api/saves/${talksSave}/talks`)).json();
  const person = (list.people as { person_id: number; flags: string[]; held: string }[]).find(
    (p) => p.flags.length === 0 && p.held === '' && !poached.includes(p.person_id),
  );
  expect(person, 'someone unflagged to promise a promotion to').toBeTruthy();
  const id = person?.person_id ?? 0;
  await page.goto(`/game/${talksSave}/people/${id}`);
  const name = (await page.getByTestId('profile-name').textContent()) ?? '';
  await page.getByTestId('one-to-one-open').click();
  await answerAll(page, ['promise_promotion']);
  await expect(page.getByTestId('talk-effects')).toContainText('promised a promotion');
  await expect(page.getByTestId('talk-promise')).toHaveCount(1);
  await expect(page.getByTestId('talk-promise-status')).toHaveText('open');
  tool('due', talksSave);
  await page.reload();
  await continueMonth(page);
  await page.goto(`/game/${talksSave}/people/${id}`);
  await expect(page.getByTestId('profile-name')).toHaveText(name);
  await expect(page.getByTestId('talk-promise-status')).toHaveText('broken');
  await page.goto(`/game/${talksSave}/inbox`);
  await expect(page.getByText(/^Promise broken: promote/).first()).toBeVisible();
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
});
