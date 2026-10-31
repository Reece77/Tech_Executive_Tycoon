# M8r: Fixes from Codex review 1

**Goal:** fix the seven findings of the first outside review (`docs/reviews/codex-review-1.md`, Codex, at `m8-done`) before the two parallel lanes (M9, M10) start, so they build on a clean base.

**ADRs:** 0003, 0004, 0007, 0014 · **Formulas:** §14.1, §16.3, §18.3, §18.8 · **Depends on:** M7c (`m7c-done`)

## Context

The product manager triaged the review on 2026-10-31 and confirmed each finding in the code at `m8-done`. All seven are in scope. Codex could not run the suite, so each fix must come with the regression test the finding asks for, written first and seen failing.

## Out of scope

Balance tuning (the recorded T2 miss stays for M15), new features, refactors beyond what a fix needs.

## Sub-tasks (commit after each; regression test first)

1. **State cache published after the lock is released** (finding 1, P1). `remember` after a write must happen while the save's write lock is still held, so the remembered state is the one just committed. Alternatively, invalidate the cache and let the next read load fresh. Apply this to actions, turns, event writes and Holiday months.
   - **Regression:** a controlled two-writer interleaving in which writer A commits and pauses before publishing while writer B commits. The next read must see B's change, and no stale employment row may be merged back.
2. **Continue can return "busy" after it has committed** (finding 2, P1). Continue must never return a retryable `save_busy` once its month has committed.
   - Writing the month's pending events must happen inside the same write lock as the turn. If that's impossible, a failure after commit must return success for the committed month and leave the events pending; the next request writes them first, as it does today.
   - The front end must retry only errors raised before anything committed (the API marks which).
   - **Holiday:** a month that committed counts as done even if writing its events then fails.
   - **Regressions:** fault injection after commit for Continue and for a Holiday month. One click never plays two months.
3. **A poached executive keeps their seat** (finding 3, P2).
   - Departure cleanup (`detach_departed`) checks staff of the unit's, seat's or plan's own company. `effect_of` treats a holder employed by another company as vacant.
   - Unit leaders and hiring-plan owners get the same company check.
   - **Regression:** a score-14 CTO accepts a rival approach, serves notice and joins the rival. The seat becomes vacant with the vacancy effect, the departure note arrives, and a replacement can be appointed.
4. **The COO's true effect shows in support and layer-tax numbers** (finding 4, P2).
   - Every API number that depends on a seat holder's skill (support penalty, layer tax, coverage effects on Overview and Org, product output breakdowns) uses the **estimated** effect from displayed ranges (§18.8) and is labelled "(est.)".
   - The engine keeps using true values.
   - **Regression:** two states with identical displayed knowledge but different hidden COO skills give byte-identical API responses for Org, Overview and the product breakdown. Extend `test_api_scaleup.py` to an occupied COO, a deep division and an under-covered pool.
5. **Price preview ignores the CRO** (finding 5, P2). Current, proposed and actual-sales price scores all use the same segment's reference price with CRO pricing power. The preview of an unchanged price must equal current appeal and share exactly.
   - **Regression:** with an occupied CRO and with a vacant one.
6. **Event raises use float arithmetic** (finding 6, P2). `salary_change`, and every cash effect path in `events/formulas.py`, compute in integers or `Fraction` and round half-to-even once, at the end (ADR-0003).
   - **Regression:** a 10% raise on 5,242,895 cents gives 5,767,184. Also add a property test: event money effects equal exact rational arithmetic rounded half-to-even.
7. **Two definitions of burn** (finding 7, P3). Decision (product manager): **burn is net cash used before financing**, meaning operating plus investing cash flow, never counting investor or loan money. Change the snapshot's `monthly_burn_cents` to that, and align `formulas.md` §14.1, the breakdown text and the glossary.
   - Regenerate golden snapshots if they move, with the reason in CHANGELOG.
   - **Regression:** a month with $10,000 of operating outflow and a $100,000 SAFE stores a burn of $10,000.
8. **Close-out:** CHANGELOG, durations, and a short "Resolution" section appended to `docs/reviews/codex-review-1.md`, listing each finding, its fix commit and its test.

## Acceptance criteria

- [ ] Each of the seven findings has a regression test that failed before its fix and passes after.
- [ ] No API response differs between states that differ only in hidden values (sub-task 4 test).
- [ ] One Continue never plays two months; a committed Holiday month is always counted.
- [ ] `make check` green (T2 stays the recorded xfail); `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m8r-done`.

## Decisions made

- **Finding 1, publish or forget.** `write_session` takes a state to remember (`repository.publish(session, state, balances)`) and stamps it after the commit, while it still holds the save's lock; a write that publishes nothing removes the remembered state. `remember` is no longer called anywhere else.
- **Finding 2, one hold for the whole Continue.** `run_turn` reserves the save (the Holiday mechanism) for its turn and its event writing, unless the calling Holiday already holds it, so no other write can land between them. Everything after the commit (events, backup, index) is logged on failure, never raised: the month is played, unwritten events stay pending and the next turn writes them first (`_PendingEvents`). `ErrorOut.retryable` is true only for `save_busy` (always raised before anything commits); `retryBusy` needs it.
- **Finding 3.** Cleanup compares (company, person) pairs; `effect_of` treats a holder whose employment is at another company as vacant, so a poached holder is vacant even before the cleanup phase runs.
- **Finding 4, a flag, not a view state.** Seat effects take `estimate=True` in the API (`effect_of`, `k_coo`, `multiplier`, `side_factor`, `churn_factor`, `modifiers`, `product_team`, `team_of`, `pricing_power`); the engine's calls are unchanged. Replacing the holder's skills with displayed midpoints in a copy of the state was rejected: displayed ranges are computed from the true value, so the copy would show different ranges. With `estimate`, the product screen's appeal, churn and pace use the estimated seat effects too. "(est.)" labels the support output effect on Org and Overview and the layer-tax note.
- **Finding 6.** `money.exact` reads a float as the decimal it was written as (0.1 is 1/10), so template shares and percents mean what the YAML says; caps and clamps of cash stay Fractions until one half-to-even rounding. `effect_cap` still returns a float, for prompts and display only.
- **Finding 7, the whole month.** Actions before Continue post under the month being played (an event paid by answering it), so `advance_turn` takes `prior_flow`, the month's operating and investing cash already moved per company. The repository reads it from the ledger and the balance runner from its own actions. Both use `statements.cash_before_financing`, the cash-flow statement's own classification. The Overview tile reads the snapshot again (one number), which retires the M7c follow-up about History's burn chart.
- **Executives are paid as executives (product manager, 2026-10-31).** The fix for finding 3 exposed that appointees became exec level on their old pay, so rivals' market-rate offers took them within months. Before the fix that cost nothing, because a poached holder kept the seat. `AppointExecutive` now takes a salary: by default the exec market rate for the person's role and region (`exec_salary_cents`), never below current pay, applied at once. The 13.8 raise bonus (+3) counts once alongside the +5. The Appoint dialog shows it, editable, with current pay; the API takes `salary_cents`; `tst appoint --salary`. The strategy scripts appoint at the default. formulas.md 18.3 is updated. Tests: `test_m8r_seats.py` (the exec rate, no pay cut, a chosen salary, and an approach right after appointment reads "likely to stay", where it read "likely to go" before) and the nightly `tests/balance/test_m8r_exec_pay.py`.
- **Recorded misses (Reece's rule: xfail only what still misses after the salary fix).** T3 blitzscale succeeds 2/10 (needs 3; 3/10 before finding 3, 1/10 after it). M8 target 2 reads 1.097 (needs 1.15; 1.512, then 0.880). Both are `xfail(strict=False)` with these values. The six-month "an executive at the default salary stays" check fails on 6 of 10 real stage-3 games: at ordinary morale (about 50), a market-rate offer reads "might go" for any employee, executives included. It is a nightly `xfail(strict=False)` with that value. All three are recorded in balance-targets.md for M15.

## Follow-ups

- **M15 (v2 balance):** T3 blitzscale (2/10), M8 target 2 (1.097) and executive retention. Poaching treats an executive like any employee: a market-rate offer at ordinary morale reads "might go". Retention terms (vesting, an exec loyalty term) or executive poaching rules are design questions for Reece.
- **Test helpers that call `advance_turn` directly** (unit tests, `tests/balance_scripts.py`) pass no `prior_flow`, so their stored burn leaves out actions before the turn. Saves and the balance runner include them.
- **Product pace and builder output** still come from builders' true skills, as since M3 (a coarse word, outside this review). Only seat effects moved to estimates.
- **Property tests for finding 6** pass against the old float code at realistic sizes; the half-cent regression is the one that fails on it. They guard the exact path from here on.
