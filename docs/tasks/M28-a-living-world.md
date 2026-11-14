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

- [x] §41.8 target 1: every price, capacity total and dated event before 2026 identical to `main` before M28 (state-cache test, every seed in the guard set).
- [x] Every chain company's ledger balances (property test); no rival valuation or capex intention reaches the API or a prompt (hidden-value test).
- [x] §41.8 targets 2–8 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m28-done`.

## Manual check (Reece, after merge)

Load `pt-world`. Open Albemarle's page from your lithium contract. Build a second refinery and watch the price and the rivals' December decisions over five years. Wait for a bid.

## Decisions made

1. **Known misses re-owned (product manager, 2026-11-13).** V3.ai, V5.cells and V5.cats moved from the finished M23 to M28 in `tst/balance/known_misses.py`, beside I1 (already M28's): the instructions give M28 all four, since M23 is closed and M28's supply-driven world is the next change that moves the integrators' margins and the 2030s markets. Bounds unchanged. Their re-measurement is under "Known misses" below.
2. **The world starts in January 2026, not December 2025.** 41.2's "each December from 2025" would put a dated decision (and its news) in 2025, which target 1 forbids. Chain companies come into being in `world.start` (January 2026); the first December decision is December 2026. Before then the world phase returns its input unchanged.
3. **Chain companies are companies, outside 15.3.** They are `company` rows with `rival_key = (7, position)` (a new family, `CHAIN_KEY`), excluded from `GameState.rivals()` and `ledger_companies()` (so 15.3's product decisions, payroll, snapshots, the board and insolvency never run on them) and kept by the world phase, which posts their books and fails them itself.
4. **Facilities are a simplified kind** (`world_facilities`) rather than rows of `facilities`, `refineries`, `mines` or `fabs`, so the player's facility lifecycle never runs on them (the brief: "simplified operations").
5. **Named executives are characters, not people.** A CEO and two executives a company, names drawn from the region's pool on stream `world`, with the company's personality; no `Person`/`Employment` rows (no payroll, growth or poaching). The brief's out-of-scope list rules out staff below them.
6. **World supply volumes are new data.** `chain_companies.yaml` adds each commodity's world output by year (USGS, ICSG and ITA figures recalled, tagged R; HPQ, semiconductor polysilicon, NdPr and neon tagged A). A supplier's capacity is its suppliers.yaml share of it; foundry wafers are the foundries' nodes.yaml capacity over `1 − foundry_other_share` (0.12, A). Shares come from suppliers.yaml (one source), so the YAML holds country, personality and cost position only; countries come from countries.yaml's `sites`, with Intel, GlobalFoundries, UMC and SMIC's added in chain_companies.yaml.
7. **Who has no company:** the wafer makers (Shin-Etsu, SUMCO, Siltronic, GlobalWafers: no M17 good) and suppliers whose share ended before 2026 (Rockwood, Molycorp, MEMC, Ingas, Cryoin).
8. **"Other producers" in tranches.** Each aggregate's capacity is four facilities along the cost curve (its position ± 0.3), so a slack market mothballs its dearest tranche first rather than the whole rest of the world.
9. **Supply is output at normal running.** In the factor, supply is chain producers' live capacity × `base_utilisation` (0.85) plus the player's output to the market; their actual output is demand less the player's, inside the 70-95% band. Without it the factor stays 1 until capacity runs out, and a player building 20% of capacity moves nothing until rivals hit their floor.
10. **Expansions need a tight market at arrival.** A company expands only when the market at its build's arrival (the good's `build_months`) would be tight without it (projected factor ≥ 1), besides 41.2's outlook-over-cost test, judged on full cost (cash, fixed and the capital's charge). Without it low-cost producers kept building after every price spike and prices sat 20-40% under M17's level by the 2030s (first seed-1 run: gallium's factor 0.62 in 2034).
11. **Restarts.** A mothballed facility restarts after spot tops its cash cost × (1 + hurdle) for 3 months (`world.restart_months`); 41.2 names none, and without it mothballed capacity could only close.
12. **Foundries.** A foundry wafer's long-run price is `world.foundry_wafer_cents` ($5,000, A) × the foundry wafer index, so foundries' costs follow wafers getting cheaper; after 2025 the foundry market's 38.3 factor reads the named foundries' chain capacity (their decisions) instead of their seeded growth, with 38.3's own elasticity and bounds.
13. **Rival deals are vertical or horizontal only.** The first run had GitHub buying Air Liquide; 41.3's buyers "prefer" related targets, and an unrelated purchase is not considered. Incumbents buy chain companies or incumbents, chain companies buy chain companies; "other producers" are never bought. One deal a buyer a quarter. A spin-off distributes the subsidiary to the owner's shareholders (its 1810 book against equity).
14. **Bids.** Only incumbents no one owns bid; one bid is open at a time and lapses after 3 months; from 2026 25.4's takeover trigger gives way to this rule (both would double the approaches). A private player gets no bids: 41.4 allows only friendly offers there and M28 adds none. Accepting sells to the bidding rival at its bid (tst.sim.mna.exit).
15. **China's lag is in generations.** 41.5's lag is the generations a Chinese foundry is behind the leading node; it shrinks by `china_catchup` (0.6) a year while a biting rule on chip equipment or EUV tools to China (or SMIC by name) applies, and by `china_free_pace` (0.35) without one (a follower buying tools), and the foundry reaches a node when the leader's generation less its lag does, whatever nodes.yaml's EUV gate. The catch-up counts from January 2026 (the October 2022 rules are what bind then): counting from 2022 would move SMIC in the first month of 2026. The `china_subsidy` research is funded by an equal state grant, so it shows in the books without moving cash.
16. **Regional cycles move demand by their ratio.** A market's addressable demand grows by the ratio of its region's multiplier to last month's (the home market reads the founder's default region); commodity demand takes the regions' mean multiplier.
17. **Breach risk.** From 2026 33.3's monthly chance is × `breach_distress` (3) for a supplier whose costs top its revenue, with insolvent months or a mothballed plant of the good, and × `breach_healthy` (0.5) above 80% utilisation; a failed supplier, or one with every plant of the good closed, breaches at once and signs nothing new.
18. **Target 2 is lithium carbonate.** 41.8 names lithium hydroxide; the game's lithium chemical (M17, M20's converter) is carbonate.
19. **Target 8 is measured as a ratio.** A 2039 turn with the full world against the same turn with the world switched off (the data without chain_companies.yaml), in memory, median of three blocks (`tests/integration/test_m28_world_perf.py`, `make check-timing`), and under the 1.0 s budget.
20. **The history guard.** `tests/fixtures/m28_history.json` is main's fingerprint recorded before any M28 code (seeds 1-10, a do-nothing game to December 2025: every commodity, power and component month, the foundry market's prices, reaches and capacities, the rival miners' capacities, every log item and event request, and every ledger entry of every company, hashed by year). It is re-recorded on main after M27a merges, and the branch must match it.
21. **Rivals plan on chain capacity.** Their "tight at arrival" test and projected factor count chain producers only: the player's output reaches them through prices (the spot in their outlook) and mothballing, as 41.2 says ("rivals respond by mothballing"). Counting the player's output there made them simply cut their own builds, and target 2's price moved 2-7%.
22. **Mothballing is a slack-market move, one plant at a time.** A month counts toward mothballing only while spot is under the cash cost in a market not short by the hurdle (last month's factor under 1 + hurdle); a month counts toward restarting while spot tops cost × (1 + hurdle) or the market is short by the hurdle. Each month at most one facility a good mothballs (the dearest qualifying) and one restarts (the cheapest). Without this, polysilicon (M17's path holds it at 2025's crashed price for years) mothballed and closed in a shortage: seed 7 ran 153 months under 70% of demand; and on seed 3 21 plants mothballed in one month, turning a glut into a shortage.
23. **Secured lending.** A shortfall may also be borrowed up to `world.asset_lending` (0.5) × net plant, so a loss-making year (polysilicon in 2026) does not sink a producer at once; it still fails after `insolvent_months` beyond that.
24. **Bids compare value per fully diluted share**, as 25.4's trigger and the sale do (market cap on outstanding shares against V_f on diluted shares made a fairly priced player look cheap).

### Tuning (rule 1, `world.*` only)

| Key | Before | After | Why |
| --- | --- | --- | --- |
| `world.bids.view_sd` | 0.12 | 0.06 | Target 5b: a player held at 1.0× was bid for on 9 of 10 seeds (the public market's sentiment step dips it to ~0.75×, and the best of ~30 rivals' views ran to 1.36× value) |
| `world.bids.tilt` | aggressive +0.10, cost leader −0.10 | ±0.05 | as above |
| `world.bids.monthly` | 0.08 | 0.01 | as above: 1 of 10 at 1.0×, 10 of 10 at 0.6× (first bid in months 0-2) |
| `world.asset_lending` | (new) | 0.5 | target 3b (decision 23) |
| `world.elasticity` | 1.5 | 1.5 | tried 2.5 and 2.0 for target 2: 2.0 gave a median drop of 11% (seeds 0-22%), worse and noisier than 1.5's 12%; kept |
| `world.hurdle` | 0.15 | 0.15 | tried 0.30 for target 2 (before decision 21): no better |

### 41.8 targets (10 seeds; `tools/m28_targets.py`)

| Target | Reading | Band | |
| --- | --- | --- | --- |
| 1 History holds | identical on seeds 1-10 (every series, every year to 2025) | identical | ok |
| 2 Markets respond | lithium 2031-33 price −12% median (seeds −1% to −17%); a rival mothballing on 8/10 | 15-40% lower; mothballing | **carried** (below) |
| 3 The world survives | 100% of chain companies alive in December 2039 (median); longest run under 70% of demand 21 months | ≥80%; ≤24 | ok |
| 4 Rivals form groups | 2+ groups holding a chain company by 2035 on 10/10; 1 rival-on-rival deal a year (median) | 7/10; ≤3 | ok |
| 5 Bids when deserved | 0.6×: 10/10 within 3 years; 1.0×: 1/10 | ≥5/10; ≤1/10 | ok |
| 6 China catches up | SMIC's lag in 2030: 3.0 / 4.25, 2.0 / 3.25, 3.0 / 4.25 generations (controls / lifted, seeds 1-3) | ≥1 shorter | ok |
| 7 Nothing else moves for a software company | its books (and every company's) identical to 2025: part of target 1's fingerprint | identical | ok |
| 8 Turn time | a 2039 turn 233 ms with the world, 224 ms without (1.04×, 313 facilities) | ≤1.3× | ok |

**Target 2 carried (recorded decision).** The player's 20% (a quarter of the chain's lithium capacity, built by January 2028 and topped up to 2030; its converters run at about 27 kt of their 50 kt a year in their ramp) lowers the price most in 2029-2031 (seed 1: factor 0.95 against 1.21 in 2031). Then the rest of the market responds as 41.2 describes: rivals' December outlooks fall with spot, so they build less, and slack markets mothball their dearest plants; by 2032-33 the two runs converge. Making rivals respond more slowly (a higher hurdle, decision 21's alternative) or prices respond harder (elasticity 2.0-2.5) did not lift the median past 12% without breaking the market elsewhere. The measure and its band are the product manager's, so this is reported rather than re-measured.

### Known misses (re-owned to M28; re-measured on the weekly workflow on m28-world)

Read on this branch (weekly run 43569674208, before the M27a merge) and on seeds 11-40 locally after it; none is closed, none is beyond its bound on 30 seeds:

| Miss | Bound | m28-world | main | |
| --- | --- | --- | --- | --- |
| I1 (year-30 margin gap) | ≥ −2.0 pts | +0.1 pts | −0.0 (weekly 43419446811) | open, known: M28's supply-driven prices barely move a 2039 group's cost of goods (0.2-0.3% of revenue, M23b) |
| V3.ai (year 10) | ≥ −2 pts | unchanged | unchanged | open, known: measured in 2020, before the world starts, so M28 cannot move it |
| V5.cells | ≤ 40% empty | seeds 1-10: 71% / 69% filled (known); seeds 11-40: 75% / 75% (met) | seeds 1-10: 72% / 69%; 11-40: 75% / 75% | open: met on 30 seeds on both |
| V5.cats | worst category-decade empty in ≤ 70% of runs | seeds 1-10: steady 7/10 (known), research_heavy fintech 2030s 7/9 = 78% (**over**); seeds 11-40: 14/30 and 12/28 (known) | seeds 1-10: 7/10 and 6/9 (known); 11-40: 14/30 and 12/28 (known) | seed variance (rule 4): one run's fintech launch on seeds 1-10; branch and main read the same on seeds 11-40. Recorded, not added to known_misses.py; the bound is the product manager's |

25. **China's lost customers.** From 2026 the customers a controlled seller loses in a closed destination (M22's exits) go to the Chinese rival (countries.yaml `rivals`) with the most customers on a product of the same category in that region and segment; before 2026 they leave the market as M22 had it. Chinese rivals' launches elsewhere stay 19.6's region entries (no rule blocks them): a follow-up below.
26. **Intel Foundry.** The foundry chain company is named "Intel Foundry" (chain_companies.yaml `name`), since the chip rival Intel already exists; the loader refuses a chain company named as a rival.
27. **The practice save `pt-world`** is `tools/e2e_m28_save.py world`: Cathode, M13's listed scale-up, moved to 2026 and played through 2026 in the world, with a 25 kt lithium converter in Latin America, a 5-year Albemarle offtake and its share price at 55% of value. `bid` moves it to the first month a rival's own valuation bids (Playwright flow c).

## Follow-ups

- The player cannot yet bid for a chain company (28.3's deals list rivals only); a "buy Albemarle" action would complete the vertical-integration story.
- M19's rival-miner capacities (`mining.risk.rival_capacity`, the Mines screen's "rival miners" table) still follow M19's spike rule after 2026; they could read the chain companies' facilities instead.
- Chinese device and chip rivals launching in regions no rule blocks them (41.5's last clause) are left to 19.6's region entries; a rule-aware entry preference would sharpen it.
- Target 2 (decision above): the product manager may want to read the market's response over 2029-2031 or with the player's plants fully ramped; that is a change to how the target is measured, so it is not done here.
- The company page shows facilities as a table; a map (41.7's "facilities on a map") would need a map component.
- Chain companies' cost positions and personalities are assumptions (A) set by hand; a dossier pass on cost curves would ground them.
