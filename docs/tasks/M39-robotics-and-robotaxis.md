# M39: Robotics and robotaxis (v5, lane F)

**Goal:** robots join the game. The player can build industrial robots and sell them to factories, or install them in its own plants to cut labour cost. It can build humanoids once their era arrives, powered by its AI models and chips. It can run robotaxi services on M38's L4 cars, city by city, where regulators approve zones and utilisation decides the economics. History to 2025 is unchanged.

**Formulas:** `docs/formulas.md` §53 (all), with §2, §26, §38, §46, §48, §49 · **ADRs:** 0002, 0003, 0013 (stream `robotics` 66), 0020 · **Research:** `docs/v5-research/robotics-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M38 (`m38-done`) · **Lane:** F, alongside M41 and M37

## Reece's decisions (2026-11-14 and 2026-11-15)

- **Robotics among the first new industries,** with robotaxis in the same milestone.
- **Markets and money at the game's scale.**

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m39-robotics` from `main`.
- **Merges after M41 and M37.** Then merge `main`, re-parent the migration, re-record the M30 fixture with `--update-state-cache` and the reason, and re-run every guard.
- **M39 owns:**
  - new `backend/tst/sim/robotics/` (industrial robots, plant automation, humanoids, robotaxi fleets, zones, depots, rides, incidents);
  - `robotics.yaml` (new);
  - the `industrial_robots`, `humanoid_robots` and `mobility` categories;
  - the depot facility kind;
  - the plant-automation hook in the plant cost models (a read of the plant's automation level);
  - the Robotics screens;
  - `tst/balance/m39.py` (new).
- **M39 must not edit:** M41's `medical/`, M37's `dynasty/`, or M38's `vehicles/` beyond reading cars and autonomy levels through their interfaces.
- **Shared files:** `categories.yaml`, `regulation.yaml` (zone approvals under the `automotive` kind), `balance.yaml` (add `robotics.*`), `docs/formulas.md` (notes in §53 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §53.4 target 1 (history holds; a company without robots plays exactly as before) is the guard. The turn-time guards are 500 ms on both V6 saves.

## Out of scope

Home humanoids before their seeded window; drones and delivery robots (follow-up); surgical robots (M41's); automating robotics decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `robotics.yaml` from the dossier (installations by region and year, prices, makers and shares, humanoid announcements, robotaxi services' dates, cities and ride volumes, Cruise's end), with every value cited;
   - the three categories sized to the game's scale, with the derivation;
   - `robotics.*` keys and stream `robotics`;
   - migration and data dictionary.
2. **Industrial robots and plant automation** (§53.1). **Property test:** plant books balance with robots installed.
3. **Humanoids** (§53.2): the era-gated category, capability from hardware, AI and chips, labour-price demand, actuators as a learning-curve good.
4. **Robotaxis** (§53.3): the `mobility` category, fleets, zones with approvals, depots, rides and utilisation, incidents and suspensions (a critical event).
   - **Hidden-value test:** no incident or approval draw reaches the API or a prompt.
5. **Screens:**
   - a **Robotics** screen (markets, the player's robots, plant automation levels);
   - a **Mobility** screen (fleets by city, zones and permits, rides, utilisation, incidents);
   - M29 unlocks;
   - glossary entries (cobot, robot density, utilisation, zone, remote assistance);
   - Explain on a plant's automation saving and a robotaxi's contribution per ride.
6. **API, CLI, e2e, balance and close-out:**
   - `tst robotics`, `tst mobility`;
   - **Playwright:** (a) automate a vehicle plant with own robots and see unit cost fall, (b) launch a robotaxi zone in a city with an approval, (c) an incident suspends a zone;
   - **a practice save** `pt-robotics`: an EV maker in 2027 with L3 cars, a vehicle plant in a high-wage region and AI models;
   - **§53.4 targets** printed and recorded, tuning only `robotics.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `robotics.yaml` cites a source for every value, and history to 2025 follows it (tests).
- [ ] A company without robots plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No incident, approval or seeded draw reaches the API or a prompt (hidden-value test).
- [ ] §53.4 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m39-done`.

## Manual check (Reece, after merge)

Load `pt-robotics`. Automate your vehicle plant, then launch robotaxis in Phoenix and San Francisco. Watch utilisation, and what an incident does.

## Decisions made

1. **Workspace and branch (2026-11-17).** This session's own worktree, on `m39-robotics` (the brief's name) from main. PR #76 (docs-m39) was merged with a merge commit after PR #74 (rule 9), once main's #74 merge was merged into it and check and e2e were green. M41 (`m41-medical`) and M37 (`m37-dynasty`) run in their own branches; none of their files were edited, and M38's `vehicles/` is read only (`spec.approved`, `capable_level`, `best_ai_quality`, `unit_cost`, `spec_of`, `config.interp`, `data.year_at`, `logit`, `sigmoid`).
2. **Research.** This session could fetch only en.wikipedia.org (ifr.org, bls.gov and ark-invest.com did not resolve), so IFR figures come from Wikipedia's IFR table (S) and IFR's press releases as quoted by search results (S (search)); recalled figures are R, derived D and assumptions A, as vehicles.yaml does. Corrections to the dossier: 2010 installations were first published as about 118,000 (120,585 is IFR's revision); China's own makers held over half their home market by 2024 (57%, IFR), not ">40%"; Midea completed KUKA in January 2017 (94.55%); the Unitree G1's price was announced in May 2024, mass production from August 2024; IFR's 2026 edition adds 2025 (about 603,000, China 59%). Regional makers' shares, humanoid prices, city ride markets and most labour costs outside the US are A or R (follow-up: re-check against IFR's tables and BLS).
3. **Scale.** `robotics.scale` 0.085 = `vehicles.scale` (M34's `economy_scale.money`), applied to real installations, worker pools and ride-hailing trips at real prices in 2010 dollars. The industrial market's addressable customers are set each month from robotics.yaml (as M38's), with `units_per_customer` (automotive 20, electronics 8, general industry 3) and `replacement_months` (84, 60, 96); after 2025 a region's installations grow by a rate drawn each year in [0%, 8%].
4. **Rivals.** Twelve incumbents appended (FANUC, ABB Robotics, Yaskawa, KUKA, Universal Robots, Estun; Tesla Optimus, Figure AI, Agility Robotics, Unitree, UBTech, Boston Dynamics), each with one robots product. Estun carries the Chinese makers' share of East Asia (one rival rather than five, for the turn's budget); Kawasaki, Epson, Nachi and the rest are not in the game (the share no rival serves). Tesla's humanoid programme is a rival of its own ("Tesla Optimus"): appending a product to Tesla's entry would move every later product id. Industrial makers' customers are pinned to their data shares to December 2025 and they do not decide before 2026; humanoid makers have no price before the humanoid era and do not decide until it arrives (and 2026). Robotaxi operators (Waymo, Cruise, Apollo Go, Pony.ai, WeRide, Tesla, Zoox) are data services, not companies: their fleets and rides follow robotics.yaml to 2025 and grow after it, and they enter new cities each December by a seeded draw.
5. **History holds (53.4 target 1).** Appending twelve incumbents moves every later company's id by 12 (entrants and start-ups), and the new markets, products and companies add lines to every fingerprint, so M28's history fingerprint and M30's state-hash fixture change (the golden snapshots do not). Evidence (seed 1, M28's fingerprint to December 2025, robot makers' entries and events filtered out and later ids moved back by 12, against main's fixture): prices, wafers, capacities and every company's books are identical in every year; events differ only in six years' January "Top 50 by revenue" profile stories, where the robot makers now take or vacate places (2011: BYD #49 and General Motors #50 enter; 2013: Google Cloud #49 no longer does; 2014: BYD #41, Google Cloud #42; 2015: SAIC #50; 2017: Baidu #50, Nuance #46; 2018: NVIDIA #47), as M38 decision 12 found for the car makers. A company without robots plays exactly as before: the robotics phases return the state unchanged for it (`test_no_automation_no_change`) and the plant hook reads exactly `variable_cents` for a plant without robots.
6. **Robotaxi services are products of a pseudo-category.** `mobility` is a pseudo-category like `os`: a service is built and launched like a product (no segments, launch at `products.launch_min_feature`, not the OS's build), and `tst.sim.robotics` runs it in zones. Its revenue is a ride's fare (4000) and its costs a car's and a ride's (5000, 6700); depots are facilities (kind `depot`) whose own costs post with the generic lifecycle.
7. **Zone approvals** read M38's automotive regulators (L4 approved in the zone's region, `vehicles.spec.approved`), kept in vehicles.yaml as M38 decision 10 did, so regulation.yaml and M34's code are unchanged. The city's permit is the zone's review (3, 6 or 9 months by size, then a seeded monthly decision with a refusal share raised by the company's serious incidents). A serious incident suspends the permit and is a critical event (templates `robotaxi_collision` and `robotaxi_pedestrian`, trigger `robotics`, answers `cooperate`, `compensate`, `contest`); it does not open an M34 case (follow-up, as M38's).
8. **Plant automation** reads the plant's region's manufacturing labour cost (robotics.yaml) and never saves more than the plant kind's line labour (`variable_cents` x `labour_share`): the existing cost model is unchanged for a plant without robots, and the saving is a deduction from the variable cost a unit run (the plant hook in `tst.sim.hardware.production`). Robots install in assembly and vehicle plants; cell plants (M38's `vehicles/`, off limits) and fabs are a follow-up. Own robots cost their bill of materials and plant run plus the integration; they are not booked as the robot line's sales (follow-up). 53.4 target 2 measures the plant's conversion cost a unit at full use (line labour, fixed cost, the plant's depreciation, the robots' depreciation and service), not the product's bill of materials, which robots do not touch.
9. **Humanoids.** Capability = 0.4 x quality + 0.4 x the AI model's quality (own or licensed 70) + 0.2 x the chips' (own or bought 60); the chips are the BOM's `ai_accelerator` (the generic own-or-bought chip path). Actuators are a learning-curve cost inside `tst.sim.robotics` (not an M17 commodity: a new good would move every commodity fingerprint), 18% a doubling of humanoids made since the era's arrival; its index against the first year's cost is printed as M38's L3 measure. Homes (the consumer segment) open at a seeded month 5-10 years after the arrival.
10. **Unlock ids.** Robotics is system 30 and Mobility 31 (M41 takes 29).
11. **Target 4's measurement** (the script, not the game, rule 2): the 40-car run's revenue cut is measured over the zone's first suspension against the 3 months before it, because on seeds 6 and 9 a seeded serious incident suspended the zone before the forced one in month 13 (the first reading compared a suspension with a suspension and read 0%). Months above break-even count only while the zone runs.
12. **No tuning was needed** (rule 1): every target is met at the first values of `robotics.*`. Humanoids reach 84-89% of robotics revenue within 8 years of their era, well above the 20% floor: real forecasts put the humanoid market at or above the industrial one by the mid-2030s (Goldman Sachs $38bn by 2035 against IFR's $16.7bn of robots, S (search)); a lower cap is a follow-up for v5's balance (M43) if Reece wants industrial robots to keep more of it.
13. **Readings (53.4), seeds 1-10 (`tools/m39_targets.py`):**

| Target | Reading | Band | |
| --- | --- | --- | --- |
| 1 History holds | installations, makers' shares, humanoid announcements and robotaxi services follow robotics.yaml to 2025 (`tests/unit/test_m39_robotics_data.py`); a company without robots plays as before (decision 5) | the data | met |
| 2 Automation pays where labour is dear | a 2,000-car plant's conversion cost a unit at 60% automation, January 2030: **28.7%** lower in North America, **3.4% higher** in South and Southeast Asia (every seed: the formula reads no draw) | >= 15% / <= 5% | met |
| 3 Humanoids follow their era | humanoid share of robotics revenue before the era: **0.00%** on every seed (the era arrives April 2031 to November 2035); within 8 years: median **87.7%** (84.4-89.4%) | < 1% / >= 20% | met |
| 4 Robotaxis are a utilisation business | **176 of 176** active months above 6 rides a car a day earn a positive contribution; a suspension cuts the zone's revenue **85-100%** | positive / >= 30% | met |
| 5 Turn time | **292 ms** a turn (median, 2026-2035, these worlds, four at once on 4 cores). Guards on the branch (before M41 and M37): `make check-timing` passes (7 tests); weekly-v6 on CI (run 44036867526): plain V6 save **412 ms** median (451 at most), integrator save **449 ms** (501 at most); re-run after the merge below | 500 ms median, 1,000 ms at most | met |

14. **Merge with M37 (after `m37-done`).** The migration is re-parented: `0061_m39` on M37's `0060_m37`, schema 61. Conflicts were each milestone's appended lines (stream ids 65 and 66, balance sections, state fields, routers, loaders), kept both, M37's first. Re-recorded on the combined code: M30's state cache (`--update-state-cache`; its repeat and memo checks pass), M28's history (`tools/m28_targets.py --write-history`, unchanged: M37 touches nothing before 2040), and M32's history fixture's books hashes only (`cost_diffs` empty, 320 books rows replaced). M32's fixture had been stale on main since M41 (M37's decision 23, rule 3); M39 moves the same books, so re-recording it here clears both. The test-durations file is refreshed for the shard balance (CI-fix lane's request).

## Follow-ups

- Re-check robotics.yaml's R and A rows (regional installations outside the named countries, makers' regional shares, labour costs outside the US, city ride markets, humanoid prices) against IFR's World Robotics tables, BLS and city transport studies when those hosts are reachable.
- Robots in cell plants (M38's `vehicles/`) and fabs; own robots booked as the robot line's internal sales; robots that can be removed or sold.
- Robotaxi incidents opening an M34 case (as M38's autonomy follow-up); own cars for fleets taken from the car line's production rather than at its unit cost; a fleet's cars moved between zones.
- Humanoid makers founded at the era's arrival rather than held from 2010; more Chinese robot makers than Estun; drones and delivery robots; an automation area for robotics decisions.
- Humanoids' share of robotics revenue (84-89%) for M43's v5 balance, if industrial robots should keep more.
- The v5 performance milestone (M45): M39's twelve rivals add to the turn as M38's thirteen did.
