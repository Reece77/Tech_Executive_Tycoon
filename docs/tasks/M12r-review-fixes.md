# M12r: Fixes from Codex review 3

**Goal:** fix the findings of the third outside review (`docs/reviews/codex-review-3.md`, Codex, at `m12a-done`) that M12b does not take, before M14.

**ADRs:** 0003, 0007, 0020 · **Formulas:** §21.3, §21.6, §21.7, §21.10, §22.5, §22.6, §22.9 · **Depends on:** M12b and M13 (`m12b-done`, `m13-done`)

## Context

The product manager triaged the review on 2026-11-03 and confirmed each finding against the source at `m12a-done`. There is no P1. **Finding 7** (compute consumers treat every facility kind as a data centre) went to the running M12b session, because M12b adds the first non-compute kind (assembly plants) and would hit it at once; check that its fix and contract test are on `main` and only finish it if they are not. The rest wait here so the two running lanes are not disturbed. Codex could not run the suite, so each fix comes with the regression test the finding asks for, written first and seen failing.

## Out of scope

Balance tuning, new features, refactors beyond what a fix needs. Subsidiary gameplay (finding 8 only prepares the signatures; v3 builds it).

## Sub-tasks (commit after each; regression test first)

1. **Licence errors reveal a rival's true lead** (finding 1, P2).
   - **Fix:** the licence-in action validates points against the same ceiling the Research screen shows, derived only from what the observer can see (the displayed range's low end, §21.10), and accepts whole points only. Check the ceiling, then cash, then energy, with error wording that depends only on public values. A request that the public ceiling allows but the true limit doesn't (impossible if the ceiling is the range's low end minus the margin; assert it) must never occur.
   - **Regression:** Codex's bisection (32 failed calls narrowing IBM's planted 23.4567) can no longer narrow the lead below the displayed range. Plus a differential test: two rivals whose true leads differ but whose displayed ranges are the same give byte-identical responses to the same failed, unaffordable and fractional requests, through the HTTP route.
2. **Research estimates carry hidden executive effects** (finding 2, P2).
   - **Fix:** build the displayed lab with estimated executive modifiers (`modifiers(..., estimate=True)`, §18.8) from the start, rather than rescaling a true output.
   - **Regression:** byte equality of `/research` responses for two saves whose CTO and COO differ only in true skills (same displayed ranges), covering `gain_per_month` and `months_to_era`. Add `/research` to the executive non-interference test.
3. **Future component rows can become current** (finding 3, P2).
   - **Fix:** `_load_facilities` loads only played supply months (turn ≤ the save's last played turn); the history query in `routers/facilities.py` gets an upper bound; the view and the quote and contract path enforce the cutoff themselves, independently of what was loaded.
   - **Regression:** a persistence-level test that writes a future `supply_month` row (turn 230 at save turn 210) and checks that no API response, quote or contract uses or shows it. Rewrite `test_no_future_index_after_2025` so it plants the row instead of searching for a rounded value.
4. **Overseas Cloud customers escape outage churn** (finding 4, P2).
   - **Fix:** the Cloud branch of `apply_outages` also applies the extra churn to the Cloud product's regional segments, with complete loss accounting, and the outage event targets the segment with the largest loss.
   - **Regression:** a foreign-only Cloud product (100 European SMB customers, 6 lost at multiplier 3 and base churn 0.03) and a mixed home and foreign product.
5. **Rival research skips the last month's premium** (finding 5, P2).
   - **Fix:** keep the larger builder pool through the final month's payroll and restore it at the start of the next month (or carry the premium as a separate cost line); every project month pays it.
   - **Regression:** extend `test_research_licensing.py` to charge payroll each month: six monthly premiums of 10% of the pool, and their sum.
6. **AI research budgets round binary floats** (finding 6, P2).
   - **Fix:** `researcher_cost_cents` converts the budget and the AI index to exact fractions (the money helper from M10r finding 5), multiplies, and rounds half-to-even once.
   - **Regression:** 600,000 cents at index 0.5000075 gives 300,004 (was 300,005), plus a property test against `Fraction` arithmetic.
7. **Per-company research and infrastructure views** (finding 8, P3).
   - **Fix:** the research and infrastructure view builders take a `company_id`; routes resolve the single UI company at the boundary. `era_news` uses `player_companies(state)` for who hears the news, and names the causing company separately from the observer.
   - **Test:** two-company builder tests (a second company with its own project and data centre gets its own view), with no subsidiary gameplay.
8. **Data dictionary interleaved on merge** (finding 9, P3).
   - **Fix:** one unbroken column table per heading for `research_project`, `research_license`, `facility_outage`, `supply_contract` and the rest of the M11 and M12a tables; the facility migration heading reads `0029_facilities`.
   - **Check:** every column, type and nullability listed against migrations 0028 and 0029 and the ORM models (a short script is fine; note it in Decisions made).
9. **Close-out:**
   - CHANGELOG and durations.
   - A "Resolution" section appended to `docs/reviews/codex-review-3.md`, listing each finding, its fix commit and its test (finding 7 points to M12b's commit).
   - Golden snapshots regenerated only if a fix moves them, with the reason in CHANGELOG.
   - Re-run the nightly guards once, alone. Recorded misses and the T2 xfail stay; any guard that passed at `m12b-done` must still pass.

## Acceptance criteria

- [ ] Each finding has a regression test that failed before its fix and passes after (finding 7: M12b's, confirmed on `main`).
- [ ] No API response distinguishes two rivals with the same displayed lead range, or two executives with the same displayed skills, on `/research` (differential tests).
- [ ] No API response, quote or contract uses a supply row after the last played month (planted-row test).
- [ ] No guard that passed at `m12b-done` fails.
- [ ] `make check` green; `make e2e` passes; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m12r-done`.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
