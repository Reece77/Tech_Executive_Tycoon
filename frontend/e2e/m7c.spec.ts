import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

// M7c flows: (a) answer an event, follow its History link and see its card with the choice
// taken; (b) a deep link to an inbox message opens it; (c) fire someone and open their
// Former employee profile from History; (d) the People table fits at 1440 x 900. Saves come from tools/e2e_event_save.py.
test.describe.configure({ mode: 'serial' });

const stamp = Date.now();

function makeSave(name: string) {
  const saveDir = process.env.TST_E2E_SAVE_DIR;
  if (!saveDir) throw new Error('playwright.config.ts sets TST_E2E_SAVE_DIR');
  execFileSync(
    'uv',
    ['run', '--project', 'backend', 'python', 'tools/e2e_event_save.py', saveDir, name],
    { cwd: resolve(process.cwd(), '..'), stdio: 'inherit', shell: process.platform === 'win32' },
  );
}

test('(a) follow a History event link and see the event card', async ({ page }) => {
  const save = `m7c-event-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/inbox`);
  await page.getByTestId('inbox-item').filter({ hasText: 'has gone quiet' }).click();
  const card = page.getByTestId('event-card');
  await card.locator('[data-choice="B"]').click();
  await expect(card.getByTestId('event-answered')).toHaveText('You chose B.');
  await page.goto(`/game/${save}/history/timeline`);
  await page.getByTestId('history-event-link').first().click();
  await expect(page).toHaveURL(/\/inbox\/\d+$/);
  await expect(page.getByTestId('event-card')).toBeVisible();
  await expect(page.getByTestId('event-card').getByTestId('event-answered')).toHaveText(
    'You chose B.',
  );
});

test('(b) a deep link opens that message', async ({ page }) => {
  const save = `m7c-deep-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/inbox`);
  const last = page.getByTestId('inbox-item').last();
  const title = (await last.textContent()) ?? '';
  await last.click();
  await expect(page).toHaveURL(/\/inbox\/\d+$/);
  const url = page.url();
  await page.goto(`/game/${save}/overview`);
  await page.goto(url);
  await expect(page.getByTestId('message-title')).not.toHaveText('');
  expect(title).toContain((await page.getByTestId('message-title').textContent()) ?? '-');
});

test('(c) a former employee opens a read-only profile from History', async ({ page }) => {
  const save = `m7c-former-${stamp}`;
  makeSave(save);
  await page.goto(`/game/${save}/people`);
  await page.getByTestId('person-row').nth(1).getByRole('link').first().click(); // not the founder
  const name = (await page.getByTestId('profile-name').textContent()) ?? '';
  await page.getByTestId('fire').click();
  await page.getByTestId('fire-confirm').click();
  await expect(page).toHaveURL(/\/people$/);
  await page.goto(`/game/${save}/history/timeline`);
  await page.getByTestId('history-person-link').filter({ hasText: name }).first().click();
  await expect(page.getByTestId('former-badge')).toHaveText('Former employee');
  await expect(page.getByTestId('profile-name')).toHaveText(name);
  await expect(page.getByTestId('former-summary')).toContainText('Let go');
});

test('(d) the People table fits at 1440 x 900 without scrolling sideways', async ({ page }) => {
  // Playtest bug: Top skills on one line pushed Status out of view at 1440 wide.
  const save = `m7c-layout-${stamp}`;
  makeSave(save);
  await page.setViewportSize({ width: 1440, height: 900 });
  // The widest top-three seen in the playtest, on every row, so the check needs no luck.
  await page.route(/\/api\/saves\/[^/]+\/people$/, async (route) => {
    const people = (await (await route.fetch()).json()) as {
      skills: { label: string; short_label: string; range: number[] }[];
    }[];
    const wide = ['Judging talent', 'Negotiation', 'Software eng'];
    for (const p of people) {
      p.skills.forEach((s, i) => {
        if (i < 3) Object.assign(s, { label: wide[i], short_label: wide[i], range: [15, 20] });
        else s.range = [1, 5];
      });
    }
    await route.fulfill({ json: people });
  });
  await page.goto(`/game/${save}/people`);
  await expect(page.getByTestId('person-row').nth(3)).toBeVisible();
  const wrap = page.locator('.tst-table-wrap').first();
  const { scroll, client } = await wrap.evaluate((el) => ({
    scroll: el.scrollWidth,
    client: el.clientWidth,
  }));
  expect(scroll).toBeLessThanOrEqual(client + 1);
});

test('(e) twelve months of statements fit at 1440 x 900', async ({ page }) => {
  // Playtest bug: the latest month was cut off at the right of the P&L.
  const save = `m7c-pnl-${stamp}`;
  makeSave(save);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route(/\/finance\/statements\?period=month/, async (route) => {
    const out = (await (await route.fetch()).json()) as {
      periods: { label: string; first_turn: number; last_turn: number }[];
    };
    const last = out.periods[out.periods.length - 1];
    // Every amount × 40: a company the size of the playtest's in late 2011 ($130k a month).
    const scale = (v: unknown, key = ''): unknown => {
      if (typeof v === 'number') return key.endsWith('_cents') ? v * 40 : v;
      if (Array.isArray(v)) return v.map((x) => scale(x, key));
      if (v && typeof v === 'object') {
        return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, scale(x, k)]));
      }
      return v;
    };
    out.periods = Array.from({ length: 12 }, (_, i) => ({
      ...(scale(last) as typeof last),
      label: `${['Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'][i]} 2011`,
      first_turn: i,
      last_turn: i,
    }));
    await route.fulfill({ json: out });
  });
  await page.goto(`/game/${save}/finance/statements`);
  await expect(page.getByTestId('pnl-net').nth(11)).toBeVisible();
  const wrap = page.locator('.tst-table-wrap').first();
  const { scroll, client } = await wrap.evaluate((el) => ({
    scroll: el.scrollWidth,
    client: el.clientWidth,
  }));
  expect(scroll).toBeLessThanOrEqual(client + 1);
});
