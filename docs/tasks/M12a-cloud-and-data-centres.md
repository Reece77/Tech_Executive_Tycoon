# M12a: Cloud, data centres and supply shocks (lane B)

**Goal:** compute becomes something a company can own. It can build general or GPU data centres in a region, run its own products on them for less than spot when they're well used, and sell spare capacity to other companies as Cloud and GPU hosting against AWS, Azure and Google. Component prices and allocation follow real history (the 2021 chip shortage, the 2023 GPU crunch), then seeded shocks, so owning capacity before a crunch pays off and building at the wrong time hurts.

**Spec sections:** §7.1 (Cloud and GPU hosting), §8 (value chain, sourcing), §9 (hyperscaler segment) · **ADRs:** 0002, 0003, 0004, 0013 (streams `supply` 26, `facility` 27, reserved), 0019 (§2 simplified facilities, §8 sell spare capacity, §9 supply shocks) · **Formulas:** `docs/formulas.md` §22 (all), with §11, §16, §19 and §20 · **Wireframes:** `docs/wireframes.md` (M12a screens) and `docs/wireframes/source/DataCentres.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M10d (`m10d-done`)

## Lane

- **Lane B.** It runs at the same time as M11 (lane A) in its own session and branch (`m12a-cloud`).
- **Merge order: M11 merges first.** Before merging M12a:
  1. merge `main` (with M11) into this branch;
  2. re-parent M12a's unmerged migrations onto `main`'s head;
  3. wire Cloud hosting features to `research.lead(state, company_id, "infrastructure")` from M11 (until then, use a lead of 0);
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

- **CU need** is hosting at index 1.0 / $1,000 (22.1's "÷ $1,000 × the index" read as ÷ ($1,000 × index)); GPU need does not move with the AI index, its price does.
- **Kinds and goods are data.** `facility.kinds` (`data_centre_general`, `data_centre_gpu`) name their input good (`server`, `gpu` in `components_history.yaml`) and output good (`compute.goods`). Shared lifecycle in `tst/sim/facilities/lifecycle.py`; goods in `goods.py`. `player_companies(state)` added (ADR-0020 1); the cloud cap and the Cloud product's quality apply to the player's companies only, as rivals' capacity is abstract.
- **History** is anchor months with geometric interpolation (`components_history.yaml`). GPU 2019-2022 continues -10% a year and 2024-2025 too (22.4 does not say). After a shock its rise fades over as many months as it ran.
- **Accounts.** Depreciation (`6700`) is a cost of revenue with hosting; data centres' operating cost posts to `6300_compute` as "Data centre operations". Take-or-pay posts to general and administrative. The cash flow counts `6700` and `1510` with investing.
- **Cloud market.** One market in general CU; each segment's customer buys a fixed number of CU (`units_per_customer`); GPU spare sells at its spot value. Cloud hosting cannot be created as a product; the Infrastructure screen's "Sell spare capacity" starts it (live at once, reference prices, energy as create_product). Rival startups are not founded in it. CoreWeave's "GPU only" is its segments (enterprise, hyperscalers).
- **Outside my namespaces in balance.yaml:** `products.seller_rate.hyperscalers` (0.03) and `rivals.function_mix.cloud_hosting` (the loader requires one per sales segment and per category).
- **Outages** are rolled in phase 6 after the month's costs; hosted products lose `customers_share` (0.5) of the critical `customers_pct` cap (8%), cloud customers' churn x3 comes off at once; one critical event per month however many sites fail.
- **API naming.** Facility sizes are `units` (the hidden-field guard bans `capacity`, 11.13).
- **Cloud incumbents' cash** (AWS 120 months, Rackspace 60) and cost (55% of reference): with 24 and 12 months and 65% they went bankrupt in price wars.
- **22.7 values** (tools/m12a_targets.py, 10 seeds): T2 at 80% 0.62, at 40% 1.23 (build in January 2016, server index 0.61; 2010 prices give 0.81 at 80%). T3 9/10 (staffed 2,000 CU, $50,000 a month of marketing, prices 0.9 x reference). T4 server +30%, GPU +60%; AI margin gap +15.7 points at 0.45 x reference price (own 76.7%, spot 61.1%; own compute $432 a CU, spot $723) after tuning the GPU table to $20,000 capex and $200 power (Reece, 2026-11-02); +7.0 at reference prices, the most any table allows while a GPU data centre at 40% use costs at least 1.2 x spot (worst build month 1.22). T3 10/10 after the key change. T5 8/10. T6 1.05 a year at coverage 0.5, 0.17 at full coverage (base 0.016).
- **Earlier guards (reported, not tuned).** Before the ADR-0013 amendment the cloud incumbents moved M10 covenants (0.7, <= 0.6), M8 support (1.056, >= 1.08) and T5. With stable keys those two pass; still failing: T2 wins (steady 9/10, <= 6; main 6), T5 bootstrap-frugal bankrupt 10% (20-50%; main 20%), and the M5 living market (1 category without a launch and 0.95 launches, want 0 and >= 1.0; main passes). The same values come out with main's incumbents.yaml and entrants.yaml, so they are the one-time reseed of the key change, not the cloud rivals or facilities. The cloud incumbents shift later rival startups' company ids, which key stream `rivals`. With the main data files on this code the value is main's 20%; seeds 11-40 give 2/30 on both main and this branch.

## Follow-ups

- Reece: target 4's margin gap needs a design decision (the AI index's 2023 level, the GPU table's power cost, or the target).
- Reece: T5 bootstrap-frugal bankrupt sits at its band's floor by seed luck (about 10% over 40 seeds on main); a re-band or a strategy change is a product decision.
- Data centres past their life keep running at operating cost: refurbishment or retirement is open.
- Rivals' physical capacity, power markets, regional risk fields in regions.yaml (ADR-0020 5) and a separate GPU hosting market are not built.
- Wire `research.lead(state, company_id, "infrastructure")` into `facilities.cloud.infrastructure_lead` at the merge with M11.
