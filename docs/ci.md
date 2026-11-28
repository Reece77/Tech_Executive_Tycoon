# CI

How the pull-request checks run (M59). Locally nothing changes: `make check`, `make check-fast`,
`make e2e` and `make check-timing` run everything on one machine, as before.

## The jobs

| Workflow | Job | Runs | Limit |
| --- | --- | --- | --- |
| `check.yml` (every push and pull request) | `check (shard N/4)`, N = 1-4 | `make check-ci-N`: a quarter of the backend tests (`-n auto`, `--shard N/4`), plus ruff and mypy (1), the API sync (2) or the front end's lint, types and tests (3) | 30 min |
| | `check (timing)` | `make check-timing`: the 9 turn-time budgets, `-n 0`, alone on their runner, with the late v6 saves restored from the cache (M60) | 30 min |
| | **`check`** | needs the five above; fails unless all succeeded | 5 min |
| `e2e.yml` (pull requests into main, pushes to main, on demand) | `e2e (shard N/4)` | `make e2e-shard SHARD=N`: `playwright test --shard=N/4`, with its own API, launcher, Vite server and save folder | 45 min |
| | **`e2e`** | needs the four shards; fails unless all succeeded | 5 min |
| `determinism.yml` | `digests (...)`, `compare` | unchanged | |
| `timing-saves.yml` (pushes to main, on demand) | `timing save (2069)`, `timing save (2100)` | `make timing-save-N`: builds one late v6 save and keeps it in the Actions cache (M60) | 180 min |

The rulesets require the summary jobs: `check` ("Main protection") and `e2e` ("Main"), so adding
or removing a shard never changes a required name. `tag-milestone` still waits for the `check`
workflow to succeed on `main`.

## The shards

- **Backend:** `tests/conftest.py`'s `--shard K/N` sorts the collected tests (after the `-m`
  filter) heaviest first by `backend/tests/durations.json` and gives each to the lightest shard,
  weighing each test at its duration plus 1.3 s. A test missing from the file counts as the mean.
- **Playwright:** `frontend/e2e/shard-reporter.ts` takes `--shard=N/T` over from Playwright
  (whose own split, by test count in file-name order, put the M31-M55 flows together at 1.99x the
  mean): whole spec files, heaviest first by `frontend/e2e/durations.json` (seconds a file), to
  the lightest shard. Tests within a file, and files within a shard, keep their order.

## The fixture cache

The e2e flows build their saves with `tools/e2e_*_save.py`, each through `tools/e2e_cache.py`.
In CI (`TST_E2E_FIXTURE_CACHE`, kept by `actions/cache` a shard) a call that builds a new save is
restored from the cache, its name written back and its output replayed, or built and stored.
Calls that edit an existing save run as before. The key is a hash of `backend/tst/**`,
`backend/data/**`, `backend/migrations/**`, `tools/e2e_*`, `backend/uv.lock` and
`frontend/e2e/durations.json`; inside it each save is keyed by its tool and arguments. The engine
is deterministic (ADR-0002); `backend/tests/integration/test_e2e_cache.py` holds a cached save's
state digest and ledger to a fresh build's. A change to the spec files alone keeps the cache: a
save a new argument asks for is built (and not stored until the key changes).

## The late v6 saves (M60)

`check (timing)` times a January 2069 month of M37's dynasty game whose player also runs the v6
industries, and a December 2100 month of M52's sandbox continuation
(`backend/tests/integration/test_m60_perf.py`: the median and the worst month under 1,000 ms runner-adjusted, Reece's rule since M60). Each save takes
about an hour to build, longer than the job's limit, so the job never builds them:

- `timing-saves.yml` builds them (`make timing-save-2069`, `make timing-save-2100`) after every
  push to `main` and keeps each in the Actions cache as `timing-save-N-<commit>`;
- `check (timing)` restores the newest `timing-save-N-` its branch can read (its own branch's, else
  `main`'s) into `/tmp/tst-timing`, and `make check-timing` passes each save it finds to the test;
  a guard whose save is missing skips (the first hour after a cache is evicted, or a fork).

A save built a few commits back is still a 2069 or 2100 world: migrations bring it up to date and
the engine plays it on. Locally, `make timing-saves` builds both into `TIMING_SAVE_DIR`
(`/tmp/tst-timing`), and `make check-timing` uses them from then on.

## The guard

`backend/tests/unit/test_ci_shards.py` predicts each shard's job minutes from the durations files
and the workflows' matrix sizes and limits:

- check: 1.7 minutes plus the shard's other work, plus 0.248 x its weighted minutes (fitted on
  main's d6d61fb: 116.6 weighted minutes a shard ran pytest in 28.9);
- e2e: 3.2 minutes plus the shard's summed file times.

Over 70% of the limit the slowest shard is a warning (the GitHub job summary and a pytest
warning); over 90% the test fails. A spec file without a measured time is a warning.

## Rebalancing

When the guard warns:

1. **Backend:** run `make test-durations` (the whole suite, `-n auto`, on a 4-core machine) and
   commit `backend/tests/durations.json`. The nightly also uploads a CI-measured file (artifact
   `durations`, `backend/tests/durations.json`, from `tools/ci_durations.py`); CI's 2-core times
   are on another scale from local ones, so if you commit that one, refit `CHECK_FACTOR` in the
   guard (CI pytest minutes / predicted weighted minutes).
2. **Playwright:** take `frontend/e2e/durations.json` from the latest nightly's `durations`
   artifact (every file measured on CI with no fixture cache) and commit it.
3. If a balanced shard is still over 70%, add a shard: the matrix in the workflow, `check-ci-N`
   (or `E2E_SHARDS`) in the Makefile, the `--shard N/M` in each `check-ci-N`. The summary job keeps
   the required check's name, so no ruleset change is needed.

Never lengthen a limit, skip or retry a test to make a shard fit (CLAUDE.md section 8).
