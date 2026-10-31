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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
