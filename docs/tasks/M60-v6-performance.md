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

1. **Profile (sub-task 1).** `tools/profile_m60.py` times each of the turn's twelve phases, the v6 steps inside them (FX, banks and insurers, telecom, media, the markets) and the save's syncs, as the month is played through `repository.run_turn`, and a second pass gives each one's allocations (`tracemalloc`, peak bytes above the start). The saves:
   - 2039: the two V6 saves (`tools/v6_save.py`, `research_heavy` and `full_integrator`), January 2040 (M30's);
   - 2069: M37's dynasty save (`full_integrator`, children 2 and 5, 708 months), copied with `tools/profile_m60_v6_arm.py`, which gives the player the v6 industries as the M53-M55 e2e fixtures do: a mobile line with low- and mid-band licences, 2,500 towers and a 4G network; a chartered bank with 300,000 and 20,000 accounts and its banking line; a line selling half in Europe; a streaming line. The rival world already has 27 mobile, 16 fixed-broadband, 10 banking, 5 insurance, 9 streaming, 8 social and 11 games lines, the FX walk (1,457 marks) and 1,876 media draws;
   - 2100: M52's sandbox save (`tools/m52_save.py --seeds 1`), 432 companies.

   M45's table had whole months, not phases: 615 ms (2039 `full_integrator`) and 674 ms (2069) locally after M45, 399 and 417-483 ms runner-adjusted on CI. The phases now, locally (this container, runner x1.00-1.05), main against the branch:

   **2039 `full_integrator` (V6 extended), January 2040** (315 companies; local, means of 6-8 months; % of main's month)

   | Phase or step | main ms | % | branch ms | alloc MB (main) |
   |---|---:|---:|---:|---:|
   | run_turn (the month) | 1005 | 100% | 929 | 7.3 |
   | advance_turn | 643 | 64% | 561 | 6.9 |
   | db.repository.apply_turn_result | 252 | 25% | 257 | 0.7 |
   | sales_revenue_churn | 227 | 23% | 186 | 1.9 |
   | db.state_io.sync_state | 199 | 20% | 205 | 2.0 |
   | products.phases.run_markets | 105 | 10% | 112 | 1.0 |
   | event_director_requests | 91 | 9% | 75 | 1.4 |
   | market_and_macro_update | 83 | 8% | 43 | 0.4 |
   | rival_decisions | 75 | 7% | 83 | 0.7 |
   | people_updates | 67 | 7% | 68 | 2.4 |
   | media.phase.with_effects | 62 | 6% | 16 | 0.2 |
   | media.phase.demand_month | 48 | 5% | 5 | 0.0 |
   | financing | 30 | 3% | 35 | 0.9 |
   | db.repository._after_commit | 26 | 3% | 21 | 0.2 |
   | research_progress | 26 | 3% | 26 | 0.8 |
   | products.phases.brand_and_demand | 26 | 3% | 29 | 0.4 |

   Largest allocations (main): people_updates 2.4 MB, db.state_io._insert_reveals 2.3 MB, db.state_io.sync_state 2.0 MB, sales_revenue_churn 1.9 MB, event_director_requests 1.4 MB, db.state_io._sync_geo 1.3 MB

   **2069 dynasty, the player running the v6 industries (v6 arm)** (369 companies; local, means of 6-8 months; % of main's month)

   | Phase or step | main ms | % | branch ms | alloc MB (main) |
   |---|---:|---:|---:|---:|
   | run_turn (the month) | 1860 | 100% | 1058 | 7.3 |
   | advance_turn | 1455 | 78% | 642 | 6.6 |
   | sales_revenue_churn | 655 | 35% | 235 | 1.8 |
   | market_and_macro_update | 437 | 24% | 52 | 0.5 |
   | media.phase.with_effects | 429 | 23% | 17 | 0.2 |
   | media.phase.demand_month | 393 | 21% | 7 | 0.0 |
   | db.repository.apply_turn_result | 274 | 15% | 290 | 1.0 |
   | db.state_io.sync_state | 224 | 12% | 233 | 1.9 |
   | products.phases.run_markets | 112 | 6% | 134 | 0.9 |
   | rival_decisions | 108 | 6% | 99 | 0.9 |
   | event_director_requests | 92 | 5% | 89 | 1.4 |
   | people_updates | 50 | 3% | 51 | 1.9 |
   | media.phase.open_month | 45 | 2% | 4 | 0.0 |
   | financing | 43 | 2% | 44 | 0.9 |
   | world.phase.world_month | 33 | 2% | 34 | 0.7 |
   | products.phases.brand_and_demand | 32 | 2% | 31 | 0.4 |

   Largest allocations (main): db.state_io._insert_reveals 2.0 MB, people_updates 1.9 MB, db.state_io.sync_state 1.9 MB, sales_revenue_churn 1.8 MB, db.state_io._sync_geo 1.8 MB, db.world_io.sync_world 1.6 MB

   **2100 sandbox (M52, seed 1)** (432 companies; local, means of 6-8 months; % of main's month)

   | Phase or step | main ms | % | branch ms | alloc MB (main) |
   |---|---:|---:|---:|---:|
   | run_turn (the month) | 3755 | 100% | 1050 | 7.6 |
   | advance_turn | 3308 | 88% | 666 | 6.9 |
   | sales_revenue_churn | 1694 | 45% | 240 | 1.7 |
   | media.phase.with_effects | 1365 | 36% | 18 | 0.2 |
   | market_and_macro_update | 1227 | 33% | 55 | 0.5 |
   | media.phase.demand_month | 1183 | 32% | 8 | 0.0 |
   | db.repository.apply_turn_result | 357 | 10% | 312 | 1.2 |
   | db.state_io.sync_state | 261 | 7% | 240 | 2.3 |
   | media.phase.open_month | 124 | 3% | 7 | 0.0 |
   | products.phases.run_markets | 112 | 3% | 116 | 0.9 |
   | event_director_requests | 110 | 3% | 102 | 1.5 |
   | rival_decisions | 102 | 3% | 94 | 0.5 |
   | db.history.prune_candidates | 71 | 2% | 44 | 0.0 |
   | financing | 52 | 1% | 52 | 1.0 |
   | people_updates | 51 | 1% | 54 | 2.2 |
   | world.phase.world_month | 43 | 1% | 44 | 0.8 |

   Largest allocations (main): db.regulation_io.sync_regulation 2.8 MB, db.world_io.sync_world 2.3 MB, db.state_io.sync_state 2.3 MB, people_updates 2.2 MB, db.state_io._insert_reveals 2.1 MB, sales_revenue_churn 1.7 MB


2. **The one large cost was quadratic in the years (sub-task 2).** `media.demand.growth_factor` and `media.ads.spend_year_cents` (M55) compounded each month since January 2026 on every call, and each month's rate was found by scanning every world draw: about 790 ms of a 1,900 ms 2069 month and 2,550 of a 3,700 ms 2100 month. `tst.sim.compound.compounded` does the same multiplications in the same order, keeping each completed year's value keyed by the initial value, the start and every completed year's rate (so a rate drawn later never reuses a stale value); the draws are indexed once per tuple. Tested against the loop with Hypothesis (`tests/unit/test_m60_compound.py`).
3. **Smaller proportional steps (sub-tasks 2-3):** rivals' served customers per segment and region, regulators' largest shares and owners' regional revenue, and the finance and telecom growth rates are each built once per state, view or draws tuple, the same values summed in the same order (Python 3.12's `sum` is compensated, so lists are summed, never a running `+=`); `sync_finserv` encodes only the kinds whose tuples changed; `_write` reads a changed row's values from the row's dict; `from_inputs` keeps 512 input tuples (64): the v6 world's indexes evicted each other within a month (main with 512 is unchanged; the branch is about 10% faster at 2039 with it).
4. **Identical results: how it was checked.** `tools/profile_m60_digests.py` prints, month by month, M30's state digest and a digest of every row of every table. Main and the branch match on the 2039 `full_integrator` save (4 months), the 2069 save (4 months) and the 2069 v6-arm save (3 months, the player's bank, network and lines), after every change; the goldens, M30's state cache and the memo recompute tests pass.
5. **check-timing's late saves (sub-task 4).** A 2069 or 2100 save takes about an hour to build, longer than `check (timing)`'s 30 minutes, so `timing-saves.yml` builds them (`make timing-save-2069`, `make timing-save-2100`) after each push to main and keeps each in the Actions cache; `check (timing)` restores the newest its branch can read, and `tests/integration/test_m60_perf.py` times ten months of each (500 and 550 ms runner-adjusted). Without a save a guard skips. docs/ci.md has the details.

## Follow-ups

(filled in by the session)
