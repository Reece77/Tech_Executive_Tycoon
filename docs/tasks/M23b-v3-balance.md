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

## Follow-ups

_(Agent fills in.)_
