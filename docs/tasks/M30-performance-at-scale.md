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

## Baseline and results (sub-tasks 1 and 6)

`tools/bench.py run` on this container (4 CPUs, Linux), three January 2039 saves built through the save path (`tools/bench.py build`): **integrator** (M23b's full_integrator, 131 staff), **software** (the v2 integrator, the largest software company the scripts make: 190+ staff and its own data centres; 59,000 people in its file) and **world** (a do-nothing player with $50B in the living world from 2026: 54 chain companies, 313 facilities). Tables: `docs/perf/baseline.md` (main's code, 42a8037 plus the tools) and `docs/perf/after.md`. Run-to-run spread on this machine is about ±15%.

| Save | Turn median ms | Turn p95 ms | Holiday 12 months s | Size MB | Load s |
|---|---|---|---|---|---|
| integrator | 768 → 375-470 | 1,248 → 721-821 | 9.9 → 5.4-5.9 | 157.5 → 158.2 | 0.38 → 0.48 |
| software | 1,713 → 646-724 | 2,333 → 1,381-1,457 | 20.8 → 9.0-9.3 | 344.3 → 345.9 | 0.74 → 0.58 |
| world | 271 → 232-239 | 363 → 378 | 3.6 → 3.3 | 18.2 → 18.4 | 0.13 → 0.13 |

Screens (the ten largest's 15 endpoints, warm 95th percentile): worst 387 ms (People, software) → 76 ms; Overview 189 → 31, Rivals 197 → 31, Mines 200 → 42, Group 170 → 9, Finance summary 175 → 14. The first request after a month is 9-306 ms (World news's first build of its feed is the slowest).

The digests of the full state after 12 turns and after the Holiday are identical before and after on all three saves; the long state-cache check (nine runs of 360 months) and the golden snapshots are unchanged.

**Targets.**
- Integrator and world: met here (median under 400 ms, no turn over 1.0 s, Holiday under 6 s), the integrator at the edge of the machine's spread. On CI's runner `tests/integration/test_m30_perf.py` reads them each week on V6's two 2039 saves (weekly-v6, weekly-v6-integrator).
- CI's runner (`test_m30_perf.py`, 12 months from V6's saves after December 2039, so the months are 2040's; weekly run 43621774091 at a74133c): research_heavy (104 staff) median 332 ms, at most 969 ms, Holiday 4.8 s: **met**. full_integrator (133 staff) median 420 ms, at most 1,432 ms, Holiday 6.3 s: **missed**. The 1,432 ms month was the yearly backup copying the 160 MB save (about 1.0 s on that runner); it now runs beside the next month (Decisions made), which here takes the integrator's worst month from 821 to 508 ms and the software save's from 1,457 to 817-883 ms with identical digests. A second weekly run after that change and main's M27b (43640076663 at a4c4c65): research_heavy median 353 ms, at most 583 ms, Holiday 4.4 s (**met**); full_integrator median 573 ms, at most 603 ms (the backup month no longer stands out), Holiday 7.2 s: the median and Holiday **missed** (rule 6). The same save built here with the same code (`tools/v6_save.py ... --strategy full_integrator`, 133 staff) plays its months in 406-447 ms, as the first run's 420 ms on CI did, so the two CI readings differ by the runner, not the code. Profile of a month on that save (cProfile, 4 months): the engine 500 ms of 820 profiled, of which the 225 market segments 100 ms, people updates 85 ms (candidate generation 70 ms of seeded draws), event triggers 100 ms, rivals 40 ms, the world 25 ms; writing the state 230 ms (updates of changed rows 50 ms, new people and records 25 ms); each is proportional to what changes. What would remain is a lighter month for a 2040 group of 130 staff and 60 products: a brief of its own (follow-ups).
- After main's M28r (PM, 2026-11-14: V6 full_integrator's budget handed to M30), weekly run 43653809923 at 27f9029 with a profiling step (`tools/m30_profile.py`, artifact `m30-profile`): full_integrator (129 staff) median **439 ms**, at most 911 ms, Holiday **5.4 s**; V6's own guard 452 ms against its 1,000 ms (main read about 1,100 ms); research_heavy 378 ms, at most 598 ms, Holiday 4.7 s. The profiling step's 12 months: median 476 ms. Here, the same save: 410-450 ms. Profile of a month (real time, about half the profiled): writing the state 105 ms (about 8,000 changed rows: knowledge narrowing 4,500, skills 1,800, segments 600, relationships 460), the 225 market segments 50 ms, people 38 ms, candidate generation 28 ms (seeded draws), the post-commit event and report texts 12 ms, two commits 17 ms each, about 590 copies of the 149-field state 20 ms. No step is out of proportion to what changes; schema lookups are now kept per session; the identical-result changes left (a faster copy of the state, tuple building in bulk updates) are worth about 10-15 ms more, short of the 40 ms the median needs on CI. Stopped and reported (rule 6); the PM ruled to merge with the miss recorded and handed to M35 (Decisions made).
- Software: **missed** (rule 6), median 650-720 ms, its yearly backup month 1.4 s, Holiday 9 s. Profile, a month: writing the state 200 ms, of which about 90 ms is inserting the ~330 candidates its scripts' searches bring each month (people and their 45 attribute rows, knowledge records) into tables of 1.5-2 million rows; generating those candidates 130 ms (seeded draws, kept as they are so results stay identical); the backup month copies 344 MB. The work is proportional to what changes; what remains is the script's hiring volume.
- Save size: integrator and world met; software **missed** at 344 MB: 95% of the file is the attributes and records of 57,000 candidates who expired unhired, which no retention rule in this brief covers (Reece, 2026-11-14: report it, follow-up below). Load is 0.6 s or less everywhere.

## Decisions made

- **The fixture follows main:** it was recorded on main 42a8037 before any M30 change, and again on main after M27b (5e5095b) and after M31 (4bc50f0) merged (each adds state), in a worktree of main with only the measuring tool copied in; this branch gave identical digests for all nine runs of 360 months each time (and plays them in 586 s against main's 1,655 s).
- **The long state-cache check** (`tst.balance.m30`, `tests/fixtures/m30_state_hashes.json`, nightly `tests/balance/test_m30_state_cache.py`): the engine in memory (`tst.balance.game`), full_integrator, integrator and research_heavy on seeds 1-3, 360 months; a canonical digest of the whole state and the ledger balances after each month (dataclass fields in order, tuples in order, sets and mappings sorted, floats exact: recorded and checked on Linux). The persistence path is covered by the golden snapshots (with `TST_STATE_CACHE_CHECK`) and the bench's digests. acquirer, the brief's natural "software group", ends its game before 2039 on seeds 1-3, so the v2 integrator took its place in the check and the bench (no surviving software script forms a group of companies).
- **Memos** (`tst.sim.state`): `derived` keeps values on one state (company and ownership indexes, group members); `from_inputs`/`from_all` keep them on the immutable input tuples they are computed from (staff, employment, person states, era arrivals, org views, rules in force, shown teams), so a state made by `replace` that keeps those tuples keeps them. `MEMO_CHECK` recomputes and compares every remembered value (`tests/unit/test_m30_memo.py`, 30 months of full_integrator). `repository.read_memo` keeps a read's value (the ledger sums, the news archive) until the save's next commit.
- **Garbage collection:** after each committed month the young generations are collected and what is alive is frozen (`repository.settle_memory`): full passes over 400,000 objects cost 150-500 ms at random moments. Measured over 36 months: memory flat at 204 MB; about 300 objects a month stay frozen as uncollected cycles.
- **Bulk writes:** new people, records, candidates and cities go in one executemany a table from plain rows; plain-column bulk UPDATEs go to the SQLite driver with the same SQL (Float values bound as `float()`, as SQLAlchemy does; a test compares the stored rows and types); world records rewrite only what changed after items dropped from the front.
- **Retention** (Reece, 2026-11-14: thin, and ADR-0004 §6 amended): `balance.yaml` `retention` (new keys; no existing key changed): snapshots past 60 months keep quarter ends, each company's first year (an achievement reads it) and every record high of `arr_cents` and `headcount` (the Hall of Fame's peaks, which stay exact); log items past 60 months become yearly counts; World news keeps the engine's 36-month window and archives the `major_news` kinds deal, spinoff, bid, failure, close and china (Reece, 2026-11-14). Migration `0054_m30` thins an existing save once.
- **Indexes:** `ix_turn_snapshot_company_turn`, `ix_candidate_status`, `ix_person_is_founder` (the screens' and loads' scans; the rest of their queries were already indexed or are whole-table by design).
- **API:** World news is paged (`offset`, `limit` 200 a page, `total`); other screens were already filtered on the server and are now cheap enough warm. **Front end:** tables over 200 rows scroll in their panel and render only the rows near the view (our own windowing in `DataTable`; no new dependency); Advance no longer refetches the Overview its response carried. Actions still refetch the screen's mounted queries only (TanStack's default).
- **Backups beside the next month:** the periodic backup (every 12 months, ADR-0004 §5) runs on its own non-daemon thread after the month's commit, with its own SQLite connection (a consistent snapshot of the committed month in WAL mode; the backup API releases the GIL while it copies). Listing backups, Back up, restore, duplicate, delete and a pre-migration backup wait for it; the interpreter finishes it before exiting; a failure is logged as before. The backup's bytes are the same.
- **tools/v6_save.py** reloads through the state cache after each scripted action: identical saves (state and balances compared), a 2039 build in about 10 minutes instead of 2 hours.

- **The full_integrator 2039 save's median (PM ruling, 2026-11-15): 439 ms on CI against M30's 400 ms target, recorded and handed to M35.** The save is V6's (`tools/v6_save.py --strategy full_integrator`, 129 staff after December 2039, the months measured are 2040's).
  - Before (main's code): this machine's January 2039 save 768 ms median, 1,248 ms p95, Holiday 9.9 s (`docs/perf/baseline.md`); CI's V6 guard on main read 677-908 ms before M28r and about 1,100 ms after it (PM), over its 1,000 ms budget.
  - After (this branch with M28r, M31, M36 and M27b merged): CI weekly runs 43653809923 median **439 ms**, at most 911 ms, Holiday 5.4 s, V6 guard 452 ms; 43666750178 (a faster runner) median 320 ms, at most 477 ms, Holiday 4.0 s, V6 guard 334 ms. Here 410-450 ms. The same code reads about 1.6 times apart between CI runners (research_heavy: 378 ms in one run, 514 ms in the next).
  - Still slowest in its CI profile (`tools/m30_profile.py`, 6 months, run 43666750178): the two SQLite commits a month, about 70 ms each on the runner's disk (140 ms of a profiled 740 ms month; 17 ms each here), then the driver's executemany of about 8,000 changed rows (45 ms), dataclass copies of the state and its records (65 ms profiled; 590 copies of the 149-field state), the 225 market segments (90 ms profiled), candidate generation (seeded draws, 44 ms profiled) and the post-commit event texts (39 ms profiled).
  - Guard while it waits: `test_m30_perf.py` holds that save's median to 500 ms (`TST_M30_MEDIAN_MS=500` in `weekly-v6-integrator`); every other save keeps 400 ms, and the 1.0 s worst month and `test_v6_perf`'s 1,000 ms stay. Not in `known_misses.py`.
  - **How the 500 ms guard measures (product manager, 2026-11-17):** on both V6 saves (`TST_M30_MEDIAN_MS=500` in `weekly-v6` and `weekly-v6-integrator`) it compares the runner-adjusted median, the raw median divided by M35a's runner ratio (`tests/calibration.py`: the workload's median over its 70 ms reference, timed right after the 12 months), against 500 ms. The report prints the raw median, the ratio and the adjusted median. A save without the variable keeps the raw 400 ms; the 1.0 s worst month, the 6 s Holiday year and `test_v6_perf`'s 1,000 ms stay raw.

## Follow-ups
- **M35 (v4 balance and polish) owns the full_integrator 2039 save's 400 ms median** (PM, 2026-11-15): re-measure after M32-M34 add power, equipment and regulation, then lower the guard from 500 ms. Leads from the CI profile: the commits' cost on CI's disk (each month's WAL pages; a checkpoint outside the turn, as the backup now is, kept identical), a lighter month for candidates (generated in full when interviewed) and segment updates for markets whose inputs changed.

- Expired candidates' data: after a window, keep their person and candidate rows (names for History) and drop their attribute and knowledge rows: about 95% of a hiring-heavy 2039 save (344 MB). A design decision for a brief.
- History timeline: `GET /history/timeline` returns 500 on the 2039 integrator save on main and on this branch (`history_views._describe` builds every action's text eagerly; one payload has `salary_cents: null`, and `int(None)` fails). One-line fix: `int(p.get("salary_cents") or 0)`.
- The full integrator's 2040 month on CI's slower runners (573 ms median, Holiday 7.2 s): a lighter month (candidates generated in full only when interviewed, segment updates for markets whose inputs changed) would bring it under 400 ms on every runner.
- The software save's turn: what remains is writing and generating about 330 candidates a month; a lighter candidate record (generated in full when interviewed) would make it proportional to what the player looks at.
- Two balance guards fail on main as on this branch (rule 3; results here are identical to main's): weekly-v5's `V5.cats research_heavy` (main's weekly run 43605652584 at 42a8037 failed the same job) and the nightly `test_38_5_targets` target 3 (seed 3 two nodes behind, 5.1%), which the M28r fix running now addresses (its 41.2 commit: 5.07% → 4.09%).
- A VACUUM when thinning frees much space (SQLite keeps the pages): small today (snapshots and logs are a few MB).
