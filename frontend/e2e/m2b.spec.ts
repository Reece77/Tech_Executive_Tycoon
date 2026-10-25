// M2b flows: build an org, run a hiring plan, give a raise and a promotion. State the tests are
// not about (hiring the first staff) is set up through the API; the rest is driven in the UI.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { api, continueMonth } from './helpers.ts';

const SEED = 11;

type Candidate = { person_id: number; candidacy: { salary_expectation_cents: number } };
type Person = { person_id: number; is_founder: boolean };

async function newSave(request: APIRequestContext, name: string): Promise<string> {
  await api(request, 'POST', '/saves', {
    name,
    company_name: 'Org Flow Co',
    scenario: 'funded_spinout',
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
  return `/saves/${name}`;
}

/** Interview and offer 1.5x the ask to open candidates (energy permitting) until `employees`. */
async function hire(request: APIRequestContext, base: string, employees: number) {
  await api(request, 'POST', `${base}/recruitment/searches`, {
    role: 'software_engineer',
    channel: 'job_post',
  });
  for (let turn = 0; turn < 8; turn++) {
    await api(request, 'POST', `${base}/advance`);
    const staff = await api<Person[]>(request, 'GET', `${base}/people`);
    if (staff.filter((p) => !p.is_founder).length >= employees) return;
    for (const c of await api<Candidate[]>(request, 'GET', `${base}/recruitment/candidates`)) {
      const path = `/api${base}/recruitment/candidates/${c.person_id}`;
      const interviewed = await request.fetch(`${path}/interview`, { method: 'POST' });
      if (!interviewed.ok()) break; // out of energy this month
      await request.fetch(`${path}/offer`, {
        method: 'POST',
        data: {
          salary_cents: Math.round(c.candidacy.salary_expectation_cents * 1.5),
          equity_bp: 0,
        },
      });
    }
  }
  throw new Error(`could not hire ${employees} people`);
}

async function confirmPreview(page: Page) {
  const dialog = page.getByTestId('preview');
  await expect(dialog.getByTestId('preview-energy')).toBeVisible();
  await page.getByTestId('preview-confirm').click();
  await expect(dialog).toBeHidden();
}

async function createUnit(page: Page, button: 'new-team' | 'new-department', name: string) {
  await page.getByTestId(button).click();
  await page.getByTestId('unit-name-input').fill(name);
  await confirmPreview(page);
  await expect(page.getByTestId('unit-title')).toHaveText(name);
}

test('(a) build company → department → team and appoint leads', async ({ page, request }) => {
  test.setTimeout(120_000);
  const save = `org-a-${Date.now()}`;
  const base = await newSave(request, save);
  await hire(request, base, 9); // departments unlock at 10 staff

  await page.goto(`/game/${save}/org`);
  await expect(page.getByTestId('new-department')).toBeVisible();
  await createUnit(page, 'new-department', 'Engineering');
  await createUnit(page, 'new-team', 'Platform'); // under the selected department
  await expect(page.getByTestId('unit-panel')).toContainText('in Engineering');

  // Move two people into Engineering and three into Platform from the company root.
  await page.getByRole('button', { name: 'Company Org Flow Co' }).click();
  for (const target of ['Engineering', 'Engineering', 'Platform', 'Platform', 'Platform']) {
    await page.getByTestId('member-row').getByTestId('move-to').first().click();
    await page.getByRole('menuitem', { name: target, exact: true }).click();
    const changes = page.getByTestId('preview-change');
    await expect(changes).toHaveCount(1); // the moved person: one-off −2
    await expect(changes.first()).toContainText('−2');
    await confirmPreview(page);
  }

  for (const unit of ['Engineering', 'Platform']) {
    await page.getByRole('button', { name: new RegExp(`^(Department|Team) ${unit}$`) }).click();
    await page.getByTestId('set-leader').click();
    await page.getByTestId('leader-option').first().click();
    await confirmPreview(page);
    await expect(page.getByTestId('unit-panel')).not.toContainText('LeaderNone');
    await expect(page.getByTestId('manager-label')).not.toHaveText('—');
  }
  await expect(page.getByTestId('org-summary')).toContainText('2 units');
  const platform = page.getByRole('button', { name: 'Team Platform' });
  await expect(platform).toContainText('Led by');
  await expect(platform).toContainText('3 people');
  await expect(page.getByRole('button', { name: 'Department Engineering' })).toContainText(
    '5 people', // its own two plus the team below it
  );
});

test('(b) a hiring plan fills its unit while founder energy stays full', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const save = `org-b-${Date.now()}`;
  const base = await newSave(request, save);
  await hire(request, base, 1); // the plan's owner
  await api(request, 'POST', `${base}/org/units`, { kind: 'team', name: 'Platform' });

  await page.goto(`/game/${save}/recruitment`);
  await page.getByTestId('new-plan').click();
  const dialog = page.getByTestId('plan-dialog');
  await expect(dialog.getByTestId('plan-owner-info')).toContainText('energy a month');
  await dialog.getByTestId('plan-unit').selectOption({ label: 'Platform' });
  await dialog.getByTestId('plan-role').selectOption({ label: 'Software engineer' });
  await dialog.getByTestId('plan-target').fill('2');
  await dialog.getByTestId('plan-channel-job_post').check();
  await dialog.getByTestId('plan-ratio').fill('1.2');
  await dialog.getByTestId('save-plan').click();
  await expect(dialog).toBeHidden();
  const row = page.getByTestId('plan-row');
  await expect(row).toContainText('0 / 2');
  await expect(row).toContainText('Platform');
  await expect(page.getByTestId('energy')).toHaveText('96 / 100'); // the team and the plan cost 2 each

  for (let month = 0; month < 3; month++) {
    await continueMonth(page);
    await expect(page.getByTestId('energy')).toHaveText('100 / 100'); // delegates use their own
  }
  await expect(page.getByTestId('plan-activity')).not.toContainText('Starts at');

  await page.keyboard.press('3');
  await page.getByTestId('unit-filter').selectOption('Platform');
  const hires = page.getByTestId('person-row');
  await expect(hires.first()).toBeVisible();
  expect(await hires.count()).toBeGreaterThanOrEqual(1);
  for (const unitCell of await page.getByTestId('person-unit').all()) {
    await expect(unitCell).toHaveText('Platform');
  }
  await page.keyboard.press('1');
  await expect(
    page.getByTestId('inbox-item').filter({ hasText: 'DELEGATE' }).first(),
  ).toBeVisible();
});

test('(c) a raise and a promotion match their previews', async ({ page, request }) => {
  test.setTimeout(120_000);
  const save = `org-c-${Date.now()}`;
  const base = await newSave(request, save);
  await hire(request, base, 1);
  const [person] = (await api<Person[]>(request, 'GET', `${base}/people`)).filter(
    (p) => !p.is_founder,
  );

  await page.goto(`/game/${save}/people/${person.person_id}`);
  const moraleText = async () =>
    Number(await page.getByLabel('Summary').getByTestId('morale-value').textContent());
  const before = await moraleText();

  await page.getByTestId('give-raise').click();
  const raise = page.getByTestId('raise-dialog');
  const salaryInput = raise.getByTestId('raise-salary');
  const current = Number(await salaryInput.inputValue());
  const newSalary = Math.round(current * 1.1);
  await salaryInput.fill(String(newSalary));
  const facts = raise.getByTestId('raise-facts');
  await expect(facts).toContainText('Up 10.0'); // the preview's change, from the API
  await expect(facts).toContainText('+3');
  await raise.getByTestId('confirm-raise').click();
  await expect(raise).toBeHidden();
  await expect(page.getByLabel('Summary')).toContainText(`$${newSalary.toLocaleString('en-US')}`);
  await expect.poll(moraleText).toBeGreaterThanOrEqual(before + 2); // +3, shown rounded
  const afterRaise = await moraleText();

  await page.getByTestId('promote').click();
  const promote = page.getByTestId('promote-dialog');
  const facts2 = promote.getByTestId('promote-facts');
  await expect(facts2).toContainText('→');
  const levels = ((await facts2.textContent()) ?? '').match(/Level([A-Z][a-z]+) → ([A-Z][a-z]+)/);
  expect(levels).not.toBeNull();
  const newLevel = levels?.[2] ?? '';
  await expect(facts2).toContainText('+5');
  await promote.getByTestId('confirm-promote').click();
  await expect(promote).toBeHidden();
  await expect(page.getByLabel('Summary')).toContainText(newLevel);
  await expect.poll(moraleText).toBeGreaterThanOrEqual(afterRaise + 4); // +5, shown rounded
});
