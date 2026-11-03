# M12a: Cloud, data centres and supply shocks (lane B)

**Goal:** compute becomes something a company can own. It can build general or GPU data centres in a region, run its own products on them for less than spot when they're well used, and sell spare capacity to other companies as Cloud and GPU hosting against AWS, Azure and Google. Component prices and allocation follow real history (the 2021 chip shortage, the 2023 GPU crunch), then seeded shocks, so owning capacity before a crunch pays off and building at the wrong time hurts.

**Spec sections:** §7.1 (Cloud and GPU hosting), §8 (value chain, sourcing), §9 (hyperscaler segment) · **ADRs:** 0002, 0003, 0004, 0013 (streams `supply` 26, `facility` 27, reserved), 0019 (§2 simplified facilities, §8 sell spare capacity, §9 supply shocks) · **Formulas:** `docs/formulas.md` §22 (all), with §11, §16, §19 and §20 · **Wireframes:** `docs/wireframes.md` (M12a screens) and `docs/wireframes/source/DataCentres.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M10d (`m10d-done`)

## Lane

- **Lane B.** It runs at the same time as M11 (lane A) in its own session and branch (`m12a-cloud`).
- **Merge order: M11 merges first.** Before merging M12a:
  1. merge `main` (with M11) into this branch;
  2. re-parent M12a's unmerged migrations onto `main`'s head;
  3. wire Cloud hosting features to `tst.sim.research.levels.lead(state, company_id, "infrastructure")` from M11 (until then, use a lead of 0);
  4. regenerate golden snapshots, with both milestones' reasons in CHANGELOG;
  5. re-run all guards on the combined code. If an M11 target moves, report it rather than tune M11's keys.
- **M12a owns:**
  - new `backend/tst/sim/facilities/` (data centres, utilization, reliability, outages, components, contracts);
  - the compute-allocation step in the hosting cost path;
  - `backend/data/components_history.yaml`, the `cloud_hosting` category and the `hyperscalers` segment appended to `categories.yaml`, cloud incumbents and entrants appended to `incumbents.yaml` and `entrants.yaml`;
  - `accounts.yaml` (depreciation accounts) and the outage event templates;
  - screens: a new **Infrastructure** screen (data centres, component indexes, contracts) and the Finance statement lines for depreciation.
- **M12a must not edit:** `backend/tst/sim/research/`, `tech_frontier.yaml`, `eras.yaml`, the AI growth curve or the Research screen. Those belong to M11.
- **Shared files:**
  - `balance.yaml`: add only `facility.*`, `supply.*` and `compute.*`;
  - `docs/formulas.md`: notes in §22 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.

## Design for v3 (ADR-0020)

- **Generic facility model.** Build data centres as one **kind** of a generic facility model (kind, owner `company_id`, region and city, capacity unit, inputs, output good, utilization, staff role and ratio, reliability, capex and depreciation, operating cost, status). Kind-specific rules go in a small per-kind module; the build, depreciate, staff, utilize and close lifecycle is shared. M12b adds assembly plants as another kind; v3 adds mines, refineries, wafer plants and fabs.
- **Market goods.** The server and GPU component indexes are **goods** in one market-good model (key, unit, history-then-seeded index, allocation, spot and contract with take-or-pay) that v3 extends to commodities.
- **No single-company assumption.** Every new function takes a `company_id`; use `player_companies(state)` (add it if missing) wherever "the player" is meant.

## Out of scope

Hardware, devices, chips and assembly plants (M12b). Rivals' physical capacity (abstract in M12a). Power markets and carbon. Owning a foundry (v3).

## Sub-tasks (commit after each)

1. **Data and formula tests:**
   - `components_history.yaml` (indexes and allocation to 2025), `facility.*`, `supply.*`, `compute.*` keys;
   - the `cloud_hosting` category and `hyperscalers` segment; cloud incumbents and entrants (Google Cloud Apr 2012, CoreWeave Jan 2019); the new accounts;
   - outage templates;
   - every §22.8 worked example as a unit test; stream rows moved into ADR-0013's main table.
2. **Compute units and spot** (§22.1): products' CU needs, general and GPU; spot hosting unchanged.
   - **Test:** a company with no data centre posts exactly the same compute costs as before (golden snapshots unchanged by this sub-task).
3. **Data centres** (§22.2):
   - the build action, capex during the build, depreciation from completion, operating costs, staff coverage and reliability;
   - own products served first by region and neighbour; close or sell;
   - migration and data dictionary;
   - **property tests:** the ledger balances with capex and depreciation, and book value never goes below 0.
4. **Components and shocks** (§22.4): indexes and allocation from history, seeded AR(1) and shocks after 2025 on stream `supply`, allocation delays, contracts with take-or-pay. A seeded test of the shocks, and the history values on every seed.
5. **Cloud hosting** (§22.3) and **outages** (§22.5):
   - selling spare CU with the capacity cap, reliability as quality, features from the infrastructure lead;
   - hyperscaler segment; cloud incumbents and entrants;
   - outages on stream `facility` as critical events.
   - Tests for each.
6. **API, CLI and screens** (per the wireframes):
   - **Infrastructure screen:** data centres with capacity, own and sold use, reliability, staff coverage, cost per CU against spot, book value and build progress; component indexes and allocation; contracts; Build and Contract dialogs.
   - **Finance:** depreciation and capex in the statements.
   - **Market:** the Cloud hosting market.
   - **Supporting work:** glossary entries and driver breakdowns for the new numbers; History entries.
   - **CLI:** `tst facilities`, `tst build-dc --region --kind --cu`, `tst contract --index --months --cu`.
   - **Hidden values:** extend the hidden-value test to the future index path.
7. **Balance, merge and e2e:**
   - The §22.7 targets, printed and recorded. Tune only M12a's keys.
   - The merge steps above, after M11 is on `main`.
   - **Playwright:**
     - (a) build a general data centre and see it complete and take your products' compute;
     - (b) sell spare capacity and see Cloud hosting customers arrive;
     - (c) a scripted understaffed data centre has an outage event.
   - **Close-out:** CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §22.8 worked example passes as a test.
- [ ] A company that never builds posts exactly the same compute costs as before.
- [ ] Data centres build, depreciate, serve own products first and sell spare capacity within the cap; the ledger balances (property test).
- [ ] Component history matches the table on every seed; shocks after 2025 are seeded and reproducible; no API response shows a future value.
- [ ] Outages follow reliability and arrive as critical events.
- [ ] §22.7 targets 2–6 met (printed, values recorded); earlier targets unchanged.
- [ ] Merged after M11, with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m12a-done`.

## Manual check (Reece, after merge)

On a stage-3 save, build a 500-CU general data centre in your home region and watch its cost per CU against spot as your products fill it. Then sell the spare. In an AI game, build GPU capacity in 2021 and compare 2023 with a run that stayed on spot.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
