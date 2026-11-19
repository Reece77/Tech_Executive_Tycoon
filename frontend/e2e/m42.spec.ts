import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M42 flows (formulas.md 55): (a) start a programme with AI discovery and see its preclinical
// stage shortened; (b) a Phase II readout fails and the programme can be redesigned or stopped;
// (c) loss of exclusivity cuts a drug's revenue. Saves come from tools/e2e_m42_save.py: Helix in
// January 2026, an AI and devices company with an ML research team and $5B.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(...args: string[]): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const [mode, save] = args;
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m42_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

function dollars(text: string): number {
  return Number(text.replace(/[^0-9.-]/g, ''));
}

test('(a) start a programme with AI discovery and see its preclinical stage shortened', async ({
  page,
}) => {
  test.setTimeout(600_000);
  const save = `m42-ai-${stamp}`;
  tool('pharma', save);
  await page.goto(`/game/${save}/products/pharma`);
  await expect(page.getByTestId('no-programmes')).toBeVisible();
  await page.getByTestId('rx-name').fill('HX-1');
  await page.getByTestId('rx-indication').click();
  await page.getByRole('option', { name: /^Obesity/ }).click();
  await page.getByTestId('rx-ai').check();
  await page.getByTestId('rx-start').click();
  const row = page.getByTestId('rx-row').filter({ hasText: 'HX-1' });
  await expect(row).toContainText('Discovery');
  await expect(row).toContainText('AI');
  await row.getByRole('link', { name: 'HX-1' }).click();
  await expect(page.getByTestId('rx-preclinical')).toContainText('with AI discovery');
  await expect(page.getByTestId('rx-preclinical')).toContainText('without');
  await expect(page.getByTestId('rx-value')).toContainText('Chance to approval');
});

test('(b) a Phase II readout fails and the programme can be redesigned or stopped', async ({
  page,
}) => {
  test.setTimeout(600_000);
  const save = `m42-phase2-${stamp}`;
  tool('phase2', save);
  await page.goto(`/game/${save}/products/pharma`);
  await expect(page.getByTestId('rx-stage-1')).toContainText('Phase II');
  await pressContinue(page);
  await page.goto(`/game/${save}/products/pharma`);
  await expect(page.getByTestId('rx-stage-1')).toContainText('failed');
  await expect(page.getByTestId('rx-stop-1')).toBeVisible();
  await page.getByTestId('rx-design-1').click();
  await page.getByRole('option', { name: 'large' }).click();
  await page.getByTestId('rx-redesign-1').click();
  await expect(page.getByTestId('rx-stage-1')).toContainText('Phase II · active');
  await page.getByTestId('rx-link-1').click();
  await expect(page.getByTestId('rx-readout').first()).toContainText('failed');
});

test("(c) loss of exclusivity cuts a drug's revenue", async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m42-cliff-${stamp}`;
  tool('cliff', save);
  await page.goto(`/game/${save}/products/pharma`);
  await expect(page.getByTestId('rx-loe-1')).toHaveText('generics');
  const history = page.getByTestId('rx-history-1');
  await history.locator('summary').click();
  const months = history.getByTestId('rx-month');
  const first = dollars(((await months.first().textContent()) ?? '').split(':').slice(1).join(':'));
  const last = dollars(((await months.last().textContent()) ?? '').split(':').slice(1).join(':'));
  expect(first).toBeGreaterThan(0);
  expect(last).toBeLessThan(first * 0.3);
});
