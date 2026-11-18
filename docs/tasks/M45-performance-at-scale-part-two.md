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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
