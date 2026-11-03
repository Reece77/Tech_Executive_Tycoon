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
  - the categories and the `device_oems` segment appended to `categories.yaml`; incumbents and entrants appended; the three eras appended to `eras.yaml`;
  - screens: product BOM and manufacturing panels, the Hardware screen, and chip products.
- **M12b must not edit:** `tst/sim/markets_public/`, `tst/sim/org/ceo.py`, `banks.yaml`, or the Finance Stock tab (M13's).
- **Shared files:**
  - `balance.yaml`: add only `hardware.*`, `chips.*` and the new facility kind;
  - `docs/formulas.md`: notes in §26 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** stream `manufacturing` (30), key `(facility_id,)`, for monthly yield noise, with 31–32 reserved for lane A. Add it to ADR-0013's main table with stable keys. New incumbents and entrants use the stable-key scheme from M12a's ADR-0013 amendment, so adding them must not move existing rivals; the M12a test for that must still pass.

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
6. **Eras** (§26.4): appended to M11's era system with their effects. Tests for historical arrival and effects.
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
- [ ] Adding the new incumbents and entrants leaves existing rivals' decisions unchanged (the M12a stable-key test).
- [ ] §26.6 targets 2–6 met (printed, values recorded); no new xfails.
- [ ] Merged after M13 with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m12b-done`.

## Manual check (Reece, after merge)

Launch a device on a Foxconn contract. Then build a plant in Shenzhen and see when it starts paying off. In an AI game, design your own accelerator and use it in your data centres.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
