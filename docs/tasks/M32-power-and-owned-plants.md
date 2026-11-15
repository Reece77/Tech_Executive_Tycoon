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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
