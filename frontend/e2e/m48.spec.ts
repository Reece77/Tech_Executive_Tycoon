import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M48 flows (formulas.md 59): (a) a board meeting where a commitment is made and later kept;
// (b) an earnings call after a miss; (c) an investor day for a new industry; (d) skip. The saves
// come from tools/e2e_m48_save.py (`reported`: listed Kestrel just after a quarterly report;
// `miss`: the same after a miss). The API server runs conversations on the mock adapter
// (TST_CONVERSATION_ADAPTER, playwright.config.ts), never Claude.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();
const reported = `m48-reported-${stamp}`;
const missed = `m48-miss-${stamp}`;
const built = new Set<string>();

function tool(mode: string, name: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m48_save.py', mode, saveDir, name],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

function ensure(name: string, mode: string): void {
  if (built.has(name)) return;
  tool(mode, name);
  built.add(name);
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

async function meetings(page: Page, save: string) {
  await page.goto(`/game/${save}/finance/meetings`);
  await expect(page.getByTestId('meetings-tab')).toBeVisible();
}

/** Answer every item with the given template moves until the meeting is over. */
async function answerAll(page: Page, moves: string[]) {
  while (await page.getByTestId('meeting-send').isVisible()) {
    const before = await page.getByTestId('meeting-answer').count();
    for (const m of moves) {
      const button = page.getByTestId(`meeting-move-${m}`);
      if (await button.isVisible()) await button.click();
    }
    if (!(await page.getByTestId('meeting-send').isEnabled())) {
      await page.getByTestId('meeting-move-explain').click();
    }
    await page.getByTestId('meeting-send').click();
    await expect(page.getByTestId('meeting-answer')).toHaveCount(before + 1);
  }
}

test('(a) a board meeting where a commitment is made and later kept', async ({ page }) => {
  test.setTimeout(300_000);
  ensure(reported, 'reported');
  await page.goto(`/game/${reported}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  await meetings(page, reported);
  await page.getByTestId('meeting-hold-board').click();
  await expect(page.getByTestId('meeting-mode')).toContainText('Template mode');
  await expect(page.getByTestId('meeting-question')).toContainText('quarter');
  await answerAll(page, ['commit', 'explain']);
  await expect(page.getByTestId('meeting-status')).toContainText('Over');
  await expect(page.getByTestId('meeting-effect').first()).toContainText('confidence');
  await expect(page.getByTestId('meeting-commitment-row')).toHaveCount(1);
  await expect(page.getByTestId('meeting-commitment-row')).toContainText('open');
  tool('keepable', reported);
  for (let i = 0; i < 3; i += 1) {
    const res = await page.request.post(`/api/saves/${reported}/advance`);
    expect(res.ok(), await res.text()).toBeTruthy();
  }
  await meetings(page, reported);
  await expect(page.getByTestId('meeting-commitment-row')).toContainText('kept');
  await page.goto(`/game/${reported}/inbox`);
  await expect(page.getByText('Commitment kept').first()).toBeVisible();
});

test('(b) an earnings call after a miss', async ({ page }) => {
  test.setTimeout(300_000);
  ensure(missed, 'miss');
  await page.goto(`/game/${missed}/overview`);
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
  await meetings(page, missed);
  await page.getByTestId('meeting-hold-call').click();
  await expect(page.getByTestId('meeting-mode')).toContainText('Free text');
  await expect(page.getByTestId('meeting-agenda')).toContainText('a real problem');
  await expect(page.getByTestId('meeting-facts')).toContainText('a miss');
  await expect(page.getByTestId('meeting-suggestion')).toHaveCount(3);
  while (await page.getByTestId('meeting-send').isVisible()) {
    const before = await page.getByTestId('meeting-answer').count();
    await page.getByTestId('meeting-suggestion').first().click();
    await page.getByTestId('meeting-send').click();
    await expect(page.getByTestId('meeting-answer')).toHaveCount(before + 1);
  }
  await expect(page.getByTestId('meeting-status')).toContainText('Over');
  await expect(page.getByTestId('meeting-effects')).toBeVisible();
  await expect(page.getByTestId('meeting-credibility')).toContainText('Credibility');
  await page.goto(`/game/${missed}/finance/stock`);
  await expect(page.getByTestId('kpi-credibility')).toBeVisible();
});

test('(c) an investor day for a new industry', async ({ page }) => {
  test.setTimeout(300_000);
  ensure(reported, 'reported');
  await page.goto(`/game/${reported}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  await meetings(page, reported);
  await page.getByTestId('investor-day-plan').selectOption('new_industry');
  await page.getByTestId('investor-day-industry').selectOption('robotics');
  await page.getByTestId('meeting-hold-investor_day').click();
  await expect(page.getByTestId('meeting-subject')).toContainText('robotics');
  await answerAll(page, ['explain']);
  await expect(page.getByTestId('meeting-status')).toContainText('Over');
  await meetings(page, reported);
  await expect(page.getByTestId('meeting-slot-investor_day')).toContainText('months from now');
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
});

test('(d) skip', async ({ page }) => {
  test.setTimeout(300_000);
  ensure(missed, 'miss');
  await page.goto(`/game/${missed}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  const before = await (await page.request.get(`/api/saves/${missed}/finance/board`)).json();
  await meetings(page, missed);
  await page.getByTestId('meeting-hold-board').click();
  await page.getByTestId('meeting-move-commit').click();
  await page.getByTestId('meeting-send').click();
  await expect(page.getByTestId('meeting-answer')).toHaveCount(1);
  await page.getByTestId('meeting-skip').click();
  await expect(page.getByTestId('meeting-status')).toContainText('Skipped');
  await expect(page.getByTestId('meetings-tab')).toContainText('Skipped: nothing moved.');
  const after = await (await page.request.get(`/api/saves/${missed}/finance/board`)).json();
  expect(after.directors).toEqual(before.directors);
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
});
