# Codex QA review 4 — m15b-done

Reviewed `Reece77/Tech_Executive_Tycoon`, read-only, on 2026-11-07.

| Reference | Verified commit |
| --- | --- |
| Target: `m15b-done` | `756b435df42397ffe180c8a2c3542ea4dc681239` |
| Baseline: `m12b-done` | `787f5d9d760e7b0f0095fd754d33f041c3778ab4` |
| Target tree | `9fe62ff2460d18118e8dfe7b527cff0cd60e0632` |

The clone succeeded after enabling sandboxed network access. Review used an archive extracted from the target tag, not the newer current main. All **1,013 tracked blobs** in that archive were checked against their Git blob SHA-1s: **zero mismatches**. No repository source was edited, and no commits or pushes were made. Harnesses, temporary saves and this report were kept outside the source tree.

Read CLAUDE.md, the ADR index and ADRs 0002–0005, 0013 (including the stable-identity amendment), 0015, 0019 and 0020; formulas §25–§30 and their build notes; the M12r, M13, M13b, M14, M14b and M15b briefs; the prior review findings/resolutions; the relevant dictionary and balance exceptions. Resolved findings from reviews 1–3 and recorded balance misses/xfails are excluded below. The dictionary finding concerns the separate 0030/0031 blocks, not review 3's repaired 0028/0029 blocks.

**Result: nine P2 findings and two P3 findings. No P1 confirmed.** References below link to the exact reviewed commit. Numerical reproductions use production functions unless explicitly described as source tracing.

## Findings

### 1. P2 — Continuing after a sale gives the buyer a company without paying for it

**Location:** [backend/tst/sim/mna/exit.py:41](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/mna/exit.py#L41), especially the return at line 66; [backend/tst/sim/modes/serial.py:140](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/modes/serial.py#L140).

**What is wrong:** `sell_company` records an all-cash, closed deal but returns only state and logs. It neither posts the buyer's cash consideration nor records its investment/goodwill. `found_again` subsequently makes the sold company the buyer's brand and posts fresh cash to the new venture from the purported sale proceeds. It never settles the acquisition or creates its `Acquisition` record. This becomes an ongoing economic defect now that M15b lets the world continue after an exit.

**Breaks:** CLAUDE.md §2.3; ADR-0003; formulas §28.3's closing postings; M15b addendum 10's sold company becoming an operating brand with its own books.

**Concrete scenario/evidence:** Built the existing IPO fixture, executed the production sale and `FoundAgain`, then inspected the database ledger. The recorded sale price was **81,776,471,406 cents**. The buyer's cash was **771,078,228,183 cents both before and after** founding again. The new venture nevertheless received **48,657,000,000 cents**, and the old company had the buyer as `parent_id`. No acquisition record existed for that sale. The buyer thus retains the purchase money while receiving a brand whose later cash can sweep to it.

**Suggested fix:** Settle the sale once through a shared brand-closing path, including balanced buyer consideration, investment/goodwill and acquisition metadata. Fund an unaffordable buyer explicitly or refuse the transaction; do not silently omit the payment. Keep the seller's own cash intact for a share sale. Add a sell → found-again → advance → cold-reload test that reconciles the buyer, brand and new venture ledgers and prevents double settlement.

### 2. P2 — A failed brand disappears from past consolidation and can unbalance the group

**Location:** [backend/tst/sim/state.py:631](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/state.py#L631), consumed by [backend/tst/api/routers/finance.py:75](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/api/routers/finance.py#L75); investment elimination in [backend/tst/sim/finance/consolidation.py:53](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/finance/consolidation.py#L53).

**What is wrong:** Finance selects only brands that are alive **now**, then uses that selection to rebuild every historical period. When a brand fails, its opening assets and all subsequent revenue, costs and cash vanish from past consolidated statements. If another brand survives, consolidation still removes the parent's entire 1810 investment account, including the investment in the omitted brand, without its corresponding net assets.

**Breaks:** ADR-0003's reconciling statements; ADR-0004's preserved history; formulas §28.5/§28.11's consolidation of brands from closing.

**Concrete scenario/evidence:** Ran the production group selector and consolidation functions with balanced parent books and two brands acquired at turn 2. Parent funding was 3,000 cents; total purchase consideration 1,200; investments 800; goodwill 400; each brand brought 400 cash. Before failure, the turn-2 consolidated sheet was **assets 3,000 = liabilities/equity 3,000**. Marking one brand failed at turn 4 changed that same historical turn-2 sheet to **assets 2,600 versus liabilities/equity 3,000**, with consolidated lines summing to **−400**. No historical ledger line changed.

**Suggested fix:** Select consolidation membership by ownership dates for each reporting period, retaining failed entities' historical contributions. Represent any terminal loss/disposal with explicit accounting instead of dropping the company from all periods. Test two brands, one failure, and unchanged prior statements, including both cash sweeps and parent funding.

### 3. P2 — Serial exits create nested groups that ownership and antitrust helpers split apart

**Location:** [backend/tst/sim/mna/antitrust.py:43](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/mna/antitrust.py#L43), [backend/tst/sim/state.py:627](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/state.py#L627), and [backend/tst/sim/modes/serial.py:142](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/modes/serial.py#L142).

**What is wrong:** `owner_of` follows only one parent, while `group_companies` includes only direct children. M15b can already create deeper ownership: sell a player company that owns kept brands, then found again. Its brands retain their parent, while the sold company becomes another buyer's brand. Grandchildren then count under the intermediate company, outside the actual controlling group. Buying a company that owns brands causes the same shape.

**Breaks:** ADR-0020 §1 and §4; formulas §28.4's group share test and §28.5's consolidation. This is reachable through shipped serial-founder behavior, not a request to implement future M16 gameplay.

**Concrete scenario/evidence:** Constructed the resulting ownership chain using existing company records: root **4** owns former player **1**, which owns brands **2 and 3**. Production `group_companies(state, 4)` returned **[4, 1]**, excluding both grandchildren. `owner_of(state, 2)` returned **1**, not 4. Their customers therefore enter a separate ownership bucket in antitrust, understating the controlling group's share. Acquiring that root can also leave the grandchildren out of the player's consolidated statements.

**Suggested fix:** Resolve ultimate ownership and group membership through a deterministic, cycle-checked traversal shared by antitrust and finance. Consolidate each subsidiary once, eliminating intercompany investments at every level. Add a sale of a parent-with-brands and a subsequent acquisition test, asserting group customer shares and consolidated balances.

### 4. P2 — Delisting after a serial exit is not persisted

**Location:** [backend/tst/db/state_io.py:1394](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/db/state_io.py#L1394), activated by [backend/tst/sim/modes/serial.py:146](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/modes/serial.py#L146).

**What is wrong:** `found_again` removes the sold company's `PublicCompany` record from the new state. `_sync_public` only inserts/updates records present in the new tuple; it never deletes removed `public_company` rows. A cold load consequently resurrects the old listing. Warm cached state and persisted state disagree immediately after the committed action.

**Breaks:** ADR-0004's faithful transactional persistence; ADR-0020's per-entity listing state; M15b's explicit build decision that the sold company is delisted.

**Concrete scenario/evidence:** On a real temporary SQLite save, executed the production IPO, sale and `repository.run_action(FoundAgain(...))`. `public_of(returned_state, old_id)` was **None**. Opening a fresh session and calling `load_state` returned a **PublicCompany** for that same, now-owned brand. The full warm/cold states were unequal. The existing serial API flow continues through the cache and does not assert this cold-load invariant.

**Suggested fix:** Delete removed current-state `PublicCompanyRow` records within the action transaction while preserving append-only share-price history. Explicitly settle or end any remaining IPO/CEO state as required by the sale. Test delisting after closing/reopening the save and with `TST_STATE_CACHE_CHECK=1`.

### 5. P2 — Acquisition pitch numbers reveal a private target's hidden costs

**Location:** [backend/tst/sim/org/pitches.py:1107](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/org/pitches.py#L1107); published cases are built at line 713.

**What is wrong:** Acquisition candidates add a fraction of `deals.monthly_costs_cents` to their central case. That helper reads the target's actual workforce costs, including private employment salaries, before diligence or acquisition. The result affects candidate ordering and the pitch's disclosed central/low/high cases. Calling the quantity an estimate does not make its hidden inputs public.

**Breaks:** CLAUDE.md §8; ADR-0005 §4 when those pitch facts enter reports/prompts; formulas §27.1's displayed-knowledge-only candidate numbers and the M13b brief's same acceptance criterion. The §28.11 synergy note does not establish that private salaries are displayed knowledge.

**Concrete scenario/evidence:** Made two pre-diligence states differing only in one Zoho employee's annual salary by **12,000,000 cents**. The complete `target_out` responses were equal. Actual monthly costs changed from **398,000,000 to 399,200,000 cents**, and the acquisition candidate's central monthly case changed from **1,025,204,000 to 1,025,504,000 cents**. This difference is the configured 25% synergy share of the hidden cost difference. It survives into the published case numbers and can also change the chosen target.

**Suggested fix:** Estimate costs using explicitly public/revealed staffing and market-rate assumptions, with public rounding, or omit that synergy term until an authorized disclosure exists. Use one public estimate for ranking, wording and cases. Add a private-target non-interference test covering salaries and pools, candidate ordering, pitch responses and report/prompt facts; the current executive-skill differential does not cover this input.

### 6. P2 — Every assembly-plant pitch proposes a capacity the build action rejects

**Location:** [backend/tst/sim/org/pitches.py:571](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/org/pitches.py#L571); validation at [backend/tst/sim/actions/facilities.py:101](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/actions/facilities.py#L101).

**What is wrong:** `_plants` chooses sizes from generic compute capacities `[100, 500, 2000, 10000]`. Assembly plants override these with `[5000, 20000, 50000, 100000]`. The sets are disjoint. Approval uses the ordinary `BuildFacility` action, which correctly rejects the proposed capacity. Modify also receives that invalid capacity as its prefill.

**Breaks:** Formulas §27.1's usable COO assembly-plant pitches and approval through normal actions; §26.8's kind-specific sizes; M13b sub-task 3.

**Concrete scenario/evidence:** With a 20,000-unit/month Foxconn contract lasting 24 months, production `_plants` proposed a **10,000-unit assembly plant**. Passing its parameters to the production action raised **`FacilityRuleError: a assembly plant has 5,000, 20,000, 50,000, 100,000 units/month`**. The company had ample cash; this was the capacity validation, not affordability.

**Suggested fix:** Choose from `kind.sizes or balance.facility.sizes`, sharing the normal build quote/validation inputs. Exercise a COO plant candidate through Approve and assert that a facility is created. Also calculate its case using the documented variable assembly costs and yield rather than only fixed cost/depreciation.

### 7. P2 — Keeping a target as a brand suppresses two of its hidden problems

**Location:** [backend/tst/sim/mna/integration.py:121](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/mna/integration.py#L121), [line 679](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/mna/integration.py#L679), and `_churn_penalties` at line 385.

**What is wrong:** The brand closing branch returns before assigning product IDs or installing the customer-concentration churn penalty. Monthly product processing explicitly skips every non-integrated acquisition, so tech-debt quality losses also never run for brands. Problems are discovered and reported, but choosing Brand neutralizes these two liabilities. Key-person risk is handled separately and is not the issue here.

**Breaks:** Formulas §28.2: a target's `tech_debt` costs 10 quality over the first year after closing and `customer_concentration` multiplies churn for 12 months. Neither effect has a brand exemption; §28.11 records their durations and implementations.

**Concrete scenario/evidence:** Closed a production brand acquisition with both problems planted. The acquisition retained both problem names but had **no product IDs** and installed **no churn modifiers**. In its next month `_products` left product quality **75.0 → 75.0**. The corresponding tech-debt-only step should subtract 10/12 quality, and customer concentration should install its separate ×1.5 churn effect.

**Suggested fix:** Apply target liabilities in a mode-independent post-close path using the products' actual owning company. Keep integration-specific churn and brand blending separate. Test both problems in both modes, including all 12 affected months and expiry.

### 8. P2 — New M&A cash consideration rounds binary floating-point money

**Location:** [backend/tst/sim/mna/deals.py:624](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/mna/deals.py#L624); the same multiplication appears in offer validation at line 297, closing at `mna/closing.py:63`, and share issuance at `mna/deals.py:667`.

**What is wrong:** Cash consideration is computed as `round(price_cents * cash_share)` in binary float. Integer inputs and a final `round` do not preserve exact half-even cents. The complementary stock amount balances the entry, so a balanced-ledger test alone misses the wrong cash/stock allocation. Other new M&A price/fee helpers also multiply monetary amounts in floats.

**Breaks:** CLAUDE.md §2.3 and §8; ADR-0003. This is the new M&A path, not the resolved event-raise, regional-price or AI-research findings.

**Concrete scenario/evidence:** Executed `closing_entries` with price **100 cents**, cash share **0.545**: cash posted **55 cents**, versus **54 cents** from exact rational half-even arithmetic. The entry still summed to zero. The same defect occurs at a plausible acquisition scale: **100,000,000,100 cents × 0.545** evaluates to `54500000054.50001`, posting **54,500,000,055 cents** instead of **54,500,000,054**. The closing property test samples only 0, 0.25, 0.5 and 1 cash shares and derives its expected amount with the same float expression.

**Suggested fix:** Centralize consideration splitting with the existing `money.exact` helper or integer basis points, round once, and use the same split in validation, closing and issuance. Audit the new price/fee helpers similarly. Add independent rational-reference half-cent tests, including non-binary shares and large prices. Migration 0031's persisted `production_contract.price_cents FLOAT` is another money-rule violation in the requested audit range: fractional unit rates need an exact scaled/rational representation, not binary floating-point storage.

### 9. P2 — A serial founder's new company gets an unstable RNG identity

**Location:** [backend/tst/sim/modes/serial.py:154](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/modes/serial.py#L154); consumers include [backend/tst/sim/markets_public/ipo.py:225](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tst/sim/markets_public/ipo.py#L225) and `markets_public/public.py:139`.

**What is wrong:** The new venture takes `max(company.id) + 1` and receives no separate stable identity. IPO demand, player sentiment and other player-company streams use that database ID. Appending an unrelated incumbent or changing unrelated company allocation therefore reseeds the player's subsequent venture. Original player ID 1 was stable; this new path removes that property.

**Breaks:** ADR-0013's M12a stable-identity amendment and the M13 brief's requirement to use company data keys or IDs that cannot shift.

**Concrete scenario/evidence:** Took the same seeded exit state and appended an unrelated company without changing the sale or founder. `found_again` allocated company IDs **41 versus 42**. For the same master seed **3**, turn **60** and climate **1.0**, production IPO demand was **0.9302178473 versus 1.4180676109**. Those values even fall on opposite sides of the 1.3 threshold for raising the IPO price. The difference comes solely from allocation-dependent identity.

**Suggested fix:** Give each player venture a persisted stable key, for example a dedicated namespace plus venture ordinal, and use it for all player-company RNG consumers and any later rival fallback. Test unchanged new-venture draws after appending an unrelated incumbent, rather than merely replaying the identical database allocation twice.

### 10. P3 — The 0030/0031 dictionary blocks attach contract columns to the CEO table

**Location:** [docs/data-dictionary.md:1337](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/docs/data-dictionary.md#L1337), with the empty `production_contract` heading at line 1243 and displaced CEO rows after `production_month` near line 1380. The `departure` section at line 1553 also omits its `name` column.

**What is wrong:** The table under `ceo` lists manufacturing-contract fields such as `supplier`, `units`, `price_cents`, `delivered` and `charged_cents`. Those belong to migration 0031's `production_contract`, whose own heading has no table. The actual CEO-specific columns are appended after the production-month section. This is separate from the repaired research/facility dictionary blocks in review 3.

**Breaks:** CLAUDE.md §6's current column-level schema reference; the M13/M12b migration documentation requirements.

**Concrete scenario/evidence:** Compared all **30 `create_table` calls** across migrations 0030–0035 with the matching dictionary sections. `ceo` had seven missing actual fields and twelve unrelated contract fields; `production_contract` had all fourteen fields missing from its section; `production_month` inherited seven CEO-only fields. Migration 0033 also creates `departure.name`, absent from its dictionary table. A developer following this reference would query nonexistent CEO manufacturing columns or miss the real contract schema.

**Suggested fix:** Restore one uninterrupted table per heading, move the contract and CEO blocks to their own sections, and add `departure.name`. Validate column names, types, nullability and primary keys against each migration and ORM table. The 0034 JSON status documentation should also include `refused`, which the review-ending path writes.

### 11. P3 — Acquisition-pitch tests can pass with the claimed behavior absent

**Location:** [backend/tests/unit/test_mna_pitches.py:37](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tests/unit/test_mna_pitches.py#L37) and [line 44](https://github.com/Reece77/Tech_Executive_Tycoon/blob/756b435df42397ffe180c8a2c3542ea4dc681239/backend/tests/unit/test_mna_pitches.py#L44).

**What is wrong:** The CPO test asserts only `all(... for c in ranked)`. Its actual fixture produces **zero acquisition candidates**, so it passes without testing that a CPO can pitch an eligible startup or respects the spend ceiling. The adjacent never-auto-approve test only searches function source for an exact string; it never executes Holiday approval behavior.

**Breaks:** CLAUDE.md §6's meaningful engine tests; M14 sub-task 7 and formulas §28.7's CPO eligibility and mandatory manual acquisition approval.

**Concrete scenario/evidence:** Executing the fixture and production candidate builder returned **`len(ranked) == 0`**. Disabling CPO acquisition candidates entirely would still satisfy this assertion. Likewise, leaving the searched source string present while bypassing that guard elsewhere would not fail the auto-approval test.

**Suggested fix:** Seed an eligible, affordable startup in the CPO's market plus an incumbent and an over-limit startup; assert a nonempty result and the exact permitted targets. Execute an acquisition pitch on Holiday with its cost below the auto-approve limit, then assert that it remains pending and no deal or consideration posting was created.

## Verification and limits

- Inspected the tag-to-tag changes and the requested baseline-inclusive migrations, accounting helpers, closing/integration/funding/sweep paths, API schemas/views, prompt construction, RNG consumers, serial-founder persistence, and associated Python/React controls and tests.
- Ran direct production-function reproductions for all numerical examples above, including a real SQLite cold-load check. The nested-group and failed-brand cases deliberately construct reachable ownership/failure states; they are not claims that those exact numeric fixtures were played end-to-end through HTTP.
- A targeted pytest run reported **80 passed** before it was interrupted after **429.51 seconds**, with HTTP tests stalled in fixture startup. A separate single-test diagnostic located the wait in **Starlette `TestClient.__enter__` / AnyIO's blocking portal**, before the request or test assertion. This is recorded as a verification limitation, not a repository finding.
- Additional targeted purity/RNG, formula/mode and persistence/schema checks were launched. No full `make check`, frontend build, Playwright run or statistical balance-suite pass is claimed. The successful migration-backed temporary-save creation and direct SQL checks do not establish that every upgrade path is correct.
- The inspected ordinary deal entries and sweep/funding pairs balance; finding 8 concerns exact cash consideration despite that balance. No additional direct reservation, board-bar, tender-chance, review-draw or pre-diligence problem-field disclosure was confirmed in the inspected response builders. Leadership fit and rival CEO profile attributes read revealed ranges. Finding 5 concerns a different hidden input leaking through acquisition-pitch numbers.
- Existing transactional turn/action boundaries and pending-event recovery were inspected. No new partial-commit defect is asserted; previously resolved cache-publication and post-commit retry findings are not repeated.

All source blob hashes matched the target tag after the reproductions. The cloned repository remained clean. Only this report is the requested deliverable.
## Resolution (M15r, 2026-11-08)

Findings 1 and 4-11 were fixed on branch `m15r-fixes` (from `main` after the docs merge, PR #20). Each regression test was written first and seen failing on the unfixed code, then passing after the fix (the 0038 upgrade test, for the contract-price half of finding 8, was written alongside its migration). **Findings 2 and 3** (consolidation membership by period; nested groups split by `owner_of` and `group_companies`) belong to **M16**, which rebuilds the group model: M15r did not edit `finance/consolidation.py`, `state.group_companies` or `mna/antitrust.owner_of`. No golden snapshot moved.

| # | Finding | Fix commit | Regression test |
| --- | --- | --- | --- |
| 1 | P2 The buyer gets a company without paying | 1c7a892 | `backend/tests/integration/test_m15r_serial_exit.py::test_the_buyer_pays_once_and_every_ledger_reconciles`: on a real save, accept the bid, found again, advance two months, reload cold: one `Acquisition of Kestrel` entry for the buyer (cash out the price; 1810 the brand's book equity, the rest goodwill), the acquisition record, no entry on the seller's books, the new venture's starting cash the proceeds, every entry balanced (no acquisition entry existed before). `::test_a_buyer_that_cannot_pay_is_refused` |
| 2 | P2 A failed brand disappears from past consolidation | — | M16 |
| 3 | P2 Nested groups split by ownership helpers | — | M16 |
| 4 | P2 Delisting after a serial exit is not persisted | 1c7a892 | `test_m15r_serial_exit.py::test_the_delisting_persists` with `TST_STATE_CACHE_CHECK=1`: no `public_company` row and no serving CEO after a cold load, share-price history kept, the cold state equal to the cached one (the old listing came back, and the sold company's board seats too) |
| 5 | P2 Acquisition pitches reveal hidden costs | 66c5be1 | `backend/tests/unit/test_mna_pitches.py::test_acquisition_pitches_use_public_numbers_only`: two states differing only in one Zoho employee's salary (+$120,000) give identical candidates, pitches and pitch words |
| 6 | P2 Plant pitches propose a rejected capacity | aa50708 | `backend/tests/unit/test_m15r_plant_pitch.py`: a 20,000-unit contract pitches a 20,000-unit plant (10,000 before), its case is 26.2's cost per good unit, and approving it builds the plant |
| 7 | P2 Brands suppress hidden problems | 670054c | `backend/tests/unit/test_mna_integration.py::test_hidden_problems_apply_in_either_mode[integrate, brand]`: each of the 12 months after closing and the 13th, quality loss and churn x1.5 on the products' owner (brands had none; integration lost the 12th month of churn) |
| 8 | P2 M&A cash consideration rounds binary floats | b5314d5 | `backend/tests/unit/test_m15r_exact_money.py`: 0.545 of 100 and of 100,000,000,100 cents posts 54 and 54,500,000,054 (55 and ...055 before); issuance and the closing cash check use the same split; a Hypothesis test against `Fraction`; a reservation at 6,466,600,254,430 x 1.35. `backend/tests/integration/test_persistence.py::test_upgrade_to_0038_makes_contract_prices_exact` |
| 9 | P2 A new venture's RNG identity is unstable | 7978dc5 | `backend/tests/unit/test_serial_founder.py::test_a_new_venture_has_a_stable_identity`: an unrelated company appended before founding again moves the new venture's id (41 to 42) but none of its keys or its IPO demand, sentiment, deal and press draws (they differed before) |
| 10 | P3 Dictionary attaches contract columns to `ceo` | 3fc23b3 | `backend/tests/unit/test_data_dictionary.py`: every table migrations 0030 onward create has one section whose columns, types, nullability and keys match the ORM (it failed on `main`'s file) |
| 11 | P3 Acquisition-pitch tests pass with the behaviour absent | 914c717 | `test_mna_pitches.py::test_the_cpo_pitches_only_affordable_startups` (exactly Zoho for the CPO; Zoho, SAP and Salesforce for the CEO) and `::test_acquisitions_never_auto_approve` (runs Holiday's `pitch_month`); each fails when the CPO's candidates or the guard are removed |

Decisions and follow-ups are in `docs/tasks/M15r-review-fixes.md`.
