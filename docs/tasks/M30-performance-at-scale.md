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
- Software: **missed** (rule 6), median 650-720 ms, its yearly backup month 1.4 s, Holiday 9 s. Profile, a month: writing the state 200 ms, of which about 90 ms is inserting the ~330 candidates its scripts' searches bring each month (people and their 45 attribute rows, knowledge records) into tables of 1.5-2 million rows; generating those candidates 130 ms (seeded draws, kept as they are so results stay identical); the backup month copies 344 MB. The work is proportional to what changes; what remains is the script's hiring volume.
- Save size: integrator and world met; software **missed** at 344 MB: 95% of the file is the attributes and records of 57,000 candidates who expired unhired, which no retention rule in this brief covers (Reece, 2026-11-14: report it, follow-up below). Load is 0.6 s or less everywhere.

## Decisions made

- **The long state-cache check** (`tst.balance.m30`, `tests/fixtures/m30_state_hashes.json`, nightly `tests/balance/test_m30_state_cache.py`): the engine in memory (`tst.balance.game`), full_integrator, integrator and research_heavy on seeds 1-3, 360 months; a canonical digest of the whole state and the ledger balances after each month (dataclass fields in order, tuples in order, sets and mappings sorted, floats exact: recorded and checked on Linux). The persistence path is covered by the golden snapshots (with `TST_STATE_CACHE_CHECK`) and the bench's digests. acquirer, the brief's natural "software group", ends its game before 2039 on seeds 1-3, so the v2 integrator took its place in the check and the bench (no surviving software script forms a group of companies).
- **Memos** (`tst.sim.state`): `derived` keeps values on one state (company and ownership indexes, group members); `from_inputs`/`from_all` keep them on the immutable input tuples they are computed from (staff, employment, person states, era arrivals, org views, rules in force, shown teams), so a state made by `replace` that keeps those tuples keeps them. `MEMO_CHECK` recomputes and compares every remembered value (`tests/unit/test_m30_memo.py`, 30 months of full_integrator). `repository.read_memo` keeps a read's value (the ledger sums, the news archive) until the save's next commit.
- **Garbage collection:** after each committed month the young generations are collected and what is alive is frozen (`repository.settle_memory`): full passes over 400,000 objects cost 150-500 ms at random moments. Measured over 36 months: memory flat at 204 MB; about 300 objects a month stay frozen as uncollected cycles.
- **Bulk writes:** new people, records, candidates and cities go in one executemany a table from plain rows; plain-column bulk UPDATEs go to the SQLite driver with the same SQL (Float values bound as `float()`, as SQLAlchemy does; a test compares the stored rows and types); world records rewrite only what changed after items dropped from the front.
- **Retention** (Reece, 2026-11-14: thin, and ADR-0004 §6 amended): `balance.yaml` `retention` (new keys; no existing key changed): snapshots past 60 months keep quarter ends, each company's first year (an achievement reads it) and every record high of `arr_cents` and `headcount` (the Hall of Fame's peaks, which stay exact); log items past 60 months become yearly counts; World news keeps the engine's 36-month window and archives the `major_news` kinds deal, spinoff, bid, failure, close and china (Reece, 2026-11-14). Migration `0051_m30` thins an existing save once.
- **Indexes:** `ix_turn_snapshot_company_turn`, `ix_candidate_status`, `ix_person_is_founder` (the screens' and loads' scans; the rest of their queries were already indexed or are whole-table by design).
- **API:** World news is paged (`offset`, `limit` 200 a page, `total`); other screens were already filtered on the server and are now cheap enough warm. **Front end:** tables over 200 rows scroll in their panel and render only the rows near the view (our own windowing in `DataTable`; no new dependency); Advance no longer refetches the Overview its response carried. Actions still refetch the screen's mounted queries only (TanStack's default).
- **tools/v6_save.py** reloads through the state cache after each scripted action: identical saves (state and balances compared), a 2039 build in about 10 minutes instead of 2 hours.

## Follow-ups

- Expired candidates' data: after a window, keep their person and candidate rows (names for History) and drop their attribute and knowledge rows: about 95% of a hiring-heavy 2039 save (344 MB). A design decision for a brief.
- History timeline: `GET /history/timeline` returns 500 on the 2039 integrator save on main and on this branch (`history_views._describe` builds every action's text eagerly; one payload has `salary_cents: null`, and `int(None)` fails). One-line fix: `int(p.get("salary_cents") or 0)`.
- The software save's turn: what remains is writing and generating about 330 candidates a month; a lighter candidate record (generated in full when interviewed) would make it proportional to what the player looks at.
- A VACUUM when thinning frees much space (SQLite keeps the pages): small today (snapshots and logs are a few MB).
