# M46: v6 balance pass one (v6, lane A)

**Goal:** settle what v5 handed on, before v6's new systems build on it. Close or tighten every known miss owned by the finished M43. Answer the two design questions v5 raised: why holding IPO cash beats putting it to work, and why listed companies' critical events bunch together. Then make the nightly run in six shards.

**Formulas:** §14, §23, §25, §30, §43, §51, §54 · **Depends on:** M43r (`m43rb-done`), M47 (`m47-done`) · **Lane:** A, alongside M48 (lane B) and M50 (lane C)

## Carried here

- **Known misses owned by the finished M43** (`known_misses.py`): V3.ai, V3.margin, V5.cells, V5.cats, I1, V4.T1.1, V4.T1.2, V4.T4, M13b.T1, M22.T2.variant. Also those M43 handed to "v6's first balance pass": V4 (at most 1.47×), V4.T2 (at most 5 of 10), M10b.T1.spacing (at most 5 of 10 seeds).
- **M43's design question:** a hiring-to-plan rule for a listed steady founder lowered its own ARR (about $368M down to $299M). Holding IPO cash beats deploying it.
- **M43's follow-up:** listed companies' `follow_up` critical events don't respect the director's 6-month critical spacing.
- **M43's follow-up:** the nightly in six shards.
- **Not here:** M37's 2069 month (v6's performance pass).

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m46-balance` from `main`.
- **M46 owns** `tst/balance/`, `known_misses.py`, the balance keys of the systems behind each miss, the events director's spacing for `follow_up` events, and the nightly workflow's sharding.
- It merges **first** of this round's three lanes (it moves the most balance). M48 and M50 merge `main` after it.
- **CLAUDE.md §9's decision rules apply.** Re-banding an earlier target is a stop-and-ask: bring each one with its numbers. Long runs go to GitHub (rule 7).

## Sub-tasks (commit after each)

1. **Deploying listed capital:** find why a steady founder can't put IPO cash to work at a positive return. Look at hiring's marginal value when products share one team, the cost of a hire against what it adds within 3–5 years, and whether new products, regions or acquisitions pay. Report the finding with numbers. Then make **one** change to the game (a rule or keys in the owning system's lane) so that a sensible founder can deploy listed capital at a positive return. Record why. **Target:** a listed steady founder who hires to plan, with work for every hire, ends 10 years at least 5% above one who leaves the cash idle (median, 10 seeds).
2. **Critical-event spacing:** listed companies' `follow_up` critical events respect the director's 6-month spacing (deferred, not dropped). Close `M10b.T1.spacing`.
3. **The known misses:** for each entry above, trace the cause on the current code, then close it, tighten its bound, or report it with numbers. Tune only the owning system's keys (rule 1). Fix balance scripts that lack sensible behaviour (rule 2). Move every entry still owned by "M43" to its new owner, with a note.
4. **The nightly in six shards:** rebalance with the durations file, and keep job names stable for any required checks.
5. **Close-out:** re-run everything (30-year runs on seeds 1–30, dynasty runs on 1–10); CHANGELOG; the README index row.

## Acceptance criteria

- [ ] The listed-capital target is met, with the cause and the change recorded.
- [ ] `M10b.T1.spacing` closed.
- [ ] Every listed known miss closed, tightened or reported with numbers; none left owned by a finished milestone.
- [ ] The nightly runs in six shards within its time limit.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m46-done`.

## Decisions made

1. **Branch and lane:** built on `m46-balance` from `main` after PR #99 (docs-v6-round2) merged with a merge commit (f4642ee8).
2. **Why listed capital sat idle (sub-task 1, the finding):** steady_regions on seeds 1-10 lists in months 69-81 and ends 2019 with $364-591M of cash and $231-466M ARR (median $370M). Where a hire could work, measured by arms on steady_regions from the listing month (cash above 24 months of costs; 10 seeds, 10 years, median of paired ARR ratios against steady_regions):
   - **builders** into the new-category teams while their feature score is under 98, up to 25: **0.99x**. Builders saturate: the feature score stops at 100 (the root product sits at 100 with 28-30 builders) and Q_cap is 5 x the team's output-weighted average skill (quality 40-57 on every product), so a larger team adds nothing once the score is full, and an average hire cannot raise the cap;
   - **sellers** into a sales unit for each product whose sales capacity bound (Pipeline's mid-market, about 1,300 of 40,000 customers), up to 40: **1.03x**. They pay (cash ends higher on 7 of 10 seeds), but only the small sales-led segments use them;
   - **marketing at 40% of revenue** instead of 20%: **1.23x**. Brand drives self-serve awareness (11.7), and the consumer products (K = 300) hold most of the ARR;
   - **marketers** added nothing: `mk = budget/$1,000 + 5 mu`, so a marketer is worth $5,000 a month of budget, and at a listed company's $0.2-2M a month a team of ten moves brand by a fraction of a point. The 5 mu was set in M3 for $10,000 budgets and never followed the economy's scale (M43a).
   M43's plan (decision 8 there: 25 a product and 6 sellers a region, hired at the root) put most hires on the root product, already at a full feature score: pure cost, hence its $368M to $299M.
3. **The one game change (sub-task 1): marketers direct a large budget** (formulas 11.5, `products.marketer_lift` 0.05, `.marketer_lift_cap` 0.5, `.marketer_lift_from_mk` 100): budget points above 100 (a $100,000 monthly budget) are multiplied by 1 + min(0.5, 0.05 mu). A startup's budget sits below the threshold, so the early game is unchanged (golden snapshots unchanged); one average marketer lifts a large budget by 5%, ten reach the cap. Chosen over raising the seller rate (helps only sales-led segments) or a team-size term on Q_cap (moves every product in every game) because it gives a hire real work exactly where the cash is, at the listed scale.
4. **The target's script (`tst.balance.m46.listed_planner`):** steady_regions plus, once listed and with cash above 24 months of costs, marketers for each product under brand 95 (one more a month to 10), sellers where sales capacity binds (two more to 40) and builders for new-category teams under a feature score of 98 (two more to 25). **steady_regions stays idle** (M43 decision 8) and is the comparison; making it the planner would move every v2-v5 guard built on it (as M43's attempt did), which this pass does not need.
5. **Target met: 1.105x** (median of paired ratios, seeds 1-10, 10 years; planner $287-520M, idle $235-466M; cash ends higher than idle on 9 of 10 seeds, so the hires pay for themselves). **Control:** the same plan without the change (`marketer_lift` 0) reads **1.041x**, under the 5%. Marketers alone read 1.109x. Nightly test `tests/balance/test_m46_balance.py`.
6. **Critical follow-ups wait for the slot (sub-task 2, formulas 16.1):** the cause was in the director: queued follow-ups (moments such as `ipo_pricing_strong` and `activist_stake`, critical-only templates) were queued at their template's severity without checking the 6-month critical slot, and did not take it, so a drawn `key_exit` could land in the same month (seed 6, month 111). Now a critical queued event takes the slot ahead of storylines, crises and drawn events, or stays queued (deferred, not dropped) until the first month the slot is free. Deferring alone delayed IPOs (the listing waits on the pricing answer) and moved M13's T4 to 24.4x in 2020-21 (band 25-45; `main` 25.6x on this machine), so **the slot is also held while the player's IPO chain is under way** (banks hired, not yet priced): drawn criticals and crises wait instead of the listing. Readings on seeds 1-10: every shortest critical gap 6-8 months (5 seeds under 6 before), 1.33 critical events per 18 months with 20+ staff (>= 1); M13 T4 17.2x / 25.7x / a 36% fall (main 17.1x / 25.6x / 37%), T2-T5 all met. `M10b.T1.spacing` is closed and removed from `known_misses.py`. Golden snapshots unchanged.
7. **The nightly in six shards (sub-task 4):** `NIGHTLY_SHARDS` 6 and two more matrix jobs, names unchanged (`nightly (nightly-ci SHARD=k)`; nightly is not a required check). Each shard now prints every test's duration (`--durations=0`), and `tools/nightly_durations.py` merges a shard's log into `tests/durations.json`; before M46 the file held no nightly test, so every nightly test weighed the mean and the shards split by name.
8. **Long fixtures recorded on CI (rule 7):** `make record-fixture FIXTURE=m30|m37|m45` (`tools/record_state_fixtures.py`) re-records a state fixture and prints it to the log, dispatched as a weekly part; the session copies it from the job log.

## Follow-ups

(filled in by the agent)
