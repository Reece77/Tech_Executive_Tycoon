# Codex QA review 6 — m23a-done

Reviewed `main` at `m23a-done`, commit `ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42`, against `m22-done`, commit `2fc5f6d859f52ead370ee9e20feb64a936b4ee96`.

Supplied inline to preserve the read-only instruction. No repository files were edited, committed or pushed. Earlier findings, recorded balance misses, balance tuning and unbuilt M27a–M29 briefs are excluded.

1. **P2 — Repeated mine rebuilds double-count inherited depletion**

   Location: [mining/actions.py:563](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/mining/actions.py#L563).

   **Wrong:** A replacement mine inherits the sum of every closed mine’s `ore_mined_mt`. Each replacement already includes its predecessors’ depletion, so subsequent rebuilds count that inherited amount again.

   **Breaks:** Formulas §35.2–§35.3: production consumes the deposit’s finite reserves once. This is a new regression in review 5’s fix, rather than the former reserve-restoration defect.

   **Reproduction:** Using `m19.miner(..., 7)` and its copper mine, set cumulative extraction to 1 Mt, close and rebuild. The replacement correctly starts at 1 Mt. Advance that cumulative counter to 2 Mt, close and rebuild again. Production initializes the third mine at **3 Mt**, although only **2 Mt** was consumed. Repeated rebuilds increasingly erase remaining reserves and advance depletion accounting.

   **Fix/test:** Persist cumulative depletion on the deposit/project, or distinguish each mine’s lifetime extraction from inherited depletion. Add three-or-more-lifetime tests, including reload between rebuilds, asserting total extracted plus remaining ore equals the original deposit. The new tests cover only the first rebuild and therefore miss this regression.

2. **P2 — Subsidiary fabs disappear from the interface and reject management actions**

   Locations: [api/fab_views.py:258](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/api/fab_views.py#L258), [fabs/actions.py:292](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/fabs/actions.py#L292), and [actions/facilities.py:80](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/actions/facilities.py#L80).

   **Wrong:** Building for another group company and transferring fabs are supported, but `/fabs` filters to `state.player.id`. Upgrade and staffing actions likewise require ownership by the founder’s operating company.

   **Breaks:** ADR-0020 §1–§2; formulas §31.1 and §38.2; M23a’s shared group-ownership integration. A correctly transferred fab continues incurring costs while becoming inaccessible through its management screen.

   **Reproduction:** Build the 2016 28 nm fixture fab, found subsidiary 41 and transfer the fab through `TransferAsset`. Facility and fab ownership both become 41, but `fabs_out(...).fabs` becomes empty. Founder-issued `StaffFacility(..., None)` and `UpgradeFab(...)` both fail.

   **Fix/test:** Scope fab views to the group or selected entity. Authorize founder management of group-owned fabs and charge the actual owner. Add API tests for a directly subsidiary-built fab and a transferred fab: visibility, staffing, conversion, sale and cold reload. The transfer regression currently verifies ownership and subsequent postings, but never exercises these management paths.

3. **P2 — Fab transfers leave foundry-contract liabilities with the former owner**

   Locations: [group/assets.py:89](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/group/assets.py#L89) and [contracts/termination.py:202](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/contracts/termination.py#L202).

   **Wrong:** `move_facility` moves the fab record but leaves its `FoundryContract.company_id` unchanged. Deliveries and revenue follow the fab’s current owner, while termination quotes and payments follow the contract’s stale owner.

   **Breaks:** ADR-0003’s faithful per-entity books; ADR-0020 §1; formulas §35.1’s ownership transfer and M23a’s contract-termination rules. Minority profit and cash attribution can consequently be wrong even though each posting balances.

   **Reproduction:** Sign a 24-month, 3,000-start foundry contract on company 1’s fab, then transfer the fab to subsidiary 41. Observed owners were **facility 41, fab 41, contract 1**. The termination quote also identified **company 1** as payer.

   **Fix/test:** Define and implement contract assignment during facility transfer, updating attached foundry contracts consistently. Test delivery revenue and termination fees before and after transfer, with minorities and a cold reload. Existing ownership tests inspect facility/fab/refinery records without attached foundry contracts.

4. **P2 — Setting aside a critical event does not make the save read-only through the API**

   Locations: [frontend/lib/setAside.ts:55](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/frontend/src/lib/setAside.ts#L55) and [db/repository.py:968](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/db/repository.py#L968).

   **Wrong:** Read-only enforcement exists solely in the JavaScript client. Ordinary API actions proceed while a critical event remains open. Another client or tab can bypass the guard.

   **Breaks:** M23c’s acceptance criterion: “A critical event can be set aside to browse read-only and answered later.” Decision 2 explicitly documents client-only enforcement; that implementation does not establish a server-side read-only boundary.

   **Reproduction:** Create `e2e_m19_save.crash`. With critical `mine_price_crash` event 5 still open, POST `/api/saves/crash/mines/{id}/safety` with `{"safety":"high"}`. It returns **200**, and GET confirms the changed safety setting. POST `/advance` still returns **409**.

   **Fix/test:** Enforce the required restriction at the server’s common mutation boundary, with explicit exceptions for answering the event and permitted browsing operations. Add direct HTTP tests proving rejected actions leave state, energy, ledger and decision log unchanged. Frontend allowlist tests cannot catch this bypass.

5. **P2 — New foundry-contract revenue uses binary floating-point money**

   Locations: [fabs/foundry.py:148](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/fabs/foundry.py#L148) and [fabs/plants.py:374](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/sim/fabs/plants.py#L374).

   **Wrong:** Delivered starts multiply a floating-point cents price and accumulate into floating-point revenue before rounding. The newly added path bypasses the exact-money machinery.

   **Breaks:** CLAUDE.md §2.3 and §8; ADR-0003; M23a sub-task 3’s exact-arithmetic requirement.

   **Reproduction:** Sign an accepted contract for 100 starts at **0.545 cents/start**. Settle a 10,000-start month with 9,900 starts consumed internally, leaving exactly 100 contracted starts and no spot sales. Production posts **55 cents** of foundry revenue. Exact arithmetic gives 54.5 cents, which rounds half-even to **54 cents**. The incorrect entry still balances.

   **Fix/test:** Store fractional prices as integer millicents or exact rationals, retain exact monetary arithmetic through aggregation, and round once at posting. Add rational-reference half-cent tests through `settle_fabs`, including mixed contracted/spot revenue. Current foundry tests check postings against the engine’s own calculated month revenue.

6. **P2 — Commodity planning drops completed own supply through a turn mismatch**

   Location: [api/commodity_plan_views.py:70](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/api/commodity_plan_views.py#L70).

   **Wrong:** `_own_supply` requires `lot.turn == state.turn`. After a completed turn, production and settled supply retain the completed month’s number, while `state.turn` points to the next month. Demand is calculated from completed production, but its corresponding own supply is discarded.

   **Breaks:** ADR-0014 §2’s turn convention; M23c sub-task 6’s requirement to show how much own supply covers projected commodity requirements.

   **Reproduction:** Advancing the wafer practice save produced state turn **97** with a settled own-supply lot dated **96**. The planner excludes it. A controlled completed-month lot of **100 units of copper**, fully taken, likewise makes `_own_supply(state, "copper")` return **0**. A corresponding commodity plan therefore overstates the purchasing gap.

   **Fix/test:** Select the completed production/supply month consistently, using group and buyer scope appropriate to the plan. Test a real refinery supplying a commodity used by a group product, then read the planner after advance and reload. Assert nonzero own cover and an independently calculated gap. The existing planning test checks demand and contract cover without asserting own-supply cover.

7. **P3 — Mine NPV Explain displays logarithmic capex as dollars**

   Location: [advisor/v3.py:80](https://github.com/Reece77/Tech_Executive_Tycoon/blob/ecb0e27ea54db1e742bc0b674ff93a6a7cacaf42/backend/tst/advisor/v3.py#L80).

   **Wrong:** `project.capex_center` is a logarithmic dollar estimate. Explain multiplies it directly by 100 instead of exponentiating it before converting to cents.

   **Breaks:** Formulas §34.2’s feasibility estimates; M23c sub-task 7’s Explain requirement.

   **Reproduction:** In the mining fixture, Exploration shows midpoint capex of **$302,536,142.93**. Explain’s “Capex estimate (mid)” returns **1,952.771 cents**, displaying approximately **$19.53**.

   **Fix/test:** Reuse the public estimate conversion, `exp(capex_center) × 100`, with the normal monetary rounding policy. Assert Explain’s capex item agrees with Exploration’s public midpoint. The existing test checks the NPV values but never checks this item.

## Review-5 fix verification

These are verification results, not repeated findings.

| Prior # | Assessment of fix and regression |
|---|---|
| 1 | Original record-ownership defect fixed. Tests check owners, crew, postings and reload; they would catch stale fab/refinery ownership. New management and contract gaps are findings 2–3 above. |
| 2 | First rebuild preserves depletion and avoids repeated capitalization. Tests catch the original restoration, but miss repeated inheritance; finding 1 above. |
| 3 | NCI now reads profit before intercompany elimination. Independent upstream/downstream, multilevel property assertions catch the original −16-versus-4 error. |
| 4 | Subsidiary refinery incidents reach the player and resolve on the affected entity. The test requires event presentation, closure and subsidiary-only payment. |
| 5 | Own-fab and mixed-origin tariff cases now have independent positive expected amounts; they catch the former missing-origin result. |
| 6 | Fixed costs follow lifecycle rather than staffing. The unstaffed test independently requires a positive expense; conversion treatment is also tested. |
| 7 | Settled materials feed fairness and trailing values. Tests distinguish the former counter reset and exercise correction to market. |
| 8 | Listing and appeal use stable company identities. Tests change allocation IDs while retaining identity and compare outcomes across seeds. |
| 9 | Unarrived-node quotes use public planning economics. Differential seed tests catch the original quote leak. |
| 10 | The reported prepayment multiplication is repaired and its half-cent regression catches the old rounding. Its mocked monetary input does not certify the entire money audit; the new foundry defect remains above. |
| 11 | Salary is converted to monthly income before tax. The annual-total helper test catches the original twelvefold payment. |
| 12 | The property requires positive tariff postings in applicable cases and derives expectations independently. A deliberate zero-tariff mutation was executed and caught. |

## Verification and limits

- **194 focused tests passed:** 92 integration/accounting/regression tests; 57 v3 API and practice-save tests; 45 purity, RNG, schema and rollback checks.
- Inspected v3 API views and schemas, including exploration/mining truths, refinery/fab economics, group valuations, founder risks and investing information. No additional hidden-value leak was confirmed in those checks.
- No new unbalanced-entry or partial-turn-transaction defect was confirmed. The wrong-entity and exactness defects above can preserve ledger balance.
- No full `make check`, frontend/browser suite, long campaign or balance-suite pass is claimed.
- Final checkout remained clean at the reviewed commit.

**Count by severity: P1: 0 · P2: 6 · P3: 1 · Total: 7.**
## Resolution (product manager, 2026-11-12)

No P1. All seven findings go to **M23r** (`docs/tasks/M23r-review-6-fixes.md`), a small fix milestone that runs now beside M23b and merges before M27a and M28 start.

| # | Severity | Finding | Goes to |
| --- | --- | --- | --- |
| 1 | P2 | Repeated mine rebuilds double-count inherited depletion | M23r sub-task 1 |
| 2 | P2 | Subsidiary fabs disappear from the interface and reject management | M23r sub-task 2 |
| 3 | P2 | Fab transfers leave foundry contracts with the former owner | M23r sub-task 3 |
| 4 | P2 | Setting a critical event aside is read-only only in the browser | M23r sub-task 4 (reverses M23c decision 2: the server enforces it) |
| 5 | P2 | Foundry-contract revenue uses floating-point money | M23r sub-task 5 |
| 6 | P2 | Commodity planning drops completed own supply (turn mismatch) | M23r sub-task 6 |
| 7 | P3 | Mine NPV Explain shows log capex as dollars | M23r sub-task 7 |

### Fixed in M23r (2026-11-13)

Each regression test was written first and seen failing before its fix. Against `m23a-done`, 10 of the 12 new tests fail, at least one per finding. The two that pass there are guards: `test_the_front_ends_read_only_allowlist_follows_the_servers` (the client and server lists agree) and `test_mixed_contracted_and_spot_revenue_matches_a_rational_reference` (float happens to match on that case; the half-cent test is finding 5's failing one).

1. **Fixed.** A project keeps its own cumulative depletion and capitalised spend (`Project.depleted_mt`, `Project.capitalized_cents`; older saves fall back to their closed mines' totals). Test: `tests/unit/test_m23r_review6.py::test_repeated_rebuilds_deplete_the_deposit_once` (three lifetimes, a reload between rebuilds; also `test_a_subsidiarys_mine_counts_the_crew_the_founder_gives_it`).
2. **Fixed.** The Fabs view lists every fab in the player's group with its owning company. The founder staffs, upgrades and sells any group fab, mine or refinery, and its owner pays or is paid (`group.assets.managed_facility`, `staff_unit`). Tests: `tests/integration/test_api_m23r.py::test_a_subsidiarys_fabs_are_visible_and_managed` and `tests/unit/test_m23r_review6.py::test_the_founder_staffs_and_sells_a_subsidiarys_refinery`.
3. **Fixed.** `move_facility` gives a fab's foundry contracts to its new owner. Test: `tests/unit/test_m23r_review6.py::test_a_transferred_fabs_foundry_contracts_are_its_new_owners` (deliveries, revenue and termination fee before and after, minority holders, a cold reload).
4. **Fixed.** `repository.run_action` refuses every action while a critical event is open, except `choose_event` on it (`ReadOnlyError`, code `read_only`, HTTP 409). Tests: `tests/integration/test_api_m23r.py::test_a_critical_event_makes_every_action_read_only_through_the_api` and `test_the_front_ends_read_only_allowlist_follows_the_servers`.
5. **Fixed.** A foundry contract's price is integer millicents (`FoundryContract.price_millicents`; a legacy `price_cents` converts on load). Revenue is an exact `Fraction` through `settle_fabs`, rounded half-even once. Tests: `tests/unit/test_m23r_review6.py::test_a_half_cent_of_contracted_revenue_rounds_half_even_once`, `test_mixed_contracted_and_spot_revenue_matches_a_rational_reference` and `test_no_float_in_the_foundry_money_path`.
6. **Fixed.** The planner counts the completed month's lots (`turn - 1`) sold to the plan's company by any group seller. Test: `tests/integration/test_api_m23r.py::test_the_planner_counts_a_group_refinerys_supply_after_continue`.
7. **Fixed.** Explain's capex is `round(exp(capex_center) × 100)` cents, Exploration's public midpoint. Test: `tests/integration/test_api_m23r.py::test_explains_capex_estimate_is_explorations_public_midpoint`.
