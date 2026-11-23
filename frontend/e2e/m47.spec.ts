import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M47 flows (formulas.md 58): (a) negotiate an acquisition in template mode and close below the
// opening price; (b) threaten to walk with an offer outside the zone and lose the deal; (c) skip
// and get the median, today's terms; (d) the conversations' cap switches to template mode. The
// save comes from tools/e2e_m47_save.py (`fresh`: Parley in January 2010 with $50B and private
// companies to buy). The API server runs conversations on the mock adapter
// (TST_CONVERSATION_ADAPTER, playwright.config.ts), never Claude; events keep their templates.
test.describe.configure({ mode: 'serial' });

const save = `m47-${Date.now()}`;
let targets: number[] = [];

function tool(mode: string, name: string): string {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  return execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m47_save.py', mode, saveDir, name],
    { cwd: resolve(process.cwd(), '..'), shell: process.platform === 'win32' },
  ).toString();
}

function ensureSave(): void {
  if (targets.length) return;
  const out = tool('fresh', save).trim().split('\n').at(-1) ?? '[]';
  targets = JSON.parse(out) as number[];
  expect(targets.length).toBeGreaterThanOrEqual(4);
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

/** The acquisition panel of a target, kept as a brand, and its negotiation opened. */
async function openTalks(page: Page, target: number) {
  await page.goto(`/game/${save}/competitors/${target}`);
  await page.getByTestId('offer-mode').getByText('Keep as a brand').click();
  await page.getByTestId('open-negotiation-acquisition').click();
  await expect(page.getByTestId('negotiation-subject')).toContainText('Acquire');
}

async function latest(page: Page) {
  const res = await page.request.get(`/api/saves/${save}/negotiations`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const list = await res.json();
  const id = list.items[0].negotiation_id as number;
  return (await page.request.get(`/api/saves/${save}/negotiations/${id}`)).json();
}

test('(a) negotiate an acquisition in template mode and close below the opening', async ({
  page,
}) => {
  test.setTimeout(300_000);
  ensureSave();
  await page.goto(`/game/${save}/overview`);
  await conversationSettings(page, { conversation_mode: 'template' });
  await openTalks(page, targets[0]);
  await expect(page.getByTestId('negotiation-mode')).toContainText('Template mode');
  await expect(page.getByTestId('negotiation-range')).toContainText('lies between');
  await page.getByTestId('negotiation-offer-0').fill('1');
  await page.getByTestId('move-anchor').click();
  await page.getByTestId('move-justify').click();
  await page.getByTestId('negotiation-send').click();
  await expect(page.getByTestId('negotiation-round')).toHaveCount(1);
  const [accepted] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/accept') && r.request().method() === 'POST'),
    page.getByTestId('negotiation-accept').click(),
  ]);
  expect(accepted.ok(), await accepted.text()).toBeTruthy();
  await expect(page.getByTestId('negotiation-status')).toContainText('Agreed');
  await expect(page.getByTestId('negotiation-debrief')).toContainText('they opened at');
  const n = await latest(page);
  expect(n.status).toBe('agreed');
  expect(n.final[0]).toBeLessThan(n.opening[0]);
  const mna = await (await page.request.get(`/api/saves/${save}/mna`)).json();
  expect(mna.deals.some((d: { target_id: number }) => d.target_id === targets[0])).toBeTruthy();
});

test('(b) threaten to walk with an offer outside the zone and lose the deal', async ({ page }) => {
  test.setTimeout(300_000);
  ensureSave();
  await openTalks(page, targets[1]);
  await page.getByTestId('negotiation-offer-0').fill('1');
  await page.getByTestId('move-threaten_walk').click();
  await page.getByTestId('negotiation-send').click();
  await expect(page.getByTestId('negotiation-status')).toContainText('walked away');
  await expect(page.getByTestId('negotiation-debrief')).toContainText('No deal');
  const n = await latest(page);
  expect(n.status).toBe('walked');
  expect(n.cooldown_until).not.toBeNull();
  const again = await page.request.post(`/api/saves/${save}/negotiations`, {
    data: { kind: 'acquisition', params: { target_id: targets[1], mode: 'brand' } },
  });
  expect(again.status()).toBe(400);
});

test('(c) skip and get the median', async ({ page }) => {
  test.setTimeout(300_000);
  ensureSave();
  await openTalks(page, targets[2]);
  const [skipped] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/skip') && r.request().method() === 'POST'),
    page.getByTestId('negotiation-skip').click(),
  ]);
  expect(skipped.ok(), await skipped.text()).toBeTruthy();
  await expect(page.getByTestId('negotiation-status')).toContainText('Skipped');
  const n = await latest(page);
  expect(n.status).toBe('skipped');
  const mna = await (await page.request.get(`/api/saves/${save}/mna`)).json();
  const deal = mna.deals.find((d: { target_id: number }) => d.target_id === targets[2]);
  expect(deal.price_cents).toBe(n.final[0]);
  expect(n.final[0]).toBeLessThan(n.opening[0]);
});

test('(d) the cap switches conversations to template mode', async ({ page }) => {
  test.setTimeout(300_000);
  ensureSave();
  await page.goto(`/game/${save}/overview`);
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
  await openTalks(page, targets[3]);
  await expect(page.getByTestId('negotiation-mode')).toContainText('Free text');
  await expect(page.getByTestId('negotiation-suggestion')).toHaveCount(3);
  await page.goto(`/game/${save}/settings`);
  const cap = page.getByTestId('conversation-cap');
  await cap.fill('0');
  await page.getByTestId('save-conversation-settings').click();
  await expect(page.getByTestId('conversation-in-use')).toContainText('Templates');
  await openTalks(page, targets[3]);
  await expect(page.getByTestId('negotiation-mode')).toContainText('Template mode (budget)');
  await expect(page.getByTestId('move-justify')).toBeVisible();
  await conversationSettings(page, { conversation_mode: 'auto', conversation_budget_cents: 1000 });
});
