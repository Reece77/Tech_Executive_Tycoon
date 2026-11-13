# M23r: Codex review 6 fixes

**Goal:** fix the seven findings of Codex review 6 (no P1), each with the regression test the finding asks for, written first and seen failing, before v3.5's rule milestones (M27a, M28) start.

**Review:** `docs/reviews/codex-review-6.md` · **Formulas:** §31, §33, §34.2, §35, §38 · **ADRs:** 0003, 0014, 0020 · **Depends on:** M23a (`m23a-done`) · **Lane:** a fix lane beside M23b (balance) and M29 (onboarding)

## Lane

- Its own session and branch (`m23r-review6`). Merges whenever ready, ideally before M23b, so M23b tunes on the fixed code; if M23b merges first, M23r re-runs M23b's v3 targets on the combined code and reports any that leave their bands (rule 2).
- **M23r owns** the files the findings name: `tst/sim/mining/actions.py`, `tst/sim/fabs/` (`actions.py`, `foundry.py`, `plants.py`), `tst/sim/actions/facilities.py`, `tst/sim/group/assets.py`, `tst/sim/contracts/termination.py`, `tst/api/fab_views.py`, `tst/api/commodity_plan_views.py`, `tst/advisor/v3.py`, `tst/db/repository.py` and the API's mutation routing for sub-task 4, and `frontend/src/lib/setAside.ts`.
- **M23r must not edit** `tst/balance/`, `balance.yaml` (M23b's), or M29's shell, navigation, Overview and inbox. If M29 has merged, rule 8 lets you fix integration bugs in its files.
- **Golden snapshots** should not change. If one does (finding 5's rounding can move a cent), regenerate with the reason in CHANGELOG.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each; regression test first, seen failing)

1. **Depletion across lifetimes** (finding 1): keep cumulative depletion and capitalised exploration on the project or deposit, not summed from closed mines. **Test:** three or more lifetimes with a reload between rebuilds; extracted plus remaining always equals the original deposit, and exploration is capitalised once.
2. **Group fabs are manageable** (finding 2): the Fabs view covers every fab in the player's group (with the owning company shown); staffing, upgrade, conversion and sale are allowed on any group fab and charge its owner. **Test:** API tests for a fab built by a subsidiary and one transferred to it: visible, staffable, convertible, saleable, and correct after a cold reload. Apply the same check to mines and refineries and fix any matching gap.
3. **Contracts move with the facility** (finding 3): transferring a facility assigns its attached foundry contracts (and any other facility-bound contracts) to the new owner. **Test:** deliveries, revenue and termination fees before and after transfer, with minority holders and a cold reload.
4. **Read-only enforced by the server** (finding 4; reverses M23c decision 2): while a critical event is open, the server refuses every mutation except answering that event and the explicitly allowed operations (settings, saving and reading), with a domain error the API maps to 409. **Test:** direct HTTP tests that a refused action leaves state, energy, the ledger and the decision log unchanged; the front end's allowlist follows the server's.
5. **Exact foundry money** (finding 5): fractional prices as integer millicents or exact rationals (as `money.exact`), exact through aggregation, rounded once at posting (half-even). **Test:** a rational-reference half-cent case through `settle_fabs`, with mixed contracted and spot revenue.
6. **Planning counts own supply** (finding 6): the planner reads the completed month's supply consistently with its demand (ADR-0014 §2), at group and buyer scope. **Test:** a real refinery supplying a commodity a group product uses; after advance and reload, own cover is non-zero and the gap matches an independent calculation.
7. **Explain's capex** (finding 7): convert the log estimate as Exploration does (`exp(capex_center) × 100`, normal rounding). **Test:** Explain's capex equals Exploration's public midpoint.
8. **Close-out:** a Resolution line per finding in `codex-review-6.md` (fixed, with the test's name); CHANGELOG; README index row.

## Acceptance criteria

- [x] Each of the seven findings has a regression test that fails on `m23a-done` and passes on this branch.
- [x] No mutation succeeds through the API while a critical event is open, except the allowed list (HTTP tests).
- [x] No float in any money path the findings name (test; a grep check in CI if one fits the existing lint).
- [x] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m23r-done`.

## Decisions made

1. **Depletion lives on the project** (sub-task 1). `Project.depleted_mt` and `Project.capitalized_cents` hold the deposit's cumulative history, updated when a mine closes and when one is built. An older save without them falls back to the closed mines' totals (`max` of the two), so nothing double-counts. Stored in the project's existing JSON record, so there is no migration.
2. **Staffing with another group company's team moves the team** (sub-task 2; extends M23a decision 1, "a facility's crew moves with it"). When the founder staffs a group facility with a unit of another group company, that unit and its active people move to the facility's owner, so the owner pays the crew it counts (`group.assets.crew_to`). Without this, a fab a subsidiary built could never be staffed: subsidiaries have no hiring screen.
3. **A fab's process level stays its owner's research** (sub-task 2). Upgrading a subsidiary's fab needs that company's process research, as before. The test gives the subsidiary its own research lead. Group-wide process research is a follow-up.
4. **Read only whenever a critical event is open** (sub-task 4). The server cannot know whether the player set the event aside, so it refuses every game action while any critical event is open, except `choose_event` on one of those events. Writes that are not game actions stay allowed: inbox marks, Explain and the COO's ask, previews, settings (including M29's onboarding and unlock marks), saves and backups. The error is `ReadOnlyError`, a subclass of `CriticalEventOpenError` with code `read_only`, so the existing 409 mapping covers it. The check sits in `repository.run_action`, the one door every API action uses. Holiday already refused a critical event. Two existing tests acted with a critical event open, as the browser had stopped a player from doing: the golden harness now answers critical events at the start of each month as well as before Continue (all golden snapshots unchanged), and `test_api_screens.py::test_people_fields_and_fire` answers "Payroll is at risk" before firing (every assertion unchanged).
5. **Foundry prices are integer millicents** (sub-task 5). `FoundryContract.price_millicents: int` replaces `price_cents: float`. A legacy record's `price_cents` converts on load (`geopolitics_io._upgraded`), so no migration. Contracted revenue is a `Fraction` added to the exact spot revenue and rounded once (half-even) in `settle_fabs`. Golden snapshots unchanged.
6. **The planner reads the completed month** (sub-task 6). Own supply counts lots with `turn == state.turn - 1` (the month the demand comes from, ADR-0014 §2) sold to the plan's company by any company in the player's group.
7. **"No float" is a unit test, not a CI grep.** No existing lint rule fits a type check on named fields, so `test_no_float_in_the_foundry_money_path` asserts the contract's money fields are `int` and the delivered revenue is a `Fraction`.
8. **Failures that also fail on a clean `main` (rule 3).** Run on this machine at `main` 24bad29 and on this branch:

   | Test | `main` | branch |
   | --- | --- | --- |
   | `test_m22_balance.py::test_39_4_targets` (target 7, `m22.target_7()`) | False | False |
   | `test_option_invariants.py::test_holdings_sum_to_fd` (Hypothesis deadline) | fails | fails |
   | `make check-timing` | 3 of 6 over budget (mna integrate, org, product) | 3 of 6 over budget (hiring, mna integrate, product) |

   Target 7 is nightly and belongs to M23b's balance lane (`tst/balance/`, which this lane must not edit). The turn-time budgets miss by a similar margin on both, with a different set each run: this machine (the repo is on OneDrive) is slower than CI, where `check` was green on `main`. CI's `check` on this branch is the measure.
9. **Every finding has a test that fails on `m23a-done`.** 10 of the 12 new tests fail there. The two that pass are guards: the allowlist agreement test, and the mixed contracted and spot reference, where float happens to give the right cent (the half-cent test is finding 5's failing one).

## Follow-ups

- Group-wide process research: let a subsidiary's fab use the parent's process level, or share research across the group (decision 3).
- M22 target 7 misses on `main` too (decision 8): M23b or the next balance pass should find what M22's data changes in a software-only run.
- The front end could show the server's `read_only` 409 as the set-aside banner, not as an error toast, if a click slips through the client's allowlist.
