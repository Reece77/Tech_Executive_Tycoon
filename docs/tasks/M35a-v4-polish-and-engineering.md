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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
