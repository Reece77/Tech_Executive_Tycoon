# M21: Fabs and process nodes (v3, lane A)

**Goal:** the last link: making chips. Named process nodes (65 nm to 2 nm, then seeded future nodes) arrive on their real dates. A company with enough `process` research can build a fab at a node, buy EUV tools from a single supplier, learn yield, run its own chips at cost and sell spare capacity as a foundry. TSMC, Samsung, Intel, GlobalFoundries, UMC and SMIC become operating rivals whose capacity sets the foundry market. Chips on better nodes are better chips.

**Spec sections:** §8 (value chain) · **ADRs:** 0002, 0003, 0013 (stream `fab` 54), 0019, 0020 · **Formulas:** `docs/formulas.md` §38 (all), with §26, §31, §33, §36 · **Data:** `docs/v3-research/v3-data-dossier.md` §3.3–§3.4, §4 · **Depends on:** M20 (`m20-done`) · **Lane:** A, alongside M22 (lane B)

## Lane

- Its own session and branch (`m21-fabs`). **Merge order: M21 merges first;** M22 merges second (it restricts EUV tools and fab services, so it wires to M21's goods at merge).
- **M21 owns:** `nodes.yaml`, the `fab` facility kind and new `backend/tst/sim/fabs/`, the `euv_tools` good, rival foundries (from `suppliers.yaml`'s foundries and equipment makers), the `fab_engineer` role, the chip node-quality rule in §26's cost path, a **Fabs** screen.
- **M21 must not edit:** `countries.yaml`, `export_controls.yaml`, `sim/geopolitics/` (M22's).
- **Shared files:** `balance.yaml` (`fab.*`, `facility.kinds.fab`), `docs/formulas.md` (§38 notes only), `CHANGELOG.md`, `docs/data-dictionary.md`, `eras.yaml`-style seeded windows for future nodes (append only).
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Export controls on tools and fab services (M22), memory fabs (DRAM, NAND), advanced packaging as its own business, rival fabless designers' own fabs.

## Sub-tasks (commit after each)

1. **Data and formula tests:** `nodes.yaml` from dossier §4 (dates per foundry, EUV, capital per wafer-per-year, wafer prices, each tagged V, R or assumption), future nodes' windows, `fab.*` keys, rival foundries' fabs by region and node (2010 to 2025), stream `fab` in ADR-0013; unit tests for capex, cost per good die at a yield, and the node-quality rule.
2. **Nodes and rival foundries** (§38.1, §38.3): history on every seed; rivals' research after 2025; the foundry market's price and allocation from their capacity (replacing M12b's abstract slots). **Test:** foundry prices through 2025 within 10% of M12b's on the same seeds.
3. **Fabs** (§38.2): building (capex, overrun, construction, EUV tools with lead time), yield learning, costs, own chips at cost, foundry sales, node upgrades. **Property tests:** ledger balance; book value never negative.
4. **Better chips** (§38.4).
5. **API, CLI, screens:** the Fabs screen (each fab's node, capacity, use, yield curve, cost per good die against the market price, foundry customers), the node timeline on the Market screen, the chain on the Group screen; **CLI:** `tst nodes`, `tst build-fab --node --capacity --region`, `tst fabs`, `tst upgrade-fab --fab`.
6. **Balance, e2e, close-out:** §38.5 targets printed and recorded; tune only `fab.*`. **Playwright:** (a) the node timeline shows TSMC's N5 in 2020; (b) build a mature-node fab and see yield climb; (c) a leading-edge fab waits for EUV tools; (d) your fab sells spare slots to a rival designer. CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Historical node dates hold on every seed; foundry prices through 2025 stay within 10% of M12b's.
- [ ] The ledger balances through fab construction and operations (property tests).
- [ ] A company that never builds a fab plays exactly as before.
- [ ] §38.5 targets met (printed, values recorded).
- [ ] `make check` and CI `e2e` green; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m21-done`.

## Manual check (Reece, after merge)

With a chip business and a high `process` level, build a 28 nm fab in 2014, then a 7 nm fab in 2019 if you can afford the EUV wait. Compare your accelerator's cost and quality against a TSMC slot.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
