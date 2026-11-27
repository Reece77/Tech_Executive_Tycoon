# M59: CI at scale (engineering, single lane)

**Goal:** every pull request gets its verdict in about half an hour instead of two. The same tests run, unchanged, on more runners in parallel, and the split keeps itself balanced as tests are added.

**Depends on:** `m55-done` (on `main`) · **Lane:** single, before M57 and the remaining v6 briefs · **Changes no game code:** nothing under `backend/tst/sim/`, `backend/data/` or `frontend/src/` changes, and no fixture, golden snapshot or state cache is re-recorded.

## Why (product manager, 2026-11-27)

After the v6 merge (M52, M54, M55), `e2e` runs 202 Playwright tests one after another in one job for about 2 hours (limit raised 90 → 120 → 150 minutes), and `check`'s two shards run 35–55 minutes (limit 40 → 50 → 60). Each push cancels and restarts both, so M55 spent about 14 hours on CI after its code was done. The public repository has free runners and up to 20 concurrent jobs, so the fix is parallelism, not looser limits.

## Rules

- **Never weaken a test** to make it fit (CLAUDE.md §8): no test removed, skipped, marked slower or retried, and no timeout made longer. A test that only passes alone stays alone (as `check-timing`).
- **Same tests:** print the collected test count for backend (`pytest --collect-only -q`, by marker) and Playwright (`playwright test --list`) on `main` before and on the branch after; they must be equal.
- **Local commands unchanged:** `make check`, `make check-fast`, `make e2e` and `make check-timing` run as before on one machine.
- CLAUDE.md §9's decision rules apply.

## Sub-tasks (commit after each)

1. **Measure:** from the last five runs of `check` and `e2e` on `main` and `m55-media`, a table of each job's steps (setup, installs, fixture builds, tests, timing) and the 20 slowest backend tests and Playwright files. Record it in "Decisions made" as the baseline.
2. **`e2e` in four shards:** a matrix job `e2e (shard N/4)` running `playwright test --shard=N/4`, each with its own API, Vite server and save folder (as now). Balance the shards by measured file time: if Playwright's split leaves one shard over 1.4× the mean, split the heaviest spec files along their existing `describe` blocks (moving tests between files only, never changing them). One summary job named **`e2e`** `needs:` all four and fails if any failed or was cancelled, so the ruleset's required check keeps its name. Traces upload per shard on failure. Limit 45 minutes a shard.
3. **Fixture saves cached:** the saves built by `tools/e2e_*_save.py` (and any the flows build at start) are cached with `actions/cache`, keyed by a hash of `backend/tst/**`, `backend/data/**`, `backend/migrations/**`, `tools/e2e_*` and `uv.lock`. A hit skips the build; a miss builds and stores. Determinism (ADR-0002) makes a cached save identical to a fresh one; add a test that one cached fixture's state hash equals a fresh build's.
4. **`check` in four shards plus timing alone:** matrix `check (shard N/4)` (backend tests split by `tests/durations.json` into four; lint, types, API sync and frontend spread so no shard carries more than its share), and a separate job `check (timing)` that runs `make check-timing` alone on its own runner after nothing (no `needs:`: it is alone on its runner either way). One summary job named **`check`** `needs:` all of them. `tag-milestone` still waits on the `check` workflow's success (unchanged). Limit 30 minutes a shard. New `make check-ci-N` targets for N = 1–4; keep `check-ci-1` and `check-ci-2`' meanings out of the Makefile's public targets list.
5. **Self-balancing:**
   - the nightly workflow writes fresh `tests/durations.json` and Playwright per-file times as artifacts, and opens no pull request (a session refreshes them with `make test-durations` when the guard below warns);
   - a guard (a unit test reading `durations.json` and the matrix size) warns in the job summary when the slowest predicted backend shard is over 70% of its limit, and fails at 90%;
   - the same for Playwright from its last recorded per-file times.
6. **Required checks and the switch-over:** the rulesets require `check (shard 1/2)`, `check (shard 2/2)` (ruleset "Main protection") and `e2e` (ruleset "Main"). Sessions can't edit rulesets. When the branch is green, **stop and report** with the exact change for Reece: in "Main protection" replace the two shard names with `check`. "Main" stays `e2e`. Merge only after Reece confirms the change.
7. **Docs and close-out:** CLAUDE.md §5 and §6 (the job names in the merging steps), `docs/ci.md` (new, one page: the jobs, the shards, the cache, the guard, how to rebalance), CHANGELOG, README index row. Merge with the trailer `Milestone-Tag: m59-done` and confirm the tag.

## Targets (printed in the pull request)

| Target | Band |
| --- | --- |
| `check` wall time on the branch (push to verdict), median of three runs | ≤ 30 minutes |
| `e2e` wall time, median of three runs, cache hit | ≤ 35 minutes |
| `e2e` wall time, cache miss | ≤ 45 minutes |
| Collected test counts, backend by marker and Playwright | equal to `main`'s |
| Slowest shard ÷ mean shard, check and e2e | ≤ 1.3 |

## Out of scope

Making tests or the game faster (the v6 performance pass); the nightly and weekly suites' own sharding (unchanged unless a step above needs them); paid or larger runners; test retries of any kind.

## Acceptance criteria

- [ ] The same tests run (counts equal), none weakened, retried or given longer timeouts.
- [ ] `check` and `e2e` meet the targets above on the branch, and on `main` after the merge.
- [ ] A cached fixture equals a fresh build (state hash test).
- [ ] The balance guard warns at 70% and fails at 90% of a shard's limit.
- [ ] Reece changed the ruleset before the merge; `check`, `e2e` and `determinism` green; merged through a pull request with `Milestone-Tag: m59-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
