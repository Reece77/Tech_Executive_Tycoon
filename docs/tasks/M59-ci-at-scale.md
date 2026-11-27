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

### 1. Baseline (sub-task 1, measured 2026-11-27)

Runs (wall = run created to last job done, minutes; cancelled runs left out):

| workflow | branch | runs (sha) | wall, each | median |
| --- | --- | --- | --- | --- |
| check | main | d6d61fb, 3da2f5b, 65f6d12, 139979f, ebce7f4 | 37.9, 26.1, 47.0, 30.3, 28.7 | 30.3 |
| check | m55-media | 06bc551 (PR, push), f8e2e5e (PR, push), 3071e60 | 38.7, 52.2, 53.5, 53.9, 37.9 | 52.2 |
| e2e | main | d6d61fb, 3da2f5b, 65f6d12, 139979f, ebce7f4 | 72.2, 81.9, 69.2, 83.2, 95.7 | 81.9 |
| e2e | m55-media | 06bc551, f8e2e5e (failed: limit), fd9c93b, ccd8822, c9c9c27 | 96.2, 124.1, 108.2, 94.6, 100.9 | 100.9 |

Steps (median minutes, [range]). Every setup step (checkout, Python, uv, pnpm, Node, both
installs) takes 0.0-0.15 minutes, with the uv and pnpm caches always hitting; queueing is 2-3
seconds and Playwright's Chromium 0.2-0.5 minutes:

| job | step | main | m55-media |
| --- | --- | --- | --- |
| check (shard 1/2) | `make check-ci-1` (ruff < 1 s, mypy 64 s, pytest on 2 workers) | 23.7 [19.9-38.8] | 30.1 [29.4-42.5] |
| check (shard 1/2) | `make check-timing` (7 tests, `-n 0`) | 4.8 [4.1-7.9] | 8.0 [7.3-10.7] |
| check (shard 2/2) | `make check-ci-2` (API sync 13 s, eslint 20 s, tsc 32 s, vitest 6 s, pytest) | 25.9 [20.3-30.1] | 50.2 [29.7-53.5] |
| e2e | `make e2e` (202 tests, 1 worker; servers up and first test after 54-72 s) | 81.3 [68.4-95.2] | 99.9 [93.7-123.3] |

The same commit (06bc551) ran shard 2 in 29.7 minutes on its pull-request run and 51.6 on its
push run, and every e2e file ran 1.2-1.45x slower on m55-media's run than on main's: runner
speed alone moves a job by about a third. Pytest on main's d6d61fb: shard 1 `1514 passed` in
28:56, shard 2 `1512 passed, 1 skipped` in 28:55 (2 xdist workers: the runners have 2 vCPUs).

Collected on main (d6d61fb): backend 3,173 tests, of which 3,027 are `not nightly and not timing
and not weekly` (CI's `check`), 121 `nightly`, 7 `timing` and 18 `weekly`; Playwright `Total: 202
tests in 60 files`.

The 20 slowest Playwright files (sum of test durations; main job 140675711155 ran 69.0 minutes
of tests and m55-media job 140632957875 92.3; the other 40 files take 20.8 and 27.0 minutes).
Only one test is over 1.5 minutes (`m43.spec.ts:23`, 3.5): the M31-M55 specs cost about a minute
a test, about 37 of main's 69 minutes.

| file | tests | main min | m55-media min |
| --- | --- | --- | --- |
| `m39.spec.ts` | 3 | 3.60 | 4.90 |
| `m43.spec.ts` | 1 | 3.50 | 4.60 |
| `m40.spec.ts` | 3 | 3.40 | 4.60 |
| `m32.spec.ts` | 3 | 3.20 | 4.60 |
| `m34.spec.ts` | 3 | 3.19 | 4.50 |
| `m55.spec.ts` | 4 | 3.17 | 3.81 |
| `m31.spec.ts` | 3 | 3.05 | 4.40 |
| `m54.spec.ts` | 3 | 3.05 | 3.80 |
| `m42.spec.ts` | 3 | 3.00 | 4.20 |
| `m41.spec.ts` | 3 | 2.91 | 3.90 |
| `m38.spec.ts` | 3 | 2.77 | 4.00 |
| `m53.spec.ts` | 3 | 2.64 | 3.60 |
| `m15b.spec.ts` | 4 | 1.96 | 2.83 |
| `m49.spec.ts` | 4 | 1.75 | 2.33 |
| `m44.spec.ts` | 3 | 1.58 | 2.19 |
| `m24.spec.ts` | 4 | 1.28 | 1.65 |
| `m7b.spec.ts` | 6 | 1.17 | 1.43 |
| `m16.spec.ts` | 4 | 1.05 | 1.41 |
| `m14b.spec.ts` | 4 | 1.02 | 1.34 |
| `m13.spec.ts` | 3 | 0.91 | 1.16 |

The 20 slowest backend tests in `check` (`tests/durations.json`, local seconds; the file's
2,938 known `check` tests sum to 164.8 minutes):

| test | s |
| --- | --- |
| `tests/property/test_product_invariants.py::test_customers_stay_within_demand_and_entries_balance` | 365 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m37_save-practice-/campaign-False]` | 316 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m48_save-boardroom-/meetings-False]` | 297 |
| `tests/unit/test_modes_scenarios.py::test_each_scenario_loads_on_its_years_world[ai_lab]` | 243 |
| `tests/golden/test_golden.py::test_same_seed_twice_is_identical` | 166 |
| `tests/balance/test_m48_balance.py::test_59_4_targets_2_and_3` | 153 |
| `tests/golden/test_golden.py::test_golden_seed[1]` | 146 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m34_save-regulated-/regulation-True]` | 133 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m32_save-power-/power-True]` | 123 |
| `tests/unit/test_m38_vehicles_data.py::test_history_ev_shares_follow_the_data` | 120 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m33_save-litho-/equipment-True]` | 120 |
| `tests/balance/test_balance_smoke.py::test_report_has_every_target` | 116 |
| `tests/integration/test_cli_org.py::test_manual_check_flow` | 106 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m40_save-space-/space-True]` | 105 |
| `tests/unit/test_m30_memo.py::test_derived_values_match_a_recompute_while_a_group_plays` | 104 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m44_save-defence-/government-True]` | 101 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m39_save-robotics-/robotics-True]` | 95 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m42_save-pharma-/pharma-True]` | 90 |
| `tests/unit/test_people_phase.py::test_young_founder_grows_and_old_founder_does_not[1]` | 90 |
| `tests/integration/test_m23c_fixtures.py::test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m31_save-platform-/platforms-True]` | 90 |

### 2. The e2e split: whole files by measured time, no spec file split (sub-task 2)

Playwright's own `--shard=N/4` splits files in name order into runs of equal test counts. With
main's file times that gives shards of 11.5, 8.6, 34.3 and 14.7 minutes (1.99x the mean), because
the M31-M55 flows (about a minute a test) sit together in name order. Splitting the heaviest
files along their `describe` blocks would not help: the pieces keep their place in that order.
Instead `frontend/e2e/shard-reporter.ts` uses Playwright 1.64's `TestRun.skipSharding()` and
`exclude()` (a reporter's `preprocess`): whole files, heaviest first by `frontend/e2e/durations.json`,
each to the lightest shard. On main's times that is 17.2, 17.3, 17.3 and 17.3 minutes (1.00x), so
no spec file moved. The command is still `playwright test --shard=N/4` (`make e2e-shard SHARD=N`).
The four `--list --shard=k/4` lists together equal the unsharded list, test for test.

### 3. The fixture cache sits in the tools, keyed by their arguments (sub-task 3)

The flows build their saves by running `tools/e2e_*_save.py` with save names stamped with the
time, so a cache keyed by file name would never hit. Each of the 50 tools' `__main__` now runs
`main` through `tools/e2e_cache.run`. With `TST_E2E_FIXTURE_CACHE` set (CI only), a call is a
build when its arguments name an existing save folder and then a save that does not exist yet.
The cache key is the tool and its other arguments. A hit does four things:

- copies the save;
- writes the new name into `save_meta.name` (the only place a save holds its name: the state's
  `SaveMeta` is read from it);
- lists the save in the folder's `index.json`, as `create_save` does;
- replays the tool's printed output with the folder and name restored (M26's and M47's flows
  read it).

A miss builds and then stores the save only if the tool exited 0.

The first cache-hit run on CI failed two flows (run 46072543176, shard 2): M7b's save list did
not show a restored save, and M25's first-launch toast never appeared. A build also writes beside
the save: it updates `index.json`, and it changes the shared profile (`profiles/default.json`) as
its months earn achievements; M25's `ready` clears the profile for a fresh one. So a miss now also
records the build's changes to the folder's JSON files entry by entry (`earned.<achievement>`,
`watch.<save>`), with the save's name templated, and a hit replays them. A build that changes any
other kind of file is never stored (`m25-ready` and `m7b-saves` build every time). The replayed
rows carry the miss's wall-clock `earned_at`, which no flow compares; the test compares the
profile without it. Locally, `m25.spec.ts` and `m7b.spec.ts` passed 11 of 11 on a cache miss and
again on a hit. Every other call (`advance`, `holiday` and the other edits) runs as before. No
spec file changed. `actions/cache` keeps one cache a shard (about 54 MB for shard 1), keyed by
the brief's file list plus `frontend/e2e/durations.json`, which decides which files a shard runs.

### 4. Timing alone, and the shards' other work (sub-task 4)

`check (timing)` installs only the backend (no pnpm or Node). Lint and types go to shard 1, the
API sync to 2 and the front end to 3. They are 1.1, 0.3 and 1.0 minutes, inside the guard's
per-shard constants. `check-ci-1` and `check-ci-2` now mean shards 1 and 2 of four; the
Makefile calls all four CI-internal, and no doc lists them as commands. The old two-shard
meanings are used nowhere else.

### 5. The guard's model (sub-task 5)

- **Backend:** `tests/unit/test_ci_shards.py` repeats `shard_of` over the collected `check`
  tests, which `tests/conftest.py` now records before the shard filter. It predicts a shard at
  1.7 minutes plus its other work plus 0.248x its weighted minutes, fitted on main's d6d61fb run.
  In a partial run (under 1,000 `check` tests collected) it skips.
- **Playwright:** it repeats `assignShards` and predicts 3.2 minutes plus the shard's file
  times. A spec file with no measured time is a warning, not a failure (the reporter counts it at
  the mean).
- **Thresholds:** over 70% of the limit the guard writes a warning to `$GITHUB_STEP_SUMMARY` and
  raises a pytest warning; over 90% it fails. Parametrised tests check 70% and 90% exactly and
  just above each.
- **Nightly:** new `durations (check N/4)` and `durations (e2e N/4)` matrices measure every test
  and file, the nightly shards write theirs too (`--durations-out`), and the `durations` job
  merges them (`tools/ci_durations.py`) into one artifact. It opens no pull request.

### 6. The 77 tests without a duration

`backend/tests/durations.json` lacked 77 `check` tests (M52's, one M55 file and M59's own). I
measured them locally (`--durations-out`, 168 s in all) and merged them in. Every other entry is
unchanged.

### 7. Local `make check`

`make check` runs the `nightly` tests too (`check-backend` leaves out only `timing` and
`weekly`). On this container it was 10% through after 30 minutes, so by §9 rule 7 I stopped it.
In its place, what it runs ran on CI on this branch: lint, types, the API sync, the front end and
every `check` test in `check (shard N/4)`, the 7 turn-time budgets in `check (timing)`, and the
121 `nightly` tests in the nightly dispatched on `m59-ci`. Locally I ran the parts M59 touched:
ruff and mypy, the front end's lint and typecheck, the new tests and a whole e2e shard (shard
4/4, 50 passed in 23.0 minutes with no cache).

### 8. Readings on the branch (2026-11-27)

| Run (commit) | `check` wall | check shards 1-4, timing | slowest / mean | `e2e` wall | e2e shards 1-4 | slowest / mean |
| --- | --- | --- | --- | --- | --- | --- |
| push 59efb4f (before main's M55) | 19.3 | 11.2, 18.9, 15.8, 14.2; 6.7 | 1.26 | - | - | - |
| push d2e0fd1 | 26.4 | 24.9, 26.2, 20.0, 23.6; 10.8 | 1.11 | - | - | - |
| PR d2e0fd1 | 27.5 | 25.7, 15.9, 27.4, 19.0; 6.9 | 1.25 | 21.6 (miss) | 21.4, 19.3, 21.4, 20.7 | 1.03 |
| PR c36149c (queued behind the nightly) | 21.0 | 13.2, 14.2, 20.5, 13.2; 10.4 | 1.34 | 33.0 (miss) | 20.1, 20.9, 18.4, 32.9 | 1.42 |
| push c36149c | 28.4 | 24.3, 27.9, 27.8, 17.1; 7.8 | 1.15 | - | - | - |
| re-run c36149c | - | - | - | 13.3 (hit) | 9.7, 13.2, 8.7, 11.0 | 1.24 |

Against the targets: `check` median of the three latest (27.5, 21.0, 28.4) is 27.5 minutes (band
30; main's baseline median 30.3, m55-media's 52.2). `e2e` on a cache miss 21.6 and 33.0 (band 45),
on a hit 13.3 (band 35; main's baseline median 81.9). Counts equal main's (decision 1) plus M59's
13 new backend tests (3,040 `check`). Slowest / mean is within 1.3 in seven of nine readings: the
two over it (1.34, 1.42) are single slow runners on a split the guard predicts flat (check
16.3-17.4, e2e 20.4-20.5 minutes a shard). As the baseline showed, the same work runs up to 1.75x
slower on one runner than another; no split removes that.

**Risk, for Reece:** the slowest `check` shard reached 27.9 of its 30 minutes (93%), on runners
1.6x slower than the guard's model. The guard judges the model's prediction (58% today), so it
does not see a slow runner coming. A fifth shard (about 14 minutes a shard by the model, 22 on
the slowest runner seen) would keep that margin; with the summary job it needs no ruleset change.
Not done: the brief names four.

## Follow-ups

- A fifth `check` shard if slow runners keep shards near 30 minutes (decision 8).
- `playwright install --with-deps` runs `apt-get update` on every e2e shard; one shard failed when
  an apt mirror answered 403 (run 46072543176). Four shards meet that four times as often. Caching
  the browser, or installing without `--with-deps` on the hosted image, would remove it.
- The guard's constants are fitted to one run; refit them from the nightly's measured files after a
  week of runs (docs/ci.md).
