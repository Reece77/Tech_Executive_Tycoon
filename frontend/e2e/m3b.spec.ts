import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { api, continueMonth } from './helpers.ts';

// M3b flows, run in order against one save: (a) create a product, assign the company,
// Continue until launch is allowed, launch; (b) change a price through its preview and see new
// customers change; (c) sunset after confirming.
test.describe.configure({ mode: 'serial' });

const SEED = 11;
const SAVE = `m3b-${Date.now()}`;
const BASE = `/saves/${SAVE}`;
const BUILDERS = 3; // engineers beside the founder: enough to reach launch within a year
const MAX_MONTHS = 15;

type Candidate = {
  person_id: number;
  candidacy: { salary_expectation_cents: number; pending_offer: unknown } | null;
};

/** A founder plus engineers, hired through the API: the setup these tests are not about. */
async function staffUp(request: APIRequestContext) {
  await api(request, 'POST', '/saves', {
    name: SAVE,
    company_name: 'Product Co',
    scenario: 'ex_big_tech_founders',
    seed: SEED,
    mission: ['ai', 'enterprise'],
  });
  await api(request, 'POST', `${BASE}/recruitment/searches`, {
    role: 'software_engineer',
    channel: 'job_post',
  });
  for (let month = 0; month < 4; month++) {
    await api(request, 'POST', `${BASE}/advance`);
    const people = await api<unknown[]>(request, 'GET', `${BASE}/people`);
    if (people.length > BUILDERS) break;
    const candidates = await api<Candidate[]>(request, 'GET', `${BASE}/recruitment/candidates`);
    for (const c of candidates.slice(0, BUILDERS + 1 - people.length)) {
      if (!c.candidacy || c.candidacy.pending_offer) continue;
      await api(request, 'POST', `${BASE}/recruitment/candidates/${c.person_id}/interview`);
      await api(request, 'POST', `${BASE}/recruitment/candidates/${c.person_id}/offer`, {
        salary_cents: Math.round(c.candidacy.salary_expectation_cents * 1.5),
        equity_bp: 0,
      });
    }
  }
  await api(request, 'POST', `${BASE}/advance`); // the last offers resolve
  const people = await api<unknown[]>(request, 'GET', `${BASE}/people`);
  expect(people.length, 'founder and engineers').toBeGreaterThan(BUILDERS);
}

async function openProduct(page: Page) {
  await page.goto(`/game/${SAVE}/products`);
  await page.getByTestId('product-row').filter({ hasText: 'Pipeline' }).getByRole('link').click();
  await expect(page.getByTestId('product-name')).toHaveText('Pipeline');
}

/** New customers in a segment's row, e.g. "+42" -> 42. */
async function newCustomers(page: Page, segment: string): Promise<number> {
  const row = page.getByTestId('segment-row').filter({ hasText: segment });
  const text = (await row.getByTestId('segment-new').innerText()).replace(/[+,]/g, '');
  return Number(text);
}

test('(a) create a product, assign the company, Continue until it can launch, launch', async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  await staffUp(request);
  await page.goto(`/game/${SAVE}/products`);
  await expect(page.getByTestId('product-row')).toHaveCount(0);

  // A product in development can be cancelled after a confirm (M3b.0).
  await page.getByTestId('new-product').click();
  await page.getByTestId('new-product-name').fill('Sentinel');
  await page.getByTestId('product-category').selectOption('cybersecurity');
  await page.getByTestId('segment-smb').check();
  await page.getByTestId('create-product').click();
  await expect(page.getByTestId('product-name')).toHaveText('Sentinel');
  await page.getByTestId('cancel-development').click();
  await expect(page.getByTestId('cancel-confirm-text')).toContainText('cannot be undone');
  await page.getByTestId('cancel-confirm').click();
  await expect(page).toHaveURL(/\/products$/);
  await expect(page.getByTestId('product-row')).toHaveCount(0);

  await page.getByTestId('new-product').click();
  const dialog = page.getByTestId('new-product-dialog');
  await expect(dialog).toContainText('Self-serve: brand brings customers');
  await expect(page.getByTestId('create-product')).toBeDisabled();
  await page.getByTestId('new-product-name').fill('Pipeline');
  await page.getByTestId('segment-smb').check();
  await expect(page.getByTestId('create-product')).toHaveText('Create · 4 energy');
  await page.getByTestId('create-product').click();

  await expect(page.getByTestId('product-name')).toHaveText('Pipeline');
  await expect(page.getByTestId('product-status')).toHaveText('In development');
  await expect(page.getByTestId('launch')).toBeDisabled();
  await expect(page.getByTestId('launch-missing')).toContainText('a price for SMB');
  await expect(page.getByTestId('no-team')).toBeVisible();

  await page.getByTestId('assign-unit').click();
  await page.getByTestId('assign-confirm').click();
  await expect(page.getByTestId('assigned-unit')).toContainText('Product Co');
  await expect(page.getByTestId('team-builders').getByRole('link')).toHaveCount(BUILDERS + 1);

  await page.getByTestId('price-input-smb').fill('40');
  await expect(page.getByTestId('price-preview')).toContainText('Set the SMB price to $40?');
  await expect(page.getByTestId('preview-price-score')).toHaveText('63'); // 50 x $50 / $40
  await page.getByTestId('set-price').click();
  await expect(page.getByTestId('price-preview')).toBeHidden();
  await expect(page.getByTestId('launch-missing')).not.toContainText('a price for SMB');

  for (let month = 0; month < MAX_MONTHS; month++) {
    if (await page.getByTestId('launch').isEnabled()) break;
    await continueMonth(page);
  }
  await expect(page.getByTestId('launch-missing')).toHaveText('Ready to launch.');
  await page.getByTestId('launch').click();
  await expect(page.getByTestId('product-status')).toHaveText(/^Live/);
  await expect(page.getByTestId('sunset')).toBeVisible();

  // The launch note reaches the inbox under the Products filter.
  await page.keyboard.press('1');
  await page.getByRole('button', { name: 'Products', exact: true }).click();
  const note = page.getByTestId('inbox-item').filter({ hasText: 'Pipeline' }).first();
  await expect(note).toContainText('Product');
  await note.click();
  await expect(page.getByTestId('view-product')).toBeVisible();
});

test('(b) change a price, see the preview, Continue, and see new customers change', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await openProduct(page);
  await continueMonth(page); // first customers
  await continueMonth(page);
  await expect(page.getByTestId('segment-row')).toContainText('SMB');
  await expect.poll(() => newCustomers(page, 'SMB')).toBeGreaterThan(0);
  const before = await newCustomers(page, 'SMB');

  const input = page.getByTestId('price-input-smb');
  await expect(input).toHaveValue('40');
  await input.fill('25');
  await expect(input).toBeFocused(); // typing never loses the box
  const preview = page.getByTestId('price-preview');
  await expect(preview).toContainText('Change the SMB price to $25?');
  await expect(page.getByTestId('preview-price-score')).toHaveText('63 → 100');
  await expect(page.getByTestId('preview-appeal')).toContainText('→');
  await expect(page.getByTestId('preview-revenue')).toHaveText('−37.5%');
  await page.getByTestId('set-price').click();
  await expect(preview).toBeHidden();
  await expect(input).toHaveValue('25');

  await continueMonth(page);
  // The product refetches after the new month shows; wait for its numbers to arrive.
  await expect
    .poll(() => newCustomers(page, 'SMB'), { message: `new SMB customers were ${before}` })
    .not.toBe(before);
  await expect(page.getByTestId('market-link')).toBeVisible();
  await page.getByTestId('market-link').click();
  await expect(
    page.getByTestId('market-smb').getByTestId('market-row').filter({ hasText: 'Pipeline' }),
  ).toContainText('Product Co (you)');
});

test('(c) sunset a product after confirming', async ({ page }) => {
  await openProduct(page);
  await page.getByTestId('sunset').click();
  await expect(page.getByTestId('sunset-confirm-text')).toContainText('cannot be undone');
  await page.getByTestId('sunset-confirm').click();
  await expect(page.getByTestId('product-status')).toHaveText('Sunset');
  await expect(page.getByTestId('sunset')).toBeHidden();
  await page.goto(`/game/${SAVE}/products`);
  await expect(
    page.getByTestId('product-row').filter({ hasText: 'Pipeline' }).getByTestId('product-status'),
  ).toHaveText('Sunset');
});
