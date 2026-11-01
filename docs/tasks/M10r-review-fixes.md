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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
