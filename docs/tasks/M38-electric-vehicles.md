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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
