# M10r: Fixes from Codex review 2

**Goal:** fix the six findings of the second outside review (`docs/reviews/codex-review-2.md`, Codex, at `m9-done`) before the balance checkpoint and the M11/M12a lanes.

**ADRs:** 0003, 0004 · **Formulas:** §14.1, §18.1, §19.2, §19.5, §20.3 · **Depends on:** M9 (`m9-done`)

## Context

The product manager triaged the review on 2026-11-01 and confirmed each finding in the code at `m9-done`. All six are in scope. None is P1. Codex could not run the suite, so each fix comes with the regression test the finding asks for, written first and seen failing.

## Out of scope

Balance tuning (the recorded misses stay for the checkpoint), new features, refactors beyond what a fix needs.

## Sub-tasks (commit after each; regression test first)

1. **Lender fees counted as operating** (finding 1, P2). The debt history (`_debt_history`) must take the month's operating profit from account classification of the whole month's ledger (§14.1: interest sits below operating profit), not from the cash-flow total. Keep the burn calculation (M8r finding 7) separate.
   - **Regression:** a waiver fee paid by answering the lender event before Continue, followed by Continue. Neither bank-loan eligibility nor the profit covenant history may see the fee as operating.
2. **Division reports include interest** (finding 2, P2).
   - **Fix:** interest (and any other below-operating account) is excluded from division operating columns and from the shared-services allocation. If shown at all, it appears below operating profit.
   - **Property test:** extend reconciliation to interest, office rent and division-tagged payroll and product costs. The division report's company operating profit must equal the real company P&L's operating profit, not only its own total.
3. **Closing an office moves inheriting teams to HQ** (finding 3, P2).
   - **Fix:** `close_office` finds the office's effective occupants before detaching the lease, including child units that inherit it. Non-HQ occupants become remote in that city; child units with their own office keep it.
   - **Regression:** a department in Berlin with a child team that inherits it and has an explicit office policy. After closing, the team is remote in Berlin, not in San Francisco.
4. **Product totals leave out overseas sales** (finding 4, P2).
   - **Fix:** current product MRR, customers and hosting, and portfolio customer counts, include live regional segments. Series that stay home-only by decision (product history) are labelled "home region" in the API and UI.
   - **Regression:** a product with only European customers shows its customers, MRR and hosting, and the portfolio's totals agree with company totals at the same point in the month.
5. **Regional prices use float ratios** (finding 5, P2).
   - **Fix:** `relative_row`'s price ratio and the rival price paths (`startups.py`, `decisions.py`) convert the original decimal indexes and personality factors to exact fractions, then round half-to-even once. The size ratio may stay a float; it isn't money.
   - **Regressions:** an East Asia HQ pricing 5,000 cents into South and Southeast Asia gives 2,188; a cost-leader AI startup entering Europe at 45 cents gives 32. Also a property test over all region pairs and personality factors against exact arithmetic.
6. **The repayment test can skip** (finding 6, P3). The 36-month schedule test uses a fixture with enough ledger-backed cash and controlled covenant conditions to reach full repayment, and asserts that it does, with no skip. Bankruptcy and loan calls keep their own tests.
7. **Close-out:**
   - CHANGELOG and durations.
   - A "Resolution" section appended to `docs/reviews/codex-review-2.md`, listing each finding, its fix commit and its test.
   - Golden snapshots regenerated only if a fix moves them, with the reason in CHANGELOG.
   - Re-run the nightly guards once, alone. Recorded misses stay recorded; any guard that passed at `m9-done` must still pass.

## Acceptance criteria

- [ ] Each of the six findings has a regression test that failed before its fix and passes after.
- [ ] Division reports reconcile with the real company P&L, with interest and rent present (property test).
- [ ] No guard that passed at `m9-done` fails.
- [ ] `make check` green (recorded xfails unchanged); `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m10r-done`.

## Decisions made

- **Finding 1, a second prior.** `advance_turn` takes `prior_operating` next to M8r's `prior_flow`: the operating result (P&L by account) of the entries the month posted before Continue. The repository (`month_operating_so_far`, sharing one ledger query with `month_flow_so_far`) and the balance runner (from its own action lines) both pass it. `_debt_history` adds it to the turn's own operating result; burn still uses `prior_flow`, unchanged. The waiver fee is still cash out, so it still counts in burn (M8r finding 7's definition: net cash before financing).
- **Finding 2, left out rather than shown below.** Interest and tax (`7xxx`, `8xxx`, the P&L's own prefixes) appear in no division column and in no allocation (`divisions.is_below_operating`). The division screen shows operating figures only, so no below-the-line row was added; the Finance P&L shows interest.
- **Finding 3.** Occupants are the active units whose effective office (`unit_office_id`) is the closed one, found before anything is detached. At a non-HQ office, a unit assigned to it goes remote with no office (as before), and an inheriting child with its own policy goes remote too; an inheriting child with no policy inherits its parent's new remote policy. At an HQ office, inheriting children follow their parent to flexible HQ space (same city), unchanged.
- **Finding 4, every regional segment, as the engine books them.** Current product MRR, customers and hosting add all regional segments, matching phase 5's revenue and phase 6's hosting (`product_costs`), which also take every regional segment; a region still localizing has no customers, so this equals "live regional segments". `ProductOut` gains `sells_abroad`, `series_scope` ("home_region") and `series_label` ("Home region"); the schema descriptions say which fields are home-only. The UI adds "(home region)" to the MRR and customer tile notes and the Products trend column, and "· Home region" to the Last 12 months panel, only once a product sells abroad (at home only, the series are the whole product).
- **Finding 5.** `geo.formulas.price_ratio` divides the two decimal price indexes as Fractions; `regional_price_cents` takes an optional personality factor (exact) and rounds half-to-even once. `relative_row`'s price index is now the float nearest that exact ratio (0.4375, not 0.43749999999999994) for appeal and the regional reference price in the Market view; sizes stay floats. Rival entry into the home region (`enter_region` for an abroad-only product) keeps v1's `round(p_ref × factor)` (see Follow-ups).
- **Finding 6.** The schedule test adds a ledger-backed $100M owner's reserve (a balanced CASH/COMMON_EQUITY entry), asserts no game end, no breach and an active-or-repaid loan every month, then full repayment. Seen failing with a temporary plugin that ends the game after one turn ("the game ended in month 1"), where the old test skipped.

- **Verification at close.** `make check` on this 4-core container: lint, types and 1,081 backend tests passed (all 1,067 non-nightly tests, golden snapshots included, and the nightly guards), with the 8 recorded xfails and 2 XPASS. Two timing checks missed inside that fully parallel run: the product turn budget (1.05 s against 1.0 s; passes alone) and S2. `make check-api` (in sync) and `make check-frontend` (lint, types, 124 tests) pass. No golden snapshot moved. The nightly guards run once, alone (`make nightly`): 15 passed, the same 8 recorded xfails, T3 blitzscale and M8 support XPASS, as at `m9-done` (Codex measured T2 steady 8 / frugal 2 and T3 5/10; the same here). S2 read 67.4 worker-minutes there, with the other nightly tests on four cores, and 16.9 with the balance runner alone (`make balance`; band < 20 on CI), as M8r recorded. `make e2e`: 45 passed (`PLAYWRIGHT_CHROMIUM_PATH` set to the container's Chromium). `tests/durations.json` refreshed (1,067 tests, 10m10s with -n auto).

## Follow-ups

- **Rival entry into the home region keeps v1's float price** (`rivals.decisions.enter_region`'s home branch and v1's own `enter_segment`: `round(p_ref × factor)`). Making it exact would move v1 rivals' prices at half-cent cases and so the home-region replay and goldens; left for a deliberate change.
- **Product history stays home-only** (M9's decision): trends, new and lost, and the 12-month chart now say "home region" once a product sells abroad. Regional history (`product_month` by region) would let them cover the whole product.
- **The division screen shows operating figures only.** Interest is visible on the Finance P&L; a below-the-line row on the company column could be added if the division screen should reach net result.
