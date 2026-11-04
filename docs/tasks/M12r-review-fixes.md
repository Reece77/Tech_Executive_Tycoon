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
9. **Turn-time headroom** (product manager, 2026-11-03; not a Codex finding). `test_product_perf` sat at the 1.0 s limit on CI after M13 and M12b (1,069 ms on one run, a pass on the next), and M12b cut `load_people` from 206 to 160 ms to get under it. Keep the 1.0 s budget; do not loosen it.
   - **Measure:** profile a turn on the combined code and record where the time goes (load, phases, save) in Decisions made.
   - **Cut:** take the largest cost that keeps the output identical (for example loading only what changed since the cached state, or batching reveal and skill rows), proven by the state-cache check and the golden snapshots.
   - **Stabilize the measurement, not the limit:** time the turns as the median of three timed blocks after a warm-up, so one noisy stretch on a shared runner can't decide it. Target at least 25% headroom on CI (≤ 750 ms per turn).
10. **Close-out:**
   - CHANGELOG and durations.
   - A "Resolution" section appended to `docs/reviews/codex-review-3.md`, listing each finding, its fix commit and its test (finding 7 points to M12b's commit).
   - Golden snapshots regenerated only if a fix moves them, with the reason in CHANGELOG.
   - Re-run the nightly guards once, alone. Recorded misses and the T2 xfail stay; any guard that passed at `m12b-done` must still pass.

## Acceptance criteria

- [ ] Each finding has a regression test that failed before its fix and passes after (finding 7: M12b's, confirmed on `main`).
- [ ] No API response distinguishes two rivals with the same displayed lead range, or two executives with the same displayed skills, on `/research` (differential tests).
- [ ] No API response, quote or contract uses a supply row after the last played month (planted-row test).
- [ ] `test_product_perf` at or under 750 ms per turn on CI (median of three blocks), with the 1.0 s limit unchanged.
- [ ] No guard that passed at `m12b-done` fails.
- [ ] `make check` green; `make e2e` passes; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m12r-done`.

## Decisions made

- **Finding 1, both directions.** Licensing out had the same oracle (its limit used the licensee's true lead), so `license_out` gets the same treatment: the ceiling is `floor(yours - margin - high)`, `high` the displayed range's high end. The licensor's refusal ("its lead is not more than 10 points ahead of yours") reads the public ceiling too, because `why_not` on the Research screen showed it for rivals whose true gap and displayed range disagreed. Whole points are checked first (a non-finite or fractional request gets "license whole points"), then the ceiling, then cash, then energy. The API schema keeps `points: float`, so the generated client is unchanged; the engine rejects fractions. The ceiling's never-above-the-true-limit property is asserted in code and tested with Hypothesis.
- **Finding 2.** `projects.lab(..., estimate=True)` builds the displayed lab: researchers' skills from range midpoints, noticed tags only, and `modifiers(..., estimate=True)` for the seat factors. `estimates.shown_lab` is removed (nothing else used it). Morale stays true, as on the product team estimate.
- **Finding 3.** "Played" means a turn before the save's turn: phase 4 of turn t writes month t, and the save's turn is then t + 1. The loader and the history route read only `turn < state.turn`; `goods.current` ignores a month after `state.turn` (in-turn, phase 4's month equals the state's turn, so quotes inside a turn still see it); the view's cutoff is at most `state.turn - 1` after the history.
- **Finding 4.** Only the Cloud branch changes, as the brief says: own products' regional losses were already counted, and their event target stays the home segment that lost most.
- **Finding 5.** The pool stays larger through the final month's payroll and `research.rivals.month_start` returns it in phase 1 of the next month, right after the macro month, rather than a separate cost line, so no other phase changes. Golden snapshots unchanged.
- **Item 7.** View builders take the company positionally (`research_out(state, data, company_id)`, `infrastructure_out(state, data, stored, company)`, `build_preview(..., company)`); routes and the CLI pass `state.player.id`. `rivals_out` skips the viewing company itself. `era_news` takes an observer; `arrive_eras` sends one note to each company in `player_companies(state)` (one today, so logs are unchanged).
- **Item 8.** The M11 section (0028) now comes before M12a's (0029), in migration order. The facility `yield_rate` note named `0030`; it reads `0031_hardware`. The check was a short script (not committed) that parses each heading's table and compares column names and order, SQL type and nullability with `tst.db.models` and the `op.create_table` calls of 0028 and 0029: 0 mismatches across the nine tables; the facility's three extra columns come from 0031. Run on the old file, it failed at `supply_contract` (no table under its heading).
- **Item 9, measured.** Turns 60-90 of the perf test's save on this 4-core container: 418 ms a turn. The test's own full `load_state` before each turn 149 ms (`load_people` 77, `_load_geo` 20); phases 152 ms (people 57, sales and churn 37, rivals 22, market 11, payroll 9, snapshot 7, research 6); the save (`apply_turn_result`) 81 ms; events, index and backup 13 ms; the turn's own load 3 ms (the cache).
- **Item 9, cut.** The largest cost was the test's full reload of the save before every turn, which the game never pays: the screens read through `read_session` / `read_state`, which reuse the state the last write published. The test now reads the same way. `TST_STATE_CACHE_CHECK=1` (a full load compared with the cached state on every read and turn) passes for all 120 turns with the same final state. Locally the median falls to 261 ms (blocks 265, 261, 241). On CI (`check` run 41748787185, shard with the perf test, alongside the other tests on a 2-core runner): median 555 ms (blocks 555, 586, 531), 26% under the 750 ms target and 44% under the limit. No engine code changed for this, so the golden snapshots cannot move.
- **Close-out guards.** The nightly ran once on `m12r-fixes` on CI (run 41757399603, the usual five jobs, each alone on its runner): all four test shards pass, with the T2 xfail (shard 1: 6 passed, 1 xfailed); the balance table is identical to M12b's value for value (only the ruled T2 miss), so no fix moved the balance. **S2 read 49.7, then 50.5 worker-minutes on a re-run (band < 43; 37.1 at M12b).** `main` re-run the same day (41765523921) read **51.9**, and locally the branch runs the balance subset within 2% of `main` (105-107 s against 104-105 s over three alternating pairs), so the rise is the runners', not M12r's. Product manager: S2 on today's runners fails on `main` too; re-band or re-measure it.
- **Verification.** CI `check` green on the branch (perf median 555 ms). Locally: 1,300 non-nightly tests (golden snapshots included) pass, `make e2e` 64 passed. A full local `make check` (nightly included) ran past the session's 60-minute limit with no failure through 91% of the backend tests; the nightly part is covered by the CI nightly above. `tests/durations.json` refreshed for the non-nightly tests (1,326 entries; the nightly timings kept).
- **Item 9, measurement.** A 6-turn warm-up, then three blocks of 38 turns; the median block's mean per turn decides, against the unchanged 1.0 s. The result is printed and raised as a `TurnTime` warning, so every CI log's warnings summary shows it.

## Follow-ups

- `load_people` still costs about 77 ms on a cold load (a screen after the app starts, the CLI, backups). Reading the person child tables through the driver cursor instead of SQLAlchemy rows measured about 3x faster on the two largest queries (skills 20 to 7 ms, knowledge records 27 to 12 ms); worth doing if cold loads matter.
- `monthly_cost_lines` runs about 180 times a turn (rival decisions price each rival's costs per candidate); memoizing it per state within a turn would save about 15 ms.
- Own products' regional outage losses are counted but not considered for the outage event's target segment; harmless today, worth aligning when regional events exist.
- The `hardware_views` builders (M12b) still select `state.player.id` internally, like the views finding 8 named; give them a company id when M16's group arrives, or earlier.
