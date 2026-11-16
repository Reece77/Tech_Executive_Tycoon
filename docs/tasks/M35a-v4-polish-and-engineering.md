# M35a: v4 polish and engineering (v4, lane A)

**Goal:** close v4's engineering debts before its balance pass. Make Windows and Linux give the same results. Fix the server errors hiding in e2e logs, and make any new one fail e2e. Bring the late-game turn back under its guard after power, equipment and regulation. Give M30's fixture an update flag. Audit the economy's money scale and write the recommendation for Reece.

**Depends on:** M32 (`m32-done`), M33, M34, M36p · **Lane:** A, alongside M35b (lane B, balance). **M35a merges first.** It changes no rule or balance key, except where a determinism fix must, as sub-task 1 says.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m35a-polish` from `main`.
- **M35a owns:** the maths and RNG call sites that differ by platform; e2e configuration and helpers; `tests/balance/test_m30_state_cache.py` and its fixture tooling; the performance work in the database write and market phase; `docs/economy-scale-audit.md` (new); CLAUDE.md's worktree rule.
- **M35a must not edit:** `tst/balance/` scripts or any balance key (M35b's), except as sub-task 1 allows.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each)

1. **The same game on Windows and Linux.**
   - Find why M30's state digests differ between Windows and Linux from the same seed (M33 decision; likely platform maths libraries in `math.exp`, `log`, `pow` or NumPy, or iteration order, or float formatting in a digest).
   - Run the same 120-turn game on both runners in CI (add a `windows-latest` job for a short determinism check) and diff the state turn by turn to find the first differing value.
   - Fix it at its cause. Possible fixes are a deterministic implementation of the function used in the sim, rounding at a fixed precision before the value feeds state, or a stable order.
   - If the fix changes results on Linux, regenerate golden snapshots and the M30 fixture with the reason in CHANGELOG, and show which series moved. If it would move history before 2026 (§41.8 target 1), stop and report.
   - **Acceptance:** the CI determinism job gives identical digests on Windows and Linux over 120 turns on seeds 1–3, and stays in CI as a guard.
2. **Server errors fail e2e.**
   - Fix the two errors in `main`'s e2e logs: `StopIteration` in `tst/api/mna_views.py` line 193, and the `KeyError` in event links (`state.person`). Each gets a regression test.
   - Make the e2e harness fail a run when the server logs an unhandled exception or a 500. Allow an explicit list for intended errors, with a reason for each, and list any new ones it finds.
3. **Turn time after v4.**
   - Re-measure the `full_integrator` and plain V6 2039 saves on the CI runner with power, equipment and regulation in. They must stay under the 500 ms guard. M30's 400 ms target is the aim; record before and after.
   - Make the remaining slow steps proportional (M36p's follow-up: the database write of reveal and skill rows, and the market phase), with identical results.
   - Add M36p's runner calibration: time a fixed CPU-bound workload beside the month and print the ratio in the log, so a slow runner shows up. The guard itself stays in milliseconds.
4. **M30's fixture gets an update flag.** Add `--update-state-cache` alongside `--update-golden`, with the same rule: regenerate only for an intentional change, with the reason in CHANGELOG. The memo-equals-recompute and repeat assertions always run. Document it in CLAUDE.md §5 and §6.
5. **The economy-scale audit** (report only; no rule changes). Write `docs/economy-scale-audit.md`:
   - **The scale of each money domain,** game against real, with the derivation: company revenues (M34's `economy_scale.money` 0.0849); salaries; office rents; cloud and compute prices; fab capex and wafer prices (M21); tool prices (M33); plant capex, PPA and grid prices (M32); commodity prices (M17); acquisition prices and valuations (M14); fines; estate figures (M36); the player's starting capital.
   - **Why revenues come out at about a tenth of real.** For example: categories that cover only part of a company's business, regions missing, user counts, or prices.
   - **What a mismatch does to play.** Heavy industry may be relatively ten times dearer than in reality, which affects fabs, mines and plants.
   - **Two or three options** with their effects on earlier targets and history, and a recommendation.
   - Reece decides after his campaign.
6. **CLAUDE.md:** add to §5 and §8 that each session works in its own clone or worktree and never shares a folder (M34 and M32 collided on 2026-11-15).
7. **Close-out:** CHANGELOG, README index row, and a summary of the audit's recommendation in the final report.

## Acceptance criteria

- [ ] Windows and Linux give identical digests over 120 turns on seeds 1–3 (CI job).
- [ ] e2e fails on any unlisted server error, and the two known errors are fixed with tests.
- [ ] Both V6 2039 saves are under 500 ms median on the CI runner, with numbers recorded.
- [ ] `--update-state-cache` exists and is documented, and the fixture's two real assertions are unchanged.
- [ ] `docs/economy-scale-audit.md` is complete with a recommendation.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m35a-done`.

## Decisions made

1. **PR #69 (docs-m35)** merged into main with a merge commit before the branch began (rule 9; check and e2e green, fa12404).
2. **Why Windows and Linux differed.** `tools/platform_digests.py` and the new `determinism` workflow play M30's three strategies on seeds 1-3 for 120 months on `ubuntu-latest` and `windows-latest` and compare every month's full-state digest, then (on demand, `dump`) every leaf. On main every run differed **from turn 0**, in `state.geo_blocks` only: hidden deposits' `true_infra_km` and `true_difficulty` by one ulp (5-6 of ~80,000 leaves; e.g. `6.4600139655327755` on Linux against `6.460013965532775` on Windows). They come from `math.exp` and `math.log` in `exploration/geology.py`: glibc and the UCRT round the last bit differently. Iteration order, digest formatting and NumPy's draws were not the cause (the leaves that differ are all libm results).
3. **The fix at its cause: `tst/sim/dmath.py`,** correctly rounded `exp`, `log`, `log10`, `log2`, `asinh`, `sin` and `pow` through `decimal` (libmpdec, the same arithmetic on every platform) at 40 digits, rounded once to a double, memoised; and AS241's normal quantile (what `statistics.NormalDist.inv_cdf` uses) with those functions. Every `math.exp/log/log10/log2/sin/asinh` (24 files), every float `**` (53 sites in 26 files) and the one `NormalDist` in `tst/sim` now go through it. `tests/unit/test_m35a_dmath.py` scans `tst/sim` and `tst/events` by AST and fails on any platform maths call or float `**` that comes back (integer constant powers and `money.py`'s integer `DECIMAL_BASE` powers stay: exact ints), and checks correct rounding with Hypothesis. Cost: about 3 ms a month (memo hits; profile of 24 months).
4. **What moved on Linux.** glibc's `exp` itself misrounds about one input in a thousand, so correct rounding moves a few last bits on Linux too. **Golden snapshots: unchanged** (11 passed). **M28's history (§41.8 target 1): unchanged** on seed 1 in `make check` and on every guard seed (nightly test, decision 13). **M30's state cache: re-recorded** with the new `--update-state-cache` (12 min locally): on seed 1 the first difference from main's fixture is one hidden deposit's `true_infra_km` at turn 0, by one ulp, to the value Windows already gave; seeds 3 of every strategy were identical over 12 months. Nothing before 2026 that history fingerprints moved, so no stop was needed.
5. **The CI guard.** `determinism` runs on every push and pull request (four-minute jobs on both runners, a comparison job). With dmath: **identical over 120 months on seeds 1-3 for all three strategies** (runs 7 and 8 on this branch). It is a separate workflow, not one of `check`'s required shards; the brief asks for it to stay in CI as a guard, and branch protection is Reece's setting.
6. **e2e's two errors.** `mna_out` took `next(...)` over acquisitions for every subsidiary; a subsidiary the player *founded* has none (M27b's flows), so `/mna` raised StopIteration (as asyncio's RuntimeError). It now reads "grow" for one, as `tst.sim.mna.style` already does. `event_links` called `state.person` for each of an open event's people; someone let go since (M7c's former-employee flow) is not in the state, so `/events` raised KeyError. Their link stays (`people/{id}` opens the Former employee profile) labelled "Someone who has left". Tests: `tests/unit/test_m35a_api_errors.py` (the first reproduced StopIteration before the fix).
7. **Server errors fail e2e.** With `TST_ERROR_LOG` set (`tst/config.py`), `tst/api/error_log.py`'s pure-ASGI middleware appends one JSON line per unhandled exception or 5xx response (method, path, status, error, innermost `tst/` frame through the exception's causes). Playwright's config sets it for both API servers (the API and the launcher's), a global setup clears it, and a global teardown (`frontend/e2e/server-errors.ts`) throws, failing the run, on any line its allow-list does not name. **The allow-list is empty**: no flow means to cause a server error. Verified: with the M&A fix reverted, `m27b.spec.ts` exited 1 naming both `/mna` requests; the full e2e run on CI found no others (decision 14).
8. **`--update-state-cache`** (`tests/conftest.py`): `test_update_the_fixture` plays the nine runs and writes the fixture only with the flag (skipped otherwise); the nightly comparison skips while re-recording; `test_the_digest_is_canonical_and_sees_every_change` and `test_a_short_run_repeats_and_its_memo_matches_a_fresh_digest` always run (the latter compares with the fixture only without the flag). CLAUDE.md §5 and §6 document it with the golden rule.
9. **Runner calibration** (`tests/calibration.py`): a fixed pure-Python workload (dicts, tuples, Fractions, hashing; 70 ms on this container) timed five times beside the month; V6's and M30's reports print `runner x<ratio> (workload <ms> against 70 ms); month = <n> workloads`. The guards stay in milliseconds.
10. **Turn time.** See decision 15 for the CI numbers (both saves under 500 ms on CI's runner). Profiled locally (a 2039 full_integrator save built on main, 133 staff): of a ~400 ms month, `advance_turn` ~60%, the database write (`apply_turn_result`) ~30%, of which `sync_state` ~23% and the SQLite commit ~5%. The write already writes only rows that changed (M30, M36p): the reveal and skill rows it writes do change every month (revealed ranges' `last_updated_turn`, monthly growth), so no further proportional cut exists there without a schema change. The market phase memoises each product's team within the phase; the remaining repeats (develop, markets and brand compute teams from different intermediate states) cannot share a cache without risking a result change. With both saves under the 500 ms guard on CI (decision 15), rule 6 asks for nothing more; the 400 ms aim is a follow-up.
11. **CLAUDE.md §5 and §8:** each session in its own clone or worktree, never a shared folder.
13. **History holds on every guard seed** (`tests/balance/test_m28_history.py::test_history_holds_on_every_seed`, run locally on the branch: passed).
14. **e2e on CI with the error check** (run 43804697408 on this branch): every flow passed and the teardown found no server error, so the allow-list stays empty.
15. **Turn time on CI's runner** (V6 2039 saves: plain research_heavy `weekly-v6` and `weekly-v6-integrator`, medians):

    | Run | Runner (calibration) | full_integrator median | worst | plain V6 median |
    | --- | --- | --- | --- | --- |
    | main fa12404 (before) | not measured | 335 ms | 488 ms | 347 ms |
    | main d1ffc39 (before) | not measured | 380 ms | 425 ms | 377 ms |
    | branch, weekly 1 | x1.85 | 604 ms | 682 ms | 613 ms |
    | branch, weekly 2 | x1.40 | 466 ms | 1,422 ms | 474 ms |
    | branch, weekly 3 | x1.55 | 482 ms | 612 ms | 510 ms |
    | **A/B, one runner** (x0.95-0.99), main x3 | | **331, 331, 315 ms** | 504, 448, 459 ms | |
    | **A/B, one runner**, branch x3 | | **336, 332, 348 ms** | 490, 578, 649 ms | |

    The weekly runs on the branch drew slow runners (the new calibration shows it); a temporary workflow timing main and the branch alternately on one runner (removed) gives medians within 3% (326 against 336 ms), worst months under 650 ms and Holiday years 4.2-4.3 s on both. Both saves are under the 500 ms guard on a normal runner; the full_integrator save is at about 335 ms, under M30's 400 ms aim, as main already was after M36p. Rule 6 (over budget alone) does not apply; the weekly guard's sensitivity to slow runners is a follow-up.
16. **`dmath.py` is exempt from the sim's literal guard** (`tests/unit/test_sim_literals.py`, with `rng.py` and `calendar.py`): its numbers are AS241's coefficients and series terms, mathematics rather than tunables.
12. **The economy-scale audit** (`docs/economy-scale-audit.md`, report only): drafted by a delegated agent from the repository's data and checked against it (salaries, rent, fab `capex_scale`, `world.ev_multiple`, the IPO gate, `economy_scale.money`'s derivation). Recommendation: option A (keep both economies, label them), plan C (raise tech demand) only if Reece's campaign shows the seam spoils play, reject B.

## Follow-ups

- **400 ms on the full_integrator 2039 save** (the aim, not the guard): the database write is ~30% of the month and is already proportional; the next step is a cheaper reveal model (writing only ranges whose shown bounds change, a schema change) or caching product teams across the turn's phases with an identity key on staff and people.
- **Weekly turn-time guards on slow runners:** at x1.4-1.85 the full_integrator save's median, worst month or Holiday year can pass a limit that a normal runner meets with room (decision 15). The guard could scale its limits by the calibration ratio (a measurement change: Reece's call).
- **Make `determinism` a required check** on main's branch protection (Reece's setting), and consider a macOS runner.
- **NumPy's normal draws** call libm's `log1p` in the ziggurat's tail (about 3 in 10,000 draws) and `exp` in its wedge test: not seen to differ in 120 months on seeds 1-3, but not covered by dmath. If the guard ever fails there, draw normals through an inverse-CDF on `rng.random()` (a result change).
- The audit's gaps: in-game 2010-2025 revenues of NVIDIA, Intel, AWS, TSMC and Salesforce (`tools/m34_economy_scale.py` could print them), and whether a game-scale player can borrow for a 5 nm fab.
