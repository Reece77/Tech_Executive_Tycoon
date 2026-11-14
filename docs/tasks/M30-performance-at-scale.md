# M30: Performance at scale (v3.5, lane B)

**Goal:** a 30-year campaign stays quick to play to the end. Late-game turns, Holiday, loading a save and opening the big screens should feel instant on Reece's PC, with **identical results**: same seed and decisions, same game.

**Formulas:** none new · **ADRs:** 0002, 0004 · **Roadmap:** `docs/roadmap.md` Phase 2 ("performance") · **Depends on:** M28 (`m28-done`) · **Lane:** B, alongside M27b (lane A) and M31 (lane C)

## Lane

- Its own session and branch (`m30-performance`) from `main`.
- **M30 may change any engine or API code to make it faster,** but **never a result.**
  - Every change must keep the golden snapshots byte-identical.
  - It must also keep a new **long state-cache check** identical (sub-task 1).
- No balance key changes. No new dependencies (ADR-0001); profile with the standard library (`cProfile`, `tracemalloc`).
- M27b and M31 are building at the same time. Where a speed-up needs a change in a file they own, make it in a small, separate commit and name it in the pull request. Merge `main` often.
- **CLAUDE.md §9's decision rules apply** (rule 6 especially).

## Sub-tasks (commit after each)

1. **Measure first.**
   - **A benchmark script**, `tools/bench.py`. It writes a table to `docs/perf/` and does not fail. It reports:
     - median and 95th-percentile turn time for three saves at January 2039: a full integrator (M23b's), a large software group, and a world with every M28 chain company;
     - Holiday for 12 months from each;
     - save size on disk, and load and cold-start time;
     - the 95th-percentile API response for the ten largest screens (Overview, People, Products, Market, Rivals, World news, Group, Fabs, Mines, Automation).
   - **A long state-cache check.** It hashes the full state after each of 360 turns for seeds 1–3 under three strategies, and saves the hashes as a fixture. It is a nightly test from now on.
   - Record the baseline numbers in this brief before optimising.
2. **The turn.** Profile the 2039 turns and make the slowest steps proportional to what changes:
   - cache derived values that only change when their inputs do (keyed on the inputs, checked against a recompute in a debug test);
   - avoid rebuilding whole collections each turn;
   - avoid repeated loader work;
   - batch the database writes.
   - **Targets:** median 2039 turn at most **400 ms**, and no turn over **1.0 s** (the existing budget), on the CI runner, for all three saves.
3. **Holiday.** 12 months of Holiday from a 2039 save in at most **6 s**, with any per-turn work outside the engine (snapshots, inbox writes) batched.
4. **Saves.**
   - Old log, news and snapshot rows past a retention window are summarised, not lost. Monthly snapshots older than 5 years become quarterly; World news older than 3 years keeps only major items. The Rivals history and the founder's archive keep everything they show.
   - Indexes are added where the API's queries need them.
   - **Targets:** a 2039 save at most **250 MB**, and loading it in at most **3 s**.
   - A migration and the data dictionary for any schema change.
5. **The API and the screens.**
   - **API:** the ten largest screens' endpoints at most **300 ms** at the 95th percentile on a 2039 save, using pagination, server-side filtering and sorting for the big tables, and cached read models invalidated by turn.
   - **Front end:** virtualised rows for long tables (TanStack Table with TanStack Virtual if already present, otherwise windowing in our own table component; no new dependency without asking), and no full re-fetch of every query after an action.
6. **Close-out.**
   - Run the benchmark again and record before and after in `docs/perf/`.
   - Run `make check-timing` alone.
   - Leave the long state-cache check identical to sub-task 1's fixture.
   - CHANGELOG and README index row.

## Acceptance criteria

- [ ] Golden snapshots byte-identical, and the long state-cache check (360 turns, seeds 1–3, three strategies) identical to its fixture made before any change.
- [ ] Sub-tasks 2–5's targets met on the CI runner, with before and after numbers recorded, or the misses reported with their profile (rule 6).
- [ ] No balance key changed and no new dependency added.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m30-done`.

## Manual check (Reece)

In your campaign, after merging: Holiday a year in the 2030s and time it, then open World news and People.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
