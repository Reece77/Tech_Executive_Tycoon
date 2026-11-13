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

- [ ] Each of the seven findings has a regression test that fails on `m23a-done` and passes on this branch.
- [ ] No mutation succeeds through the API while a critical event is open, except the allowed list (HTTP tests).
- [ ] No float in any money path the findings name (test; a grep check in CI if one fits the existing lint).
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m23r-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
