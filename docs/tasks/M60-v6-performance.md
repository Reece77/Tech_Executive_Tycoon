# M60: v6 performance (lane A)

**Goal:** the bigger v6 world plays as fast as v5 did, with identical results: a 2039 month within 400 ms, a 2069 month within 500 ms and a 2100 sandbox month within 550 ms, each runner-adjusted.

**Precedents:** M30 and M45 (`docs/tasks/M30-performance-at-scale.md`, `M45-performance-at-scale-part-two.md`): profile, then make the slow step proportional to what changes, with identical results · **Known misses owned here:** `M37.2069_month` (535 ms adjusted on M46, bound 550) and `M52.2100_month` (610 ms adjusted on CI, bound 650) · **Depends on:** `m57r-a-done`, `m57r-b-done` · **Lane:** A, alongside M50b (lane B) and M57 (lane C)

## Rules

- **Identical results:** the state cache, golden snapshots, the M45 and M52 fixtures and the `determinism` digests are unchanged. A speed-up that changes one hash is a bug, not a re-record.
- No test or budget loosened; no job limit lengthened (CLAUDE.md §5).
- CLAUDE.md §9's decision rules apply, rule 6 above all.

## Lane

- Its own session, in its **own clone or worktree**, on branch `m60-perf` from `main`.
- **Owns:** the internals of slow phases (caches, indexes, incremental updates) wherever the profile points, the timing tests and their budgets' readings, `tools/profile_*`.
- **Must not edit** data (`backend/data/**`) or balance keys. M57 tunes those.
- Conflicts are likely in `tst/sim/**` with M57's tuning and M50b's start code: merge `main` often, and re-prove identical results after each merge.

## Sub-tasks (commit after each)

1. **Profile:** the 2039 saves (M30's), a 2069 dynasty save and a 2100 sandbox save, each with the v6 industries active (telecom, banks, insurers, media titles, currencies). Record the top 15 phases by time and by allocations, against M45's table, in "Decisions made".
2. **Make the slow steps proportional:** for each phase over 5% of a late month, work in proportion to what changed this month (dirty sets, per-region indexes, cached totals invalidated by the entities they sum). Expect the v6 phases first: FX translation over every regional line, the ad market's impressions, banks' and insurers' monthly books, telecom networks, and the rival count after 2069.
3. **Saving and loading:** per-turn saving writes only changed rows (M45's approach) for the v6 tables.
4. **Guards:**
   - `make check-timing` gains a 2069 v6 save and the 2100 sandbox save, with budgets of 500 ms and 550 ms (runner-adjusted as M45 measured);
   - the 2039 saves stay at 400 ms;
   - the two known-miss rows close.
5. **Close-out:**
   - the before-and-after table in the brief;
   - remove the two rows from `known_misses.py`. This brief authorises that edit; tell M57's session if it is still running;
   - CHANGELOG;
   - merge with `Milestone-Tag: m60-done` and confirm the tag.

## Acceptance criteria

- [ ] Identical results everywhere (state cache, golden snapshots, fixtures, digests).
- [ ] 2039 ≤ 400 ms, 2069 ≤ 500 ms, 2100 ≤ 550 ms a month (runner-adjusted, alone).
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged with `Milestone-Tag: m60-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
