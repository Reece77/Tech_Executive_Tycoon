# M38: Electric vehicles (v5, lane C)

**Goal:** cars join the game on the chain the player already owns. Vehicles become a category family. Battery cells are a market good, or the output of the player's own cell plants fed by its lithium. The car runs a platform with software revenue. Autonomy is a research path with regulatory approval. Charging networks, subsidies and tariffs shape regional markets. Tesla, BYD and the incumbents follow history to 2025.

**Formulas:** `docs/formulas.md` §49 (all), with §17, §20, §21, §26, §33, §36, §39, §41, §44, §46, §48 · **ADRs:** 0002, 0003, 0013 (stream `vehicles` 63), 0020, 0021 · **Research:** `docs/v5-research/ev-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M31, M32, M34 (all merged) · **Lane:** C, alongside M35a (lane A) and M35b (lane B)

## Reece's decisions (2026-11-14)

- **EVs and robotics first** among the new industries.
- **Market sizes and money follow the game's own scale:** the `devices` category's convention, pending M35a's economy-scale audit. Don't import raw real-world unit counts or revenues.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m38-vehicles` from `main`.
- **Merges after `m35b-done`,** so v4 closes on a settled game. Then merge `main`, re-parent the migration, re-record the M30 fixture with the reason, and re-run every guard on the combined code, M35b's v4 targets included.
- **M38 owns:**
  - new `backend/tst/sim/vehicles/` (the category family's specifics, batteries, cell plants, the car platform hooks, autonomy, charging, subsidies);
  - `vehicles.yaml` (new);
  - cell makers as chain companies;
  - the vehicle-plant, cell-plant and charging facility kinds;
  - the autonomy domain in `tech_frontier.yaml`;
  - the `automotive` regulator kind's data;
  - the Vehicles screens;
  - `tst/balance/m38.py` (new).
- **M38 must not edit:** M35a's files (determinism call sites, e2e harness, the M30 fixture tooling, the audit) or M35b's balance keys and scripts. Read them as they land, and merge `main` often.
- **Shared files:** `categories.yaml` (append `vehicles`), `commodities.yaml` (add graphite if missing), `chain_companies.yaml`, `balance.yaml` (add `vehicles.*`), `docs/formulas.md` (notes in §49 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §49.6 target 1 (history holds) is the guard. A new category moves V5's empty-category counts: re-run V5 and report its change.

## Out of scope

Robotaxi services (M39); hydrogen; motorcycles and heavy trucks; used-car markets; automating vehicle decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `vehicles.yaml` from the dossier (EV shares by region and year, battery prices, cell makers and capacity, rivals' line-ups and shares, subsidies, tariffs, charging coverage, autonomy approvals), with every value cited;
   - the `vehicles` category and segments sized to the game's scale, with the derivation in comments;
   - `vehicles.*` keys and stream `vehicles`;
   - migration and data dictionary.
   - **Test:** loader validation, and history's shares to 2025.
2. **The category family** (§49.1): vehicle products with range, charging speed, autonomy and platform; the bill of materials; vehicle plants and contract assembly; rivals.
3. **Batteries** (§49.2): cells as a market good with the learning curve; cell makers as chain companies; own cell plants (`nmc` and `lfp`) with yield learning and group supply.
   - **Property test:** materials and money balance per entity through a cell plant.
4. **The car as a platform** (§49.3): the `car` platform kind; own, licensed or closed systems; subscriptions and over-the-air features.
5. **Autonomy** (§49.4): the domain and levels; approvals through §48's regulators (`automotive` kind); incidents and recalls.
   - **Hidden-value test:** no incident draw reaches the API or a prompt.
6. **Charging, subsidies and tariffs** (§49.5): coverage, the player's charging network (open or exclusive), subsidies with sourcing rules, tariffs through §39.
7. **Screens:**
   - a **Vehicles** screen (market by region, EV share, rivals, the player's cars and plants);
   - car product pages (bill of materials, range, platform, autonomy, software revenue);
   - cell plant and charging network pages;
   - M29 unlocks (Vehicles once the 2012 EV era opens or the player holds lithium supply);
   - glossary entries (kWh, LFP, NMC, L2+/L3/L4, attach rate);
   - Explain on a car's unit cost and battery price.
8. **API, CLI, e2e, balance and close-out:**
   - `tst vehicles`;
   - **Playwright:** (a) design and launch an EV with bought cells, (b) build a cell plant fed by group lithium, and see the unit cost fall, (c) a subsidy's sourcing rule disqualifies a car with Chinese cells in the US;
   - **a practice save** `pt-ev`: an integrator in 2022 with lithium refining and a phone line, ready to enter cars;
   - **§49.6 targets** printed and recorded, tuning only `vehicles.*` (rule 1); re-run every earlier guard and M35b's v4 targets;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `vehicles.yaml` cites a source for every value, and history to 2025 follows it (tests).
- [ ] Every earlier guard and M35b's v4 targets are unchanged on the combined code, or explained under rules 1–4 (V5's change reported).
- [ ] Materials and money balance per entity through cell plants, vehicle plants and charging (property tests).
- [ ] No incident draw, seeded rule or rival plan reaches the API or a prompt (hidden-value test).
- [ ] §49.6 targets 2–6 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m38-done`.

## Manual check (Reece, after merge)

Load `pt-ev`. Launch a car on bought cells, then build a cell plant on your own lithium and compare the unit cost. Try selling it in the US with Chinese cells.

## Decisions made

1. **Workspace and branch (2026-11-16).** This session's own clone, on `m38-vehicles` (the brief's name) from main after merging PR #70 (docs-m38; it had to merge main first, keeping both tasks-index rows). M35a and M35b run in their own branches; none of their files were edited.
2. **Research.** The session could fetch only en.wikipedia.org (the IEA, BNEF, SNE, IRS, EUR-Lex, USTR and USGS pages were refused), so figures quoted by a search engine from those sources are tagged S with "(search)", Wikipedia's IEA tables S, recalled figures R, derived D and assumptions A, as power.yaml does. Corrections to the dossier: BNEF's 2010 price is "above $1,200" in 2021 dollars (about $1,400 in 2023 dollars), not $1,100; 2025's survey is $108 (cells $74); BYD led battery-electric sales in Q4 2023 but Tesla kept the 2024 full year (BYD led only counting plug-in hybrids) and BYD took 2025; 2025 is now an actual (over 20 M, about 25%). Regional maker shares are D where one region dominates a maker's sales and A otherwise (no public table was reachable); re-check them with the IEA's data explorer when it is reachable (follow-up).
3. **Scale.** `vehicles.scale` 0.085 = M34's `economy_scale.money` (the devices incumbents' in-game over real revenue), applied to real new car buyers at real prices in 2010 dollars; plant and cell-plant sizes are scaled the same way (a 500,000-a-year plant is about 3,500 cars a month).
4. **One market, EV buyers only.** The vehicles category is a unit-sale market of EV buyers (the ICE market is outside the game); its addressable customers are set from vehicles.yaml each month rather than grown, and its regions use vehicles.yaml's own sizes. Fleets and commercial buyers are sales-led segments of 50 and 20 cars a customer.
5. **History holds by pinning.** To December 2025 each car maker's customers are its data share of the market not held by other companies' lines, prices start at its launch month, and car makers neither decide nor fail before 2026 (they open with $500M of car capital: their lines sell little before the 2020s). A player who enters early takes buyers from the unserved share and, through the pin, proportionally from every maker.
6. **A rival car's cost of goods** is 82% of its own price (`rival_cost_share`): one `hosting_cents` for a market whose prices run from $18,000 to $50,000 made the cheap makers lose money on every car and fail.
7. **Cells are an M17 commodity** so offtake, allocation, export rules, group supply and M28's chain companies all apply; after 2025 the AR(1) reverts to the learning curve, and M28's long-run price for cells is that curve too (with the 2015-2025 median the cell makers never expanded and the price doubled). Nickel, manganese and graphite join the commodities (the brief named nickel and manganese as present; they were not). The game's lithium good is lithium carbonate (M20's), not hydroxide.
8. **Own cells are settled like M20's own supply:** a car pays the market price for its cells at sale, the cell plant's costs post in its month, and the market price of the cells the line used is reversed (a sister company pays the transfer price). A car on own cells also assembles its packs in house (`integration_saving`).
9. **The car platform** is the design's `platform` field (own OS product, licensed Android Automotive, closed), with software revenue, licence fees, OTA churn and feature points; car platforms are not M31 Platform records (no developer or catalogue model for cars: a follow-up).
10. **Autonomy approvals and incidents** are vehicles.yaml's automotive regulators (a kind of their own, kept out of M34's regulation.yaml so M34's code is unchanged); an incident recalls and suspends the level, and does not open an M34 case (a follow-up). An exclusive charging network over `scrutiny_share` of a region's chargers is ordered open rather than opening an M34 case (likewise).
11. **The Vehicles unlock** (M29 system 28) is the EV era from 2012 at stage 3, a car line, or the group's lithium supply: a stage-1 software start-up does not see it in 2012.
12. **Guards and fixtures.** Appending thirteen incumbents moves every later company's id by 13 (entrants and start-ups), and the new goods, suppliers and companies add lines to every fingerprint, so golden snapshots, M28's history fingerprint and M30's state-hash fixture change. Evidence that history holds otherwise (seed 1, `docs` evidence in this brief): with M38's goods, suppliers and companies filtered out and later ids moved back, M28's fingerprint to December 2025 equals main's for prices, wafers, capacities and every company's books; its event log differs only in four "Top 50 by revenue" profile stories (2012-2013) where car makers now rank. The fixtures are re-recorded on the combined code at the merge (CLAUDE.md 6; the reason in CHANGELOG).
13. **Tuning (rule 1, `vehicles.*` only), seeds 1-3 then 1-10:** `cell_plant.other_share` 0.40 -> 0.20 and new `cell_plant.integration_saving` 0.5: target 3's median gap 0.0 -> 2.0 (plants kept staffed) -> 3.5 (0.25) -> 3.9 (0.20) -> 4.4 points (0.5). Target 3 measures the car line's own margin (its revenue less its cars' costs by line, own cells at the plant's cost with depreciation), with the plant sized to the line (100 MWh a month), and the script replaces the plants' leavers each month as a sensible player would (M21's fab script does too).
14. **Readings (49.6), seeds 1-10 (`tools/m38_targets.py`):**

| Target | Reading | Band | |
| --- | --- | --- | --- |
| 1 History holds | EV shares, rivals' shares, battery prices, subsidies, tariffs and approvals follow vehicles.yaml to 2025 (`tests/unit/test_m38_vehicles_data.py`); earlier guards: decision 12 | the data | met |
| 2 S-curve | global EV share of new cars 2035: median **47.1%** (43.3-51.7%); with the learning rate at its top it is higher than at its bottom on **10 of 10** seeds | 35-65% | met |
| 3 Integration pays | car line's gross margin 2034, own cells and lithium **33.6%** median against **28.6%** bought: gap **5.0 points** median (3.4-12.7) | >= 4 | met |
| 4 Software | own OS and L2+: software **1.3%** of the line's revenue 2026-2035 | >= 10% | carried (decision 15) |
| 5 Tariffs bite | a Shenzhen-made car priced at its landed cost in North America: at most **1.06%** of EV buyers 2025-2030 | < 2% | met |
| 6 Turn time | **201 ms** a turn (median, 2026-2035, these worlds); `make check-timing`: see the merge | M30's guards | see the merge |
15. **Target 4 is carried.** Software is about 1-2% of the line's revenue to 2035 at today's prices (connectivity at $7 a month on most cars, L2+ at $60 on 15%), close to the real benchmark (Tesla's software and services, FSD included, are a low single-digit share of its automotive revenue, R). 10% would need subscriptions about five times today's; rather than set unreal prices the target is carried for Reece's ruling (keys `vehicles.software.*`, `levels.*.attach` and `price_cents`).

## Follow-ups

- Re-check vehicles.yaml's R and A rows (regional maker shares, charger counts outside China, Europe and the US, manganese and graphite prices before 2021, LFP/NMC material intensities) against the IEA Global EV Data Explorer, BNEF and USGS when those hosts are reachable.
- Car platforms as M31 Platform records (developers, catalogues, car apps), and M34 cases from autonomy incidents and exclusive charging networks.
- Fuel prices in the S-curve (49.5 names them; not modelled), seeded new subsidies and tariffs after 2025, and the 200,000-car phase-out of the US credit.
- Robotaxi services (M39), and an automation area for vehicles (pricing, plants, cell supply).
- Target 4's software share needs Reece's ruling (decision 15).
