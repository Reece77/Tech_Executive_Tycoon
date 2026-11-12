# M28: A living world (v3.5, lane B)

**Goal:** rivals play the same game as the player. Miners, refiners and foundries become companies with facilities, books and capacity decisions; after 2025 their choices and the player's move commodity prices; incumbents buy chain companies and each other and run them as groups; rivals bid for a cheap listed player; Chinese chipmakers catch up under controls; regions have their own cycles. History to 2025 stays exactly as it is.

**Formulas:** `docs/formulas.md` §41 (all), with §28, §31, §33–§39 · **ADRs:** 0002, 0003, 0007, 0013 (stream `world` 57), 0020 · **Roadmap:** `docs/roadmap.md` Phase 2 ("a living world") · **Backlog:** `docs/ideas-backlog.md` ("A living world") · **Depends on:** M23b (`m23b-done`) · **Lane:** B, alongside M27a (lane A) and M29 (lane C)

## Lane

- Its own session and branch (`m28-world`). **Merges last of the three** (it moves the most balance); it re-parents its migration, regenerates golden snapshots with a recorded reason, and re-runs every guard on the combined code.
- **M28 owns:** `backend/tst/sim/rivals/` and new `backend/tst/sim/world/` (chain companies, capacity decisions, the balance factor, rival groups, bids, China's catch-up, regional cycles); the data files for chain companies (`suppliers.yaml` and a new `chain_companies.yaml`); `tst/sim/commodities/` and `tst/sim/fabs/market.py` where prices read the balance factor; `tst/sim/mna/rivals.py`; the World news feed and the Rival screen as a company page; `tst/balance/m28.py` (new).
- **M28 must not edit:** M27a's `automation/` and the seat code; M29's shell, navigation, Overview and inbox; the player's facility rules beyond reading them for rivals' simplified operations.
- **Shared files:** `balance.yaml` (add only `world.*`), `docs/formulas.md` (notes in §41 only), `CHANGELOG.md`, `docs/data-dictionary.md`, ADR-0013: keep both sides.
- **CLAUDE.md §9's decision rules apply.** §41.8 target 1 (history holds) is the guard everything else answers to: if any series before 2026 moves, stop and report.

## Out of scope

Currencies and hedging, more countries with their own rules, rivals' lobbying, rival staff below the named executives, rival personal investing. All are later (v4 or the backlog).

## Sub-tasks (commit after each)

1. **Data:** `chain_companies.yaml` from `suppliers.yaml`, M19's rival miners, M20's refiners and M21's foundries: each company's country, facilities, goods and `world_share` per year to 2025, and an "other producers" aggregate per good; `world.*` keys; stream `world` in ADR-0013; migration and data dictionary. **Test:** capacity sums match the data's world supply each year to 2025.
2. **Chain companies as companies** (§41.1): the generic company and facility models, simplified operations, books on the ledger, CEOs from the rival characters; contracts and offtakes point at them; breach risk from their state from 2026. **Property test:** every chain company's ledger balances. **State-cache test:** §41.8 target 1.
3. **Capacity decisions and the balance factor** (§41.2): December capex by personality, mothballing and closing, the factor on M17's path and the foundry market from 2026. **Seeded test** of a December's decisions; **unit test** of the factor's clamp.
4. **Rival groups** (§41.3): incumbent-on-incumbent and vertical deals with antitrust, rival subsidiaries with mandates, consolidation, spin-offs, rivals' offtakes for supply security.
5. **Bids for the player** (§41.4): rivals' valuations drive §28.6's bids, at most one a year per rival. **Hidden-value test:** the rival's valuation never reaches the API or a prompt.
6. **China under controls** (§41.5) and **regional cycles** (§41.6).
7. **The world you can see** (§41.7): World news (filters, links) and a company page per rival.
8. **API, CLI, e2e, balance and close-out:**
   - **CLI:** `tst world` (chain companies by good, capacity, utilisation), `tst company --rival <name>`.
   - **Playwright:** (a) open a rival miner's company page from a contract; (b) filter World news by good; (c) a scripted bid for a cheap listed player arrives as a critical event.
   - **A practice save** `pt-world`: a listed integrator in 2027 with a lithium refinery, trading cheaply.
   - **§41.8 targets** printed and recorded; tune only `world.*` (rule 1). Target 8's turn time is measured with `make check-timing`.
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] §41.8 target 1: every price, capacity total and dated event before 2026 identical to `main` before M28 (state-cache test, every seed in the guard set).
- [ ] Every chain company's ledger balances (property test); no rival valuation or capex intention reaches the API or a prompt (hidden-value test).
- [ ] §41.8 targets 2–8 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m28-done`.

## Manual check (Reece, after merge)

Load `pt-world`. Open Albemarle's page from your lithium contract. Build a second refinery and watch the price and the rivals' December decisions over five years. Wait for a bid.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
