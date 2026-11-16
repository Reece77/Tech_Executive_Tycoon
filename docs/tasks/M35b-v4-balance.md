# M35b: v4 balance (v4, lane B; closes v4)

**Goal:** v4's systems (platforms, power, equipment and regulation) work together over 30 years. Their strategies are viable but not dominant, and each system's targets still hold on the combined code. The `m35b-done` tag closes v4.

**Formulas:** §44.9, §46.8, §47.5, §48.5, and the v3 targets (M23b's section) · **Depends on:** M32 (`m32-done`), M33, M34, M36p; merges **after M35a** · **Lane:** B, alongside M35a (lane A)

## Lane

- Its own session, in its **own clone or worktree**, on branch `m35b-balance` from `main`. Build strategies and measurement first. Tune and merge only after `m35a-done` exists: then merge `main` and re-run everything on the combined code.
- **M35b owns:** `tst/balance/` (new `v4.py` and strategy scripts), the balance keys of M31–M34 (`platforms.*`, `power.*`, `equipment.*`, `regulation.*`), `known_misses.py` entries for v4 targets, and `regulation.yaml` and `platforms.yaml` data for the follow-ups below.
- **M35b must not edit** M35a's files (see its brief).
- **CLAUDE.md §9's decision rules apply.** Long runs go to GitHub (rule 7).

## Sub-tasks (commit after each)

1. **v4 strategies** in `tst/balance/`:
   - **`platform_owner`:** a device maker that launches its own OS and store by 2014 and licenses it from 2018;
   - **`power_hyperscaler`:** a cloud company that builds its own plants behind its data centres from stage 4 and sites by power;
   - **`litho_bet`:** M23b's `full_integrator`, which also starts the lithography programme in 2028 at the 60th-percentile funding;
   - **`compliant_platform`:** `platform_owner`, but settling early and paying for influence.

   Each behaves as a sensible player would (rule 2's test).
2. **30-year runs on the combined code** (seeds 1–10, and the weekly on 1–30) for the four v4 strategies, with M23b's v3 strategies and `devices_regions` as comparisons. Dispatch on GitHub.
3. **The v4 targets** (printed):
   - **T1, viable, not dominant:** each v4 strategy's median year-30 ARR is between 0.9× and 1.4× its natural comparison:
     - `platform_owner` against `devices_regions`;
     - `power_hyperscaler` against a steady cloud company without plants;
     - `litho_bet` against `full_integrator`.
   - **T2, no strategy always wins:** no v4 strategy is top on more than 4 of 10 seeds among all strategies.
   - **T3, regulation bites platforms:** `platform_owner` meets at least one duty or fine by 2034 on at least 7 of 10 seeds, and `compliant_platform` pays at least 30% less in fines.
   - **T4, power binds:** `power_hyperscaler` reaches its 2032 capacity at least 1 year earlier than the steady cloud company in congested regions.
   - **T5, each system's targets still hold:** §44.9's 2–5, §46.8's 2–5, §47.5's 2–4 and §48.5's 2–5 re-measured on the combined code, and the v3 targets (I1–I3, S1, S2, F1, L1–L4).
   - **T6, the known misses:** each one closed, or reported with its numbers and owner. They are:
     - I1 (M28);
     - V3.ai and V5.cells / V5.cats (M28);
     - M28's target 2 (accepted at 12%);
     - M30's 439 ms (now M35a's).
4. **Follow-ups from M32–M34 that are balance or data:**
   - **Google Play's regulated rates** (M34): add them to `platforms.yaml` with sources. Re-record M28's §41.8 target 1 fingerprint for the fee series only, with the diff shown.
   - **Regulators' strictness after 2025:** a seeded drift moved by politics and §32.5 influence, within `regulation.*` bounds.
   - **Mergers review linked to regulators:** §28.7's antitrust review reads the regulator's strictness and an open investigation.
   - **The scripted phone line with a production contract that books no hardware sales** (M34): fix the script, or report the engine gap.
   - **Rival foundries' expansions waiting on EUV deliveries** (M33): rivals' new EUV capacity arrives only with their queue deliveries.
5. **Tune** only the keys this lane owns, as far as needed (rule 1), recording before and after values.
6. **Close-out:**
   - CHANGELOG;
   - a v4 section in the roadmap's status;
   - the M35 rows in the README index;
   - trigger the weekly on `main` after merging and report it.

## Acceptance criteria

- [ ] T1–T5 printed and met, or carried with a recorded decision; T6 reported in full.
- [ ] Every earlier guard on the combined code is unchanged, or explained under rules 1–4.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m35b-done`. **This tag closes v4.**

## Decisions made

1. **Branch and lane.** Built on `m35b-balance` from main (fa12404) in its own clone; strategies and measurement first, no tuning until `m35a-done` existed (it appeared with main 6d706d1); then main merged (3122bcc) and everything re-run on the combined code on GitHub (rule 7).
2. **The v4 scripts** (`tst/balance/strategies_v4.py`):
   - `platform_owner` is devices_regions with its own OS: a 4-engineer team from January 2012 once runway allows (by January 2013 in any case); the OS launched by 2014 (seed 1: May 2013; every seed in the weekly rung table), its phone on it from the line's first month, licensed to other makers from January 2018 at half Android's licence a unit. It answers regulators as M34's "default" player.
   - `compliant_platform`: M34's "compliant" answers (commitments at an inquiry) and $500k a month of lobbying in North America and Europe from January 2026.
   - `cloud_steady` (T1's and T4's "steady cloud company without plants"): steady_regions with integrator's own general data centres (30.6) selling their spare capacity as cloud hosting at 0.9x reference with $50k a month of marketing (M12a's seller). Not counted in T2.
   - `power_hyperscaler`: cloud_steady, but from stage 4 each new data centre sited by the build screen's rows (shortest queue, then cheapest grid, among the cities that serve the home market), with a plant behind its meter when it would queue, sized to the whole load (46.3).
   - `litho_bet`: full_integrator, its holding company formed from January 2027 (stage 5, where lithography opens), a 120-researcher lithography unit (litho_2's staff) from then, and the programme from January 2028 at the 60th-percentile funding (1.1x) once its gate opens and cash covers six months of a stage's funding.
3. **Rule 2 fixes to my own scripts:** litho_bet's first cash rule (two years of funding in cash) held a 2028 start back to 2035 on seed 1: six months' cover starts it in 2028 and the group's income pays the rest. power_hyperscaler first took the screen's cheapest $/MWh plant, which put 250 MW of wind behind a 50 MW load: it now takes the type whose whole-load size costs least a year (size x capacity factor x levelised cost). T1.2 read 0.86x with the first rule (weekly 43805030250).
4. **An engine gap, fixed (rule 8: M33's lane has merged):** lithography opens "at stage 5", which is a holding company's (31.2), but the gate read the operating company, which keeps the chip and the fab and stays at stage 4, so no player could ever start it. `ep.group_stage` reads the stage through the group, in the programme's gate and in lithography research's (`actions/research.py`). M33's own targets are unchanged (its harness sets the lab directly).
5. **T1's ARR** is §43's (12 x the group's last month); the trailing year's ratio prints beside it because cloud revenue swings month to month.
6. **T4's measure** (the brief says "reaches its 2032 capacity at least 1 year earlier ... in congested regions"): for each seed, the month all the data centres a cloud company ordered by December 2032 are live (2040 if not by 2039), cloud_steady's month less power_hyperscaler's, median of the 10 paired gaps. Both serve North America, the data's most congested region (M32's `CONGESTED`); the data centres in a region whose queue median passed 24 months when ordered print beside it.
7. **T3's fines** are the player's 6970 account (settlements and fines, refunds net) to December 2039; "a duty or fine by 2034" reads duties in force or 6970 by December 2034.
8. **Regulators' strictness after 2025** (follow-up; `tst/sim/regulation/strictness.py`, formulas 51.1): a seeded yearly path of uniform draws only (no libm call: M35a's determinism), an election swing every 4 years from a seeded first year, moved by the region's top influence, within [0.3, 1.3]. Stream `regulation` key family 3. Hidden: never in the API (the Regulation screen shows no strictness, 48.6).
9. **Mergers review** (the brief's "§28.7" is formulas 28.4's antitrust review; 28.7 is pitches): from `regulation.start` the block probability x (the region's strictest regulator now / its 2025 value) x 1.5 while one of its regulators investigates the acquirer.
10. **Rival foundries' EUV capacity** (follow-up): from 2026 an EUV-only foundry's yearly seeded growth has its EUV share (0.5, A) scaled by the share of its expected tools ASML delivered (`fabs.market.euv_gated`), pro rata through the year; memoised per month.
11. **Google Play's regulated rates** (follow-up): EU from March 2024 at 27% (DMA, 3 points off), US from October 2025 at 0% (Epic v. Google; no fee collected by December 2025), with sources. `tools/m35b_play_diff.py` on seed 1: 116 entries differ, all platform-fee entries, only in 2025 ($9.06M less in 5150 fees), every company's 2010-2025 net revenue 0.0000% from without the rows (the EU row moves no entry in a do-nothing game: no seller's European Android revenue is on that path in 2024). **M28's fingerprint re-recorded for `books` only**: on all 10 seeds the only series-year that differed was books 2025; every other series and year kept main's hash (the rewrite asserted it).
12. **M31's `test_an_app_pays_store_fees`** assumed every store path pays at least 15%; Google Play's US 0% path (data, not a rule change) makes that false for the regulated share. Its floor now allows `alternative_share` of sales at 0% (the test was wrong for the new data, not weakened to pass: the upper bound and the entries' sum are unchanged).
13. **The scripted phone that books no hardware sales** (M34's note): not reproduced on main. M34's own `owner()` phone books "Revenue: Own Phone" ($386M in January 2026 on seed 1), cost of goods and tariffs every month (`ProductMonth.new` 858k units). The app stays in M34's script: it is the target's premise, and changing it would move §48.5's readings.
14. **§48.5 target 4 regressed with the strictness path** (rule 2, my own keys): main 44% ($2.12B to $1.20B, run in a clean worktree of main d1ffc39), branch -26% ($1.51B to $1.90B). Tuned `regulation.strictness`: sd 0.03 -> 0.02, swing +/-0.10 -> +/-0.05, influence_cut 0.15 -> 0.30: 33% ($2.29B to $1.53B), the other §48.5 targets unchanged (10/10, 0/10, 0/10, 9/10).


15. **Rule 2 fixes to power_hyperscaler's siting, and one reverted.** (a) The screen's cheapest $/MWh alone (1.) put 250 MW of wind behind a 50 MW load: it now takes the plant type whose whole-load size costs least a year. (b) It quoted only the best-sited city and built nothing when that one's CU cost was not below spot: it now tries the next site. (c) With cheaper power ranking first, every data centre moved to the neighbour region (Latin America) from 2017, before power binds: its consumer app had 984M customers in 2039 against cloud_steady's 3.0B on seed 1 (T1.2 0.86x on seeds 1-10, 0.76x on 11-20, weekly 43830576778); it now prefers its home region among equal waits (6cd7833). (d) Ranking by grid reliability first (ef1cde0) left seeds 11-20 at 0.89x and dropped T4 to +0 on seeds 21-30 (weekly 43871833186), so it was reverted (031b0de: the scripts are 6cd7833's).
16. **`litho_bet`'s founder value read 0** once it formed its holding company: the founder holds the holding's shares. `Game.record_value` reads the founder's stake at the top of the group (balance harness only; no game rule). Before the fix T2 could never count a litho_bet win.
17. **The ten-year API run** (nightly) failed since M32 on `/power/siting`, `/power/quote/plant` and `/power/quote/ppa`, new required-query routes with no sample (main's last nightly ran before M32 merged). Samples added (rule 8: M32's lane has merged); passed locally (97 s) and in nightly 43871838922.
18. **Fixtures re-recorded for Google Play's US row (October 2025):** M30's state cache (all nine runs first differed at turn 189; `--update-state-cache`, 12 min) and M32's history fixture for `books` 2025 only (full_integrator and integrator on 10 seeds; every power cost unchanged, asserted by the rewrite).

## Results (the combined code: main 6d706d1 with M35a, branch 6cd7833 / 031b0de)

### T1-T4 (weekly shards on GitHub on 6cd7833: run 43852709862 for seeds 1-10 and 11-20)

| Target | Seeds 1-10 | 11-20 | 21-30 | Band |
| --- | --- | --- | --- | --- |
| T1.1 platform_owner / devices_regions | 0.96x | 0.98x | TBD | 0.9-1.4x |
| T1.2 power_hyperscaler / cloud_steady | 0.93x | 0.89x | TBD | 0.9-1.4x |
| T1.3 litho_bet / full_integrator | 1.08x | 0.99x | TBD | 0.9-1.4x |
| T1.4 compliant_platform / devices_regions (printed) | 0.94x | 0.94x | TBD | printed |
| T2 most wins by a v4 strategy | 1 of 10 (litho_bet) | 3 of 10 (litho_bet) | TBD | <= 4 |
| T3.1 platform_owner duty or fine by 2034 | 10 of 10 | 10 of 10 | TBD | >= 7 |
| T3.2 compliant_platform's fines below | 100% ($0 vs $1,647M) | 100% ($0 vs $1,098M) | TBD | >= 30% |
| T4 2032 capacity all live earlier | +36 months | +24 months | TBD | >= 12 |

### T5: each system's targets on the combined code (weekly 43830576778, 38447e4c)

- **§44.9 (M31):** 1 history (books only, net 0.00%), 2 tipping 0/10 and 10/10, 3 own store 9.4% of revenue, 4 removal -41% then 163%, 5 open 2.22x customers / 0.11x revenue, 6 software books 0 non-fee entries: all met.
- **§46.8 (M32):** 2 time to power 52 months grid / 20 behind the meter; 3 gas 34.4% below grid, IRR 8.3%; nuclear IRR -2.9% to 2.4%, overruns above 50% on 5 seeds; 4 the EU's cheapest plant moves from gas on 10/10; 5 outages 2.8% of starts, 0.0% behind the meter: met. Solar with storage's IRR -4.6% is carried as at M32 (its brief).
- **§47.5 (M33):** queue 18 / 9 months, banned buyers none, litho_2 by 2039 on 5/10, die cost 0.94-0.98 of ASML's, China's lag 9.1 years: all met.
- **§48.5 (M34):** 2 remedy 10/10, 3 structural orders 0/10 and 0/10, 4 settling and influence 33% ($2.29B to $1.53B), 5 rivals regulated 9/10: all met (4 after decision 14's tuning).
- **v3 (§43):** I1 +0.1 points (KNOWN MISS, M28), I2 0.99x, I3 0 of 10; S1, S2, F1, L1-L4 passed (weekly parts v3-shocks, v3-long); V1, V1-V4 (incl. V3.ai's known miss), M27b passed.
- **Turn time:** V6 on the 2039 full_integrator save 443 ms median, M30's month 434 ms (worst 656), on a x1.41 runner; plain V6 passed; `make check-timing` passed locally.

### T6: the known misses

- **I1 (M28):** +0.1 points at year 30 (band +3 to +10): still a known miss within its bound (-2.0). Owner M28 (closed): carried to M43 (v5 balance) as the roadmap's next balance pass; not closed here.
- **V3.ai (M28):** within its bound in weekly-v1to4 (passed); owner as above.
- **V5.cells / V5.cats (M28):** V5.cells 71% and 69% of cells (known, >= 75% wanted). V5.cats fails for research_heavy (fintech 2030s empty in 7 of 9 runs, one run ended before 2039) **identically on main** (weekly 43850649969 on 6d706d1, the same nine category-decades): rule 3, not M35b's; owner M28's known miss, for M43.
- **M28's target 2 (accepted at 12%):** not re-measured here (M28's tool, unchanged code paths); carried as accepted.
- **M30's 439 ms (now M35a's):** M35a measured 331-348 ms on a calibrated runner; this branch's weekly read 434-443 ms on a x1.4 runner, under the 500 ms guard.

## Follow-ups

- **T1.2's spread across seeds.** power_hyperscaler's ARR against cloud_steady is in band on seeds 1-10 and just under on 11-20 (see Results). Its ARR is the consumer app's: the cloud product earns little in every run, so a hyperscaler is mostly a software company with data centres. A cloud-first strategy (hosting as the main product) would measure power's effect more directly; a balance or design question for M43.
- **The economy-scale audit's recommendation (M35a)** is Reece's decision after his campaign; nothing here assumes it.
- **Regulators' strictness path** is hidden by design (48.6); a Regulation-screen line on the political climate (an election coming, a tougher regulator) would make it legible without showing the number.
- **Rival foundries' EUV gate** reads ASML's deliveries to each buyer; rivals' own lithography (China's EUV-class window, M33) still grows on its seeded path.
- **The lithography gate's group stage** also matters for any other stage-5 gate written against the operating company; worth an audit when M43 balances v5.
- **V5.cats and V5.cells (M28's known misses)** fail or sit near their bounds on main too (rule 3): owner M43.
- **I1 (M28's known miss)** at +0.1 points at year 30: integration's margin advantage is still about nil; owner M43.
- **M28's target 2 (accepted at 12%)** was not re-measured in M35b.
