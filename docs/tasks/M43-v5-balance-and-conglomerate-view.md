# M43: v5 balance and the conglomerate view (v5, lane L; closes v5)

**Goal:** close v5 on a believable, balanced game across every industry, and give the player one view of the whole conglomerate. This milestone re-tunes the earlier targets that M43a's corrected economy moved, closes or bounds every known miss, adds v5's own strategies over 30 and 60 years, and builds the **conglomerate view** Reece asked for. The `m43-done` tag closes v5.

**Formulas:** §43 (v3 targets), §51 (v4), §54 (markets), and each v5 section's targets (§45, §49, §50, §52, §53, §55, §56, §57) · **Depends on:** M42, M40, M44 · **Lane:** L

## Reece's decision (2026-11-15)

- **The conglomerate view** in M43.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m43-balance` from `main`.
- Start now with **measurement and the conglomerate view.** **Don't tune or merge until `m42-done`, `m40-done` and `m44-done` all exist**; then merge `main` and re-run everything on the combined code.
- **M43 owns:**
  - `tst/balance/` (new `v5.py` and strategies);
  - every `known_misses.py` entry (owner M43 after sub-task 1);
  - the balance keys of the v5 milestones;
  - the conglomerate view (screen, API and read model).
- **CLAUDE.md §9's decision rules apply.** Long runs go to GitHub (rule 7). **Re-banding an earlier target is still a stop-and-ask:** bring each one with its numbers.

## Sub-tasks (commit after each)

1. **Known misses:** move the four entries still owned by the finished M28 (`V3.ai`, `V5.cells`, `V5.cats`, `I1`) to owner M43, with a note.
2. **The conglomerate view:**
   - one screen across every industry the group is in: revenue, gross margin, operating profit, capital employed and return on capital by industry and by company in the group, ten-year trends, and where capital went;
   - **a capital-allocation panel**: each industry's displayed return, growth and risk, the player's planned allocation for next year, and the proposals waiting;
   - **a yearly letter to shareholders**, written in the founder's voice by the LLM within §16's budget from engine facts only (template fallback), each January, kept in History;
   - read-only, no energy;
   - hidden values never shown (displayed figures only).
3. **The IPO thresholds:** check whether M13's listing requirements are fixed dollar amounts. If so, scale them with `economy_scale.money` as M34's thresholds were (§48.1). Re-measure M13 T2.
4. **v5 strategies** in `tst/balance/`, each behaving as a sensible player would (rule 2's test):
   - **`ev_integrator`:** cars on own cells, lithium and chips;
   - **`life_sciences`:** devices into medical devices and pharma with AI discovery;
   - **`space_and_defence`:** chips into satellites, broadband and government;
   - **`robotics_first`:** industrial robots into humanoids and robotaxis;
   - **`dynasty`:** any of the above with a family to 2069;
   - **`cloud_first`:** M35b's follow-up, to measure power's effect directly.
5. **Runs on the combined code:**
   - 30-year runs (seeds 1–10, weekly 1–30) for every strategy since v1;
   - 60-year dynasty runs (seeds 1–10) for the v5 strategies;
   - dispatched on GitHub.
6. **Targets** (printed):
   - **T1, viable, not dominant:** each v5 strategy's median year-30 ARR is 0.9–1.4× its natural comparison (named in the brief's Decisions made before measuring).
   - **T2, no strategy always wins:** no strategy is top on more than 4 of 10 seeds among all strategies.
   - **T3, every system's targets hold** on the combined code: §45.8, §49.6, §50.6, §52.5, §53.4, §55.6, §56.4, §57.6, and §54.4's economy targets.
   - **T4, the known misses:** each closed, or reported with its reading, bound and cause. They are:
     - I1, V3.ai, V3.margin, V5.cells, V5.cats and V5's startup coverage;
     - V2.wins;
     - V4.T1.1, V4.T1.2 and V4.T4;
     - M13.T2.blitzscale, M13b.T1 and M22.T2.variant;
     - M28 target 2 (accepted at 12%).
   - **T5, compliance isn't free:** M34's `compliant_platform` pays at least 10% of `platform_owner`'s fines (it paid none), or M43 reports why zero is right.
   - **T6, the economy is believable:** in every year to 2069, technology stays under 15% of world GDP, and the pre-2026 AI excess in Africa and Asia (M43a's follow-up) is fixed or bounded.
7. **Tune** only the keys this lane owns (rule 1), recording before and after values. Bring any re-banding to the PM.
8. **Close-out:**
   - CHANGELOG;
   - a v5 section in the roadmap's status;
   - the README index row;
   - trigger the weekly on `main` after merging and report it.

## Acceptance criteria

- [x] The conglomerate view and the yearly letter work on a 2039 save with at least four industries (e2e), and show no hidden values (test).
- [x] T1–T6 printed and met, or carried with a recorded decision; T4 reported in full.
- [x] Every earlier guard on the combined code is unchanged, or explained under rules 1–4.
- [x] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m43-done`. **This tag closes v5.**

## Decisions made

1. **T1's natural comparisons (named before measuring, `tst/balance/v5.py` PAIRS):** ev_integrator against full_integrator (the chain it grows out of), life_sciences, robotics_first and space_and_defence against devices_regions (devices and their own SoC, the base each adds its line to), and cloud_first against cloud_first_grid (the same company on the grid only, so the ratio measures power directly: M35b's follow-up). T2's field is M35b's v4 field plus the five v5 strategies; devices_regions and cloud_first_grid are comparisons, not in the field.
2. **The conglomerate read model (sub-task 2, `tst/sim/group/conglomerate.py`, `tst/db/conglomerate.py`):**
   - a ledger line belongs to an industry when its memo names one of the company's products, facilities, plants or mines (the longest name wins), or its account is one an industry lists (`conglomerate.industries` in balance.yaml: thirteen industries, from software to government);
   - every other operating line is split over the company's industries by their external revenue (largest-remainder cents); a company with no industry revenue keeps them as Corporate;
   - intercompany sales and purchases are left out of the industry figures (shown per company);
   - capital employed = assets less investments in group companies (1810), less liabilities other than debt (2500, 2600); capex = debits to 1500, 1520 and 1530; acquisitions = the cash lines whose memo begins "Acquisition of", "Venture investment in", "Shares of" or "Bought out the minorities of"; returned = the root company's equity debits for dividends and buybacks;
   - risk is the spread of an industry's yearly revenue growth over `conglomerate.risk_years` (5), in words ("low" below 0.10, "moderate" below 0.25, else "high"); trends cover `trend_years` (10).
3. **"The player's planned allocation for next year"** reads what the state holds: the capex still to pay on builds under way (by the facility's industry) and each subsidiary's yearly capex limit from its mandate (under the subsidiary's largest industry). There is no separate budget object to plan into; a new one would be a v6 feature (follow-up).
4. **The yearly letter:** December's turn queues an LLM text of kind `letter` for the year just played; the event service writes it in January from the books (the facts the conglomerate view shows, displayed values only), through the LLM within §16's budget, else the template. It lands in the inbox as "Letter to shareholders, YYYY" and History files it under finance. No energy, read-only.
5. **25.1's IPO floor from real listings (PM ruling 2026-11-20):** `ipo.min_arr_cents` = $241M, the 2015-2024 median of US tech IPOs' LTM sales (Jay R. Ritter, "Initial Public Offerings: Technology Stock IPOs", Table 4a, updated 30 Dec 2025; the yearly medians weighted by count, $234.3M in 2024 dollars, x 1.03 to 2025 dollars), x `economy_scale.money` = $20.5M game ARR (`ipo.min_arr_cents()`, exact money arithmetic). Before: $80M unscaled.
6. **M13 T4 re-banded (Reece, 2026-11-19):** 15-30x in 2012-19, 25-45x in 2020-21, a fall of at least 25% in 2022. Reading: 17.1x, 25.6x, 37%.
7. **A v5 line is funded from its own marketing budget (rule 2):** steady split one 20%-of-revenue budget equally over every product, so a $1M-a-month car line took a share of every app's marketing (-$2.6B of app revenue on seed 3; ev_integrator / full_integrator 0.94x -> 1.07x on seed 3). `fund_lines` sets each line's own budget (`LINE_BUDGETS`) and splits steady's 20% over the other products.
8. **steady_regions' marketing set once a month, first (PM rulings 2026-11-21, rule 2; `tst/balance/strategies_v2.py`):** steady set the whole 20% of revenue on every product, then `split_marketing` reset it, one energy an act; a founder short of energy (a family game's divorce) kept some products at the whole 20%, about 8x the plan, and robotics_first went bankrupt in dynasty mode on seeds 1, 4, 6 and 9 ($130-180M a month of marketing on $110M of revenue). The split is now the only pass and runs before the month's hiring (set after it, it found no energy left and kept last month's budgets: steady_regions' 10-year ARR fell 18%). The chain scripts also refill energy before staffing exploration, as before their other key acts (the month's hiring could leave none for moving the geologists in, so the desk study never started).
   - **A hiring plan for the listed founder was tried and dropped (PM, option 1):** with cash above a 24-month reserve going into a plan's open roles (25 a product, 6 salespeople a region, at most 10 hires a month), steady_regions grew to about 140 staff by 2019 (72 before) and its own 10-year ARR fell from about $368M to $299M: its products share one root team, and the extra people cost more than they earned within ten years. It also moved turn times (M30's 2039 month 507-611 ms against 400; M37's 2069 month 680 ms, its worst 1,134 ms against the 1 s limit), M10b's event spacing, M32's history and the nightly's run time, and V4 to 1.73x. **Design question for v6's balance pass (M46):** holding IPO cash beats putting it to work in this game; a sensible founder should be able to deploy listed capital at a positive return (investment opportunities may pay too little for their cost, or hiring may not scale with team structure).
   - **readings, V1-V4 (10 years, seeds 1-10), HEAD -> marketing fix:** V1 most wins research_heavy 5 -> 4; V2 1.42x -> 1.27x (in band); V2.wins 5 -> 4 (in band); V3 1.03x -> 0.92x; V3.margin -0.4 -> +0.6 pts; V4 1.45x -> 1.46x; steady_regions median ARR $368M -> $369M. robotics_first on dynasty seed 6: bankrupt in 2021 -> $2.47B of cash in 2023.
   - **seeds 11-20, HEAD -> marketing fix:** V1 research_heavy 8 -> 9 wins (fails on both); V2 1.40x -> 1.56x (recorded here, PM ruling 2026-11-22; seeds 1-10, where the guard is judged, read 1.27x); V2.wins 8 -> 9 (fails on both); V3.margin -2.9 -> -1.3 pts (within its known bound); V4 1.27x -> 1.38x.
   - research_heavy seed 2 goes bankrupt in month 31, before listing: HEAD's run was a month from the same end (cash negative in months 19, 23, 26 and 29-30; its Series A closed in month 31); the new marketing order cuts revenue about 4% in those months and the A closes a month later. Seed fragility, not a new behaviour.
9. **Known misses owned by v6 (PM rulings 2026-11-20 and 2026-11-21), each with its bound:** V4 (at most 1.47x; 1.46x on seeds 1-10), V4.T2 (litho_bet at most 5 of 10; `main` 3 on seeds 11-20, 6 on 21-30), M37's 2069 month (at most 550 ms runner-adjusted, owner v6's performance pass; 526 ms, profiled under rule 6: markets 27%, state sync 22%, rival decisions 11%, no M43 step). V2 and V2.wins pass on the marketing fix and their entries are removed; the four M28 entries moved to owner M43 in sub-task 1; M13.T2.blitzscale closed on the real-listings floor.
10. **The dynasty rows print the family's value** (45.6: its people and the trust, at the top of the group) rather than the founder's, which reads 0 after a succession; a run that reaches December 2069 ends in `dynasty_end`, a finished game, and keeps its value.
11. **The v5 weekly runs in five-seed 30-year jobs and two- or three-seed dynasty jobs** (10-seed shards ran past GitHub's limit on the real-listings floor), at GitHub's 360-minute limit; T1 and T2 pool the jobs' printed run tables (the runs' JSON uploads are on a host this session cannot reach). T3 and T6 run on demand (`weekly-m43-t3-*`, `weekly-m43-t6`).
12. **T5, compliance isn't free:** `compliant_platform` pays $0 in fines because it settles every case with commitments, which carry no fine (§48); its compliance cost is the $500k a month of lobbying and the remedies the settlements require. Zero fines is the right reading of a company that settles, so T5 is reported rather than tuned.
13. **Rule 3 (fails on `main` too):** V5.cells and V5.cats (49% against 75%, `main` 49%; M40's space categories and samd found no startups by design); the M30 holiday year on the V6 save (7.0 s, `main` 9.1 s, against 6 s); M30's 2039 month on the V6 integrator save (471 ms adjusted, `main` 459 ms, against 400; the V6 save itself reads 392 ms, within its guard).

14. **M10b target 1's spacing a known miss owned by v6 (PM ruling 2026-11-22):** at most 5 of 10 seeds with a shortest critical-event gap under 6 months (`M10b.T1.spacing`; 5 on M43: seeds 3, 4, 6, 7, 10; `main` 0). Cause: under the real-listings IPO floor the scripts list from 2015, and a listed company's `follow_up` critical events land within months of a key exit (seed 6: both in month 111). The commit before the marketing fix reads the same, so the floor moved it. The rate itself holds: 1.47 critical events per 18 months with 20+ staff (>= 1).
15. **M32's history fixture re-recorded on the combined code (PM ruling 2026-11-22):** its scripted runs (full_integrator, integrator) list earlier and build more, so 16 facility-years' power costs moved by more than 1% (11 before the marketing fix); `main` passes on its own recording, so the engine's pre-2026 power history is unchanged.
16. **The nightly's job limit 120 -> 180 minutes (PM ruling 2026-11-22):** shard 3 already passed 120 minutes on `main` (runs 79, 81, 84); listed companies from 2015 lengthen shards 1 and 4 past it too.

## Results on the combined code (seeds 1-10 unless stated)

| Target | Reading | Band | Verdict |
| --- | --- | --- | --- |
| T1 ev_integrator / full_integrator | 0.96x (seeds 1-20 0.96x) | 0.90-1.40x | met |
| T1 life_sciences / devices_regions | 1.02x (1.03x) | 0.90-1.40x | met |
| T1 robotics_first / devices_regions | 1.08x (0.99x) | 0.90-1.40x | met |
| T1 cloud_first / cloud_first_grid | 1.05x (1.04x) | 0.90-1.40x | met |
| T1 space_and_defence / devices_regions | 1.02x (0.97x) | 0.90-1.40x | met |
| T2 most wins of 10 | litho_bet 4 (seeds 11-20: acquirer 3) | <= 4 | met |
| T3 each system's targets | 45.8, 49.6, 50.6, 53.4, 55.6, 56.4, 57.6 met; 52.5's turn time a known miss (539 ms, bound 550) | | met with known misses |
| T4 known misses | V4 1.46x (bound 1.47x), V4.T2 (5 of 10), M37's 2069 month, M10b spacing (5 of 10), V3.ai, V3.margin, V4.T1.1, V4.T1.2, V4.T4, I1, M13b.T1, M22.T2.variant, V5.cells, V5.cats; closed: V2, V2.wins, M13.T2.blitzscale | | reported |
| T5 compliance isn't free | compliant_platform $0 in fines (settles with commitments) | >= 10% of platform_owner's, or why zero | reported (decision 12) |
| T6 technology's share of world GDP | 12.77% at its largest (addressable 52.4%); no market grows past its ceiling after 2026; the 16 category-regions above it from history (AI models in Africa, East and South Asia among them) are held, not grown | <= 15% | met; bounded |

Dynasty runs to 2069 (seeds 1-10, with a family): robotics_first reaches December 2069 on all ten seeds (before the marketing fix it went bankrupt on four); one run ends early, cloud_first on seed 7 ($4.5B of ARR when it stops); every other run reaches 2069, the family's value about the group's ARR (medians $51-149B by strategy and job).

## Follow-ups

- **Deploying listed capital (M46, v6 balance pass one):** a sensible founder should be able to put IPO cash to work at a positive return; hiring to a plan lowered steady_regions' ARR because every product shares the root team (decision 8). V4 rides on it.
- **A planned-allocation budget (v6):** the capital-allocation panel shows builds under way and mandates' capex limits; a player-set yearly budget by industry would need its own state.
- **Robotaxis out of reach in robotics_first:** its AI model plateaus near quality 75 against L4's 80, so no run reaches robotaxis by 2069.
- **M16's stage-5 threshold ($2B) is not scaled** with `economy_scale.money`, as 25.1's floor now is.
- **Listed companies' follow-ups must respect the director's 6-month critical spacing** (M10b target 1's known miss).
- **The nightly in six shards** (it runs at 180 minutes a job from M43).
- **V5.cells and V5.cats** should count M40's space categories and samd, which found no startups by design.
