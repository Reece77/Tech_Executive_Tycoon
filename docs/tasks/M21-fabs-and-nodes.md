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

Engineering and data decisions the spec, ADRs and brief left open (M21 agent, 2026-11-09). Items marked **for review** change what a reader might expect. formulas.md 38.6 has the as-built rules.

1. **Rival foundries are data-driven rivals, not companies (for review).** suppliers.yaml has no foundries or equipment makers, so `nodes.yaml` lists the six foundries (dossier 3.3) and ASML (3.4). Each has the nodes it reached (dossier 4; TSMC, Samsung and Intel on the node table's `first` dates, the others their own, R), capacity by year (TSMC, GlobalFoundries, UMC and SMIC from annual-report figures, R/D; Samsung's and Intel's logic capacity A), an open share (Intel 0, then 5% from IFS in March 2021) and where it stops. They own no products and hold no cash: their research after 2025 is a seeded lag per node, their capacity a seeded growth a year, all a pure function of the seed (nothing stored). Intel stays M12b's chip incumbent as well.
2. **How capacity sets the foundry market (for review).** Through 2025 M12b's foundry wafer index and allocation (the 2021-2022 shortage, the 2023-2024 advanced-node crunch) are read as the rivals' capacity against demand, so the factor `(expected / actual)^1` is exactly 1 there unless the player sells slots (38.5 target 6 holds at 0.00%). After 2025 each foundry grows 3-9% a year (seeded) against an expected 6%, so prices and allocation drift with the rivals' capacity (within 0.8-1.25x) on top of M12a's seeded shocks. This changes a fabless chip company's prices after 2025 only; a company without chips sees nothing.
3. **Node prices.** A node's market price is its dossier price at its stated month, moved by the foundry wafer index since and by 14.5% for each generation it falls further behind the edge (dearer when it was nearer): 28 nm $3,000 in 2024 is about $3,800 in January 2016; N7 $9,346 in 2020 about $10,300 in mid-2024 (dossier ≈ $9,500). Mature nodes' prices (65 nm $1,600, 20 nm $3,600) are assumptions; 40 nm uses the dossier's UMC price. A wafer contract may now name a node (`production_contract.node`, nullable): it locks the node's price at a foundry that runs it; without one it buys M12b's wafer of its type, as before. `chips.contract.foundries` gains Intel (from March 2021), GlobalFoundries, UMC and SMIC (price multipliers A).
4. **Building.** Construction by the node's age at the order: under 36 months (or not yet in volume) is leading-edge (36 months), else mature (24). A fab may be ordered up to 36 months before its node's first volume (fabs are built for nodes in development) and goes live no earlier than it; the process level it needs is the domain's baseline at the node's first volume + 10 (`fab.node_level`; a future node: its window's midpoint, so nothing reveals the drawn month). Overrun 0-25% (M20's range for vendor-quoted plants).
5. **EUV tools.** One tool per 2,000 starts a month (A: 25 for a 50,000-start fab). Lead time 12 months, 24 in a shortage of the new `euv_tools` good (`components_history.yaml`: $120M a tool c.2020, V; tight 2021-01 to 2023-06, A); and no sooner than ASML's open share (25%, A) of its yearly shipments (2017-2025 R, then +5% a year) covers the company's queued tools. They must arrive 12 months before completion. Their cost is inside the capex (the CSET capital per wafer-per-year includes tools); the index is shown and is M22's lever.
6. **Yield learning.** Start yield by the node's age at go-live (0.35 at first volume to 0.7 at 36 months); a month closes `0.075 x skill / 12 x (1 + 0.02 x min(20, lead over the need)) x coverage` of the gap to 0.9. Measured: 35% to 80% in 24 months (target 4).
7. **Costs.** Fixed running cost 6% of paid capex a year (staff beyond the lead engineers, maintenance, utilities; A); materials: M20's 300 mm wafer at market price plus gases and chemicals at 8% of the node's reference wafer price, moving with neon (0.5), gallium and germanium (0.25 each); power 0.6 + 0.2 MWh a generation a start (5 nm about 2 MWh; A) at M20's $68/MWh x the region's index. Fab engineers (new role, manufacturing and data, one per 2,500 starts) are the lead engineers only; their pay is payroll and counted in the cost a start shown. Cash costs post to 5000, depreciation (each capex part over 60 months from its live month) to 6700, slots to a new `4420_foundry_sales`.
8. **Own chips (for review).** A fab supplies chip products of its own company only (a group transfer is a follow-up). Its starts are shared by last month's need (equally at first) and taken before contracts (so a contract the fab covers pays take-or-pay). A fab chip posts packaging only at sale, the fab's month carrying the wafer, so nothing is counted twice; the unit cost shown (and used for the GPU capex cut) blends the fab's last cost per good die with the contracts' by capacity. A chip product may launch on a live fab instead of a wafer contract.
9. **Slots.** Spare starts sell at the node's price x 0.9: 85% of them x yield / mature yield x reliability, all of them while the foundry market or the foundry wafer good is short. The customers listed are the chip incumbents (NVIDIA, Intel, AMD, Qualcomm), equally: their own costs stay abstract (M12b).
10. **Node quality.** A chip's node is its largest fab share's, else its running contracts' newest; the category's median node is the one in volume 36 months earlier (A), for every chip category; +3 cap points a generation ahead, nothing for being behind (so M12b's chips lose nothing). Power efficiency is not modelled (follow-up).
11. **Conversions** go one node at a time, once the next node is in volume, offline for 12 months (A) or until new tools are installed; yield restarts at the new node's start. A fab sells through M12a's facility sale (half its book value).
12. **Measuring the targets.** T1: every (foundry, node) date against the timeline, seeds 1-10. T2: the quote for 50,000 starts in January 2021 at 0% and 25% overrun. T3: a 5 nm fab live in April 2020 (made ready at once, staffed at skill 12), ten years of real months; the project's cash flows are its capex spread over 36 months then each month's slot revenue at the use asked (80%, 50%) less fixed cost in full and materials and power by use; "two nodes behind" is the same fab at a price two generations older (x 0.88^2); seeds 1-3. T4: a 5 nm fab live in April 2020 with exactly the node's research. T5: an AI accelerator on a TSMC 5 nm contract (January 2021) against the same company with its own 10,000-start 5 nm fab, cost per good die after the ramp (yield 80%+) at the fab's use (own chips and slots); seeds 1-3. T6: M12b's wafer price with the factor against without, January 2010-2025, seeds 1-10, and the golden snapshots.
14. **A nightly failure from main (rule 3).** `tests/integration/test_ten_years.py` opens every GET route; M20's `/refineries/quote` needs query parameters, so the test has failed on main since M20 (nightly run 42611693052, shard 4: 422 on `/refineries/quote`) and on this branch (run 42679888355, shard 3), and M21's `/fabs/quote` would fail the same way. Fixed here: the route list skips GET routes with required query parameters (the two quotes), which their own API tests cover.
13. **Tuning** (`fab.*` and `nodes.yaml` capital only): `fab.fixed_share` 0.09 → 0.06 and `fab.price_decay` 0.12 → 0.145 (T3: at 0.09/0.12 80% use gave 10.3%; at 0.07/0.12, 12.5-13.9% but 5.9% two nodes behind on seed 3; at 0.06/0.145, 12.5-13.8%, 0.0-1.7% and 2.5-4.1%); `fab.yield.learn` 0.07 → 0.075 (T4: 25 months); 28 nm capital $4,500 → $4,400 (T2: $6.08B at the most overrun).

## Follow-ups

- Fabs supplying other group companies' chips at a transfer price (M16 flows), and the group's own wafers (M20) into its fabs at transfer price (fabs buy the substrate at market now).
- Rival foundries as full rival companies (cash, products, fab announcements as events), and rival fabless designers choosing among foundries by price and node.
- A chip's power efficiency by node (38.4) as a feature for devices and data centres.
- Sandbox's "all seeded" mode (30.2) could seed historical nodes too; they follow history in every mode now.
- Memory fabs, advanced packaging (out of scope here).
- The Fabs screen's region list shows keys formatted, not regions.yaml labels (an API field would be cleaner).
