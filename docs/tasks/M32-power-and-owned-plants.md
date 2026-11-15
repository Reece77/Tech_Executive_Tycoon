# M32: Power and owned plants (v4, lane A)

**Goal:** electricity becomes an input every facility needs and the late 2020s' binding constraint. The player buys power on the grid or under power-purchase agreements, or builds its own gas, solar-with-storage, wind and nuclear plants (from stage 4). Grid queues delay projects by years in congested regions, carbon prices move the cheapest plant type, outages cost wafers and uptime, and power decides where data centres and fabs can be built. History to 2025 is unchanged.

**Formulas:** `docs/formulas.md` §46 (all), with §22, §26, §33, §35, §36, §38, §41 · **ADRs:** 0002, 0003, 0013 (stream `power` 60), 0020, **0022 (new, power as an input everywhere; written in sub-task 1)** · **Research:** `docs/v4-research/power-dossier.md` · **Outline:** `docs/v4-outline.md` · **Depends on:** M28r (`m28r-done`), M30 (`m30-done`) · **Lane:** A, alongside M33 (lane B) and M34 (lane C)

## Reece's decisions (2026-11-13)

- **Power contracts by region and owned plants** (gas, solar with storage, wind, nuclear, small modular reactors later). Owned plants from **stage 4**.

## Lane

- Its own session and branch (`m32-power`) from `main`. **Merges last of the three** (it moves every facility's costs): merge `main` after M34 and M33, re-parent the migration, regenerate golden snapshots with a recorded reason if needed, and re-run every guard on the combined code.
- **M32 owns:** new `backend/tst/sim/power/` (demand, dispatch, contracts, plants, queues, carbon, outages); `power.yaml` (new, from the dossier with a source on every value) and M17's regional power data where it extends; the power-cost line in every facility's monthly costs (`fabs/`, `mining/`, `refining/`, cloud and assembly: a read of §46.1's energy cost in place of the region index); power producers as M28 chain companies (data and their December rule); the plant facility kind; the siting panel on build screens; the Power screen; `tst/balance/m32.py` (new).
- **M32 must not edit:** M33's equipment code (`equipment/`, ASML's chain-company data) or M34's regulation code; M31's platforms; M36's family code.
- **Shared files:** `balance.yaml` (add `power.*`), `accounts.yaml` (add accounts the plants need), `chain_companies.yaml` (add power producers; M33 adds ASML: keep both sides), `docs/formulas.md` (notes in §46 only), CHANGELOG, data dictionary, ADR-0013.
- **CLAUDE.md §9's decision rules apply.** §46.8 target 1 (history holds) is the guard: facilities' power costs to 2025 within 1% of `main`. M30's turn-time guards (500 ms on the `full_integrator` save, 1,000 ms everywhere) must still pass.

## Out of scope

Owning transmission lines; hydrogen; retail electricity to consumers; automating power decisions (a follow-up for an automation area). The named 2025 construction projects for fabs and mines go into M28's data here **only** if the dossier work finds them cheaply; otherwise list them as a follow-up.

## Sub-tasks (commit after each)

1. **Research, data and ADR-0022:** `power.yaml` from the dossier (plant types' capex, build times, capacity factors, fuel and operating costs, carbon intensity by year; queue waits by region; carbon prices and start dates; reliability; power producers with capacity by type), every value cited; `power.*` keys with comments; ADR-0022 (power demand from every facility, supply order, where outages and carbon post, per-entity books for plants); stream `power`; migration and data dictionary. **Test:** loader validation.
2. **Demand** (§46.1): draws per facility kind, monthly energy per company and region, replacing the region index cost. **Guard test:** §46.8 target 1's 1%.
3. **Supply** (§46.2): grid, PPAs (take-or-pay, termination), owned plants (types, overruns, the stage-4 unlock as a one-off), dispatch, surplus sales, behind the meter. **Property test:** energy and money balance per entity.
4. **Grid queues** (§46.3) and **siting** (§46.6): queue waits as ranges, projects that finish before connection, the siting panel.
5. **Carbon and disclosure** (§46.4) and **outages** (§46.5). **Seeded test** of outages.
6. **Rivals** (§46.7): power producers as chain companies with capacity decisions; rivals' PPAs and plants from 2026.
7. **Screens:** a **Power** screen (demand by region, supply mix, contracts, plants, emissions, outages), plant pages, the siting panel on data-centre and fab orders, M29 unlocks (Power at stage 4, or with a data centre or fab), glossary (PPA, capacity factor, interconnection queue, behind the meter, scope 2) and Explain on energy cost and a plant's levelised cost.
8. **API, CLI, e2e, balance and close-out:** `tst power`; Playwright: (a) sign a PPA for a data centre, (b) build a solar-with-storage plant behind a fab's meter and see the queue skipped, (c) a grid outage costs wafers and is shown; a practice save `pt-power` (a stage-4 integrator in 2027 with a fab and two data centres in congested regions); **§46.8 targets** printed and recorded, tuning only `power.*` (rule 1); re-run every earlier guard; CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `power.yaml` cites a source for every value; prices, carbon prices and dated rules to 2025 follow it (tests).
- [ ] §46.8 target 1: facilities' power costs to 2025 within 1% of `main` before M32, and every earlier guard unchanged.
- [ ] Energy and money balance per entity through dispatch, PPAs, plants and surplus sales (property tests).
- [ ] No plant overrun, outage draw or seeded future price reaches the API or a prompt (hidden-value test).
- [ ] §46.8 targets 2–6 printed and met, or carried with a recorded decision; M30's turn-time guards pass.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m32-done`.

## Manual check (Reece, after merge)

Load `pt-power`. Look at the siting panel for a new data centre in Virginia and in Texas. Build a plant behind your fab's meter, and watch your energy cost and outages over five years.

## Decisions made

1. **Workspace (2026-11-14).** The M34 session worked in the main checkout without a worktree; M32's `git checkout -b m32-power` there put M34's first commit on m32-power. M34 moved to `m34-regulation` itself, nothing was rewritten, and M32 worked only in `.claude/worktrees/m32-power` from then on.
2. **One meter, one price (ADR-0022).** Facilities keep posting their energy at the grid price in their own phases; a month-end settlement credits back what own plants and PPAs replaced and charges their costs (`5950 energy`, `4950 energy sales`). The alternative, each facility paying a blended price in its phase, cannot balance when a fab's run changes after the forecast. Consequence: a facility's unit cost shows grid-priced energy; the saving is on the Power screen and in 5950.
3. **History to 2025 is exact, not within 1%.** The grid multiple is M17's index to December 2025 and every site multiplies in the same order as before, so golden snapshots are unchanged and target 1's books hashes are identical on 20 runs (two strategies x seeds 1-10).
4. **Data centres' draw is their whole opex.** Their old opex was all x the power index (33.5), so their MWh are opex / the reference price (3.676 and 2.941 MWh a CU-month), recorded in power.yaml `draws` as D. Assembly plants and offices are not metered (their power is in fixed costs; metering them would change history).
5. **Carbon is in the data's prices to 2025.** The grid pays only the change in carbon price since 2025 x its intensity (`carbon.pass_through`); own gas plants pay carbon on their direct emissions from the start.
6. **From when.** Queues for data centres and fabs, grid outages, the carbon pass-through and power producers start at `power.start` (January 2026, with M28's world); PPAs any time; plants from stage 4. Before 2026 only M12a's outages exist.
7. **No hidden future is stored.** A queue connects by a monthly hazard (a median at the region's wait), outages are drawn the month they happen, paths only for the current year; the only hidden values are a plant's overrun (capex) and true completion, revealed as the capex is paid.
8. **Power producers live in power.yaml, not chain_companies.yaml**, so one file cites every power figure (the acceptance criterion) and M33's ASML entry cannot conflict. They are M28 chain companies of each region's power good, appended after every earlier stable key (M33's insert of ASML moves only M33's own indices).
9. **Rival hyperscalers** are M17-era static incumbents without facilities (ADR-0017), so only rival foundries sign PPAs and build plants (a follow-up).
10. **Assumptions in power.yaml** where no series was found (each marked A): Europe's and other regions' queue waits, capacity factors outside North America, gas prices outside North America, Europe and East Asia, outage rates outside the US, Africa's generation before 2024, producers' technology mixes. Africa's outage rate is 6 a year (12 would be an outage every month).
11. **The Power unlock is M29 system 27** (25 is M34's Regulation; 26 is left for M33).
12. **M30's state-hash fixture** (`tests/fixtures/m30_state_hashes.json`) changes with the new state fields from the first month, as M27b's, M28r's and M31's did. It is recorded on Linux (exact float digests), so it is re-recorded once, after merging M33 and M34, by a temporary CI job.
13. **Target 3's reading.** "A fab with an owned gas or solar-storage plant" is read as the better of the two, the player's choice; both are printed. Solar with storage misses its IRR band: at North America's $68/MWh (2010 dollars) its levelised cost (about $73 at the data's 2023 capex) is above the grid's, and its 4-hour battery serves half a 24-hour load (`plants.load_share`), so it saves 20% of the fab's energy bill but earns -4.6% on its capital. Carried: the data, not a key, decides it.
14. **Tuning (rule 1, `power.*` only), seeds 1-10, before -> after:**
    - `plants.capex_premium` 1.0 -> 1.2, `plants.gas_adder` 0 -> 1.5 $/MMBtu, new `standby_share` 0.2 (behind-the-meter energy pays the utility's standby charge): gas behind a fab saved 66% at a 22% IRR (seed 1) -> **34.4% at 8.3%** (median).
    - New `plants.load_share` (solar with storage 0.5, wind 0.6): a plant serves only its hours of a load (monthly averages had let solar run a fab around the clock).
    - `plants.sizes_mw` adds 10 and 25 MW, so a plant can be sized to a fab.
    - `plants.overrun.nuclear` hi 1.5 -> 2.0: overruns above 50% on 2 -> **5** seeds; nuclear's IRR on its operating years **-2.9% to 2.4%** (inside -5 to 12%).
15. **Readings (46.8), medians over seeds 1-10:** target 1 met (20 runs identical to main); target 2 met (a 40 MW data centre ordered January 2028 in North America has power after **52 months** on the grid, **20** with solar and storage behind its meter sized to its load); target 3 met for gas, solar carried (decision 13); target 4 met (**10 of 10** seeds: gas -> wind by 2035 in the EU); target 5 met (a grid fab in Africa loses **2.8%** of a year's starts; behind a gas plant **0.0%**); target 6: `make check-timing` passes alone (7 tests); M30's 500 ms guard on the 2039 full_integrator save runs in the weekly workflow (dispatched on the branch before merging).

16. **Money scale (PM note 2026-11-15, M34's `economy_scale.money` = 0.1):** not applied to M32. That factor scales real-world *revenue and market-size thresholds* (the game's incumbents book about a tenth of their real revenue); M32's money figures are the costs of physical inputs, and the game already prices those inputs at real scale. M17's grid price is EIA's real 2010 industrial price (`refining.power_cents_per_mwh` 6800, $68/MWh), and ADR-0022 makes M32's grid price equal M17's index exactly to 2025; PPAs are quoted off that price. M21's fab capex is real scale: a 5 nm, 50k-start fab costs $15-25B (`fab.capex_scale`, 38.5 target 2). M32's plant capex (Lazard/NREL ATB $/kW, in 2010 dollars) sits on that same scale: a 1 GW nuclear unit costs about $10-15B with overrun, against a fab's $15-25B, which is the real ratio. Its fuel (Henry Hub and regional gas, $/MMBtu) is real scale too, as M17's own gas and power history is. The readings agree: gas behind the meter saves 34% against the grid at an 8.3% IRR (decision 15); were either side scaled by 0.1, the saving would be about 90% or negative. Real figures are therefore the game figures, and the power screen shows them as they are. M33's tool prices are M33's to check.

## Follow-ups

- Rival hyperscalers' load, PPAs and plants (decision 9): needs rival data centres (ADR-0017's static incumbents have none).
- The named 2025 construction projects for fabs and mines (TSMC Arizona, JASM Kumamoto, ESMC Dresden, Intel Ohio, Samsung Taylor; the largest lithium, copper and nickel projects): not found cheaply in this session's sources; for M28's data.
- An automation area for power (buying PPAs, siting plants), out of scope by the brief.
- Hourly or seasonal dispatch: monthly averages with `load_share` stand in for the day's shape; solar's case improves only with a cheaper battery or a higher grid price.
- Sources to re-read when reachable: EIA SAIDI/SAIFI tables (EIA's annual PDF was over the fetch limit), the World Bank Pink Sheet's annual gas series (2010-2021 values are R), producers' technology mixes (A).
