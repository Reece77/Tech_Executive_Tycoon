# v3 balance summary (M23b, for the v3 retrospective)

## What was built

- **Strategies** (`tst/balance/strategies_v3.py`): three v3 scripts plus a baseline, on top of v2's arms. They act only through `Game.act` and read only what a player sees.
  - `full_integrator` adds mines, a lithium converter, a wafer plant and a 28 nm fab to steady_regions' software, phone and SoC lines.
  - `mineral_baron` explores and mines, selling to the market.
  - `foundry` is a pure-play fab with foundry contracts.
  - `devices_regions` is the same phone and SoC on contracts with no owned chain: the integration baseline.
- **Group measurement** (`tst/balance/game.py`): the group's monthly P&L with intercompany sales eliminated. Group ARR is 12 × the last month's revenue.
- **The v3 targets** (formulas §43; `tst/balance/v3.py`, `tools/v3_targets.py`):
  - I1–I3: integration pays modestly, at year 30, against devices_regions.
  - S1–S2: the lithium spike and the gallium ban.
  - F1: foundry demand.
  - L1–L4: 30 years across the chain.
  - V6 extended to a 2039 full-integrator group.
- **Weekly jobs**: `weekly-v3-shocks`, `weekly-v3-integration` and `weekly-v3-long`, plus `weekly-v6-integrator`.

## What was tuned, and what moved

No balance key was tuned. Every change was to measurement (product manager rulings) or to a script a sensible player would play differently (rule 2).

| Change | Why | Effect |
| --- | --- | --- |
| I1/I2 against devices_regions (ruling, 2026-11-11) | steady_regions is pure software at a 63% margin; any device line dilutes it, so the original comparison measured hardware, not integration | I1 −12.8 → −2.6 points at year 20 (pre-merge) |
| I1–I3 at year 30, year 20 printed (ruling, 2026-11-12) | at year 20 the group fab is inside its 5-year depreciation, dearer a start than market wafers | I1 −3.3 → +0.1 points; I2 1.03× → 1.04×; I3 0 → 2 wins |
| full_integrator stops renewing TSMC once its fab covers its SoCs, and contracts spare starts | the script kept buying foundry wafers beside its own fab | own fab supplies the SoCs; foundry sales fill spare starts |
| foundry signs M23a's foundry contracts (80% of capacity, 36 months, slot price) | the pure-play fab had no customers before M23a | F1 10 of 10 from month 1 |
| mines at the smallest capacity, funded at the definitive study's overrun cover | the script asked for 2× a $4.9B estimate | mines get built, but after 2024 on 9 of 10 seeds (L4) |
| exploration from stage 3, four projects, no pre-feasibility; converter on a resource estimate, concentrate at spot | the chain started too late to order by year 15 | converter, wafer plant and fab ordered 2020–2023 |
| L2 counts a derived good's spot market as its rival supply | solar polysilicon and 300 mm wafers have no named refiner (M20 derives them) | L2 met |
| M22 target 7 narrowed (ruling from M23a) | M23a's export controls on rivals move rivals' books from October 2022 | nightly reads yes |

## What remains

| Miss | Owner | Reading | Bound | Why |
| --- | --- | --- | --- | --- |
| I1 (formulas §43) | M28 | +0.1 points at year 30 | −1.9 points | in 2039 subscriptions are 100% of the group's revenue and cost of goods 0.2–0.3% (8–17% at year 20); an own fab 23–24% cheaper a chip cannot move group margin by points. Supply-driven prices from 2026 (M28) change the fab's economics |
| V3.ai (§30.7) | M23 | +0.9 points at year 10 (54.1% vs 53.2%) | 2 points below ai_regions | an AI-models company is about $7M ARR at year 10 |
| V5.cells (§30.7) | M23 | 72% (steady_regions), 69% (research_heavy) | 40% empty | long-lived startups hold rivals.startup.max_alive's places |
| V5.cats (§30.7) | M23 | fintech 2030s empty in 6 runs; ai_models 2030s in 5 | 7 of 10 runs | as V5.cells |
| M16 T3, T4 (§31.9) | the product manager's later ruling | T3 integrated down on 3 of 10; T4 revenue 7 of 10, cash 9 of 10 | recorded, not in `known_misses.py` | the fixture's subsidiaries take compute supply, which M23a's group supply does not touch: identical to M16 |
| L4 (printed) | follow-up | 1 of 10 | — | a lithium deposit's estimate ($4–5B) exceeds the group's 2024 cash ($2–4.5B) |

M23 closes with this milestone, so V3.ai, V5.cells and V5.cats need a new owner from the product manager.

Other v3 follow-ups:
- Rival chip, cloud, device and contract-manufacturing startups never launch (V5's scheduled-only list).
- Mine finance (project finance or offtake prepayment) for L4.
