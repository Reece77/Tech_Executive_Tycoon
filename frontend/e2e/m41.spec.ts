import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pressContinue } from './helpers.ts';

// M41 flows (formulas.md 50): (a) submit a wearable by 510(k) with a predicate and see the review
// range; (b) run a pivotal study for an implantable and file a PMA; (c) a class I recall arrives
// as a critical event. Saves come from tools/e2e_m41_save.py: Lumen in January 2024, a device
// and AI company with medical products ready to be designed and filed.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function tool(...args: string[]): void {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  const [mode, save] = args;
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_m41_save.py', mode, saveDir, save],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) submit a wearable by 510(k) with a predicate and see the review range', async ({
  page,
}) => {
  test.setTimeout(600_000);
  const save = `m41-wearable-${stamp}`;
  tool('medical', save);
  await page.goto(`/game/${save}/products/medical`);
  const pulse = page.getByTestId(/^device-/).filter({ hasText: 'Lumen Pulse' });
  await expect(pulse).toBeVisible();
  await pulse.getByTestId('device-use').click();
  await page.getByRole('option', { name: 'Arrhythmia detection (ECG)' }).click();
  await expect(pulse).toContainText('US class II (510(k))');
  await pulse.getByTestId('device-design').click();
  const fda = pulse.getByTestId('route-row').filter({ hasText: 'Food and Drug Administration' });
  await expect(fda).toContainText('510(k)');
  await expect(pulse.getByTestId('review-fda')).toContainText('3-7 months');
  await pulse.getByTestId('file-fda').click();
  await expect(pulse.getByTestId('stage-fda')).toContainText('under review');
  await expect(pulse.getByTestId('stage-fda')).toContainText('filed Jan 2024');
});

test('(b) run a pivotal study for an implantable and file a PMA', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m41-implant-${stamp}`;
  tool('implant', save);
  await page.goto(`/game/${save}/products/medical`);
  const beat = page.getByTestId(/^device-/).filter({ hasText: 'Lumen Beat' });
  await expect(beat).toContainText('US class III');
  await expect(beat.getByTestId('file-fda')).toBeDisabled();
  await beat.getByLabel(/Patients/).fill('241');
  await beat.getByTestId('start-study').click();
  const study = beat.getByTestId('study-row');
  await expect(study).toContainText('Pivotal');
  await expect(study).toContainText('241');
  await expect(study).toContainText('running');
  tool('readout', save);
  await page.reload();
  const done = page.getByTestId(/^device-/).filter({ hasText: 'Lumen Beat' });
  await expect(done.getByTestId('study-row')).toContainText('met its endpoint');
  await done.getByTestId('file-fda').click();
  const fda = done.getByTestId('route-row').filter({ hasText: 'Food and Drug Administration' });
  await expect(fda).toContainText('PMA');
  await expect(done.getByTestId('stage-fda')).toContainText('under review');
});

test('(c) a class I recall arrives as a critical event', async ({ page }) => {
  test.setTimeout(600_000);
  const save = `m41-recall-${stamp}`;
  tool('recall', save);
  await page.goto(`/game/${save}/overview`);
  await pressContinue(page);
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('Class I recall: Lumen Glucose');
  await expect(modal).toContainText('40,000');
  await modal.getByTestId('event-choice').filter({ hasText: 'Recall every affected unit' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'Class I recall' })).toHaveCount(0);
  await page.goto(`/game/${save}/products/medical`);
  await expect(page.getByTestId('recalls')).toContainText('class I');
});
