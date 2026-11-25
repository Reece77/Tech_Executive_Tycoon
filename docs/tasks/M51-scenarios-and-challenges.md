# M51: Scenarios and challenges (v6, lane C)

**Goal:** reasons to start again. Six new scenarios join §30.3's five: the 2008 crash, a failing chipmaker, an EV maker, a Chinese foundry under controls, a platform war, and a dynasty. Challenge rules can be added to any game, each enforced by the engine and scored. A Scenarios screen keeps your best results across saves.

**Formulas:** `docs/formulas.md` §63 (all), with §30, §60 · **ADRs:** 0002, 0024 · **Depends on:** M50 (`m50-done`) · **Lane:** C, alongside M49 (lane A) and M53 (lane B)

## Reece's decision (2026-11-21)

- **Scenarios** are part of v6.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m51-scenarios` from `main`.
- **Must not edit** M49's or M53's's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M51 owns:** `scenarios.yaml`, `tst/sim/modes/` (scenario and challenge rules), the scenario and result screens, the app-wide results file, `challenges.*` keys, and `tst/balance/m51.py`.
- **Merges last** of this round.
- §63.4 target 3 (a normal game with no challenge rules plays exactly as before) is the guard.

## Sub-tasks (commit after each)

1. **The six scenarios** (§63.1) in `scenarios.yaml`, built with §30.2's world code (and M50's 2008 start for "The crash"). Each start and goal is checked with a scripted sensible player and a passive one on seeds 1–10. Adjust a goal or deadline to land in §63.4 target 1's band, and record each change.
2. **Challenge rules** (§63.2): each enforced as a refusal with a clear reason, with its score multiplier.
3. **The Scenarios screen and results** (§63.3): briefs, difficulty from seeds 1–10's win rates, best results and challenges kept in an app-wide results file (outside saves; it survives the M58 installer's updates), and the result screen's breakdown and comparison.
4. **API, e2e, balance and close-out:**
   - **Playwright:** (a) start "The crash" and fail it, (b) add the bootstrapped challenge and see a funding round refused, (c) a best result appears on the Scenarios screen;
   - **§63.4 targets** printed;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] All six new scenarios load, and each is winnable and losable as §63.4 target 1 says.
- [ ] Every challenge rule is enforced with a clear reason, and lowers the score as target 2 says.
- [ ] A normal game with no challenges plays exactly as before (state-cache check).
- [ ] `make check`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m51-done`.

## Decisions made

1. **Where scenarios live.** The six join `scenarios.yaml`'s `historical` list after §30.3's five and use the same engine (`tst/sim/modes/scenarios.py`, `world.py`). A start can now set: the founder's age and region (`founder_age` past the new-game range: the new game builds the founder that many years younger in the world's first year, so the family's ages check against it, and `apply_start` sets the age), the home city, a family (children's ages at the start, built in the world's first year and aged through the dormant years), named teams (`unit` on a staff line), a prototype (product `status: in_development`), an assembly contract, and fabs already running (ordered as `BuildFab` orders one, then live for `age_months` with a mature yield, its capex on the books against the starting equity less the depreciation since, never paid in cash). The crash plays on M50's 2008 world.
2. **Goal kinds** (formulas 63 M51 notes): `solvent_series` and `family_succession` are judged at the deadline; `platform_share`, `vehicles_year`, `fab_catch_up` (both conditions in one month) and `node_volume` end the scenario a success in the month they hold. "A successor in place" is a child of the first head at the head running the company (head mode `founder`, not a professional CEO, 45.5) with the family's `family.control_bp`: a founder's death with no heir in the company hands it to the eldest child with a board-appointed CEO, which is not a success.
3. **The scripts** (`tst/balance/m51.py`): the passive player does nothing. The sensible ones: the crash plays v1's steady; the platform war keeps the phone current (16 engineers, $2M a month of marketing, contracts renewed, region launches), builds an OS with 6 engineers from the first month and moves the phone onto it; the EV maker grows the prototype's team to 100 senior hires while runway allows, prices at the $35,000 reference, signs and renews assembly contracts, markets $10M a month once live and launches regions; the chipmaker raises when allowed, runs a 20-person process unit, staffs its fabs, contracts their starts and builds a fab on each newer node the process level and cash allow (cash for the estimate and every build still owed), converting the newest when nothing else is building; Under controls saves for one DUV 7 nm fab in China and requests an export licence when the controls ask; the dynasty runs the company as it is, gives the family time, offers each adult child a senior job in a role their interests match, mentors the readiest and names them once ready (or from 72, at least developing).
4. **Process research needs builders.** `process_engineer` has `product_function: none`, so it adds no research output (21.10); v3's `_process_research` (the foundry and full_integrator scripts) staffs it and researches nothing. M51's scripts use `manufacturing_engineer` (a builder with manufacturing skill). v3's scripts are left as they are (their guards are recorded against them): a follow-up.
5. **Before 2026 an own store's fee is 30%** (M31, `platforms.data.schedule` reads `platform.fee` only from 2026), so in the platform war developers follow users alone; the script sets no fee.
6. **Tuning to target 1** (sensible 3-8 of 10, passive at most 2; seeds 1-10; before -> after):

| Scenario | Change | Sensible before | after | Passive |
| --- | --- | --- | --- | --- |
| The crash | deadline Dec 2010 -> Dec 2009 (start cash $500,000: 14 months of runway) | 10/10 (Series A closed Dec 2009-Mar 2010) | 5/10 | 0/10 |
| The platform war | goal 20% -> 11% of developers in one region | 0/10 (0.101-0.122 by Dec 2020) | 6/10 (reached Oct 2019-Jul 2020; misses 0.101-0.108) | 0/10 |
| The EV maker | goal 200,000 -> 68,500 cars a year (before 2026 a new maker sells only into demand history's makers do not hold, 49.1), then deadline Dec 2023 -> Aug 2023 | 0/10 (an earlier script: 63,000-73,000 by Dec 2023); with the final script and 68,500, 10/10 (crossed May-Dec 2023) | 6/10 (Jun-Aug 2023) | 0/10 |
| The failing chipmaker | deadline Dec 2020 -> Jun 2016 (start: process lead 8, cash $2B, a 25,000-start 65 nm fab four years old) | 9/10 (caught up Dec 2015-Sep 2016, a 20 nm fab while 16 nm led) | 6/10 (Dec 2015-Apr 2016) | 0/10 |
| Under controls | start cash $3B -> $1.5B (deadline Dec 2027 kept) | 10/10 (7 nm ordered in early 2020, before the controls) | 6/10 (Jul 2024-Apr 2025; four seeds got no tool licence before the 2024 ban) | 0/10 |
| The dynasty | deadline Dec 2045 -> Dec 2035 | 10/10 (handed over 2030-2031 to an heir ready early, else 2036-2038 by 72) | 4/10 | 0/10 |

7. **Challenge rules** (`tst/sim/modes/challenges.py`): refused in `apply_action` for every action (the player's, a delegate's, an automated one) with the rule named. Bootstrapped: rounds, term sheets, SAFEs, bridges, loans, the IPO's banks, secondary offerings. Hardware only: a product in a category whose revenue model is not units. No acquisitions: bids, stakes, minority buy-outs. One region: region launches. No automation: automation areas, seat authority, CEO scopes. Hard rivals refuses nothing: in each market segment's month (11.6) a product of a company outside the player's group weighs in at quality x 1.2 (at most 100), its stored quality unchanged. Each rule's `score_mult` is 1.25. A campaign with rules has a mode record (`kind` campaign); one without has none, as before.
   The five M15b scenarios (rated only, v1's steady script, seeds 1-10): AI lab 0/10, Mobile first 0/10, Survive 2022 10/10, The chip startup 0/10, The turnaround 10/10 (passive 0, 0, 10, 0, 10: these two are won by holding on), recorded as `sensible_wins`.
8. **Results** live in `<saves>/results/<profile>.json` beside M25's achievement profile (Documents in the installed game: kept by updates), one record per scenario save (slug and seed) once its verdict is in, written after the committed turn (a cheap check of `save_meta.game_state` first). The best is a success over a failure, then the higher adjusted score, then the earlier. Difficulty bands `challenges.difficulty_wins` (3, 6): hard at 3 wins or fewer, medium to 6, else easy. The five M15b scenarios are rated with v1's steady script (`sensible_wins`).
9. **Target 2, Reece's decision (2026-11-25): carry three rules.** Measured at December 2014 (60 months; by year 10 the score has saturated) on the scripted player each rule cuts into, median of seeds 1-10:

| Rule | Arm | Without | With | Drop | |
| --- | --- | --- | --- | --- | --- |
| bootstrapped | steady_regions | 569.5 | 31.0 | 95% | ok |
| hardware_only | steady_regions | 569.5 | 25.0 | 96% | ok |
| one_region | steady_regions | 569.5 | 429.0 | 25% | ok |
| hard_rivals | steady_regions | 569.5 | 562.5 | 1% | carried |
| no_acquisitions | acquirer | 553.0 | 569.5 | -3% | carried |
| no_automation | ceo | 569.5 | 569.5 | 0% | carried |

At December 2019: 685 -> 31, 25, 633 (8%), 684, and acquirer 678.5 -> 684.5, ceo 698.5 -> 692.5. Hard rivals does bite (seed 1, December 2013: 25% fewer customers, 13% less MRR), but the score barely moves; the scripted players gain no score from acquisitions or delegation (V4 keeps delegation below hands-on play). The spec fixes Hard rivals at x1.2, and no key of M51's moves the other two, so Reece chose to keep the six rules as defined and carry the three (`m51.TARGET2_CARRIED`).
10. **Target 3.** Golden snapshots unchanged; M30's state cache (nightly, dispatched on the branch: FILL). `GameMode` gained `challenges`: M45's dynasty digest and M37's pre-2040 digest leave the (empty) field out, as M37 left out `length` (the dynasty campaign carries a mode record); nothing else in their runs changes.
11. **CI guards met on the way:** `multiplier` is a forbidden API key (hidden multipliers never leave the engine), so the results' field is `score_mult`; the score's points moved from the sim to `tst.api.modes_views.score_points` (the money and platform-maths guards); every historical scenario has a win achievement (six added: 49 in all).

## Follow-ups

- v3's `_process_research` (foundry, full_integrator) staffs `process_engineer`, which researches nothing (decision 4): staff builders, then re-measure V3/V5's guards.
- Target 2's three carried rules (decision 9): a scripted player that gains from acquisitions and from delegation, or a score that shows market share lost to stronger rivals, for the next balance pass.
- The Fundraising tab could show a challenge's refusal before the button is pressed (`next.allowed` reads only the engine's gates).
- Ratings for the five M15b scenarios use v1's steady script; scenario-specific scripts (a chip line for The chip startup) would rate them better.
