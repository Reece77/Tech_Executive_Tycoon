# M45: Performance at scale, part two (v5, lane J)

**Goal:** keep the game quick to the end of a 60-year dynasty, with **identical results**. v5's new industries and dynasty mode have pushed late-game turns up: about 546 ms for a 2069 month on the CI runner, and the 2039 saves back near their limits. M45 makes rival decisions and per-turn saving proportional to what changed, brings both 2039 saves back to 400 ms and a 2069 month under 500 ms, and keeps dynasty saves within their size limit.

**Formulas:** none new · **ADRs:** 0002, 0004 · **Depends on:** M43a (`m43a-done`; it changes the economy being measured) · **Lane:** J, alongside M42 and M40

## Carried here

- **M38 (decision 19):** the plain V6 save's December 2039 guard was raised to 500 ms; bring it back to 400.
- **M30 and M35a:** the `full_integrator` save's 2039 target of 400 ms.
- **M37 (decision 19):** a 2069 month at about 546 ms median on CI, and 1,022 ms worst on a very slow runner; the 2069 save at 397–409 MB against 400.
- **M36p's follow-up:** the database write of reveal and skill rows, and the market phase.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m45-performance` from `main` **after `m43a-done` exists**.
- M45 may change any engine, database or API code to make it faster, but **never a result.** Golden snapshots and M30's state cache must stay byte-identical, as must M37's 2040–2069 runs on seeds 1–3, recorded as a new long fixture before any change. No balance key changes, and no new dependencies.
- M42 and M40 are building at the same time. Keep changes in their files to small, named commits, and merge `main` often.
- **CLAUDE.md §9's decision rules apply** (rule 6 especially).

## Sub-tasks (commit after each)

1. **Measure first:**
   - extend `tools/bench.py` with a 2069 dynasty save and the two 2039 saves;
   - record a 720-turn state-cache fixture for seeds 1–3, dynasty mode on, before changing any code;
   - profile on the CI runner (a temporary step, removed before merging), and record the baseline.
2. **Rival decisions:** make rival companies' monthly decisions proportional to what changed for them. Skip unchanged rivals' re-evaluation, cache derived values keyed on their inputs (checked against a recompute in a debug test), and batch rivals by category.
3. **Per-turn saving:** write only changed rows (reveal and skill rows especially), batch the writes, and add indexes the queries need.
4. **The market phase:** avoid rebuilding whole demand tables each month, and make the 60-year history summaries proportional.
5. **Save size:** extend M30's retention rules to dynasty games (summaries for decades past), keeping everything the screens show. The 2069 save must be at most 400 MB.
6. **Close-out:**
   - re-run the benchmark, with before and after numbers in `docs/perf/`;
   - restore the plain V6 2039 guard to 400 ms, and set the `full_integrator`'s to 400 ms if reached, with a 2069 guard at 500 ms;
   - CHANGELOG, README index row.

## Acceptance criteria

- [ ] Golden snapshots, M30's state cache and the new 720-turn fixture identical before and after.
- [ ] Both 2039 saves at most 400 ms median, and a 2069 month at most 500 ms median, on the CI runner (runner-adjusted, per CI-fix's guard), with numbers recorded; or the misses reported with their profiles (rule 6).
- [ ] The 2069 save at most 400 MB.
- [ ] No balance key changed and no new dependency added.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m45-done`.

## Decisions made

1. **Measured first.**
   - `tools/bench.py` builds and times `v6` and `v6i` (both 2039) and `dynasty` (708 months).
   - The 720-month fixture `backend/tests/fixtures/m45_dynasty_hashes.json` was recorded before any engine change: seeds 1-3, dynasty mode, the `full_integrator` script, M30's `Digester` each month (`tst/balance/m45.py`, `tools/m45_state_hashes.py --write`). `tests/balance/test_m45_state_cache.py` compares it weekly (`make weekly-m45`, in `weekly.yml`), and a 4-month slice runs in `make check`.
   - The CI baseline (run 44321745111) and every after-reading are in `docs/perf/m45.md`. The temporary `m45-profile` workflow and its probe are removed.
2. **Runner-adjusted guards.** The brief measures "per CI-fix's guard", which was not on `main` (branch `claude/eloquent-lamport-mlnznj`, PM ruling 2026-11-17). Its one commit is cherry-picked here unchanged (`49f194c`): with `TST_M30_MEDIAN_MS` set, `test_m30_perf.py` compares the raw median divided by M35a's runner ratio. On top of it, M45 sets both V6 saves to 400 ms (`weekly-v6`, `weekly-v6-integrator`). `test_m37_perf.py` now asserts a 500 ms runner-adjusted 2069 median, and the save at most 400 MB (raw bytes). The 1.0 s worst month, the 6 s Holiday year and `test_v6_perf`'s 1,000 ms stay raw, as the ruling has it. When the CI-fix branch merges, its commit is already here (a clean merge).
3. **Results stay identical: how it was checked.**
   - Every change keeps the order of the work it replaces: indexes are built in tuple order, kept values are keyed on their inputs' identity, and one vector draw replaces a loop of single draws of the same numbers.
   - Checked by the goldens, M30's state cache, the memo recompute test (`MEMO_CHECK`) and the 720-month fixture.
   - A local harness also compared, before and after each change, the state digest and a whole-database digest (every row of every table) on copies of the `v6i` save. Both matched, for example digest `56fe87a1e1951f68` at turn 369.
4. **Save size: closed candidates' records** (`retention.candidate_people_months: 120`, new; no existing balance key changed).
   - The 2069 save's growth was people who were only ever candidates: about 42,000 by 2069, each with dozens of skill, trait, reveal and city rows.
   - A research pass over every reader (`tst/db`, `tst/api`, the screens) found that nothing reads those rows once the candidacy is closed and the person is not in the state. Only the person's name is read, by the Timeline (`history_views._names`).
   - `tst.db.history.prune_candidates` drops those rows for people whose candidacy closed more than 120 months ago, who are not founders and not in the state, and whom no foreign key names except their own `candidate` and `offer` rows (found from `Base.metadata`). The `person`, `candidate` and `offer` rows stay.
   - At most `PRUNE_BATCH` = 3,000 people a year: an old save's backlog of 42,000 took 2.6 s in one month. A year's prune costs about 50-80 ms.
   - No migration: an existing save works off its backlog in its next Junes. The data dictionary has the rule under *Old history summarised*.
   - Results: 391 to 197 MiB on CI's 2069 build. The old-code save goes to 176 MiB after the first prune and a `VACUUM`.
   - This is a deletion of current-state rows of people outside the state (ADR-0004 §7), not of a §6 history table.
5. **The prune runs in June, not December.** On CI's `research_heavy` runner, one month read 1,034-1,086 ms (twice the median) at `708099f`. A probe on CI timed the same months three ways: 907 ms as played, 515 ms with the periodic backup off, 572 ms with the prune off. The year's deletes and the backup's copy of the save, which follows each December's commit, shared one slow disk. In June (`PRUNE_MONTH = 5`) the spike went: 835 ms worst at x1.81 on `3870344`. Nothing reads the rows, so the month changes no result.
6. **No new indexes, no migration.** Every query the turn sends was checked with `EXPLAIN QUERY PLAN` on the 2069 save, and all were already indexed. The only scans were of small `*_record` tables and `llm_text`. An Alembic revision would also have collided with M42's and M40's migrations. A pruned-copy experiment showed table size does not change turn time, so retention is for size only.
7. **Not done, judged too risky or too small:**
   - caching `product_team` across the three phases that recompute it (its inputs change between them);
   - keeping a rival's whole decision across months when nothing changed (the inputs include the month's prices, shares and seeded draws, so "unchanged" is rare);
   - vectorising the person generator's draws (they interleave normals and uniforms per key, so one vector would change the numbers).
8. **CI readings** (runner-adjusted medians; raw, ratio and workloads in `docs/perf/m45.md`):
   - V6 `research_heavy` 2039: 430 ms before, 367 and 396 ms after (target 400).
   - V6 `full_integrator` 2039: 528 ms before, 399 and 404 ms after (target 400).
   - 2069 dynasty: 518 ms before, 434 and 417 ms after (target 500).
   - 2069 save: 391 MiB before, 197-198 MiB after (target 400 MB).
   - The weekly run on the final branch: WEEKLY_PLACEHOLDER
9. **The raw Holiday guard on slow runners (rule 3).** `test_m30_perf.py`'s 6 s Holiday year is raw (the PM's ruling keeps it raw). It fails on slow runners on main and on this branch alike: before M45, v6 10.4 s at x1.92 and v6i 6.1 s at x0.95; after, v6 9.3 s at x1.81 and v6i 8.0 s at x1.58. That is 4.7-5.1 s adjusted on this branch, against 5.4 and 6.4 s before. M45 makes Holiday faster, not slower; the measure is the CI-fix lane's.

## Follow-ups

- **The remaining costs of a 2039 month on CI** (`docs/perf/m45.md`):
  - the two commits' fsyncs (33 ms each on a slow runner's disk);
  - `run_markets` over 336 segments (about 150 ms; segments whose inputs did not change could keep last month's result, which needs an input key per segment);
  - the dataclass copies of the 149-field state (about 45 ms);
  - `product_team`, recomputed in three phases (40-57 ms);
  - candidate generation (30-60 ms).
- **The `full_integrator` 2039 save sits at the 400 ms line** (5.7-5.8 workloads). Any milestone that adds monthly work to that save will cross it. The `run_markets` lead above is the largest left.
- **The CI-fix lane** may want the Holiday year and the 1.0 s worst month runner-adjusted too (decision 9).
- **Retention for other unread rows of people outside the state:** departed staff's skill and reveal rows after a window. The Timeline and the people history screens read some of them, so this needs a screen-by-screen check first.
