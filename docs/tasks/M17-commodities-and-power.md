# M17: Commodities, offtake and regional power (v3, lane A)

**Goal:** the raw materials under chips and devices get real prices. Twelve commodities (high-purity quartz, silicon metal, polysilicon, gallium, germanium, copper, tin, tantalum, cobalt, lithium carbonate, NdPr oxide, neon) follow their 2010–2025 history, including the rare-earth bubble, the lithium super-spike and the 2022 neon shock, then move in seeded cycles with export bans and booms. They flow into device, server and wafer costs. Companies can buy spot, sign contracts or lock multi-year offtake deals with named suppliers. Power gets a price by region, so data centres cost less where power is cheap.

**Spec sections:** §8 (value chain), §9 · **ADRs:** 0002, 0003, 0013 (stream `commodity` 47), 0019, 0020 (one market-good model) · **Formulas:** `docs/formulas.md` §33 (all), with §22, §26 · **Data:** `docs/v3-research/v3-data-dossier.md` §1–§3 · **Depends on:** M16 (`m16-done`) · **Lane:** A, alongside M18 (lane B)

## Lane

- Its own session and branch (`m17-commodities`). **Merge order: M17 merges first;** M18 then merges `main`, wires its feasibility studies to M17's price deck, and regenerates golden snapshots.
- **M17 owns:** `commodities.yaml`, `commodities_history.yaml`, `suppliers.yaml`, `power_history.yaml`; the commodity and power goods in the market-good code; the BOM and wafer cost mixes; offtake agreements; the Market screen's Commodities tab and the product cost breakdown; data centres' regional power cost.
- **M17 must not edit:** `geology.yaml`, `cities.yaml`, the new exploration code or the geologist role (M18's).
- **Interface for M18:** `commodity.price(state, key, turn)` and `commodity.deck(state, key)` (the price deck a feasibility study uses: the current price and the long-run level). Publish these early on the branch (sub-task 2) so M18 can code against them.
- **Shared files:** `balance.yaml` (add only `commodity.*`, `offtake.*`, `power.*`), `docs/formulas.md` (notes in §33 only), `CHANGELOG.md`, `docs/data-dictionary.md`.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Mines, refineries and suppliers as operating rivals (M19, M20). Gallium and germanium as by-products (M20). Export controls as policy (M22; M17's export-ban shocks are price and allocation events only). Commodities in software or cloud products beyond data centres' power.

## Sub-tasks (commit after each)

1. **Data:**
   - `commodities_history.yaml` from dossier §1.1 and §1.3 (annual values held per year, shocks in their months), each value with its source tag;
   - `power_history.yaml`: research industrial power prices by region 2010–2025 from public sources (EIA, Eurostat, IEA or national regulators), cited in the file; use §33.5's defaults only where sources are thin, marked as assumptions;
   - `suppliers.yaml` from dossier §3.1–§3.2, **spot-checking every 2010 revenue the dossier marks as recalled (R)** against a source, cited;
   - the keys; stream `commodity` in ADR-0013; §33.3's and §33.5's examples as unit tests.
2. **Commodity goods** (§33.1): the twelve goods and power in the market-good model, monthly history, the index, seeded AR(1) and shocks after 2025, allocation in shocks. Publish `commodity.price` and `commodity.deck`. **Tests:** history equals the file on every seed; a seeded test of shocks; no future value in the API (extend the hidden-value test).
3. **Costs** (§33.2): the device, server and wafer mixes; the product cost breakdown. **Test:** a software-only company plays exactly as before.
4. **Contracts and offtake** (§33.3–§33.4): commodity contracts, offtake with collar, prepayment, take-or-pay and supplier breach; the suppliers. **Property test:** the ledger balances through offtake payments and prepayment.
5. **Regional power** (§33.5): data centres' power by region; the North American build unchanged.
6. **API, CLI, screens:** the Commodities tab (price charts to the current month, allocation, contracts, offtakes, suppliers), the cost breakdown, power by region on the Infrastructure screen. **CLI:** `tst commodities`, `tst offtake --good --supplier --years --volume [--prepay]`. Glossary entries.
7. **Balance and e2e:** §33.6 targets printed and recorded; tune only `commodity.*`, `offtake.*` and `power.*`. **Playwright:** (a) the Commodities tab shows 2022's lithium spike on a 2023 save; (b) sign a lithium offtake and see it on the device cost breakdown; (c) a data centre in South and Southeast Asia shows a lower power cost than one in North America. Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every price equals history through 2025 on every seed; no future value reaches the API.
- [ ] §33.3 and §33.5 examples pass as tests; the ledger balances through offtake (property test).
- [ ] A software-only company plays exactly as before; §22.7 target 4 holds for a North American build.
- [ ] §33.6 targets met (printed, values recorded).
- [ ] `make check` and CI `e2e` green; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m17-done`.

## Manual check (Reece, after merge)

On a device maker in 2020, sign a lithium offtake, play into 2022 and compare your margin with the cost breakdown's spot line. Then build a data centre in Bangalore and compare its power cost with your home one.

## Decisions made

Engineering and data decisions the spec, ADRs and brief did not cover (CLAUDE.md §9 rule 1 for the tuning), with their numbers:

1. **Branch.** Built on `claude/m17-commodities-power-pbrgmr` (the session's designated branch) rather than `m17-commodities`; it is this milestone's only branch.
2. **One market-good model.** Commodity and power months are `GoodMonth`s in `GameState.supply` and rows of M12a's `supply_month` (new nullable `shock_kind`), after M12a's goods, sorted by key. The index is the price over the 2010–2019 mean of the monthly history.
3. **History shape.** Annual values are held for their year; §1.3's shocks are geometric paths between dated points (`shocks` in the history file) replacing the annual value inside their months. The monthly shapes are assumptions tagged A where the dossier gives only annual values: lithium rises from $8,000 (January 2021) to $80,000 (November 2022, the peak; Chinese spot ran far above the contract average) and back to $18,000 by December 2023, each year's mean near its annual value; Nd oxide peaks at $260/kg in August 2011; neon follows §33.1 exactly. History allocations (all shares assumptions): rare earths Jul 2010–Dec 2011 0.8, neon Mar–Jun 2022 0.6, gallium/germanium Aug–Dec 2023 0.8 and Dec 2024–Dec 2025 0.75/0.67, cobalt Feb–Dec 2025 0.85, quartz Oct–Nov 2024 0.6.
4. **Quartz** is the USGS ground-HPQ range midpoint (2021 $8,250/t held back to 2010). **Neon** trades in lots of $1,000 at index 1.0. **Polysilicon** is priced at semiconductor grade (solar × 5); its index is solar's.
5. **After 2025.** Monthly AR(1) on the log price toward the 2015–2025 **nominal** median (the game's other goods are not inflation-indexed), monthly persistence `phi^(1/12)`, sd `vol/√12`. `commodity.vol` is each good's robust sd of 2011–2025 annual log changes (MAD × 1.4826, so the shocks are not counted twice); quartz and neon use the plain sd. Shock chances a month: export ban 0.002 (×3 above 60% concentration), demand boom 0.003, supply disruption 0.003; rise, allocation and length per kind in `balance.yaml`; `commodity.gap_months` 24 after one ends. Power: AR(1) toward each region's 2010–2019 mean, `power.phi` 0.9, `power.vol` 0.08, no shocks; North America held at 1.0.
6. **Stream keys.** `commodity` (47) keys `(0, good_index)`, `(1, region_index)` and `(2, deal_id)`: ADR-0013's "the good's index (power: its region's index)" would have given quartz and North America's power the same generator, so a family comes first (ADR-0013's row updated).
7. **Interface for M18.** `commodity.price(state, key, turn, data, balance)` and `commodity.deck(state, key, data, balance)`: the brief's signatures plus the data and balance every engine function takes. `price` serves any history month and, after 2025, the state's own month (between turns the month just played); a later month, or an earlier seeded month the state no longer holds, raises `FutureMonthError`. `deck` gives the current price and the long-run level in the good's unit and in dollars a volume unit.
8. **Costs.** BOMs blend `(1 - w) × own + w × mix`; wafers scale `price × ((1 - v) + v × mix)` (§33.2's two forms, `mode: blend|scale`). A unit's commodity use is `base × share × weight / (mean price in cents a volume unit)`; a chip's through its wafer. In a commodity shortage a product makes at most `Σ weight × the company's allocation` (a weighted mean, not the minimum: partial substitution and stocks).
9. **Deals.** Spot stays in the BOM; a deal's effect posts separately: `taken × (deal price - spot)` to 5000 against cash each month, deals in id order. Offtake take-or-pay is monthly (`0.7 × deliverable - taken` at the deal price, to 6900); a contract's is 30% of its unused volume at its end (M12a's rule). Prepayment sits in the existing `1200_prepaid`, drawn against each month's purchases and take-or-pay; what is left comes back in cash when the deal ends or breaches. Protected volume (100% allocation): a prepaid offtake, or any deal signed before the shortage began. A severe shock for a supplier is spot ≥ 2 × the collar ceiling; breach chance `(1 - reliability) × 0.10` a month; a supplier past its `until` month breaches at once (Ingas, Cryoin after February 2022).
10. **Suppliers.** 44 in `suppliers.yaml`: the dossier's §3.1–§3.2 companies plus producers §2 names, so every good has at least two. Every 2010 revenue the dossier tagged R was spot-checked (2026-11-08) against a published figure (the session's network could not open sec.gov or company PDFs directly; each figure is read from search results quoting the source): Freeport $18,982M, BHP $52,798M, Codelco $16,066M, Albemarle $2,363M, SQM $1,830M, MEMC $2,239M match; Rio Tinto's ~$60B was gross sales ($60.32B), the IFRS revenue line $56,576M is used; Molycorp is $35.2M, not ~$40M; Lynas pre-revenue and GlobalWafers (inside SAS) are consistent but unverified; Hemlock is not disclosed. Production shares and reliabilities are assumptions.
11. **Power data.** Research (EIA Table 2.4, Eurostat nrg_pc_205 releases, Eskom tariffs) gave sourced ratios only for Europe 2022–2025 (2.40, 2.79, 2.55, 2.46) and Africa 2019–2025; everything else used §33.5's defaults, marked A. The research's own rough estimates put South and Southeast Asia at about 1.1–1.3× the US and East Asia at about 1.4–1.5× (US industrial power is cheap); as the brief directs for thin sources, the defaults (0.85, 1.2) stand. §33.5's Europe example ($300 in 2022's spike) implies 1.5; the data say 2.40 for 2022, so the example's unit test checks the formula at the example's index.
12. **Who pays power.** A data centre's whole operating cost (§22.2: mostly power) × its region's index; assembly plants are not (§33.5 names data centres; fabs later). Own-capacity ranking (cheapest first, §22.2) still uses the North American cost.
13. **Target 2's measure.** §26.7's reference phone (components index 1.0, $40 SoC, $13 fee) with its commodities at their monthly history, against the same phone with commodities at their 2020 mean: "against 2020" then isolates the commodities from the 2021 chip shortage in the components index.
14. **Target 3's script.** M12b's device company from January 2020 signs 5-year lithium (SQM) and cobalt (Glencore) offtakes after its first month, sized to 12 × that month's use (a first draft sized to the 20,000-unit contract bought twice what it sold and paid take-or-pay on the rest); no prepayment.
15. **Tuning (rule 1, my keys only).** `commodity.mixes.device_bom.share` 0.15 → 0.033: at 0.15 the reference phone rose 43% at the lithium peak (band 3–8%); at 0.025 target 3's gap was 2.5 points; 0.033 gives 7.3% and 3.1–3.3 points. `commodity.phi` 0.9 → 0.6: at 0.9 lithium's trend stayed above index 3.0 for 103 months (≤ 36), at 0.6 at most 24 months on seeds 1–10 and 25 on seeds 11–40 (every good shocked on 22–29 of 30). `server_bom` (0.08) and `foundry_wafer` (0.10) keep §33.2's shares (no target binds them).
16. **Earlier milestones' expectations.** M12b's unit cost at January 2010 is now $232.54 (the BOM carries January 2010's commodity mix, index 0.925): its hardware unit tests and e2e flow (a) expect the blended index. M12b's §26.6 targets on this branch: T2 32.5% on 10/10, T3 0.69/0.66/1.35, T4a +8.4, T4b −49%, T5 30%, T6 100%, all in band; M12a's §22.7: T2 0.62/1.23, T3 10/10, T4 +30%/+60% and AI margin gap +15.6 points, T5 10/10, T6 1.05/0.17, all as before.

## §33.6 targets (seeds 1–10, `tools/m17_targets.py`)

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| 1 history holds | 0 months off the file on 10 seeds; no future month in any response (`test_api_commodities.py`) | 0 | pass |
| 2 reference phone at the lithium peak (Nov 2022) | +7.3% ($249.15 against $232.11) | 3–8% | pass |
| 3 hedged (lithium and cobalt offtakes from 2020) − spot, 2022 gross margin | +3.1 to +3.3 points, 10/10 (seed 1: 37.6% → 40.9%), no breaches | ≥ 3 | pass |
| 4 cheapest region's GPU opex per CU, 2023 | South and Southeast Asia 0.85 (Europe 2.79, East Asia 1.2, Latin America 0.9, Africa 1.17, Oceania 1.3); §22.7 target 4 +15.6 points for North America | ≤ 0.85; target 4 holds | pass |
| 5 seeds with a shock in 2026–2039, per good; longest above 3.0 | 7–10 of 10 for every good; 24 months | 6–10; ≤ 36 | pass |
| 6 software-only | golden snapshots unchanged | unchanged | pass |

## Follow-ups

- **Power data.** With eia.gov, ec.europa.eu and iea.org reachable, replace the A rows of `power_history.yaml` from EIA Table 2.4, Eurostat nrg_pc_205 and IEA's end-use prices; on the research's estimates South and Southeast Asia and East Asia would be dearer than North America, so §33.5's design intent (cheap power somewhere) may need a region-level design call (for example Nordic or hydro cities as their own sites).
- Verify the four unverified supplier revenues (SAS full year from MOPS, Lynas FY2010/11, OCI, Hemlock) from primary filings.
- Pitches and the CFO's build proposals still cost a data centre at the North American operating cost (M10c/M13b paths); the cheapest-first ranking of own capacity too.
- Commodity shocks after 2025 have no inbox news or event; an export ban could be a minor event with M22's geopolitics.
- Offtake volumes are fixed a year; a "flex" band or a renewal flow would help a growing company. Rivals do not hedge (their costs are abstract).
- Gallium and germanium as by-products (M20), suppliers as mining and refining rivals (M19, M20), export controls as policy (M22), as the brief says.
