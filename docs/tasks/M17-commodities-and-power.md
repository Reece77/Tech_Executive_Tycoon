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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
