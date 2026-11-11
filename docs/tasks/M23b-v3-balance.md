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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
