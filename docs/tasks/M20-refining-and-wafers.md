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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
