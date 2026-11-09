# M19: Mining operations (v3, lane A)

**Goal:** turn a permitted project into a working mine. Build it (with a hidden cost overrun), staff it, ramp it up and run it for decades: output, grade, costs, royalties, depletion and closure. Sell to the market, into offtakes, or to your own group at transfer price so your devices and chips stop riding the spot market. Live with the four critical mine events: accidents and spills, protests and permits, nationalization, and price crashes. Rival miners operate alongside you. You can also found a subsidiary from scratch, so mining can be its own business.

**Spec sections:** §8 (value chain) · **ADRs:** 0002, 0003, 0004, 0005, 0007, 0013 (streams `mining` 50, `region_risk` 52), 0019, 0020 (facility kinds, region risk fields) · **Formulas:** `docs/formulas.md` §35 (all), with §22, §31, §33, §34 · **Data:** `docs/v3-research/v3-data-dossier.md` §5, §6 · **Depends on:** M18 (`m18-done`) · **Lane:** A, alongside M20 (lane B)

## Lane

- Its own session and branch. **Merge order: M19 merges first;** M20 merges `main` after and regenerates golden snapshots.
- **M19 owns:** the `mine` facility kind and its module; new `backend/tst/sim/mining/` (construction, operations, closure, events, rival miners); the `found_subsidiary` action; region fields `royalty_rate` and `resource_nationalism` in `regions.yaml`; `nationalization_history.yaml`; the `mining_engineer` role; accounts 1520, 2600, 6750, 6960; `data/events/mining.yaml`; a **Mines** screen.
- **M19 must not edit:** refinery kinds, recipes, the `process` research domain or M20's screens.
- **Shared files:** `balance.yaml` (`mining.*`, and `facility.kinds.mine`; M20 adds its own kinds: keep both), `docs/formulas.md` (§35 notes only), `CHANGELOG.md`, `docs/data-dictionary.md`, `regions.yaml` (M19's two fields only).
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Refining (M20), fabs (M21), export controls as policy (M22; M19's export bans are nationalization events), rivals exploring.

## Sub-tasks (commit after each)

1. **Data and formula tests:** `mining.*` keys (overrun ranges, construction times, ramp, staffing, costs, royalties, accident rates, reclamation), the region fields with sources, `nationalization_history.yaml` from dossier §5 (each event cited), event templates; streams in ADR-0013; unit tests for depletion, the reclamation provision, royalties and the accident-rate formula.
2. **Found a subsidiary** (§35.1) with transfers of projects, licences and facilities at book value. **Property test:** the ledger balances across the transfer.
3. **Building** (§35.2): the mine kind on the generic facility lifecycle, capex with the hidden overrun, capitalization (including M18 spend), construction, ramp, staffing.
4. **Running** (§35.3): output, revealed grade, costs, royalties, depletion, sales (spot, contracts and offtakes as seller, the group at transfer price, feeding the group's BOM and wafer mixes), closure and reclamation. **Property tests:** ledger balance; book value never below 0; reserves never negative.
5. **Critical events** (§35.4): accidents and spills, protests and permits, nationalization (history then seeded), price crashes with care and maintenance. Seeded tests for each.
6. **Rival miners** (§35.5): suppliers' capacity responding to prices; buying the player's projects; their mines in M14's deal code.
7. **API, CLI, screens:** the Mines screen (each mine's construction, output, grade, cost per unit against price, reserves, staff, events, closure), mines on the Group screen; **CLI:** `tst found-subsidiary --name --region --cents`, `tst build-mine --project --capacity`, `tst mines`, `tst care-maintenance --mine`. Hidden values: the overrun and the deposit's truth stay hidden until revealed (differential test).
8. **Balance, e2e and close-out:** §35.6 targets printed and recorded; tune only `mining.*`. **Playwright:** (a) found a mining subsidiary and transfer a permitted project into it; (b) build a mine and watch construction, ramp and first sales; (c) a price crash and care and maintenance; (d) a scripted accident's critical event. CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] The ledger balances through construction, operations, transfers and closure; reserves and book values never go negative (property tests).
- [ ] No hidden deposit truth or overrun reaches the API or a prompt before it is revealed.
- [ ] A company that never mines plays exactly as before.
- [ ] §35.6 targets met (printed, values recorded).
- [ ] `make check` and CI `e2e` green; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m19-done`.

## Manual check (Reece, after merge)

Found "<Name> Mining", move a permitted lithium project into it, build the mine, and sell to your device business at cost plus. Play through a price crash.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
