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

- [x] The ledger balances through construction, operations, transfers and closure; reserves and book values never go negative (property tests). *`tests/property/test_m19_invariants.py` (Hypothesis: seeds, commodities, transfer, care, close, capacity), unit tests in `tests/unit/test_m19_mining.py`.*
- [x] No hidden deposit truth or overrun reaches the API or a prompt before it is revealed. *Differential and prompt tests in `tests/integration/test_api_mining.py`; the forbidden-key rule on every response.*
- [x] A company that never mines plays exactly as before. *Golden snapshots unchanged; T6 (with and without the mining phases).*
- [x] §35.6 targets met (printed, values recorded). *`tools/m19_targets.py`, seeds 1-10 and 11-40, in docs/balance-targets.md.*
- [ ] `make check` and CI `e2e` green; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m19-done`.

## Manual check (Reece, after merge)

Found "<Name> Mining", move a permitted lithium project into it, build the mine, and sell to your device business at cost plus. Play through a price crash.

## Decisions made

Engineering, data and measurement decisions the spec, ADRs and brief did not settle (CLAUDE.md §9). Balance values are before → after, tuned only in `mining.*` (decision rule 1). formulas.md §35.7 has the rules as built.

1. **Branch.** Built on `m19-mining`, as the instructions name it, after merging `docs-m19-m20` (pull request #36, merge commit).
2. **A mine is a facility plus a record.** The `facility` row (kind `mine`) is the shared record (owner, region, capacity, status, staffing unit, the study's estimate); `Mine` (keyed by the facility id) holds what only mines have, with the hidden fields named `hidden_*` so the API's field rule catches any leak. `FacilityKindDef` gains `module` (`generic` | `mining`): the generic capex, depreciation, operating cost and sale skip non-generic kinds (M20 can add `refining`); `sell_facility` refuses a mine. The loader accepts a non-generic kind's output good (`mined`: the deposit's commodity).
3. **Accounts.** The brief's `2600` asset retirement obligation is `2610_asset_retirement_obligation`: 2600 is SAFEs'. A mine's sales need a revenue account the brief does not list: `4400_revenue_commodities`.
4. **The overrun stays hidden by paying at the estimate's rate.** Until `mining.reveal_at` (half) of construction, capex is paid at the estimate / construction months, so neither the ledger nor the screen shows the overrun; then the cost to complete is revised (an inbox item with the whole capex and its percentage over the estimate) and the rest is paid over the months left.
5. **Capitalization.** At the build order the project's M18 spend moves from 6600 to 1520 (a credit to 6600 that month).
6. **Subtype and capacity.** Brine deposits are brine operations; placers and hard rock whose top is at most 250 m deep (`mining.underground_depth_m`) open pits; deeper hard rock underground (hole costs already reveal depth). Capacity is 0.75-1.25x the study's design; capex x (capacity / design)^0.7.
7. **Staff.** One mining engineer per 10,000 t a year (at least one): the key technical staff; the site workforce is in the fixed cost. The brief's "engineering and operations" are `mining_engineering` and `operations` (no new skills: they would redraw every person). A unit of any group company may staff a mine (hiring into a subsidiary is M18's follow-up 3); its employer pays the salaries.
8. **Output is ore-based.** The mill takes the capacity's ore at the design grade and recovery; product = ore x the month's grade x the true recovery, so a deposit richer or poorer than estimated shows in the reconciled grade and output, as mined. The grade profile is M18's 66 drill positions in mining order (x `profile_share` 0.3 x the commodity's hole sd) with a month's noise (0.08).
9. **Costs from public numbers.** A tonne of ore costs the commodity's typical cost a tonne of product x the deposit type's opex multiple x its reference grade x recovery x the subtype's multiple: richer ore costs less a tonne of product without the cost revealing the truth. Fixed share 45% (open pit), 55% (underground), 50% (brine); energy 30% of the variable cost x the region's power index; sustaining capital expensed with operations.
10. **Depletion on the estimate.** Units of production on the estimated tonnage, as the book left x ore mined / estimated ore left, so the ledger never reveals the true reserves; closure writes off what is left. Royalties are charged on output at spot however it is sold (group sales included).
11. **Group sales.** The buyer's commodity use this month (M17's `company_use`) is supplied at 31.6's transfer price (cost: the mine's cash cost a tonne that month); the buyer's spot purchase is reversed (5000) and it pays the mine (5900/4300). Allocation in shortages is unchanged (follow-up 3). During an export ban the mine cannot supply a group company headquartered outside its region.
12. **Selling as seller.** Contracts at a fixed price for 6-36 months; offtakes for 3-10 years in a ±20% collar; no penalty when output falls short (follow-up 4).
13. **The accident formula is normalised.** 35.4's f(s, c) = (1.6 - 0.04 s) x (1.3 - c) is divided by its value for a full crew of skill 10, so "average safety" has the subtype's base rate (0.2% open pit, 0.4% underground, 0.1% brine a mine-year). `mining.accident.skill_slope` 0.04 → 0.07: at 0.04 skill 15 cuts the rate by only 22% against skill 8 (target 3 needs 40%; 0.07 gives 47%). Accident costs: a $5M fine, brand -5 on the group's products, credibility -8; investigate 3 months without output and half a fine more; compensate $15M and Beloved +5; contest Ruthless +5 and a 40% chance of three fines more.
14. **Protests at operating mines.** 35.4's "protest or permit" row runs at M18's monthly rate x the deposit's hidden sensitivity, with M18's choices and costs; consult loses a month of output, push on risks a 3-month blockade. There are no expansions in M19 (follow-up 5).
15. **Nationalization.** Region-wide events by (region, commodity), a pure function of the seed and the month. History (10 events): Indonesia's ore bans (2014, 2020; nickel and bauxite are not game commodities, so news only), Mexico (Apr 2022), Zimbabwe (Dec 2022), Bolivia (Jan 2023, YLB), Chile (Apr 2023), Namibia (Jun 2023: lithium, cobalt, rare earths), DRC (Feb 2025, until the October quotas). DRC's 2018 Mining Code is a royalty (Africa's 8%), not an event. Takeover answers: a state partner buys a 30-51% stake at book value and takes that share of the cash margin (6960); fighting seizes the mine (written off to 4930 with its reclamation duty) for 24-60 months of arbitration at $500k a month, then a 50% chance of 60-100% of the book value; selling out fetches 50% of book. Export bans: 6-24 months at 70% of spot inside the region.
16. **Price crashes.** The all-in cost is the month's cash cost (operations, royalties, sustaining) over output; three months under spot raise one event until the price recovers. Hedge: an offtake on half the capacity for 3 years.
17. **Events go to the player's company.** The event director shows only the player company's queue, so every mine event is queued there and finds its mines by the month it is shown (one of each kind a month). This exposed the same gap in M18's protests on a subsidiary's project (never shown; the permit waited for ever): fixed in `tst/sim/exploration/phase.py` (decision rule 8, M18 has merged), with a test.
18. **Rival miners are computed, not stored.** Their capacity is a pure function of the price path and the region's events (nothing new in the save for a company that never mines); they bid 110% of M18's sale price for permitted projects and 90% of book for producing mines (2% a month each, open three months). "Their mines in M14's deal code" (buying a rival's mine) is not built: follow-up 1.
19. **A founded subsidiary** has no personality (rivals' decisions skip it), its parent is the listed company, its HQ the region's first city, and it is held 100% from the month before founding (nothing pre-acquisition). Stage 1; founding costs 5 energy and at least $1M. Transfers are paid in cash by the receiver at book value (a project's is nil: exploration is expensed).
20. **Measuring 35.6 (for review).** T1-T2 build, on each seed, up to three mines per commodity (copper, lithium, cobalt, NdPr) on definitive studies whose NPV midpoint is positive (what a sensible player builds), in January of 2012-2020 by seed (one build year only clustered the returns), with full crews of skill 12, run to the end of their lives; the IRR is from each mine's yearly cash flows, exploration excluded. T3 is the exact expected chance a mine-year. T4's "a high-risk region's mines" is a lithium mine in each of Africa and Latin America (the highest `resource_nationalism`). T5 uses M17's reference phone (components at 1.0) and reads volatility as the 2021-2024 monthly cost's standard deviation over its mean.
21. **Tuning** (`mining.*` only; first values were assumptions): `sustaining_share` 0.02 → 0.07 and `overrun.definitive` [0, 0.3] → [0, 0.5], `overrun.pre_feasibility` [0, 0.45] → [0, 0.55] (T1: with the first values 3% of mines returned under 5% and the median was 17%); `nationalization.monthly_base` 0.0045 → 0.0035 (T4: 0.0045 hit 67% of seeds 11-40); `accident.skill_slope` 0.04 → 0.07 (decision 13). A stronger grade profile (`profile_share` 0.6) was tried and reverted: it raises the mean grade (lognormal) and the IRR.

## Follow-ups

1. **Buying a rival's mine** through M14's deal code (35.5's "their mines in M14's deal code"): rivals bid for the player's projects and mines; the player cannot yet buy one of theirs.
2. **Hiring into a subsidiary** (M18's follow-up 3): mining engineers are hired into the operating company and staff a subsidiary's mine from there.
3. **Own supply in shortages:** a group mine's supply could keep 100% allocation in a commodity shortage (M17's protected volume); today it changes only the price.
4. **A seller's shortfall** under a contract or offtake carries no penalty; deliver-or-pay could follow M17's take-or-pay.
5. **Mine expansions** (35.4 lists them as a protest trigger) do not exist yet.
6. **Rival miners' capacity** does not move the commodity's price (M17's prices are history then seeded); M22's export controls or a supply-driven price could use it.
7. **The founding gate** counts the group's highest stage; a subsidiary's own stage stays 1 and never advances.
