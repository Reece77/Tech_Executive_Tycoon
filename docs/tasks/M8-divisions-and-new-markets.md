# M8: Divisions, executives and new markets

**Goal:** a company that reaches stage 3 becomes a scale-up. It can form divisions with presidents and their own P&L, fill an executive team, and feel coordination and support costs. Every company, from January 2010, can enter two new markets: Fintech, and AI models and inference, whose demand and compute cost follow history. Named real entrants such as Stripe and OpenAI arrive in their real year.

**Spec sections:** §2, §3 (stage 3), §6 (corporate structure), §7.1 (categories), §8 (cloud as a priced input), §9 · **ADRs:** 0002, 0003, 0010, 0013 (new stream), 0017, 0019 · **Formulas:** `docs/formulas.md` §18 (all), with §11, §13 and §15 for what it extends · **Wireframes:** `docs/wireframes.md` (M8 screens) and `docs/wireframes/source/OrgDivisions.dc.html`, `DivisionPL.dc.html` · **Roadmap:** `docs/v2-roadmap.md` · **Depends on:** M7b (`m7b-done`). M7c (fixes and the agent playtest) runs after M8 (Reece, 2026-10-31); the v1 retrospective follows Reece's playtest

## Context

This is the first v2 milestone and a single lane (ADR-0019). Its systems are the base for M9 (cities and regions) and M10 (capital and macro), which run as two parallel lanes afterwards. Keep the new code in its own modules (for example `tst/sim/org/divisions.py`, `tst/sim/org/executives.py`, `tst/sim/products/markets_v2.py`) so the next lanes touch them as little as possible.

Reece's decisions (2026-10-30):
- Executive seats unlock at **stage 3**, as the spec says.
- Support staff become **necessary from stage 3**, with central or embedded shared services.
- Fintech and AI are open from **2010**: AI's market grows on a curve by year, and its compute prices follow an index.
- **Scheduled real entrants** arrive in their real month.

Nothing in §18.1–§18.5 changes a company before stage 3, so v1's early game and balance targets must still pass.

## Out of scope

Regions and cities (M9). Debt, Series C onward and macro (M10). The R&D tree (M11). Owned compute, hardware and chips (M12): AI compute stays a priced input. CEO appointment (M13). Rivals using divisions or seats. Subsidiaries and the holding company (v3).

## Sub-tasks (commit after each)

0. **Carried:** any item named in the instructions. Refresh `tests/durations.json` after each sub-task, and add a third CI shard if any job passes 17 minutes.
1. **Data and formula tests.**
   - **New data:**
     - `balance.yaml` keys `org.*` (`max_divisions`, `layer_tax`, `cross_division_factor`, `support_ratio`, `embedded_bonus`) and `exec_seats.*` (weights and effect coefficients);
     - the appended categories with `launch_quality` and `growth_by_year`;
     - `compute_index.yaml`;
     - the appended incumbents and their function mixes;
     - `entrants.yaml`;
     - RNG stream `entrants` (id 20) in ADR-0013's table.
   - All of it is validated at load.
   - Every §18.10 worked example is a unit test.
2. **Divisions and the ledger dimension** (§18.1, §18.2):
   - The `division` unit type, gated by stage. Presidents. `product.division_id`, with the `set_product_division` action.
   - `ledger_line.division_id`, with posting rules for every existing posting site. The migration backfills null. Update the data dictionary.
   - Division statements derived from the ledger, with the shared-services allocation.
   - The layer tax and the cross-division factor.
   - **Property tests:** division statements plus corporate sum to the company statement every month, and the allocation sums to the corporate operating costs it spreads.
3. **Executive seats** (§18.3):
   - `appoint_executive` and `remove_executive` actions (energy, morale, exec level).
   - Exec-level searches from stage 3.
   - Seat effects in phases 3, 5, 9 and 7 (CFO on `V_base` and confidence). Vacancy penalties from stage 3.
   - The displayed fit and estimated effect (§18.8).
   - **Tests:** each seat's effect, a vacancy, and that before stage 3 nothing changes.
4. **Support and shared services** (§18.4, §18.5): coverage by pool, the shortfall factor and `W_support`, the `set_shared_services` action, the embedded bonus, and the order of effects. A unit test for each pool case.
5. **New markets and entrants** (§18.6, §18.7):
   - The two categories with their incumbents. Starting shares by the M3a steady-state method; record the values.
   - `growth_by_year` and the compute index.
   - Rival pools for the new function mixes. Startups spawn in the new categories (§15.4 unchanged).
   - Scheduled entrants on stream `entrants`.
   - **Tests:** each entrant appears in its month; AI hosting follows the index; a seeded test of entrant generation.
6. **API, CLI and screens** (per the wireframes):
   - **Org:** divisions with president, shared-services policy, coverage and P&L summary; an **Executive team** panel with seats, holders, fit words, estimated effects and vacancy penalties; Appoint and Remove dialogs.
   - **Finance:** a **Divisions** tab with each division's statement and allocation.
   - **Products:** the owning division on the product profile; the new categories in New product.
   - **Overview:** a support coverage tile from stage 3.
   - **Supporting work:** glossary entries and driver breakdowns for every new number (M7b rules); History entries for appointments, divisions and entrants.
   - **CLI:** `tst divisions`, `tst execs`, `tst appoint --seat --person`.
   - **Hidden values:** extend the hidden-value test to seat fit and estimated effects.
7. **Balance, golden snapshots and e2e:**
   - The §18.9 targets, printed and recorded. Tune only `org.*`, `exec_seats.*`, the new categories' keys and the new incumbents' values.
   - Golden snapshots regenerated: the new incumbents and entrants act from turn 0, so rivals' moves change. Put the reason in CHANGELOG.
   - **Playwright:**
     - (a) at stage 3, create a division, move a department into it and see its P&L tab;
     - (b) appoint a CTO and see the estimated effect, then vacate it and see the penalty;
     - (c) create a fintech product and launch it;
     - (d) the Competitors screen shows Stripe after September 2011.
   - **Close-out:** CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §18.10 worked example passes as a test.
- [ ] Before stage 3, nothing in §18.1–§18.5 changes a company. All v1 balance targets still pass (§18.9 target 1).
- [ ] Division statements and corporate always sum to the company statement (property test). Allocations move no cash.
- [ ] Each seat's effect and each vacancy penalty works as specified. The API never shows true `s` or `e` (planted-value test).
- [ ] Support coverage, the shortfall and the embedded bonus work for the central and embedded cases.
- [ ] Fintech and AI play from 2010; AI demand and hosting follow their tables; every entrant appears in its month on every seed.
- [ ] §18.9 targets 2–6 met (printed, values recorded).
- [ ] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m8-done`.

## Manual check (Reece, after merge)

Load a stage-3 save (or play to $20M ARR). Form two divisions, appoint an executive team, and watch the Divisions tab for a year. Start a second game in AI and note how the market feels before and after 2016.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
