# M12b: Hardware, devices and fabless chips (lane A)

**Goal:** the company can make physical things.
- **Devices and servers:** built through a contract manufacturer, or in its own assembly plant (usually unprofitable until it's well used), with spare plant capacity sold to others as contract manufacturing.
- **Fabless chips:** mobile SoCs, server CPUs and AI accelerators, designed in-house and fabbed on foundry wafers bought from TSMC or Samsung. They're sold to a chip market against NVIDIA, Intel, AMD and Qualcomm, and used in the company's own devices and GPU data centres at cost.
- **Supply:** bills of materials and wafers follow the 2021 shortage and the 2023 crunch.

**Spec sections:** §7.1 (hardware and devices, fabless chips), §8 (value chain, sourcing) · **ADRs:** 0002, 0003, 0013 (stable rival keys, the M12a amendment), 0019 (§8, §13), 0020 (one facility model, goods, internal supply) · **Formulas:** `docs/formulas.md` §26 (all), with §11, §21, §22 · **Wireframes:** `docs/wireframes.md` (M12b screens) and `docs/wireframes/source/Hardware.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M11 and M12a (`m11-done`, `m12a-done`)

## Lane

- **Lane A.** It runs at the same time as M13 (lane B, IPO) in its own session and branch (`m12b-hardware`).
- **Merge order: M13 merges first.** Before merging M12b:
  1. merge `main` (with M13) into this branch;
  2. re-parent M12b's unmerged migrations;
  3. regenerate golden snapshots with both milestones' reasons in CHANGELOG;
  4. re-run every guard on the combined code. If an M13 target moves, report it rather than tune M13's keys.
- **M12b owns:**
  - new `backend/tst/sim/hardware/` (unit-sale markets, bills of materials, contract manufacturing, the contract-manufacturing market) and `backend/tst/sim/chips/` (chip products, wafers, yield, internal use);
  - the `assembly_plant` kind in `balance.facility.kinds` and its per-kind rules in `tst/sim/facilities/`;
  - goods `device_bom`, `server_bom`, `equipment` and `foundry_wafer` appended to `components_history.yaml`;
  - the categories and the `device_oems` segment appended to `categories.yaml`; incumbents and entrants appended; the three historical eras and the two future (windowed) eras appended to `eras.yaml`, and windowed eras in M11's era code and loader (`tst/sim/research/`, era functions only);
  - screens: product BOM and manufacturing panels, the Hardware screen, and chip products.
- **M12b must not edit:** `tst/sim/markets_public/`, `tst/sim/org/ceo.py`, `banks.yaml`, or the Finance Stock tab (M13's).
- **Shared files:**
  - `balance.yaml`: add only `hardware.*`, `chips.*` and the new facility kind;
  - `docs/formulas.md`: notes in §26 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** stream `manufacturing` (30), key `(facility_id,)`, for monthly yield noise; stream `era_window` (31), key `(era_index,)`, drawn at turn 0, for future eras' scheduled months (§26.4); 32 reserved for lane A. Add it to ADR-0013's main table with stable keys. New incumbents and entrants use the stable-key scheme from M12a's ADR-0013 amendment, so adding them must not move existing rivals; the M12a test for that must still pass.

## Design for v3 (ADR-0020)

- Assembly plants are a kind of M12a's facility model; add only per-kind rules.
- Bill-of-materials goods and foundry wafers are goods in the one market-good model.
- Chips used by the same company's devices or data centres go through the internal-supply path at cost (no revenue), the path v3's intercompany transfers will extend.
- Everything belongs to a `company_id`; use `player_companies(state)`.

## Out of scope

Owning a fab, wafers or refining (v3). Inventory and build-ahead: M12b is build-to-order with a capacity cap. Rivals' physical plants (abstract). Device software ecosystems and app stores.

## Sub-tasks (commit after each)

1. **Data and formula tests:**
   - categories, segment, goods history (the 2021 shortage and the 2023 advanced-node crunch), the facility kind, `hardware.*` and `chips.*` keys, incumbents, entrants, eras;
   - every §26.7 worked example as a unit test; the stream row in ADR-0013.
2. **Unit-sale markets** (§26.1): `revenue_model: units` in the market phase, the replacement cycle, the capacity cap, launch requirements, fast feature expectations, and the quality cap through `research.tech_factor`.
   - **Test:** subscription categories are unchanged (golden snapshots unchanged by this sub-task).
3. **Bill of materials and contract manufacturing** (§26.2): BOM costs from goods, cost of goods sold at sale, contract-manufacturing contracts with take-or-pay and shortage allocation. Ledger property tests.
4. **Assembly plants** (§26.2): the facility kind, yield on stream `manufacturing`, fixed and variable costs, staffing, city bonus, and the contract-manufacturing market for spare capacity.
   - **Tests:** the cost at 80% and 30% use against §26.7, and selling spare capacity.
5. **Fabless chips** (§26.3): chip products by type, wafer contracts and allocation, yield from the chip-design lead, unit cost, chip demand by segment, internal use in own devices and servers, and the GPU capex reduction in own data centres. Rivals and entrants.
   - **Tests:** internal use books no revenue; the capex reduction applies.
6. **Eras** (§26.4): appended to M11's era system with their effects.
   - **Historical eras:** tests for arrival and effects.
   - **Future eras (windowed):** the `window` field and its loader checks; the scheduled month on stream `era_window`; the threshold from the window's midpoint; the §26.4 example as a test.
   - **Seeded tests:** the scheduled month is the same for the same seed and inside the window on every seed (30 seeds); across 30 seeds both halves of each window occur; appending an era leaves other eras' months unchanged.
   - **Hidden values:** extend the hidden-value test so no API response or LLM prompt contains a future era's scheduled month before it arrives (the window and threshold are public).
7. **API, CLI and screens** (per the wireframes):
   - **Product BOM panel:** lines and unit cost.
   - **Manufacturing panel:** source, contract use, plant yield.
   - **Hardware screen:** plants, contracts, contract-manufacturing sales, chip products, wafer and component indexes.
   - **Supporting work:** glossary and driver breakdowns; History entries.
   - **CLI:** `tst hardware`, `tst cm-contract --units --months`, `tst build-plant --city --units`, `tst wafer-contract`.
8. **Balance and e2e:**
   - the §26.6 targets printed and recorded;
   - the merge steps above, after M13 is on `main`;
   - **no new xfails:** any guard that fails versus `main` and M12b's keys can't fix is reported with values;
   - **Playwright:**
     - (a) launch a device on a contract and see the unit cost and gross margin;
     - (b) build a plant and see it take over from the contract;
     - (c) design an AI accelerator and see a GPU data centre's capex fall;
   - close-out.

## Acceptance criteria

- [ ] Every §26.7 worked example passes as a test.
- [ ] A company that never enters hardware plays exactly as before.
- [ ] Unit-sale markets, bills of materials, contracts, plants and chips work as specified; the ledger balances (property tests); internal use books no revenue.
- [ ] Future eras arrive inside their windows, are reproducible from the seed, and their scheduled month never appears in the API before arrival.
- [ ] Adding the new incumbents and entrants leaves existing rivals' decisions unchanged (the M12a stable-key test).
- [ ] §26.6 targets 2–6 met (printed, values recorded); no new xfails.
- [ ] Merged after M13 with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m12b-done`.

## Manual check (Reece, after merge)

Launch a device on a Foxconn contract. Then build a plant in Shenzhen and see when it starts paying off. In an AI game, design your own accelerator and use it in your data centres.

## Decisions made

- **Chips are three categories** (`chips_mobile_soc`, `chips_server_cpu`, `chips_ai_accelerator`; `family: chips`, `chip_type` on the category), so each type has its own demand and incumbents; the type is still the product's attribute (from its category). Their demand follows other markets per segment (`growth_follows`).
- **Units per customer.** A unit-sale customer buys `units_per_customer` units (consumer 1, an enterprise account 50 devices, a hyperscaler 5,000 servers); sales-led segments' seller capacity stays per customer. The installed base is the customers; the replacement cycle is the base churn.
- **Rivals' cost of goods** is the market's `hosting_cents` a unit (40-45% of reference): at 55%, as Cloud hosting's, Lenovo and Supermicro went bankrupt in price wars. AMD still fails around 2020 on seed 1 (its two products' feature pushes grow its builders); see Follow-ups.
- **The capacity cap** and production apply to the player's companies only; rivals' manufacturing is abstract. Lost demand goes to the next-best product that can make it.
- **Take-or-pay** runs from signing (before launch too), monthly, on volume delivered but unused: 50% for contract manufacturing, 30% for wafers (22.4's share; 26.3 says "as 22.4"), to G&A as M12a's.
- **Shortages**: a contract signed before the running shortage began keeps 100%; history's allocation periods give the start, a seeded shock its first month. Advanced-node wafer shortages (2023-2024) bind server CPUs and AI accelerators only (`advanced_only`).
- **Plants.** `fixed_opex_cents` posts in phase 6 to `5000_cogs` ("Assembly plant operations"), $3 a unit run at sale; staff coverage scales runnable units; a server takes 6 units of plant capacity; sizes 5,000-100,000 a month; no outages; Infrastructure ignores plants. Build in a city (`BuildFacility.city`).
- **New roles** (appended to `roles.yaml`): hardware engineer, chip designer, manufacturing engineer (all builders). No role had hardware, chip-design or manufacturing skills as primary.
- **Mobile SoC wafers $2,000** (mature node), so an own SoC costs about $13 against $40 bought: target 4's 8 points need about $26 saved on a $320 device.
- **GPU capex cut** applies at the quote while the company has a live own AI accelerator; the build does not consume its chips.
- **Future eras.** `EraDef.arrival` (YAML `arrival`) is now `historical`; the `arrival` property returns the historical month or a window's midpoint, so M11's applied migration 0028 runs unchanged on the new data. Custom silicon's +5 is an era boost with `cap_points` and `own_chip` in `tech_factor`. Migration 0030 records M12b's eras a save is past (future ones at their seeded month).
- **Outside my namespaces in balance.yaml** (needed by the loader): `products.seller_rate.device_oems` (0.1) and `rivals.function_mix` for the six new categories. `tech_frontier.yaml` gains tech weights for the new categories (devices and servers on devices, chips on chip design).
- **Codex review 3, finding 7 (P3): facility kinds dispatch by output** (commit `M12b: Codex review 3 finding 7`, referenced by M12r). Compute consumers take only kinds whose `output_good` is a compute good (`compute.is_compute`): `live_facilities` (so `allocate`, `spare_by_region` and `equivalent` never see a plant; no KeyError), Cloud reliability (`mean_reliability`), Cloud's "can start" and spare capacity on the Infrastructure view, and the Infrastructure build preview (refuses a non-compute kind). Outages are rolled only for kinds with `outages: true` **and** compute output (`outages.has_outages`), since an outage takes down hosted products. Operating cost dispatches by kind (data centres to `6300`, others to `5000`). Payment, going live, depreciation and sale stay in the shared lifecycle. Contract test: `tests/unit/test_facility_kinds_contract.py`, with a synthetic non-compute kind.
- **Sub-tasks 1-6 landed in one commit** (they share the data and the phase-5 plumbing), 7-8 in another.

## Follow-ups

- AMD goes bankrupt around 2020 on seed 1: rivals' feature pushes grow builder pools by 10% each with fast feature expectations (8-10 a month) and two products. Rival tuning is outside this lane; M15 should look at pushes in fast categories.
- Rival device makers do not buy chips from the chip market or contract manufacturing from Foxconn: those markets' demand is abstract (D0 and growth), not derived from rivals' sales.
- Inventory and build-ahead (out of scope), plant refurbishment after its life, and chips consumed by GPU data-centre builds.
- Old saves (before M12b) get no hardware markets or incumbents, as M12a's Cloud hosting.
