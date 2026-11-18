# M43a: Market sizes and saturation (v5, lane G; the first part of M43)

**Goal:** the game's economy stays believable for 60 years. Every market gets a ceiling tied to the size of the economy that buys from it, so growth fades instead of compounding forever. Each category's 2025 size is recalibrated against published figures. M37's runaway (an AI market hundreds of times world GDP by 2039, and money values near the integer limit by 2069) is closed.

**Formulas:** `docs/formulas.md` §54 (all), with §8, §21.4, §26.4, §37, §52 · **ADRs:** 0002, 0003 · **Research:** `docs/v5-research/market-sizes-dossier.md` · **Depends on:** M37 (`m37-done`) · **Lane:** G, alongside M39 (finishing) and the next v5 lanes

## The product manager's decision (2026-11-17)

M37 found the AI-models market at about $1.2–1.6T a year in 2025 (real-dollar equivalent) and $1,600–2,600T by 2039. This affects Reece's standard 30-year campaign, not only dynasty mode, so it is fixed now rather than in M43's final balance pass. History before 2026 **may change** where calibration needs it (§54.3), with every change listed.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m43a-markets` from `main`.
- **Merges after M39**: merge `main` after `m39-done`, then re-run everything on the combined code.
- **M43a owns:**
  - market growth and saturation (`tst/sim/markets/` demand growth; the era-boost application in `tst/sim/eras/` where it multiplies growth);
  - `categories.yaml`'s `growth_by_year` and starting sizes;
  - `markets.*` in `balance.yaml`;
  - the post-2025 GDP path in `macro_history.yaml` (seeded, from M37's continuation rules);
  - `tst/balance/m43a.py` (new);
  - `known_misses.py`'s `M37.money` entry (to close it).
- **M43a must not edit** any later lane's new code (M40, M42, M45 when they start). Merge `main` often.
- **CLAUDE.md §9's decision rules apply,** with §54.3's exception: history before 2026 may change, listed. Changing M8 target 4's band, or any earlier target's band, is still a stop-and-ask.

## Sub-tasks (commit after each)

1. **Research:** a 2025 published size (and 2010 and 2020 where available) for every category, with definition and source, from the dossier. Report the game's current 2025 sizes at real-dollar equivalent beside them, as a table in Decisions made.
2. **Ceilings and saturation** (§54.1):
   - `markets.ceiling_share.<category>` with sources;
   - the GDP path;
   - growth as `g × (1 − A / C)`;
   - era ceiling lifts;
   - long-run growth decaying to GDP plus a premium.
   - **Unit tests** of the formula. **Property test:** no market passes its ceiling.
3. **Calibration** (§54.2): recalibrate categories outside 0.5–2× their published 2025 size, keeping 2010 starts and curve shapes where possible. List every pre-2026 series that changes, with before and after values. Re-measure M8 target 4 and report it.
4. **Re-run everything** on the combined code: §54.4's targets, and every earlier guard (V1–V6, M8, M13b, M21–M23b, M28, M31–M35b, M36–M41).
   - Re-record M28's history fingerprint, M30's state cache and golden snapshots, with reasons.
   - Tune only `markets.*` and category growth (rule 1).
   - Apply rules 2–4 to anything that moves.
5. **Close-out:**
   - close `M37.money`, or report its reading;
   - CHANGELOG, data dictionary;
   - an economy note in `docs/economy-scale-audit.md` (what changed, and whether the audit's option C is still needed);
   - README index row.

## Acceptance criteria

- [ ] Every category has a sourced 2025 size and a ceiling; no market passes its ceiling in any year to 2069 (property test and target 1).
- [ ] §54.4 targets 1–6 printed and met, or carried with a recorded decision; `M37.money` closed.
- [ ] Every pre-2026 change is listed with before and after values; every earlier guard re-run, and the results reported under rules 1–4.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m43a-done`.

## Decisions made

1. **Research (sub-task 1).** `docs/v5-research/market-sizes-dossier.md` carries a sourced 2025 size for every category (2010 and 2020 where found), with definitions and [V]/[D]/[M] tags; GDP figures are [M] (imf.org was blocked). `ai_models` is pinned to AI models and applications (Gartner AI application software $172B + GenAI models $14B = $186B); medical categories use M41's own sourced 2024 sizes (`medical.yaml`). The game's 2025 sizes beside them: decision 4 and `tools/m43a_targets.py`.
2. **Target 2 judges served revenue (Reece, 2026-11-17).** Published sizes are spending, which in the game is booked revenue (customers x price x units a month, plus medical consumables). Ceilings still bound the addressable market (target 1). Target 1's technology share of world GDP is judged on served revenue too; the addressable sum is printed beside it.
3. **Ceilings start in January 2026 (PM ruling, 2026-11-18).** `markets.ceiling_start_year` 2026: the history to 2025 grows as on main, recalibrated only where 2025 was outside 0.5-2x (decision 4). A market that leaves the history already past its ceiling is held at its size, never cut, until its region's economy catches up (the clamp is max(C, its value before the month's growth)). With ceilings from 2010 (the first design), about eight earlier guards moved (decision 10's first table); loosening the ceilings only moved the misses.
4. **Targeted recalibrations (sub-task 3), the only pre-2026 changes.** On main (seed 1, full_integrator, real-dollar equivalent = game / 0.0849) four categories sat outside 0.5-2x of published 2025 served revenue: AI models 8.0x, cloud hosting 3.5x, developer tools 3.7x, servers 0.08x. Changes: AI models' D0 x0.19 (200,000 / 20,000 / 2,000 / 300 -> 38,000 / 3,800 / 380 / 57; growth tables kept, so 18.9 target 4 and 21.8 target 1, ratios to January 2010, are unchanged: 343x); cloud hosting growth 0.30 -> 0.225; developer tools' eras.yaml base growth x0.66 (0.2208 / 0.25 -> 0.1457 / 0.1650) with categories.yaml's rate refitted to 0.1749 for 21.8 target 1; servers D0 x5 (30,000 / 30 -> 150,000 / 150) and growth 0.10 -> 0.15. Server CPUs follow cloud and servers, so they move with them. Every other category's history is main's (the small differences below are knock-on effects through shared rivals and chips). Medical served revenue differs in this table only because the measure now counts consumables. Seed 1, $B a year, main (`m37-done` code) -> M43a:

| Category | served 2010 | 2015 | 2020 | 2025 | addressable 2025 |
| --- | --- | --- | --- | --- | --- |
| ai_models | 1.2 → 0.2 | 4.1 → 0.8 | 29.8 → 5.8 | 1,494.6 → 286.9 | 23,827 → 4,527 |
| b2b_saas | 10.9 → 10.9 | 24.7 → 24.7 | 66.9 → 67.0 | 192.7 → 193.7 | 766 → 766 |
| chips_ai_accelerator | 0.9 → 0.9 | 1.2 → 1.3 | 5.6 → 6.3 | 256.0 → 258.4 | 13,476 → 13,495 |
| chips_mobile_soc | 3.8 → 3.8 | 8.6 → 8.6 | 19.3 → 19.3 | 46.7 → 46.7 | 81 → 81 |
| chips_server_cpu | 2.6 → 2.6 | 3.4 → 3.4 | 5.8 → 5.0 | 30.6 → 18.9 | 378 → 144 |
| cloud_hosting | 26.5 → 26.3 | 90.6 → 71.2 | 375.6 → 214.3 | 1,465.2 → 529.9 | 10,178 → 3,267 |
| consumer_apps | 2.7 → 2.7 | 16.0 → 16.0 | 62.9 → 62.9 | 278.9 → 288.7 | 812 → 812 |
| contract_manufacturing | 3.1 → 3.1 | 4.8 → 4.8 | 8.0 → 8.0 | 13.8 → 13.8 | 46 → 46 |
| cybersecurity | 14.1 → 14.1 | 27.0 → 27.0 | 57.6 → 57.6 | 153.7 → 153.9 | 543 → 543 |
| dev_tools | 3.7 → 3.7 | 9.2 → 7.5 | 27.5 → 17.4 | 91.6 → 39.4 | 594 → 173 |
| devices | 53.4 → 53.4 | 182.4 → 182.4 | 389.7 → 386.6 | 684.6 → 655.8 | 1,102 → 1,102 |
| fintech | 12.5 → 12.5 | 27.7 → 27.7 | 90.3 → 90.5 | 378.6 → 380.3 | 1,868 → 1,868 |
| imaging | 19.3 → 31.7 | 22.2 → 36.6 | 25.9 → 42.6 | 30.3 → 49.9 | 46 → 46 |
| implantables | 20.9 → 20.9 | 21.8 → 21.8 | 24.9 → 24.9 | 25.4 → 25.4 | 52 → 52 |
| samd | 0.0 → 0.0 | 0.1 → 0.1 | 0.2 → 0.2 | 1.1 → 1.1 | 7 → 7 |
| servers | 9.6 → 48.2 | 13.6 → 75.6 | 21.6 → 147.8 | 36.2 → 318.6 | 132 → 1,495 |
| surgical_robotics | 0.3 → 1.6 | 0.4 → 2.1 | 0.7 → 3.7 | 1.2 → 6.5 | 5 → 5 |
| wearables_diagnostics | 0.1 → 2.3 | 0.2 → 5.2 | 0.5 → 11.7 | 1.0 → 24.4 | 1 → 1 |

   2025 served revenue, median of seeds 1-4, against published: SaaS 183 (0.61x of 299), dev tools 41 (1.65x of 25), consumer apps 273 (1.63x of 167), cybersecurity 153 (0.72x), fintech 353 (0.93x), AI models 282 (1.52x of 186), cloud 534 (1.28x of 419), devices 667 (0.89x of 750), servers 318 (0.72x of 444), mobile SoCs 47 (1.03x), server CPUs 18 (0.68x of 27), AI accelerators 214 (0.93x of 230), vehicles 350 (0.58x, M38's data), wearables 24 (1.75x), imaging 50 (1.13x), surgical robotics 6.6 (0.66x), implantables 25 (0.81x), SaMD 1.0 (0.70x). **Contract manufacturing 14 (0.02x of $648B EMS) is reported, not judged:** a spare-capacity market by design (economy-scale audit §4).
5. **Ceiling shares** (`markets.ceiling_share`, of regional GDP, on the addressable market), about 5x North America's 2025 addressable share on main's curves where 2025 was in band (SaaS 8%, consumer apps 2.6%, cybersecurity 2.4%, fintech 7%, devices 5%, servers 6%, mobile SoCs 0.4%, server CPUs 1.2%, AI accelerators 30%, medical 0.05-0.5%, default 1%), and AI models 1.5%, cloud 1.2%, dev tools 0.2%. With 10x shares technology reached 15.7% of world GDP in the 2040s (target 1); at 5x, 11.4%. Shares sit above real spending shares because served revenue is 15-70% of addressable (4-7% for chips). `era_ceiling_lift` 0.10 an arrived era; GDP growth after 2025 3.5-6.5% nominal by region.
6. **Long-run growth** decays from 2030 (`mature_start_year`; 2026 was tried for target 1 with the 10x shares, but cut rival startups after 2020, V5.cats; with the 5x shares 2030 gives 12.6%) toward 4% + a premium (1% default; AI 4%, accelerators 3%, cloud and cybersecurity 2%), half-life 4 years; rates a table lists after 2030 are replaced (they are not history). M8's worked example of AI growth in 2039 follows it.
7. **M37's dynasty mature growth raised (rule 1 and 2, M37's key):** `dynasty.markets.mature_growth` default 0.01 -> 0.02; AI models, cloud hosting, AI accelerators 0.015 -> 0.025; dev tools 0.03, devices and fintech 0.025 (new entries; fintech read 0.98% at 0.02); vehicles unchanged. M37 had lowered them only to fit int64; the ceilings now bound the books. At 0.01, target 3 read 0.1-0.97% for 16 categories. Nothing before 2040 changes.
8. **Target 3 prints, not judges, data-set markets:** vehicles (M38), industrial and humanoid robots (M39) take their demand from data each month and have no growth rate for 54.1 to act on (2060s: vehicles 0.21%, humanoids 0.10%, industrial robots 2.97% a year).
9. **§54.4 readings (seeds 1-4, dynasty games to 2069, final keys, `tools/m43a_targets.py`):** T1 no market grown past its ceiling in any year; technology served revenue at most 12.6% of world GDP (addressable 52.1%): met. Held past their ceiling from the history (printed): AI models in Africa, East Asia, Latin America, Oceania and South and Southeast Asia; AI accelerators in Africa and South and Southeast Asia; cloud hosting in every region; developer tools in Oceania and South and Southeast Asia. T2 met (decision 4). T3 met (decision 8). T4 largest balance 1.48e16 cents (IBM's was 6.07e18): met, **`M37.money` closed**. M8 target 4 is unchanged (ceilings start after 2024).

10. **Earlier guards (sub-task 4), re-run on the combined code with the final keys: five are this branch's and are reported for the PM's ruling (not re-banded).** CI on `m43a-markets` (nightly and weekly), main's latest runs for comparison (the weekly parts on main at `6a6b985`, dispatched for this), and side-by-side local runs of `tools/m13_targets.py`, `m13b_targets.py` and `m22_targets.py` on this branch and a worktree of main, seeds 1-10:

    | Guard | Main | M43a | Band | Cause |
    | --- | --- | --- | --- | --- |
    | M13 §25.9 T2: blitzscale listed by turn 180 | 4/10 | 1/10 | >= 4 | blitzscale's second product is developer tools (`strategies.SECOND_PRODUCT`), whose base growth is x0.66: its 2020 market is about 63% of main's. Steady 6/10 -> 5/10 (passes) |
    | M13b §27.5 T1: new product and region | 7/10 | 6/10 | >= 7 | AI models' D0 x0.19: about 5x fewer AI customers in the era window (target 5 still met, 8 seeds) |
    | M22 §39.4 T2: revenue lost with a variant, Oct 2022-Sep 2023 | 10.5-10.8% | 10.5-20.8% | 5-15% | one seed out; the chip markets the variant sells into follow cloud and servers (recalibrated) |
    | V2 research_heavy wins (weekly-v1to4) | <= 4 (pass) | 5/10 | <= 4 | before 2026: only the recalibrations act there |
    | V3 integrator - steady_regions operating margin (weekly-v1to4) | pass | -1.4 pts (62.1% vs 63.6%) | -1 pts or more | before 2026 (as V2) |

    Rule 2 tried: my keys (the four recalibrations) cannot move these back without leaving 0.5-2x (developer tools is at 1.65x; at x0.72 it read 2.00x), and changing the scripts' choices (blitzscale's second product, the AI era script) would change how those targets are measured (CLAUDE.md §9: the PM's call). Fixed under rule 2: the pt-dynasty builder (decision 11); M14b T4, M24 T3 and M36 pass with ceilings from 2026. **Not this branch's (rule 3):** V5.cats and V5.cells fail on main too (main at `6a6b985`: samd empty in 9-10 runs both decades, fintech 2030s in 7; this branch is no worse); M30's 2039 turn-time guard fails on main too (587 ms on CI; this branch 582-718 ms, 6.0-6.4 workloads against main's 6.1). V4.T1.1 (platform_owner / devices_regions, December 2039, 0.90-1.40x): 0.89x on this branch with the 2026 decay; re-run with the 2030 decay and on main still running at this writing.

11. **Practice save pt-dynasty (`tools/e2e_m37_save.py`), a script fix under rule 2.** `check`'s `test_every_v3_practice_save_opens_people_and_org_with_a_team[e2e_m37_save-practice]` failed on this branch ("no CTO appointed"; it passes on main): with the recalibrated history the full_integrator's CTO leaves in the campaign's last months, and `fixtures.finish` appoints the replacement in January 2040, after the standard campaign has ended, when the engine refuses appointments ("the standard campaign ended in December 2039"). The tool now refills a vacant CTO seat from the company's own engineers before December 2039 (what a player does); the game is unchanged.

## Follow-ups

- **M43: the pre-2026 excess left in Africa and Asia (PM ruling, 2026-11-18).** With ceilings from 2026, markets whose history ran past their region's economy stay held there: AI models in Africa and South and Southeast Asia (about 70x their ceiling in January 2026; in 2025 their addressable markets were 90-105% of those regions' GDP on main's curves, the cause is M9's regional growth multipliers of 1.3-1.8x applied to AI's 100-220% boom years), and cloud hosting in every region. M43 can rescale the regional growth multiplier for high-growth categories, or recalibrate the regional history.
- **`economy_scale.money` was not re-derived** (M34's key): cloud and AI books moved, so Microsoft's and others' 2025 revenue changed.
- **Turn time:** saturation adds a per-month pass over every market (main's 2039 month 587 ms on CI, the branch's measured in decision 10).
