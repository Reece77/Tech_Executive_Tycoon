# M3b: Product screens

**Goal:** run products from the browser: create and launch them, staff them with org units, set prices and marketing, and see how they stand against the incumbents.

**Spec sections:** §7, §9, §13 · **ADRs:** 0007, 0009, 0014, 0017 · **Wireframes:** `docs/wireframes.md` (M3b screens) and `docs/wireframes/source/Products.dc.html`, `Product.dc.html`, `Market.dc.html` · **Depends on:** M3a (`m3a-done`)

## Context

M3a provides every rule, endpoint and preview. This milestone is front end only: display, sort, filter and format what the API returns; never compute a game value (`CLAUDE.md` §7). If a screen needs a value the API lacks, add it to the backend schema, regenerate the client, and record it under Decisions made.

## Out of scope

Any new rule. Finance, Competitors and History screens.

## Screens

1. **Products** (nav key 6, now live): the portfolio (name, category, status, quality, feature score, brand, customers, MRR, trend, development pace) and New product.
2. **Product profile:** score bars for quality, features, brand and appeal against each competitor in the market; per-segment table (price with edit and preview, customers, share, new and churned last month, MRR, the sales-capacity note); assigned units with Assign and Unassign; marketing budget; launch readiness (what is missing) and Launch; Sunset with a confirm; a 12-month chart of customers and MRR.
3. **Market view** (from a product or the Products screen): every product in a category by segment, owner, scores and share, incumbents included.
4. **Org additions:** each unit shows the product it works on, with Assign from the unit panel.
5. **Overview additions:** MRR and ARR tiles; revenue next to costs on the month's breakdown; the cash chart shows revenue.
6. **Recruitment:** a Scout button on each search for the founder (20 energy).
7. **Inbox:** product kinds (launch, first customer, ARR milestones, capacity notes); filters apply across all pages, not only the current 50 (M2b follow-up).

## Sub-tasks (commit after each)

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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
