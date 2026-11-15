# M36r: Codex review 7 fixes, and a money-exactness guard

**Goal:** fix the five findings of Codex review 7 (no P1), each with the regression test the finding asks for, written first and seen failing. End the recurring float-money defect with an audit and a guard.

**Review:** `docs/reviews/codex-review-7.md` · **Formulas:** §31, §40.2, §40.7, §40.12, §44.1, §44.4, §45.6 · **ADRs:** 0003, 0020, 0021 · **Depends on:** M36 (`m36-done`), M30 (`m30-done`) · **Lane:** a fix lane beside M32, M33 and M34

## Lane

- Its own session and branch (`m36r-review7`) from `main`. Merges whenever ready, **before M32** (which merges last).
- **M36r owns** the files the findings name: `tst/sim/automation/run.py`, `scope.py` and `limits.py`; `tst/sim/contracts/termination.py`; `tst/sim/platforms/fees.py`; `tst/sim/finance/consolidation.py`; `tst/sim/family/estate.py`; and, for sub-task 2's audit, any money formula elsewhere in `tst/sim/` (small, separate commits per module, named in the PR).
- **Coordinate:** M34 may touch `platforms/` for duty hooks (fee-rule rows and forced settings). Keep `fees.py` changes to the money arithmetic and the group-pair classification, and merge `main` often. M32 and M33 own `power/` and `equipment/`. If the audit finds a float in their new code before they merge, leave a note in their PRs instead of editing.
- **Golden snapshots** may move by a cent where rounding was wrong. If so, regenerate with the reason in CHANGELOG, and show which values changed.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each; regression test first, seen failing)

1. **Never-actions stay the founder's** (finding 1). When an approved proposal of kind `set_grey_route` or `terminate_contract` is carried out, the actor is always the founder, inside a subsidiary too. Record the required actor on the proposal and enforce it centrally. Keep the runner's direct refusal.
   - **Tests:** end-to-end approval inside a subsidiary for both kinds:
     - the proposal reaches the player;
     - approving acts as the founder and changes the subsidiary's record and books once;
     - declining changes nothing;
     - a cold reload keeps the result;
     - the decision log never names a delegate for either kind.
2. **Exact money everywhere** (findings 2 and 3, and the pattern):
   - Automation commitments come from the same integer-cent quote that creates the deal, with rates applied by `money.times` and fractions rounded half-even once.
   - Platform fees use exact fractions for `paid_share`, user shares and fee rates, aggregated exactly and rounded once.
   - **Audit:** list every place in `tst/sim/` where a money amount is multiplied or divided by a float (a table in Decisions made: module, line, fixed or proven exact) and fix each.
   - **Guard:** a test that scans `tst/sim/` for money-typed arithmetic with float literals or float-typed rates outside `money.py`'s helpers. An AST check is preferred to a grep. It fails CI on a new occurrence, with an explicit allow-list comment for any proven-exact case.
   - **Tests:** Codex's two boundary regressions (commitment equal to the quote's obligation, and cost equal to the limit always making a proposal; the 1,750 × 0.4 × 0.7 × 0.15 fee case through `fees_due` and `fee_entries`). Add rational-reference property tests for commodity contracts, offtakes and platform fees that compute the expected cents independently.
3. **Group OS licences eliminate** (finding 4): own-OS licence fees between group companies post intercompany sales and purchases, as app-store fees do.
   - **Tests:** a property or integration test for subsidiary, parent and sister-company licences: every entity balances, cash moves between the right entities, the consolidated platform-fee lines net correctly, and a reload is identical.
4. **The estate pays what it owes** (finding 5): settlement realises every taxable asset in the quote in a defined order (personal cash, then family office, public holdings, angel stakes at their exit or secondary value, then company shares), or carries a real estate-tax payable that reduces what passes to the heir. Record only actual payments, and make the displayed cumulative tax equal the postings.
   - **Tests:** table-driven or property cases where the estate is mostly the family office, public holdings or angel stakes. Check against independent sums: tax paid equals the quote; gross estate equals tax plus net inheritance; no value disappears; and a cold reload agrees.
   - Remove the existing property's acceptance of `paid = min(tax, cash + share proceeds)`. It encoded the gap; say so in Decisions made.
5. **Close-out:** a Resolution line per finding in `codex-review-7.md` (fixed, with the test's name), CHANGELOG, and the README index row.

## Acceptance criteria

- [ ] Each of the five findings has a regression test that fails on `m30-done` and passes on this branch.
- [ ] No delegate is ever the actor of a grey route or a contract termination, approved or not (property test over random proposals and subsidiaries).
- [ ] The float-money guard runs in CI and passes, and the audit table is complete.
- [ ] Every entity's books balance and consolidation eliminates every intra-group platform payment (property tests).
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m36r-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
