# M3a: Products and markets (rules, API, CLI)

**Goal:** the player can create a product, put org units on it, launch it into a market of 2010 incumbents, set prices and marketing, and earn revenue that responds to price, quality, features and brand, all through the API and the command line, fully tested. Screens come in M3b.

**Spec sections:** §3, §7, §9, §10 · **ADRs:** 0002, 0003, 0006, 0010, 0013, 0014, 0017 · **Formulas:** `docs/formulas.md` §11 (all), plus the M3 rows in §6 and §12 · **Depends on:** M2 (`m2b-done`)

## Context

M1 and M2 built a company of people with an org chart but no revenue: cash only goes down. M3 closes the loop. Units from the org chart are assigned to products; their builders raise quality and features, sellers and marketers bring customers; customers pay every month and churn when a better product appears. The other products in each market belong to incumbents (Salesforce, Atlassian, Facebook, Symantec and others) whose scores are fixed until rivals get AI in M5 (ADR-0017).

`docs/formulas.md` §11 is authoritative for every rule and number. Category, segment and incumbent values are data (`categories.yaml`, `incumbents.yaml`); tunables are in `balance.yaml` (§12).

## Out of scope

Rival AI, rival people and rival ledgers (M5). Bankruptcy and financing (M4): cash may still go negative. Regions (one global market per segment), the technology tree and R&D projects (v2), beta stage, tech debt, crunch and bugs, shared services, executive seats and decision latency. The `politician` tag's effect (M6). Product screens (M3b).

## Rules (summary of `docs/formulas.md` §11)

1. **Four categories** (B2B SaaS, developer tools, consumer apps, cybersecurity), each with segments (consumer, SMB, mid-market, enterprise) holding addressable customers, a reference price, a hosting cost and market growth.
2. **Products** are created in development, launched once quality ≥ 25 and feature score ≥ 30, and can be sunset. Prices are set per segment; marketing budgets per product.
3. **Units work on products.** A unit (including the company root) is assigned to at most one product; its builders produce output from a category-weighted development skill, morale, tags, a coordination cost and noise. Sellers give sales capacity for mid-market and enterprise; marketers and budget build brand.
4. **Quality** climbs toward a cap set by the builders' output-weighted skill; **features** accumulate against a rising market expectation.
5. **Appeal** per segment weighs quality, price, brand and features. Each month, churned and newly adopting customers are in play; products win them by `appeal³` against an outside option, limited by awareness (self-serve segments) or sales capacity (sales segments).
6. **Revenue** is booked monthly; hosting and marketing are costs. ARR gates stages 2 and 3.
7. **Founder scouting:** the founder can scout a search for 20 energy (the M2b follow-up).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `categories.yaml` (§11.1 tables and §11.3 skill weights, validated: weights sum to 1, segments known), `incumbents.yaml` (§11.9), `product_function` on every role in `roles.yaml`, all §12 M3 keys in `balance.yaml`. Every §11.14 worked example as a unit test (noise off).
2. **State and persistence:** `product` (company, category, name, status, quality, feature points, brand, marketing budget cents, created and launched turns), `product_segment` (product, segment, price cents, customers), `org_unit.product_id`, `market_segment` (category, segment, addressable customers), `product_month` history (per product and segment per turn: quality, feature score, brand, appeal, customers, new, churned, revenue cents), `next_ids` for products. Incumbent companies and products are created at new game (turn 0); older saves get them on upgrade, with addressable demand grown to the save's turn. Migration `0008_products`; data dictionary.
3. **Development (phase 3):** builders, output, `Q_cap`, quality, features, rot, tag effects (§11.3, §11.4, §11.10), stream `product_dev` (id 15) added to `STREAM_IDS` and ADR-0013's table (already listed there). Property tests: quality and brand stay in [0, 100]; output is never negative; a product with no units only loses quality.
4. **Market (phases 5, 6, 9, 10):** appeal, churn, in play, choice, awareness and sales capacity, customers (§11.6, §11.7), stream `market` (id 4); revenue, hosting and marketing ledger entries (§11.8); brand and demand growth (§11.5, §11.1); ARR stage gates (§11.11); MRR and ARR in `turn_snapshot`. Property tests: customers never negative; in each segment total customers never exceed addressable demand; every ledger entry balances.
5. **Actions** (ADR-0014) with energy per §6: `create_product`, `set_price`, `add_segment`, `assign_unit`, `unassign_unit`, `set_marketing`, `launch_product`, `sunset_product`, and `scout_search` for the founder (§11.12). Validation errors for every rule in §11.2 and §11.3 (for example, launch before the thresholds, a unit already assigned, a price of zero).
6. **Inbox:** product launched; first paying customer; ARR passing $100k, $1M and $10M; a sales-capacity note when capacity limited a segment ("Sales capacity limited new customers in Enterprise"); a product's quality falling because nobody works on it.
7. **API** (save-scoped): categories and segments with addressable demand; markets (every product in a category: owner, public scores, appeal and customers per segment, share of served customers); the player's products (as above plus prices, budget, assigned units, builders, sellers and marketers by name, development pace label, 12-month history); product actions with a launch-readiness check (what is still missing); a price preview (appeal and share* at the new price against current competitors, without customer numbers); company MRR and ARR. Extend the hidden-field test: no response contains `Q_cap`, `d_i`, `o_i`, capacity numbers or per-person contributions (§11.13).
8. **CLI:** `tst products`, `tst product create|show|price|segment|assign|unassign|marketing|launch|sunset`, `tst market --category`, `tst scout --search`.
9. **Golden and balance checks:**
   - Golden script: around turn 2 the root is assigned to a B2B SaaS product (SMB and mid-market); launch when allowed; an account executive and a marketer hired by turn 12; one price cut at turn 18. Regenerate snapshots with a CHANGELOG note (MRR and ARR join the snapshot).
   - **Incumbent equilibrium:** with no player product, each incumbent's share of its segment's served customers moves by at most 5 points over the first 24 turns. If not, adjust only the starting shares in `incumbents.yaml` until it holds, and record the changes under Decisions made.
   - **Earn-and-burn band** (printed): a `funded_spinout` script with the founder, 3 builders, 1 account executive and 1 marketer ($10,000 a month marketing) on one B2B SaaS product reaches its first revenue by turn 10 and an ARR between $500,000 and $4M at turn 36 (the formulas.md §11.14 design check expects about $2.6M). If it falls outside the band, report the numbers and the likely cause; do not tune to it silently.

## Acceptance criteria

- [ ] Every §11.14 worked example passes as a test.
- [ ] A product can be created, staffed by a unit, launched and sunset through the API and the CLI; launch is refused below the thresholds, with the missing items named.
- [ ] **Share responds to price and quality:** on the same seed, a 20% lower price, or 10 more quality points, gives more new customers in the following month than the baseline (two comparative tests).
- [ ] Revenue, hosting and marketing post balanced ledger entries; MRR and ARR appear in snapshots; a company reaching $1M ARR enters stage 2.
- [ ] Sales capacity limits mid-market and enterprise wins, and the inbox says so; awareness limits self-serve wins.
- [ ] Incumbent equilibrium holds (with any starting-share changes recorded).
- [ ] The earn-and-burn run is printed, with its numbers recorded under Decisions made.
- [ ] The founder can scout a search for 20 energy.
- [ ] Replay reproduces a save with products, price changes and assignments.
- [ ] No API response leaks a hidden field or a §11.13 forbidden value (exact-name test).
- [ ] 120 turns with 25 staff, 3 products and all incumbents average under 1 second per turn (printed).
- [ ] `make check` green; golden snapshots regenerated with a CHANGELOG note.

## Manual check (Reece, command line, optional)

1. Start a `funded_spinout` game; hire three engineers; `tst product create` a B2B SaaS product for SMB; `tst product assign` the company root to it.
2. Advance until `tst product show` says it can launch; launch it at $40 a month.
3. Advance 12 months; compare `tst market --category b2b_saas` against Salesforce and Zoho; try a price change and watch new customers the next month.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
