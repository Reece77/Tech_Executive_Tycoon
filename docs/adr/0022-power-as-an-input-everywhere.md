# ADR-0022: Power as an input everywhere

- Status: Accepted
- Date: 2026-11-14
- Spec sections: formulas.md §46 (M32), with §22, §26, §33.5, §35, §36, §38, §41

## Context

Before M32, each facility kind priced its electricity in its own way. Data centres paid their whole operating cost × the region's power index (§33.5). Refineries and fabs paid MWh × `refining.power_cents_per_mwh` × the index. Mines paid an energy share of their variable cost × the index. Chain companies paid a power share of their cash cost × the index. M32 adds contracts, owned plants, grid queues, carbon prices and outages. Each needs to know how much energy a company uses, where, and at what price. M32 must also keep every facility's power cost to December 2025 within 1% of `main` (§46.8 target 1), keep every earlier guard, and fit the 500 ms turn-time guard.

## Decision

1. **One meter, one price.** Every facility that pays for power reports its **energy in MWh** for the month, by company and region (`tst.sim.power.demand`). Each data-centre kind gets an energy figure per live unit, set so that energy × the reference price equals its old operating cost. A fab reports wafer starts run × its node's MWh a start. A refinery reports output × its recipe's MWh. A mine reports the energy share of its variable cost ÷ the reference price. All of these are in `power.draw`. Each facility then pays **energy × the region's grid price**, where the grid price is `refining.power_cents_per_mwh` × M17's index (`tst.sim.power.grid.price_cents`). Until 2026 this is the old cost, worked out a different way, so history holds. Assembly plants and offices have no meter: their power is inside their fixed costs, as before.
2. **The grid price after 2025** is the index (M17's seeded path) × M28's balance factor for the region's power good × (1 + carbon pass-through). The pass-through is the change in the region's carbon price since December 2025 × the grid's carbon intensity, as a share of the price. Data prices to 2025 already include carbon, so carbon is never counted twice.
3. **Supply order and settlement.** Facilities post their energy at the grid price in phases 4–6, as they always have. Phase 6 ends with **power settlement** (`tst.sim.power.settle`), one entry a company. Energy is matched to supply in this order:
   1. behind-the-meter plants at the site;
   2. the company's other plants in the region;
   3. PPAs;
   4. the grid.

   Matched energy that was already charged at the grid price is credited back. Own plants charge their fuel, operating cost and carbon. Energy from a plant that is not behind the meter also pays `power.grid_charge_share` of the grid price. PPAs charge their price on the energy used and the take-or-pay share on the volume not taken. A plant's surplus energy sells to the grid at the grid price × (1 − `power.export_discount`). Energy balances per company and region: demand = own plants used + PPAs used + grid. Each plant's output = used + exported + curtailed (a behind-the-meter plant never exports). Money balances because every line is a double-entry posting to cash.
4. **Accounts.** The settlement's energy lines post to `5950 energy`, a new cost-of-revenue account. Plant revenue (exports) posts to `4950 energy sales`. A plant is a `Facility` of kind `plant` (ADR-0020's one facility model), with a `Plant` record keyed by the facility id, as fabs are. Its capex goes to 1500 and its depreciation to 6700/1510 over its type's life. It is a per-entity book like every facility's: nothing assumes one player company.
5. **Hidden values, and what is drawn.** A plant's capex overrun is drawn once at the order (stream `power` key `(1, facility)`), like a mine's or a refinery's. It is revealed as the capex is paid, and it stretches nuclear builds by `power.overrun_delay`. Nothing else in the future is stored:
   - A queued project connects with a monthly hazard (key `(2, entry)`). The API shows the wait as a range, never a draw.
   - Grid outages (key `(0, region_index)`) are drawn the month they happen.
   - A plant's forced outages (key `(1, facility)`, offset by the turn) are also drawn the month they happen.
   - After 2025, carbon prices, policy steps, grid decarbonisation and queue waits follow a seeded yearly path (key `(0, region_index)`). It is stored only up to the current year.
6. **From when.** Grid queues for data centres and fabs, grid outages, the carbon pass-through and rival power producers all start at `power.start` (January 2026, with M28's world). PPAs and owned plants are the player's choice at any time (plants from stage 4, a one-off unlock). No balance script used them before M32, so earlier guards hold.
7. **Power producers** are M28 chain companies. Each region gets a world good `power_<region>`, in MWh a year: named producers from `power.yaml` and one aggregate of "other generators" per region. They are appended **after** every existing chain company and aggregate, so no existing stable key moves. They use M28's operations and its December capacity rule on the region's power price. Rival foundries' plants are world facilities of that good. Rival PPAs are M28 offtakes on it.

## Consequences

- Every facility site calls one function for its energy price, so later supply changes reach every kind at once.
- The settlement runs after phase 6's operating costs and before financing, so a month's energy books close inside the turn's transaction (ADR-0004).
- Unit costs on facility screens show grid-priced energy, and the Power screen shows the settlement. A fab with a behind-the-meter plant therefore sees its saving on the Power screen, not in its cost per start. This is recorded in M32's brief.
- Outages before 2026 stay M12a's (§22.5) only.

## Alternatives considered

- **Charge each facility its blended contract and plant price in its own phase:** it needs the month's supply before demand is known, and money stops balancing when a fab's run changes after the forecast.
- **A separate power-producer model outside M28:** it would duplicate M28's books, capacity rule and news.
- **Apply queues and outages from 2010 using the data:** that would change M12a's and M21's history guards.
