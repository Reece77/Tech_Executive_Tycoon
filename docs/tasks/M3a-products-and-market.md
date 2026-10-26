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

**Incumbent starting shares (equilibrium check).** The §11.9 shares drifted up to 15 points of served customers in 24 turns (Evernote +15, Zoho SMB +15, Facebook −12, GitHub mid-market +8). Only the starting shares in `incumbents.yaml` changed: each segment keeps its §11.9 total, split in proportion to share\*/churn at the fixed scores (the steady state), rounded to 50 bp. Worst move over 24 turns: 1.14 points on seeds 1–10. New values (bp, was → now):

| Segment | Changes |
| --- | --- |
| B2B SaaS SMB | Sales Cloud 1500 → 1000, Zoho CRM 1000 → 1500 |
| B2B SaaS mid-market | Sales Cloud 3000 → 2150, CRM On Demand 1500 → 1600, Zoho CRM 1000 → 1750 |
| B2B SaaS enterprise | Sales Cloud 3000 → 3650, CRM On Demand 3000 → 2350 |
| Dev tools SMB | unchanged (JIRA 2000, GitHub 1500) |
| Dev tools mid-market | JIRA 2500 → 1800, TFS 2500 → 2000, GitHub 1000 → 2200 |
| Dev tools enterprise | JIRA 1500 → 2350, TFS 4000 → 3150 |
| Consumer | Facebook 3000 → 2450, FarmVille 1000 → 800, Evernote 500 → 1250 |
| Cybersecurity SMB | Norton 2000 → 1750, McAfee 1500 → 1750 |
| Cybersecurity mid-market | Norton 2500 → 2450, McAfee 2000 (same), Check Point 1500 → 1550 |
| Cybersecurity enterprise | Norton 2500 → 2850, McAfee 2000 → 2250, Check Point 2500 → 1900 |

**Earn-and-burn run (printed by `tests/integration/test_market_balance.py`).** Founder, 3 builders (d = 11), 1 account executive and 1 marketer on mid-level market salaries, $10,000 a month marketing, SMB $40 and mid-market $700, launched when allowed:

| Seed | Launch | First revenue | Break-even | ARR at turn 36 | Cash at turn 36 |
| --- | --- | --- | --- | --- | --- |
| 1 | 5 | 5 | 18 | $2,545,724 | $2,085,030 |
| 2 | 6 | 6 | 18 | $2,557,954 | $2,050,248 |
| 3 | 5 | 5 | 17 | $2,571,946 | $2,151,659 |

Without the marketing budget (seed 1): $1,277,633. Both are inside the band and close to the §11.14 design check ($2.6M and $1.4M, first revenue around turn 5, break-even around turn 17). Nothing was tuned to it.

**Rule readings** (formulas.md is silent or open to two readings; each is noted in code):

1. *Above Q_cap* ("falls 1% a month toward Q_cap"): Q ← max(Q_cap, 0.99 Q).
2. *Rot*: when o < 0.25σ the product loses 0.5 quality instead of climbing (the two rules do not stack); with no builders at all, Q_cap is undefined and the product rots.
3. *In play is capped* at the customers who churned plus the unserved, so demand noise can never push a segment's customers above its addressable demand (the brief's property test). It binds only in near-saturated segments.
4. *Displayed feature score* uses F_exp of the last turn whose phase 3 ran (`state.turn − 1`), as the §11.14 example does ("feature score after turn 8 … F_exp(8)"); the launch check uses the same value.
5. *Incumbent feature score* is stored on the product (`held_feature`), and phase 3 sets F = held × F_exp(t) / 100 each month. Incumbents skip development and brand updates; in the market they are ordinary products with awareness 1 and no capacity limit.
6. *Incumbents and the ledger*: companies with `is_player = false` get no payroll, overhead or snapshot rows (ADR-0017: no ledger until M5); `GameState.ledger_companies()` is the one place this is decided. This changed the M0 test that posted overhead for a second company.
7. *Sunset and retirement*: only a live product can be sunset. A sunset product retires when every segment's customers round to 0 (< 0.5); the units and root on it are freed.
8. *Segments without a price* do not sell (a segment added after launch starts selling once priced).
9. *Revenue* is booked on customers after this month's churn and wins; hosting is charged on the same customers in phase 6. Hosting and marketing are lines in the monthly-costs entry, so the Overview projection and phase 6 stay identical (`monthly_costs` now takes the game data).
10. *Inbox notes fire on the change*: "first paying customer" when a product first has ≥ 1 customer (rounded); the sales-capacity note when capacity starts binding in a segment (`product_segment.capacity_limited`); the slipping note when rot starts (`product.rotting`); the ARR note for the highest of $100k / $1M / $10M passed for the first time (`company.arr_milestone_cents`, thresholds in `balance.yaml`).
11. *Growth / Mature label*: Growth if total customers rose more than 5% a month over the last 6 months of history, Mature otherwise, "Live" with under two months of history (`products.growth_label_months`, `products.growth_label_rate`).
12. *Upgrade of older saves*: migration `0008_products` reads the current `categories.yaml` and `incumbents.yaml`, grows demand to the save's turn deterministically (no noise), and gives each incumbent its starting share of that demand. Incumbent company ids follow the highest existing id.
13. *Founder scouting* is a new action `scout_search` (search id, 20 energy from `founder.energy_cost.scout_search`) sharing the delegates' scouting pass; a closed search whose candidates are still open can be scouted.
14. *Incumbent companies* carry a stage (public companies 4, large private ones 3, GitHub and Evernote 2) and a founding year (shown as a negative `founded_turn`); neither changes a rule in M3.
15. *Golden script*: in addition to the brief's steps, the M2a "Product" team (formed at turn 6, when the script empties the root) also works on the product from turn 7. Without it, seeds 5, 6 and 8 left the founder alone and never launched.

**Engineering.** Product code lives in `tst/sim/products/` (formulas, models, team, phases, setup) and `tst/sim/actions/products.py`; API views in `tst/api/product_views.py`, routes in `tst/api/routers/products.py`. Customers are floats; money stays integer cents (`round(C × price)`).

## Follow-ups

- formulas.md §11.9's table still shows the original starting shares; update it to the tuned values above (or note that `incumbents.yaml` holds them).
- Sunsetting a product in development (cancelling it) is refused today; decide whether it should retire at once.
- The 120-turn performance run (164 ms a turn) starts with 25 staff but, like the M2a run, loses some to resignations over ten years (11 left); a fixed-headcount variant would measure the stated load more strictly.
- Sales capacity is shared in full by every sales segment (§11.3 simplification); v2 may split seller effort.
- M3b screens can show the `launch.missing` list, the capacity `note`, and `rotting` directly; the inbox front end has no badge for the five new templates yet (they fall back to "Notice").
