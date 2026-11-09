# M20: Refining and wafers (v3, lane B)

**Goal:** the middle of the chain. Smelters, polysilicon plants, wafer plants, lithium converters, cobalt refineries, rare-earth separators and gallium or germanium recovery lines turn ores and concentrates into the materials chips and devices use. Each has a recipe, a yield and a large power bill priced by region. Margins are thin; the payoff is control: own wafers for your chips, own lithium for your batteries, and supply that keeps flowing in a shortage or an export ban.

**Spec sections:** §8 (value chain) · **ADRs:** 0002, 0003, 0013 (stream `refining` 51), 0019, 0020 (facility kinds, market goods) · **Formulas:** `docs/formulas.md` §36 (all), with §21 (research), §26 (chips), §31 (transfer prices), §33 (commodities, power) · **Data:** `docs/v3-research/v3-data-dossier.md` §1–§3 · **Depends on:** M18 (`m18-done`) · **Lane:** B, alongside M19 (lane A)

## Lane

- Its own session and branch. **Merge order: M20 merges second:** merge `main` (with M19), re-parent migrations, wire refineries' inputs to M19's own-group mine supply, regenerate golden snapshots once with both milestones' reasons, re-run every guard and both milestones' targets.
- **M20 owns:** the refinery facility kinds and recipes; new `backend/tst/sim/refining/`; concentrate goods; the `process` research domain (appended to M11's tree and `tech_frontier.yaml`); the `process_engineer` role; `data/events/refining.yaml`; a **Refineries** screen; the wafer-cost path in §26.3 for own-group wafers.
- **M20 must not edit:** the mine kind, `sim/mining/`, the subsidiary action, M19's region fields.
- **Until M19 merges:** refineries buy inputs from contracts or spot (M17); own-group mine supply is wired at merge.
- **Shared files:** `balance.yaml` (`refining.*`, `facility.kinds.<refinery kinds>`, the `process` domain's research keys: keep both sides), `docs/formulas.md` (§36 notes only), `CHANGELOG.md`, `docs/data-dictionary.md`.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Fabs (M21), export controls as policy (M22; M20's power curbs and bans are events), battery cells as a product (later).

## Sub-tasks (commit after each)

1. **Data and formula tests:** recipes, yields, power per unit, capex and staffing per kind (cited where public, labelled as assumptions otherwise), concentrate goods, the `process` domain's baseline, event templates (including the September–October 2021 power curbs); stream in ADR-0013; unit tests for each recipe's unit cost at a given power index.
2. **Refinery kinds** (§36.1) on the generic facility lifecycle: inputs from group, contract or spot with allocation; outputs to group, contract or spot; construction, overrun, staffing.
3. **Wafers for chips** (§36.2): own-group wafers in the chip cost path; spare wafers sold. **Test:** a fabless company without a wafer plant pays exactly what it did before.
4. **Process research** (§36.3): the domain, its levels and baseline, the yield rule for semiconductor grades.
5. **Events** (§36.4): power curbs (history then seeded), plant incidents as critical events.
6. **API, CLI, screens:** the Refineries screen (each plant's inputs, outputs, yield, power cost, unit cost against market, margin), the chain on the Group screen (mine → refinery → wafer → chip → device); **CLI:** `tst build-refinery --kind --region --capacity`, `tst refineries`, `tst recipe --kind`.
7. **Balance, merge and e2e:** §36.5 targets printed and recorded; tune only `refining.*`. **Playwright:** (a) build a silicon smelter in a cheap-power region and compare its unit cost with Europe's; (b) a wafer plant supplying the group's chips at transfer price; (c) a power curb event; (d) a gallium recovery line holding chip costs through a ban. The merge steps above. CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Each recipe's unit cost matches its worked example at a given power index (unit tests); the ledger balances through refining (property test).
- [ ] A company that never refines plays exactly as before.
- [ ] §36.5 targets met (printed, values recorded), on the combined code with M19.
- [ ] `make check` and CI `e2e` green; merged after M19 through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m20-done`.

## Manual check (Reece, after merge)

Build a wafer plant and feed your own chips; then a silicon smelter where power is cheap. Watch a 2021 power curb hit a smelter in East Asia.

## Decisions made

Engineering and data decisions the spec, ADRs and brief left open (M20 agent, 2026-11-09). Items marked **for review** change what a reader might expect.

1. **What a wafer plant makes (for review).** 36.1's 2,000 wafers a tonne is raw 300 mm substrate (0.5 kg of polysilicon a wafer), and 36.2's spare wafers sell to foundries "at the wafer price", so the plant's good is a **substrate** wafer (`silicon_wafer`: $110 at polysilicon index 1.0, its poly share 0.55 moving with polysilicon; tight with foundry wafers in 2021–2022), not M12b's foundry wafer ($2,000–$9,000). In the chip cost path (36.2, 26.3) the share of a chip product's wafer starts covered by own wafers pays the group's substrate price instead of the market's inside the foundry wafer: `wafer price − share × (market substrate − transfer price)`, and those starts keep 100% allocation in a shortage. Target 3 reads the substrate's saving (a foundry wafer costs only 1–4% less).
2. **Concentrates.** Four goods priced off their refined product (`refining.goods`, A): quartz lump 0.014 × silicon metal; lithium concentrate (t LCE) 0.55 × carbonate (tuned from 0.65, then 0.6, so a converter's margin can be thin, not negative); cobalt hydroxide (t Co) 0.75 × cobalt; mixed rare-earth concentrate (t REO) 0.12 × 1,000 × NdPr a kg. Their allocation is the refined good's. Solar polysilicon is the semiconductor price / 5 (33.1's multiple, checked equal at load).
3. **Contracts.** M17's contracts and offtakes hedge products' commodity use only; refineries buy and sell under their own fixed-price contracts (`refining.deal`: 12–36 months at the signing month's price; a buy contract signed before a shortage keeps 100%, take-or-pay 30% a month of what it could deliver but did not take; a sell contract delivers up to its monthly volume from the company's plants).
4. **Group supply** is a month's lot (`OwnSupply`) handed out in phase 4 from each plant's output: to the group's later plants (inputs), then the group's chip products' wafer starts (product order) or companies' last month's commodity use (company order). Inside one company it moves at the plant's full unit cost (inputs, power, other, fixed, depreciation and the plant's staff); between companies at M16's new `materials` flow (cost by default). After production a lot is taken up to what was used (after M17's deals); the rest sells at spot.
5. **Costs** (calibrated from in-game runs, `tst.balance.m20.margin_runs`): power at $68/MWh × the region's index (EIA's 2010 US industrial 6.77 ¢/kWh); fixed cost 4% of capex a year; `other_cents` set per recipe so the median 2015–2025 margin in North America is 8% (wafers 14%). Wafer plant capex $250 → $150 per wafer a year (at $250 depreciation alone was 27% of an $82 wafer). Capex figures are assumptions where the dossier has none (labelled in balance.yaml).
6. **Overrun** (M19's rule): 0–40% → **0–25%** (`refining.overrun`, tuned for target 3: the spread moved a wafer plant's cost 5 points between seeds); revealed only as capex is paid (the API shows the estimate and what has been paid).
7. **Process domain** starts at 25 and gains 1 a year (40 by 2025 without research), so semiconductor grades need research before about 2025; below 40 they run at half yield (twice the input, half the output).
8. **Staff.** `process_engineer` (new role) with the existing skills manufacturing and data as primary (the spec's "engineering, chemistry" are not skills in skills.yaml); manufacturing sets reliability and the incident rate.
9. **By-product lines** need a host: one of the company's other refineries in the same region (build fails without one); they buy no input (the host's stream), so their cost does not follow the by-product's price in a ban. Built in 18 months (an add-on).
10. **Curbs and incidents** are drawn per plant (stream `refining`, keys `(2, facility)` and `(1, facility)`), not per region. Incidents only at rare-earth and polysilicon plants (36.4's "critical event for rare-earth and polysilicon plants"); brand falls 3 points on each of the company's products and credibility 4 at the incident; the answer sets the rest.
11. **Accounts.** Refineries' costs post to 5000; sales to a new `4410_materials_sales`.
12. **Measuring the targets (for review).** Target 1: one plant of each recipe in North America, live from January 2015, staffed at skill 12 and topped up when engineers leave, measured after its ramp through December 2025, semiconductor grades with a process lead (as if researched). Target 2: the same smelter in the cheapest-power region (South and Southeast Asia) and Europe, mean unit cost 2015–2025. Target 3: M12b's device maker with its own SoC (26.6's company) signing its wafers a year at a time, with a wafer plant in East Asia, the saving read after the ramp; seeds 1–3. Target 4: the chip mix's **gallium line** at the peak of each seeded gallium export ban in 2026–2039 against the 12 months before it, the group with a gallium recovery line against a spot buyer (whole-mix readings printed beside). The whole mix cannot rise 30% for a spot buyer: gallium weighs 0.15 in it (33.2) and a ban raises gallium 50–150% (33.1); and it moves with polysilicon, neon and germanium, which a gallium line does not touch.

## Follow-ups

- Rival refiners: M17's refining suppliers (Wacker, Hemlock, GCL, Shin-Etsu, SUMCO, Umicore, Lynas…) as operating rivals with capacity responding to prices (as M19 did for miners).
- Minority-complaint fairness for `materials` flows (M16's check reads compute and chips spend only), and materials flows in the conglomerate discount's intra-group share.
- Inventory: refineries make and sell in the month; stockpiles (and buying ahead of a ban) would make by-products and contracts richer.
- Region-wide curbs (one draw a region) if per-plant curbs read oddly with many plants in one region.
- The Build dialog could show the effective yield at the player's process level for semiconductor grades before building.
