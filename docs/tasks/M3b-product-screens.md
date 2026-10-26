# M3b: Product screens

**Goal:** run products from the browser: create and launch them, staff them with org units, set prices and marketing, and see how they stand against the incumbents.

**Spec sections:** §7, §9, §13 · **ADRs:** 0007, 0009, 0014, 0017 · **Wireframes:** `docs/wireframes.md` (M3b screens) and `docs/wireframes/source/Products.dc.html`, `Product.dc.html`, `Market.dc.html` · **Depends on:** M3a (`m3a-done`)

## Context

M3a provides every rule, endpoint and preview. This milestone is front end only: display, sort, filter and format what the API returns; never compute a game value (`CLAUDE.md` §7). If a screen needs a value the API lacks, add it to the backend schema, regenerate the client, and record it under Decisions made.

## Out of scope

Any new rule beyond the backend slice. Finance, Competitors and History screens.

## Backend slice (sub-task 0)

`cancel_product` for a product in development (`docs/formulas.md` §11.2: energy 3, retires at once, frees its units), with API, CLI (`tst product cancel`) and tests. The M3a follow-up: sunsetting a product in development was refused.

Also make the M1c Playwright test "ten hires within six turns using all three channels" robust: it takes `search-row` locators once with `.all()` and clicks the n-th row's first button while the list can change, so it can wait forever on a row that no longer exists. Re-read the rows on each step (or iterate by search id) so the test never depends on the list's order or length.

## Screens

1. **Products** (nav key 6, now live): the portfolio (name, category, status, quality, feature score, brand, customers, MRR, trend, development pace) and New product.
2. **Product profile:** score bars for quality, features, brand and appeal against each competitor in the market; per-segment table (price with edit and preview, customers, share, new and churned last month, MRR, the sales-capacity note); assigned units with Assign and Unassign; marketing budget; launch readiness (what is missing) and Launch; Sunset with a confirm; a 12-month chart of customers and MRR.
3. **Market view** (from a product or the Products screen): every product in a category by segment, owner, scores and share, incumbents included.
4. **Org additions:** each unit shows the product it works on, with Assign from the unit panel.
5. **Overview additions:** MRR and ARR tiles; revenue next to costs on the month's breakdown; the cash chart shows revenue.
6. **Recruitment:** a Scout button on each search for the founder (20 energy).
7. **Inbox:** product kinds (launch, first customer, ARR milestones, capacity notes); filters apply across all pages, not only the current 50 (M2b follow-up).

## Sub-tasks (commit after each)

0. Backend slice (above).
1. Regenerate the client; shared `ScoreBar`, `SegmentTable` and `MarketTable` components with tests.
2. Products screen and New product dialog.
3. Product profile and market view.
4. Org, Overview, Recruitment and Inbox additions.
5. Playwright: (a) create a product, assign the root, Continue until launch is allowed, launch; (b) change a price, see the preview, Continue, and see new customers change; (c) sunset a product after confirming.

## Acceptance criteria

- [ ] Every M3a product action is reachable from the screens, with its preview or readiness check shown first.
- [ ] Screens match their wireframes and stay usable with 6 products and every incumbent shown.
- [ ] No game value is computed in the front end.
- [ ] `make check` green; `make e2e` passes all flows.

## Manual check (Reece)

Play a `funded_spinout` game for 24 months with one B2B SaaS product. Note whether price, quality and marketing feel like real levers, and whether incumbents feel beatable in some segment. These notes feed the balance pass and M4.

## Decisions made

- **Cancel (sub-task 0).** `cancel_product` retires the product with `retired_turn` = the current turn and frees its units through the same `release_assignments` the sunset path uses. Its route (`POST /products/{id}/cancel`) returns the energy and unread count only, since the product no longer exists. Sunsetting a product in development is refused with "cancel its development instead"; the M3a test that expected the old wording now expects the new one (the behaviour change is the brief's).
- **E2E fix (sub-task 0).** Search rows carry `data-search-id` and their select button a `select-search` test id; the ten-hires test collects ids first and re-finds each row by id, skipping one that has gone.
- **Values the screens needed, added to the API** (CLAUDE.md §7: the front end only formats):
  - Products: `price_score` per segment and per market row; last closed month's `new_last_month` and `churned_last_month` per segment and in total; total `customers`; `customer_trend` and `mrr_change` (last month end against the one before, from `product_month`); `hosting_cents` this month; `launched_label`; `brand_trend` (rising, falling or steady from the last two month ends, steady within 0.05 points; never the target brand); `counts_users`; `monthly` totals for the 12-month chart.
  - Markets: `annual_growth`, and per segment `unserved`, `reference_price_cents`, appeal `weights`, `counts_users` and `player_sells`. Categories gain the same `weights` and `counts_users`.
  - Price preview: the current price and price score, and `revenue_per_customer_change`.
  - `GET /portfolio` for the Products tiles (MRR and its change from the snapshots, ARR, stage label, business customers and consumer users apart, hosting, marketing and their total). `GET /meta/products` for energy costs and launch thresholds, so no screen hard-codes them.
  - Overview: `month_revenue_cents`, this month's revenue at today's customers and prices (the same projection as hosting). Its `mrr_cents` and `arr_cents`, and the snapshot points', are now required in the schema (always set), so the client types are not optional.
  - Org units: `product_id` and `product_name`.
  - Inbox: a repeatable `kind` query parameter filters across every page; the front end maps its People, Hiring and new Products filters to template keys (`lib/inbox.ts`), and Unread uses `unread_only`.
- **"Consumer users".** The `consumer` segment's customers are users; the API flags them with `counts_users` (the segment key is the only marker in the data).
- **ARR tile note.** The wireframe's "Passed $1M in Jan 2012" needs the month a stage was reached, which is not stored; the tile shows the stage label instead.
- **Immediate actions.** Assign, Unassign, Add segment and the marketing budget apply at once with their energy on the button, like the M1 actions: there is no preview endpoint for them and nothing to preview. Price changes open the API preview first; Launch is enabled only when the readiness check passes; Sunset and Cancel development ask to confirm.
- **Routes.** `/products`, `/products/markets/:category?` and `/products/:productId`, so the Products nav item stays highlighted on all three.
- **Price boxes keep focus.** The segment table's columns are built once per mode; the price text and the editing segment reach the cells through context (rebuilding the columns remounted the inputs on every keystroke).
- **E2E setup.** The M3b flows hire three engineers through the API (setup the tests are not about), then drive every product step through the screens. Locally the run used `PLAYWRIGHT_CHANNEL=msedge` because Playwright's Chromium is not downloaded on this machine.

## Follow-ups

- Store the turn each stage is reached (or log it), so the ARR tile can say when stage 2 arrived as the wireframe does.
- A preview for assigning a unit (the development pace it would give) would make staffing a clearer lever; it needs a rule-side preview of team output that shows only the pace label.
- The product page loads the whole category market for its competition panel; fine at v1 sizes, worth a narrower endpoint if markets grow.
- Vite on the OneDrive-synced checkout once served a stale module after an edit (fixed by restarting the dev server); if it recurs, `server.watch.usePolling` in `vite.config.ts` is the usual fix.
- Reece's manual check (24 months of `funded_spinout` with one B2B SaaS product) is still to do.
