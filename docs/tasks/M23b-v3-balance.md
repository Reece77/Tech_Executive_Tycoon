# M23b: v3 balance (lane B)

**Goal:** balance v3 across the full chain and 30 years, close or rule on every known miss, and leave a game ready for Reece's 30-year campaign.

**Formulas:** §30.7 and §31–§39's targets · **Balance:** `docs/balance-targets.md`, `known_misses.py` (V3.ai, V5.cells, V5.cats; M16's T3 and T4 recorded misses) · **Playtest:** `docs/playtests/reece-playtest-5.md` · **Depends on:** M22 (`m22-done`) · **Lane:** B, merges last (after M23a and M23c)

## Lane

- Its own session and branch (`m23b-balance`). Starts now with strategies and measurement; **tunes and merges after `m23a-done` and `m23c-done`**, re-running everything on the combined code.
- **M23b owns** `tst/balance/` (strategies, targets, known misses), the target tools, the nightly and weekly workflows, and tuning any existing key (recording before and after).
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each)

1. **Strategies:** `full_integrator` (group with mines, a refinery, a wafer plant, a fab and devices by year 15, supplying itself at transfer price); `mineral_baron` (exploration and mining, selling to market); `foundry` (a pure-play fab business with foundry contracts); keep v2's arms.
2. **30-year runs across the chain** (weekly workflow): every v2 V-target plus, by 2039, at least one era a domain, rivals alive in every chain category (miners, refiners, foundries), commodity prices inside their seeded bands, and a 2039 full-integrator group turning in under 1.0 s (V6 extended).
3. **v3 targets:**
   - **Vertical integration pays modestly:** `full_integrator`'s operating margin at year 20 is 3–10 points above `steady_regions`, with ARR 0.9–1.4×; it wins at most 4 of 10.
   - **Chains feel shocks:** in the 2022 lithium spike and the December 2024 gallium ban, an unhedged device or chip maker's unit cost or output suffers visibly (a gallium ban limits **output** through allocation, not only price; playtest 5).
   - **Foundry demand:** a 28 nm fab with foundry contracts reaches 70%+ use within 3 years on 7 of 10 seeds.
   - **Mines and fabs are long bets** (§35.6, §38.5 hold on the combined code).
4. **Known misses:** V3.ai, V5.cells and V5.cats re-measured with v3's new startup categories; M16's T3 (integrated spin-offs) and T4 revisited with M23a's group supply in place; each closed, or carried with a recorded product-manager decision.
5. **Close-out:** a "v3 final" section in `docs/balance-targets.md`; `docs/reviews/v3-balance.md`; CHANGELOG; the weekly workflow run on `main` after merging.

## Acceptance criteria

- [ ] Every §30.7 and §31–§39 target, and the v3 targets above, printed and in band on the combined code (or carried with a recorded decision).
- [ ] The weekly 30-year runs pass on `main` after the merge.
- [ ] `make check` and CI `e2e` green; merged last through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m23b-done`. That tag closes v3.

## After M23

Reece plays one full 30-year campaign (2010–2039) with Continue until, over as many evenings as it takes (roadmap Phase 2). Its notes shape v3.5.

## Decisions made

1. **I1 and I2 baseline (PM ruling, 2026-11-11).** I1 and I2 are measured against `devices_regions` (steady_regions plus the same phone and SoC on contracts, no owned chain), bands unchanged: I1 +3 to +10 points, I2 0.9–1.4×. The steady_regions readings print as I1s and I2s, for information only. Why: steady_regions is a pure software company at a 63% margin; any device line dilutes it, so the original comparison measured hardware, not integration. Weekly run 42963443104 (pre-merge): against steady_regions −12.8 points and 0.89×; against devices_regions −2.6 points and 1.05×. I1 is tuned after the merge with this lane's integration keys (rule 1), with I3 held at 4 wins or fewer. Wording in formulas.md §43 (numbered after M29's §40–§42).
2. **M22 target 7 (PM ruling from M23a, 2026-11-11).** `tst.balance.m22.target_7` now measures (a) the software company's own books, snapshots and decisions (its events and products) are identical with and without M22's data, and (b) every company's books are identical before October 2022. Why: M23a puts rivals under export controls, so rivals' books legitimately differ from October 2022. Wording in formulas.md §39.4 target 7. The nightly must read yes after the merge.
3. **L4 plan (accepted).** The lithium mine and converter arrive after 2024 on 9 of 10 seeds; the fix uses M23a's group supply after the merge.
4. **Hypothesis deadline (M23c, rule 5).** `test_holdings_sum_to_fd` sets `deadline=None`: it flaked on Hypothesis's timing deadline under parallel load, not on its invariant.

5. **The refusal wording (M23c, rule 8).** "a wafer contract" → "a foundry contract" in the engine's refusal: M23a made the change in its merge, so this lane had nothing left to edit.
6. **I1–I3 at year 30 (PM ruling, 2026-11-12).** I1, I2 and I3 read the trailing 12 months to December 2039 on 30-year runs of every compared strategy plus `devices_regions` (`v3.PLAYED`; weekly `weekly-v3-integration`, `tools/v3_targets.py --integration`). Bands unchanged. Each run's December 2029 reading prints as I1y20, I2y20, I1sy20, I2sy20 and I3y20, for information only. Why: at year 20, a group fab built in 2020–2023 is still inside its 5-year depreciation, so each start costs more than the market's wafers. M21's fab capital costs and lives are unchanged (§38.5). Wording in formulas.md §43.
7. **The v3 targets are §43.** M29 took §40–§42 on `main`, so the v3 targets section moved to the next free number. Both sides were kept.
8. **The fab property test (PM ruling, 2026-11-12).** `test_a_fab_keeps_its_books` draws its region only from the ones the export controls allow for the drawn node and month (`geopolitics.fabs.check_order`). What it checks is unchanged. `test_controls_refuse_an_advanced_fab_in_china` tests the refusal on its own: a 16 nm fab in East Asia in 2023 is refused, and the books and facilities are unchanged.
9. **Group ARR = 12 × the group's last month's revenue.** A group's revenue includes device units, mine sales and foundry slots, which the MRR-based ARR leaves out.
10. **The scripts on M23a's code (rule 2: a sensible player).**
    - `foundry` signs foundry contracts on its live fab: each designer up to its share cap, 80% of capacity, 36 months, at the slot price.
    - `full_integrator` stops renewing its TSMC wafer contract once its own fab's chips cover its SoC units × 1.2, and contracts the fab's spare starts the same way.
    - It explores from stage 3 alongside the device line. It builds its lithium converter in the parent as soon as a deposit has a resource estimate, buying concentrate at spot until the group's mine replaces it.
    - Mines are built at the study's smallest capacity (0.75 × design). The subsidiary is funded at the definitive study's 50% overrun cover, with cash 1.25 × the capital.
    - Exploration runs four projects per commodity and skips pre-feasibility (scoping, then definitive).
11. **L1–L3 measures.**
    - L1 counts an era arrival in 2026–2039 in each of chip_design, devices, infrastructure and ai.
    - L2 counts a derived good's spot market as its rival supply. Solar polysilicon and 300 mm wafers have no named refiner: M20 derives them.
    - L3 is the longest run of a commodity's index outside [1/3, 3], at most 36 months.
12. **I3's comparison set.** The full integrator's wins count over the founder-played compared strategies (as V1). `devices_regions` is the I1/I2 baseline, not a contender, and `ceo` stays a delegation benchmark.
13. **I1 at year 30: a known miss owned by M28 (PM ruling, 2026-11-12).** Weekly run 43350478720: I1 +0.1 points (band +3 to +10); I2 1.04×; I3 2 of 10. Year 20 for information: −3.3 points and 1.03×; against steady_regions −13.4 points and 0.91×.
    - **Why no lane key closes it:** subscriptions are 98–100% of both groups' revenue. Cost of goods (the whole device and chip line) is 8–17% of revenue at year 20 and 0.2–0.3% in 2039: seeds 1 and 3, where compute is 22% and marketing 19%. The own fab saves 23–24% a chip once depreciated (§38.5 target 5), which cannot move group margin by points. `group.supply_cost` (M16's) and the transfer price move cost between group companies, not the group's own costs, so no key this lane may tune reaches +3 without changing M21's fab economics.
    - **Bound:** `KnownMiss("I1", owner="M28", worse_than=0.019)`, the year-30 reading minus 2 points. M28's supply-driven prices from 2026 change the fab's economics.
14. **L4 stays printed only.** One of 10 seeds orders the whole chain by December 2024. On the other nine, only the lithium mine is late: a deposit's estimate is about $4–5B against the group's $2–4.5B cash. The converter, wafer plant and fab are ordered in 2020–2023. A follow-up.
15. **M16's T3 and T4 re-measured on the combined code.** The readings are identical to M16's record, because the fixture's subsidiaries take compute supply, which M23a's group supply does not touch.
    - T3: unrelated spin-offs 8 of 10 met; integrated spin-offs down on 3 of 10 (a miss).
    - T4: revenue in band on 7 of 10 (seeds 1, 2 and 4 above, at +83%, +67% and +72%); cash on 9 of 10 (seed 1 at 1.9×).
    - T5: 10 of 10.
    - Carried as recorded misses awaiting the product manager's later ruling (2026-11-08). Not added to `known_misses.py` (rule 3).
16. **Commit identity.** The worktree commits as Claude <noreply@anthropic.com> (CLAUDE.md §8).

## Follow-ups

- **Rival chip startups never launch** (M23a follow-up 2): V5 prints chips_ai_accelerator, chips_mobile_soc, chips_server_cpu, cloud_hosting, contract_manufacturing, devices and servers as scheduled-only, with no rival launch in the 2020s or 2030s.
- **L4: the lithium mine's affordability.** A deposit's estimate ($4–5B) exceeds what the group holds by 2024 on 9 of 10 seeds. Options: a smaller minimum capacity, project finance or offtake prepayment for mines, or a later year-15 rung.
- **I1 for M28:** re-measure once supply-driven prices from 2026 move fab economics; tighten the known-miss bound or remove it.
- **M16 T3 and T4:** the product manager's deferred ruling (2026-11-08).
- **V3.ai, V5.cells and V5.cats** stay known misses owned by M23 (readings in `docs/reviews/v3-balance.md`). The new v3 startup categories did not fill the 2020s and 2030s cells.
