# Balance targets (v1)

**Status: approved by Reece, 2026-10-30, with three changes** (success needs traction above the floor; founder value is the mean of turns 109–120; steady's standard bankruptcy band is 5–25%). Spec §16 asks for this file: target curves, a do-nothing strategy that fails, and no strategy winning more than 60% of seeds.

The balance runner (`make balance` or `tools/balance_runner.py`, nightly in CI; code in `backend/tst/balance/`) plays every strategy below on the same 10 seeds for 120 turns (10 years) and prints each target with its measured value. Targets T1–T3 are pass/fail for the nightly run; T4–T8 are bands, also checked. Anything outside a band is either tuned (only keys in `balance.yaml`) or brought back to Reece.

## Setup

| | |
| --- | --- |
| Seeds | 1–10 |
| Turns | 120 (January 2010 to December 2019) |
| Scenario | `ex_big_tech_founders` ($400,000): the middle scenario, where both bootstrapping and raising are plausible |
| Difficulty | `standard`; T5 also plays `easy` and `hard` |
| Events | on, written by `MockLLMAdapter`; open events are answered with their first choice (as in M6) |
| Hiring | through the real actions (job post or recruiter plan, interviews, offers at the candidate's ask), so hiring friction and energy count |

## Strategies (spec §16; v1 only, D3a)

Research-heavy, acquirer and vertical-integrator need v2 and v3 systems and are not played.

| Strategy | Product | People | Money | Marketing |
| --- | --- | --- | --- | --- |
| **do-nothing** | none | founder alone | none raised | none |
| **bootstrap-frugal** | one B2B SaaS product, launched as soon as allowed | founder + 1 engineer; an account executive at launch; then one more hire each time cash covers 12 months of costs, to at most 15 (Reece, M7a B1) | never raises | 10% of last month's revenue |
| **steady** | one product, a second at $5M ARR | founder + 5 (the M3a earn-and-burn team); grows so that runway stays above 18 months | seed at launch or when runway falls below 12 months, whichever comes first (Reece, M7a B3); Series A when its gate allows; best term sheet; bridges when offered | $10,000 a month, then 20% of revenue |
| **blitzscale** | one product, a second at Series A | 15 staff by month 12, then hires while runway is above 12 months | every round as soon as allowed (seed, A, B, and from M10d C and D: product manager, 2026-11-02), largest amount offered; bridges when offered | 40% of revenue, at least $25,000 a month |

Every strategy answers critical events with the first choice, sets prices at the category's reference price, and never fires anyone.

## Outcome measure

**Founder value** in a month = the founder's ownership × V_base (formulas.md §14.3, investors' base value, no bias or noise) + nothing for cash. A bankrupt company or a removed founder scores 0 from then on. Success and wins use the **mean founder value over turns 109–120** (Reece: the squared six-month growth in the multiple makes a single month noisy).

- A strategy **succeeds** on a seed when the game is still active at turn 120, the mean founder value over turns 109–120 is at least **3×** its turn-0 value, and **V_traction > V_floor at turn 120** (Reece: so the headcount floor alone can't make a success; a live product with 23 staff reaches 3× the start value with no revenue).
- A strategy **wins** a seed when it has the highest mean founder value over turns 109–120 on that seed (ties: nobody wins).

## Pass/fail targets

| # | Target | Why |
| --- | --- | --- |
| T1 | do-nothing fails on **10/10** seeds | spec §16. With no product it keeps the $2M floor value at best, so it never reaches 3× |
| T2 | no strategy wins more than **6/10** seeds | spec §16 |
| T3 | bootstrap-frugal, steady and blitzscale each succeed on at least **3/10** seeds | every v1 strategy should be a real option |

### Known misses (from 2026-11-05)

A known miss is a target that misses on `main` with a recorded owner and a bound, kept in one list, `backend/tst/balance/known_misses.py`. Both `tools/balance_runner.py` (`make balance`, CI's nightly "balance" job) and the nightly pytest balance tests (`test_known_misses`, its xfail) read it.
- **Within its bound,** the runner prints `MISS … KNOWN MISS (<owner>)` and doesn't fail the job, and pytest xfails it.
- **Beyond its bound,** or for any target not listed, a miss still fails.
- **If the target passes,** it prints `ok` (remove the entry when its owner fixes it).

| Target | Owner | Fails only if ("worse than") | Why |
| --- | --- | --- | --- |
| V3.ai (30.7 V3's AI arm, +3 to +10 points) | M23 | integrator_ai more than 2 points below ai_regions | +0.9 pts at year 10: an AI-models company is about $7M ARR in 2020 and its own GPU data centres save little (product manager, 2026-11-07) |
| V5.cells (≥ 75% of run × startup category × decade-after-2020 cells with a rival launch) | M23 | more than 40% of cells empty | 77% (steady_regions), 68% (research_heavy): about 11 startups a decade over 6 categories is about 1.8 launches per category-decade, e^-1.8 ≈ 17–20% empty by chance, and long-lived startups hold the 8 places (found_rate 0.05 with 12 places fell to 63%) |
| V5.cats (no category misses a decade in more than 2 of 10 runs) | M23 | a category-decade empty in more than 7 of 10 runs | as V5.cells |

T2 (closed by M15a: wins counted over the founder-played strategies, as V1) and M10.T3 (closed: covenants re-measured as V7 with `debt.venture.covenant_burn_months` 2) left the list.


## Target curves (bands)

| # | Measure | Band |
| --- | --- | --- |
| T4a | Median months to a closed seed (steady; blitzscale) | steady 1–24 (Reece, M7a C1: 5 hires on $400k leave under 12 months of runway, so it raises at once); blitzscale 1–12 (Reece, M7a B2: its seed has no gate, so it raises at once) |
| T4b | Median months to a closed Series A (steady; blitzscale) | steady 24–60; blitzscale 12–36 |
| T4c | Median months to a closed Series B (blitzscale) | 30–72, reached on at least 4/10 seeds |
| T4d | Median months to IPO | not in v1 (IPO is v2); printed as "–" |
| T5 | Bankruptcy rate by 120 turns | steady: easy ≤ 10%, standard 0–25%, hard 0–70% (Reece, M7a C2: a cautious strategy that keeps 18 months of runway and retries its seed should survive); blitzscale standard 0–40% (Reece, M7a B3: reached by round gates and investor appetite, so it fails when traction lags, not by its script; 10–40% until M10d, re-banded by the product manager on 2026-11-02 once blitzscale raises Series C and D); bootstrap-frugal standard 0–50% (Reece, M7a C3: today's launch gates kept; bootstrappers win whenever they survive; 20–50% until M12a, re-banded by the product manager on 2026-11-02: 7% on seeds 11–40 on both main and the combined code; M15 decides whether bootstrapping should carry more risk) |
| T6 | Employee tenure (player staff, all strategies pooled) | median tenure of leavers 18–48 months; 10–25% of staff leave each year; at most 25% of hires leave in their first 12 months |
| T7 | Rival survival at turn 120 (do-nothing runs, so the player doesn't distort it) | incumbents: at least 10 of 12 in business on average; rival startups: 20–65% of those founded are alive 5 years later (20–60% until M10d; re-banded by the product manager on 2026-11-02: most startups are founded abroad, where markets are less served) |
| T8 | ARR at turn 120 (median per strategy) | printed only: bootstrap-frugal, steady and blitzscale should rank in that order on the median |

## Events (carried from M6, plus the two known issues)

E1 and E2 run on the M3a earn-and-burn script, so they are checked by `backend/tests/integration/test_event_balance.py` (nightly), not by the runner; the runner prints E3.

| # | Measure | Band |
| --- | --- | --- |
| E1 | §16.10 on the earn-and-burn script, 10 seeds × 120 turns | 1.0–1.6 events a month; at most one critical event in any 6 months; event cash within ±5% of revenue; at least 40 distinct templates |
| E2 | Events' effect on average morale | within ±3 points on **every** seed (seed 4 was +3.22 at M6) |
| E3 | Solo founder with no product (do-nothing, and bootstrap-frugal before launch), first 24 months | at least 10 distinct templates per run on average; finance and quiet-month templates at most 50% of events; no template more than 3 times in 24 months |

## Speed

| # | Measure | Band |
| --- | --- | --- |
| S1 | Persisted turn 120 of the product-perf save (25 staff, 3 products, all rivals), local | under 300 ms (131 ms after M7a sub-task 0) |
| S2 | The full balance run (4 strategies × 10 seeds × 120 turns, plus T5's 20 difficulty runs) | under 65 worker-minutes on CI from M13b (M12r measured 50-52 on main and its branch alike: the runners got slower; CI's need plus 25%, product manager 2026-11-03), under 43 from M10d (CI's measured need plus 25%; `make balance` run alone gates it), under 20 for v1 (first measured run, M7a sub-task 2: 17.5 worker-minutes and 4m43s wall clock locally with 4 jobs; companies of 130+ staff cost about 0.5 s a turn) |

## Recorded results

M7a sub-task 4, after Reece's B1–B4 and C1–C3 (2026-10-30), `make balance` (60 runs × 120 turns, 130 s wall clock with 4 jobs, 8.4 worker-minutes); every target passes:

| Target | Measured | Result |
| --- | --- | --- |
| T1 do-nothing fails | 10/10 | pass |
| T2 wins | bootstrap-frugal 6, steady 4, blitzscale 0 | pass |
| T3 succeed | bootstrap-frugal 6/10, steady 10/10, blitzscale 7/10 | pass |
| T4a seed (median month) | steady 4, blitzscale 1 | pass (bands 1–24 and 1–12) |
| T4b Series A | steady 29.5, blitzscale 19.5 | pass |
| T4c Series B | blitzscale 36 on 7/10 | pass |
| T5 bankrupt | steady easy 0%, standard 0%, hard 0%; blitzscale 30%; bootstrap-frugal 40% | pass |
| T6 tenure | leavers' median 25 months; 11% leave a year; 9% of hires leave in their first year | pass |
| T7 rivals | incumbents 12/12; startups alive after 5 years 54% | pass |
| T8 median ARR | bootstrap-frugal $18.4M, steady $44.2M, blitzscale $57.4M | printed |
| E1, E2 (`test_event_balance`) | 1.35 events a month; cash −1.35% of revenue; morale worst +2.90 | pass |
| E3 | solo founder 15.0 distinct, 18% dull, ≤ 2 repeats; bootstrap before launch 8% dull | pass |
| S2 | 8.4 worker-minutes locally | pass |

Keys changed: `resign.base_bp` 50 → 80; `rivals.startup.raise_chance` 0.6 → 0.25, `raise_months` 18 → 12, `found_rate` 0.02 → 0.03. Findings carried forward (M7a brief, Follow-ups): hard difficulty does not threaten a cautious funded strategy; funded companies plateau at about $45–57M ARR (v1 has one market per product line); a 2-person team launches at about month 21.

### M8 (2026-10-31)

The scripts changed: the second product is now staffed (an M7a bug: hires were never moved to the second team), and from stage 3 the scripts appoint executives (formulas.md 18.9, "Scripts"). `rivals.startup.raise_chance` 0.25 → 0.18; T7 counts the 15.4 startups only.

| Target | Measured | Result |
| --- | --- | --- |
| T1 | 10/10 | pass |
| T2 wins | do-nothing 0, bootstrap-frugal 0, steady 10, blitzscale 0 | **fail** (follow-up for M15) |
| T3 succeed | bootstrap-frugal 7/10, steady 10/10, blitzscale 3/10 | pass |
| T4 | seed 4 and 1; Series A 28 and 18.5; Series B 36.5 on 8/10 | pass |
| T5 bankrupt | steady 0/0/0%; blitzscale 20%; bootstrap-frugal 30% | pass |
| T6 | leavers' median 21 months; 12% a year; 11% in the first year | pass |
| T7 | incumbents 17/17; startups alive after 5 years 58% of 91 | pass |
| T8 median ARR | bootstrap-frugal $12.1M, steady $65.9M, blitzscale $64.0M | printed |
| E3, S2 | as before; 13.0 worker-minutes | pass |
| M8 targets 2–6 | 1.512; 1.088; 0.97 and 359×; 1.472 (3 seeds); all entrants on time | pass (see the M8 brief) |

Blitzscale's founder is removed on 5 seeds around months 92–108: with its second product staffed and its seats filled it reaches about $64M ARR, but its board confidence decays under the burn. Reece approved merging M8 with this recorded (2026-10-31).

### M8r (2026-10-31)

Codex review 1 finding 3: a poached executive now leaves their seat (before, they kept it and its effect from the rival's payroll). Appointees were exec level but still on their old pay, so rivals' offers at the exec market rate took them within months. Product manager's fix: an appointment sets a salary, by default the exec market rate (formulas.md 18.3). Measured on the commit before finding 3, after it, and with the salary:

| Target | Before | Finding 3 | With exec pay | Result |
| --- | --- | --- | --- | --- |
| T3 blitzscale succeeds | 3/10 | 1/10 | 2/10 | **fail**, xfail for M15 |
| M8 target 2 (seats, needs 1.15) | 1.512 | 0.880 | 1.097 | **fail**, xfail for M15 |
| An executive at the default salary stays 6 months (10 real stage-3 games) | — | — | 4/10 seeds | **fail**, xfail for M15: at ordinary morale (about 50), any employee reads "might go" against a market-rate offer |

Every other target is unchanged: T1, T3 for bootstrap-frugal (7/10) and steady (10/10), T4 to T8, E3, and S2 (12.0 worker-minutes run alone). T2 stays the recorded M7c miss.

### M10 (2026-11-01)

Consumer confidence now scales consumer and SMB adoption (formulas.md 20.1); the venture climate is unchanged through 2025.

| Target | Measured | Result |
| --- | --- | --- |
| T1 | 10/10 | pass |
| T2 wins | do-nothing 0, bootstrap-frugal 0, steady 10, blitzscale 0 | **fail**, the recorded M7c miss |
| T3 succeed | bootstrap-frugal 7/10, steady 10/10, blitzscale 4/10 | pass (blitzscale's recorded xfail now passes) |
| T4 | seed 4 and 1; Series A 29 and 19; Series B 37 on 8/10 | pass |
| T5 bankrupt | steady 0/0/0%; blitzscale 20%; bootstrap-frugal 30% | pass |
| T6 | leavers' median 21 months; 12% a year; 11% in the first year | pass |
| T7 | incumbents 17/17; startups alive after 5 years 58% of 91 | pass |
| T8 median ARR | bootstrap-frugal $13.6M, steady $68.6M, blitzscale $74.8M | printed |
| S2 | 12.4 worker-minutes run alone; 22.6 under the parallel suite (not a valid measurement) | pass |
| M8 target 3 (support, needs 1.08) | 1.069 (1.088 before M10): confidence lifts SMB adoption in both arms over 2016-2020 | **fail**, xfail for M15 (Reece, 2026-11-01) |
| 20.5 target 2 (debt saves dilution) | +5.2 founder points (median), bankruptcy +0 points | pass |
| 20.5 target 3 (covenants bite sometimes) | 90% of seeds breach (80% with a 2- or 1-month covenant): blitzscale with venture debt goes below zero cash before its next round on 8/10 seeds | **fail**, xfail for M15 (Reece, 2026-11-01) |
| 20.5 target 4 (the future varies) | 41/50 seeds with a downturn in 2026-2039; 2030 climate sd 0.171 | pass |
| 20.5 target 5 (later rounds happen) | blitzscale reaches a Series C on 8/10 seeds | pass |

### M9 (2026-11-01, on the combined M9 and M10 code)

| Guard | Before M9 (main, M10 merged) | After M9 (combined) | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy | steady 10 | steady 8, bootstrap-frugal 2 | recorded xfail (stays) |
| T3 succeeds: bootstrap-frugal / steady / blitzscale | 7 / 10 / 4 of 10 | 8 / 10 / 5 of 10 | pass (blitzscale's xfail passes) |
| T4a-c seed, Series A, Series B | 4 and 1; 29 and 19; 37 on 8/10 | 4 and 1; 28.5 and 18; 36 on 9/10 | pass |
| T5 bankruptcy: steady easy/std/hard; blitzscale; bootstrap-frugal | 0/0/0%; 20%; 30% | 0/0/0%; 10%; 20% | pass |
| T6 tenure; leaving a year; first-year leavers | 21 months; 12%; 11% | 23 months; 11%; 10% | pass |
| T7 incumbents in business | 17/17 | 23/23 | pass |
| **T7 rival startups alive 5 years on (20-60%)** | 58% of 91 | **62% of 94** | **fail** |
| S2 worker-minutes, run alone | 12.4 | 18.8 | pass |
| M8 target 2 (seats) | 1.097 | 1.005 | recorded xfail (stays) |
| M8 target 3 (support) | 1.069 | 1.113 | recorded xfail, now passes |
| M8 target 5 (blitz Fintech) | pass | 1.317 | pass |
| **§20.5 target 2 (debt saves dilution, needs +5)** | +5.2 points | **+4.8 points** (bankruptcy +0) | **fail** |
| §20.5 target 3 | 90% | 90% | recorded xfail (stays) |
| §20.5 target 4; target 5 | 41/50, sd 0.171; 8/10 | 41/50, sd 0.171; 9/10 | pass |
| Ten-year run through the API (v1 acceptance) | pass | pass | pass |
| Funding diagnostics (a), (b), (c) | pass | pass | pass |
| M5 poaching felt, not crushing | pass | pass | pass |
| **M5 living market: share ratios; launches per category (needs 1.0)** | 0.56-1.65; 1.0 | 0.57-1.65; **0.925** | **fail** (ratios pass) |
| **Potential spotting gap (needs 3.0 PA points)** | 3.04 | **2.83** | **fail** |
| Executive at the default salary stays | xfail | xfail | recorded xfail (stays) |
| §19.8 target 2 (expansion, needs 1.4) | - | 7.014 (last-month ARR 3.44x) | pass |
| §19.8 target 3 | - | $119,331 against $304,020, 60.7% less; split x0.95 | pass |
| §19.8 target 4 (0.8-1.2) | - | 0.850 | pass |
| §19.8 target 5 | - | 10/10 seeds | pass |


M9 keys tuned to get here: `geo.pay_level` 0.876 (Reece); `geo.region_entry.unserved` 0.4 → 0.8 and `.span` 0.4 → 0.2 (rivals entered the served home market and squeezed v1 incumbents: Salesforce's SMB share fell to 0.47 of its start); `geo.region_entry.cooldown_turns` 12; and a product that sells only abroad comes home through `enter_region` only, not v1's per-segment `enter_segment`. Four guards that passed on main still miss after tuning M9 keys (bold above); Reece recorded them for M15 and approved the merge.

**Recorded misses for M15** (`xfail(strict=False)`, Reece 2026-11-01; main's value before M9, after M9, cause):

| Guard | Test | Before M9 | After M9 | Cause |
| --- | --- | --- | --- | --- |
| T7 rival startups alive 5 years on (20-60%) | `test_balance_t7_startups` | 58% of 91 | 62% of 94 | most startups are founded abroad, where they face less competition |
| §20.5 target 2, debt saves dilution (+5 points) | `test_2_debt_saves_dilution` (its bankruptcy half, `test_2_debt_bankruptcy_risk`, stays a hard check) | +5.2 | +4.8 | incumbents' sales abroad fund bigger rival teams |
| M5 living market, startup launches per v1 category (1.0) | `test_1_living_market_launches` (share ratios, `test_1_living_market`, stay a hard check) | 1.0 | 0.925 | most startups are founded abroad, so fewer launch into the v1 home markets |
| Potential spotting gap (3.0 PA points) | `test_judgment_spots_potential` | 3.04 | 2.83 | the city talent bonus raises candidates' CA and so their PA (hires' mean 141 against 133) |

**Top priority for the next balance pass:** expansion is too strong (7.0x vs 1.4x target; home-only blitzscale fails every seed).

### M10b (2026-11-02)

The nightly guards run alone after M10b's feel fixes (event modifiers, crises, numbers in events, self-serve abroad and marketing by region). No balance key outside `events.*` was tuned.

| Guard | Before M10b | After M10b | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy | steady 8, bootstrap-frugal 2 | steady 7, bootstrap-frugal 3 | recorded xfail (stays) |
| T3 succeeds: bootstrap-frugal / steady / blitzscale | 8 / 10 / 5 | 8 / 10 / 5 | pass |
| T4a-c | 4 and 1; 28.5 and 18; 36 on 9/10 | 4 and 1; 27.5 and 18; 36 on 10/10 | pass |
| **T5 blitzscale (standard) bankrupt by the end (10-40%)** | 10% | **0%** | **moved: reported for M10d** (`xfail(strict=False)`, awaiting the product manager) |
| T5 others | 0/0/0%; 20% | 0/0/0%; 20% | pass |
| T6 | 23 months; 11%; 10% | 23 months; 11%; 10% | pass |
| T7 incumbents; startups alive | 23/23; 62% of 94 | 23/23; 62% of 94 | pass; recorded xfail (stays) |
| S2 worker-minutes, run alone | 16.9 | 17.8 | pass |
| §20.5 target 2 (debt saves dilution) | +4.8 (xfail) | passes | recorded xfail, now passes |
| M8 support; T3 blitzscale | xpass | xpass | recorded xfails, still pass |
| Other recorded xfails (M8 seats, covenants, executive retention, M5 launches, potential) | xfail | xfail | unchanged |
| E1, E2 event balance | 1.35 a month; cash −1.35%; morale worst +2.90 | 1.37 a month; cash −1.68% (worst −2.69%); morale worst +1.38 | pass |
| §23.7 target 1: critical events per 18 months with 20+ staff (steady, 10 seeds) | - | 1.08; shortest gap 6 months | pass |
| §23.7 target 2: every template choice has an effect or says do nothing; 28 benefit templates carry a modifier | - | data tests | pass |
| Ten-year run through the API | pass | pass | pass |

### M10c (2026-11-02)

The §24.5 targets (formulas.md §24.5), printed by `tools/m10c_targets.py` and checked nightly by `tests/balance/test_m10c_balance.py`. From each seed's steady game at its first month of stage 3 (M8's fork), five senior seat holders (CTO, CRO, CMO, COO, CFO) are added and appointed, then 36 months in three arms: `steady` (score 15, no authority, the steady script), `delegated` (score 15, every seat given authority at its defaults; the founder only approves proposals and refills a seat that falls vacant, as the steady script does) and `delegated_8` (the same at score 8). 10 seeds, all reach stage 3 (turns 78-89).

| Target | Value | Result |
| --- | --- | --- |
| 1. Delegated within 15% of steady (median ARR) | 0.92; no live product below its maintenance line in any month | pass |
| 2. Score 15 against score 8 (median ARR) | 1.29 | pass |
| 3. No runaway hiring: caps; support coverage within 0.1 of the target | 0 runs over a builder or seller cap; mean monthly shortfall at most 0.009 (worst single month 0.27, seed 8: two support people left in one month and the COO's plan filled in two) | pass |
| 4. Founder energy unspent on average | 94% | pass |

One balance default was set: the CRO's default seller cap `exec_authority.defaults.cro.headcount_cap` is 20 (10 held delegated ARR at 0.83 of steady; every delegated run sat at the cap). No other balance key changed; golden snapshots are unchanged (no script gives authority).

### M10d balance checkpoint (2026-11-02)

One pass over v1 and M8-M10c (product manager's decisions of 2026-11-02 in the M10d brief). Every target, before (`m10c-done`) and after; 10 seeds unless stated. **No xfail remains in the suite.**

| Target | Before | After | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy (each <= 6) | steady 7, frugal 3 | steady 6, frugal 4 | pass (xfail removed) |
| T3 succeeds: frugal / steady / blitzscale | 8 / 10 / 5 | 8 / 10 / 10 | pass (xfail removed) |
| T4a-c | 4 and 1; 27.5 and 18; 36 on 10/10 | 4 and 1; 27.5 and 18; 36 on 10/10 | pass |
| T5 steady easy / standard / hard; frugal | 0 / 0 / 0%; 20% | 0 / 0 / 0%; 20% | pass |
| **T5 blitzscale (standard) bankrupt** | 0% (band 10-40%) | 0% (**band 0-40%**) | **re-banded** (product manager, 2026-11-02): with Series C and D raised as soon as allowed, blitzscale's failure mode is board removal or slow growth, not bankruptcy; it ends every seed with $1.5-2.9B of cash (see the M15 follow-up on late-round sizing) |
| T6 tenure; leaving a year; first-year leavers | 23; 11%; 10% | 22; 12%; 11% | pass |
| T7 incumbents | 23/23 | 23/23 | pass |
| **T7 startups alive 5 years** | 62% of 94 (band 20-60%) | 61% of 98 (**band 20-65%**) | **re-banded** (product manager, 2026-11-02): most startups are founded abroad, where markets are less served (M9) |
| E3 template variety | pass | pass | pass |
| **S2 balance run, worker-minutes on CI** | 28.2 (< 20) | 18.0-34.2 across four CI runs (**< 43**) | pass; **S2 for v2** is CI's need (34.2, its highest reading) plus 25%. `make balance` gates it alone (CI's nightly "balance" job); inside the parallel nightly it is printed only |
| Median employee morale, steady / blitzscale | 56.5 / 53.7 | 62.3 / 60.2 | pass (58-68) |
| Executive retention (score-14 CTO, 6 months) | 7/10 (xfail) | 8/10 | pass (>= 8; xfail removed) |
| 15.7 target 4, poaching approaches a year; accepted | 1-4; in 20-60% | 4.00; 14% | pass (**acceptance band 10-40%**, re-banded by the product manager: happier staff refuse more offers) |
| 15.7 target 6 (new), staff lost to rivals a year, 30+ staff: steady / blitzscale | 0.14 / 0.36 | 0.58 / 1.05 | pass (0.5-1.5) |
| M5 launches per v1 category | 0.925 (xfail) | 1.02 | pass (xfail removed) |
| Potential spotting gap (PA points) | 2.83 (xfail) | 2.83 | pass at the approved **re-band >= 2.8** (the city talent bonus raises candidates' CA and so their PA, M9) |
| 18.9 seats | 1.097 (xfail) | 1.370 | pass (xfail removed) |
| 18.9 support; blitz | 1.069 (xfail); pass | 1.101; 1.263 | pass (xfail removed) |
| E1, E2 event balance | 1.37 a month; cash −1.68%; morale worst +1.38 | 1.37 a month; cash −1.36% (worst −2.62%); morale worst +1.54 | pass |
| 19.8 target 2 expansion | 6.93x (home alive 5/10) | 2.18x (all alive) | pass (1.4-2.5x) |
| 20.5 target 2 debt saves dilution | +4.8 (xfail) | +6.9 | pass (xfail removed) |
| 20.5 target 3 covenants breach | 90% (xfail) | 60% | pass (20-60%; xfail removed) |
| 20.5 targets 4, 5 | pass | 41/50, sd 0.171; 10/10 reach a C | pass |
| 23.7 target 1 critical events per 18 months, 20+ staff | 1.08 | 1.19 | pass |
| 24.5 targets 1-4 | 0.92; 1.29; 0 over caps, 0.009; 94% | 0.94; 1.33; 0 over caps, 0.012; 94% | pass |
| Founder energy, hands-on (brief sub-task 5) | - | removed | **a manual check** in Reece's next playtest (product manager, 2026-11-02); the delegated target is 24.5 target 4 |

Strategy change (product manager, 2026-11-02): blitzscale raises every round as soon as allowed, now including Series C ($80M) and D ($200M), largest amount offered.

Keys and data tuned: `morale.target_base` 50 to 56; `resign.morale_floor` 40 to 50; `finance.multiple_base` 4 to 2.5 and `multiple_per_growth` 4 to 5.5; `rivals.need.poach_gain` 0.007 (unchanged after trials); `rivals.poach.leave_penalty` -0.5 to -0.3 and the new `seat_holder_weight` 0.4; `geo.region_entry.unserved` 0.8 to 0.6 and `cooldown_turns` 12 to 6; `markets.localize_cents` $40,000 to $80,000 and `localize_months` 3 to 6; Europe and East Asia sizes 0.80 and 0.70 to 0.55 and 0.45 (`categories.yaml`); `debt.venture.max_of_round_bp` 3000 to 5000; `events.crisis.breach_chance` 0.004 to 0.008, `outage_chance` 0.003 to 0.006, `key_exit_top_fraction` 0.10 to 0.20. One formula change, approved: a rival's poach target is drawn by CA (§15.6).

### M11 R&D tree and era milestones (2026-11-02, lane A)

`make balance` on the merged-first M11 code against main at `m10d-done` (M10d table above); 10 seeds. The full nightly suite (27 tests: every v1, M8, M9, M10, M10b-d target and M11's) passes; **no xfail added**.

| Target | Before (m10d-done) | After (M11) | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy (each <= 6) | steady 6, frugal 4 | steady 6, frugal 4 | pass (at 21.6's `era_bonus` 0.3 it was steady 7: tuned to 0.15) |
| T3 succeeds: frugal / steady / blitzscale | 8 / 10 / 10 | 8 / 10 / 10 | pass |
| T4a-c | 4 and 1; 27.5 and 18; 36 on 10/10 | 4 and 1; 27.5 and 18; 36 on 10/10 | pass |
| T5 steady easy / standard / hard; blitzscale; frugal | 0 / 0 / 0%; 0%; 20% | 0 / 0 / 0%; 0%; 20% | pass |
| T6 tenure; leaving a year; first-year leavers | 22; 12%; 11% | 21; 12%; 11% | pass |
| T7 incumbents; startups alive 5 years | 23/23; 61% | 23/23; 60% of 99 | pass |
| T8 median ARR: frugal / steady / blitzscale | printed | $23.8M / $75.4M / $90.9M | printed |
| E3, S2 | pass | pass; 15.3 worker-minutes locally | pass |
| 21.8 target 1: AI demand January 2024; others January 2020 | 359x | 350x; 0.944-1.000 of before | pass |
| 21.8 target 2: research / steady median ARR net; quality | - | 1.11 (gross 1.13); +18.7 | pass |
| 21.8 target 3: AI lab before 2017; rivals early in do-nothing | - | 10/10; 0% | pass |
| 21.8 target 4: a lead of 30 after 46 months | - | 14.95 | pass |
| 21.8 target 5: licence / research for 15 points | - | 0.67 | pass |

Tuned (`rnd.*` only; the M11 brief's Decisions): `rival.era_bonus` 0.15, `rival.need_span` 30, `rate` 0.4, `cap_per_point` 0.010, `feature_per_point` 0.005, `license.price_per_point_cents` $24,000. Golden snapshots unchanged.

### M12a Cloud, data centres and supply shocks (2026-11-03, lane B, merged after M11)

The full nightly suite on the combined M11 + M12a code (golden snapshots regenerated once). M12a adds four cloud incumbents and two entrants, and amends ADR-0013 so rivals' streams are keyed by stable identity (appending a company reseeds no one outside its category); that change reseeds every game once against main. Every guard passes except three, measured on 10 seeds and, to separate seed luck from an M12a effect, on seeds 11–40 on both the combined code and main (with M11). T2's cap scales to 18/30 on 30 seeds.

| Guard | Band before | Combined, seeds 1–10 | Combined, seeds 11–40 | main, seeds 1–10 | main, seeds 11–40 | Ruling (product manager, 2026-11-02) |
| --- | --- | --- | --- | --- | --- | --- |
| T2 wins per strategy | each ≤ 6/10 (18/30) | steady 8, frugal 2 | steady 22, frugal 8 | steady 6, frugal 4 | steady 21, frugal 9 | xfail(strict=False): "steady wins 21–22/30 on main and combined; M15's v2 strategies should split wins" (the one permitted exception to no new xfails) |
| T5 bootstrap-frugal (standard) bankrupt | 20–50% | 10% | 7% | 20% | 7% | re-banded to 0–50%; M15 decides whether bootstrapping should carry more risk |
| M5 living market: seeds with a share breach | 0 | 1 | 0/30 | 0 | 0/30 | seed variance: at most 1 of 10 |

Launches per v1 category (M5 living market, ≥ 1.0): combined 1.0 (1–10) and 1.17 (11–40); main 1.08 and 1.12.

M12a's own §22.7 targets (`tools/m12a_targets.py`, nightly): T2 0.62 at 80% use and 1.23 at 40% (general data centre built January 2016); T3 10/10; T4 server +30%, GPU +60%, AI margin gap +15.7 points at 0.45× reference price (+7.0 at reference) with the GPU table tuned to $20,000 capex and $200 power, a GPU data centre at 40% use costing at least 1.22× spot in every build month; T5 8/10; T6 1.05 and 0.17 outages a year.


### M13 IPO, public company, and Chair and CEO (2026-11-03, lane B, merges before M12b)

The full nightly suite on the M13 branch (main at `m12a-done` plus M13): 29 passed and 1 xfailed, the existing T2 xfail (product manager, M12a); **no xfail added**. `make balance` (10 seeds, 120 turns) gives the same table on `main` and on M13. Steady and blitzscale now hire banks when eligible, but no 120-turn guard moved: blitzscale's earliest listings fall in months 108–121.

| Target | main | M13 | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy (each ≤ 6) | steady 8, frugal 2 | steady 8, frugal 2 | xfail as before (M12a ruling) |
| T3 succeeds: frugal / steady / blitzscale | 9 / 10 / 9 | 9 / 10 / 9 | pass |
| T4a-c | 4 and 1; 27.5 and 17.5; 36 on 9/10 | same | pass |
| T5 steady easy / standard / hard; blitzscale; frugal | 0 / 0 / 0%; 10%; 10% | same | pass |
| T6 tenure; leaving a year; first-year leavers | 22; 12%; 11% | same | pass |
| T7 incumbents; startups alive 5 years | 27/27; 55% of 98 | same | pass |
| T8 median ARR: frugal / steady / blitzscale | $22.0M / $74.6M / $92.2M | same | printed |
| E3, S2 | pass; 26.4 worker-minutes | pass; 26.7 | pass |

M13's own §25.9 targets (`tools/m13_targets.py`, nightly), 10 seeds:

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| T2 IPOs by turn 180: steady / blitzscale | 6/10 (2020–2021) / 5/10 (2019–2020) | ≥ 4 each | pass |
| T2 median first-day return | +6.6% | 0–30% | pass |
| T3 guiding 10% above trend: quarters missed | 100% | ≥ 60% | pass |
| T3 median price after 3 years, above / at trend | 0.51 | ≤ 0.85 | pass |
| T4 reference listing P/S (growth 27%, margin +38%): 2012–2019 / 2020–2021 | 11.6× / 18.1× | 4–15 / 8–25 | pass |
| T4 Jan → Dec 2022 | 10.4× → 5.0× (−52%) | ≥ 30% fall | pass |
| T5 CEO (score 14, full authority) / steady script, median ARR over 36 months | 1.01 | 0.85–1.15 | pass |
| T5 the Chair's energy spent | 0% | ≤ 40% | pass |

Actual listings' P/S: steady 14.7–22.1× (2020–2021), blitzscale 5.5–7.2× (2019–2020, loss-making). Tuned (`public.*` and `ipo.*` only): `public.multiple` growth 25 → 18 and margin 15 → 5; `ipo.min_growth` 0.40 → 0.20. Golden snapshots unchanged.

### M12b Hardware, devices and fabless chips (2026-11-03, lane A, merged after M13)

The full nightly suite on the combined M13 + M12b code (`main` at `m13-done` plus M12b; CI nightly run 41689697846): every test shard passes; `make balance` fails only on T2, the existing xfail (product manager, M12a). **No xfail added**, no guard tuned and no M13 key touched. Golden snapshots unchanged. No guard other than the ruled T2 misses on seeds 1–10, so no 11–40 measurement was needed.

| Target | main (M13's record) | M13 + M12b | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy (each ≤ 6) | steady 8, frugal 2 | steady 8, frugal 2 | xfail as before (M12a ruling) |
| T3 succeeds: frugal / steady / blitzscale | 9 / 10 / 9 | 9 / 10 / 9 | pass |
| T4a-c | 4 and 1; 27.5 and 17.5; 36 on 9/10 | same | pass |
| T5 steady easy / standard / hard; blitzscale; frugal | 0 / 0 / 0%; 10%; 10% | same | pass |
| T6 tenure; leaving a year; first-year leavers | 22; 12%; 11% | same | pass |
| T7 incumbents; startups alive 5 years | 27/27; 55% of 98 | 39/39 (twelve hardware and chip incumbents added); 55% of 98 | pass |
| T8 median ARR: frugal / steady / blitzscale | $22.0M / $74.6M / $92.2M | same | printed |
| E3, S2 | pass; 26.4 worker-minutes | pass; 37.1 | pass (S2 < 43 on CI; the twelve rivals cost about 40% more run time) |

M12b's own §26.6 targets (`tools/m12b_targets.py`, nightly `tests/balance/test_m12b_balance.py`), 10 seeds, combined code:

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| T2 15-person devices company on contract, gross margin in year 3 (price 0.8 x reference) | 32.6% on 10/10 | 30–45% on ≥ 6/10 | pass |
| T3 plant (20,000 a month, Jan 2013, yield 0.92): cost per good unit / $13 fee | 0.69 at 75%, 0.66 at 80%; 1.35 at 30% | ≤ 0.70 at ≥ 75%; ≥ 1.30 at 30% | pass |
| T4a own mobile SoC: device margin points after 3 years | +8.5 on 10/10 | ≥ +8 | pass |
| T4b own AI accelerators: GPU capex per CU | −49% | ≥ 20% cut | pass |
| T5 no contract before the 2021 shortage: fewer units in 2021–2022 | 30% on 10/10 | 15–35% | pass |
| T6 NVIDIA share of hyperscaler AI-accelerator units in 2023 (do-nothing) | 100% on 10/10 | ≥ 50% on ≥ 7/10 | pass |

Notes: T2–T5 are scripted (demand above capacity; price, cost and allocation fix the outcome), so they barely vary by seed. T6's 100% is because AMD goes bankrupt around 2020 (feature pushes grow its builder pools in the fast hardware markets) and Cerebras and Groq sell almost nothing; listed as an M15 follow-up. Tuned (M12b's own data only): rivals' hardware cost of goods 40–45% of reference, the mobile SoC wafer $2,000, cost leaders' and AMD's cash cushion 60 months.

## M13b: executive ambition and visible eras (§27.5)

`tools/m13b_targets.py`, nightly `tests/balance/test_m13b_balance.py`, 10 seeds, measured 2026-11-05 on `m13b-ambition` after the product manager's two rulings of 2026-11-04 and the new-product calibration of 2026-11-05.

How the arms run:
- **Targets 1-4 and 7** fork each seed's steady game at stage 3 and appoint six senior seat holders.
- **Targets 1-4** give every seat authority, then play 36 months as on Holiday (auto-approve at the default 5% of cash).
- **Target 7's founder arm** (`steady_regions`) plays M10c's steady script with the same holders and no authority. It also launches its live product in the CRO's best region whenever the CRO's gates are met, at most once per 24 months.
- **Target 5** runs M11's 10-person AI lab from January 2014 with an AI product. The era arrives in month 52 or 53, and the run compares the window against no window in that same month.

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| 1 new product and new region launched | 8/10 seeds | ≥ 7/10 | pass |
| 2 median ARR at 36 months, pitches / pitches off | 1.68 | ≥ 1.10 | pass |
| 3 hit rate (central case), score 15 against score 8 | 86% against 40% (+46 points) | ≥ +10 points | pass |
| 4 pitches a year per company, median | 2.3 | ≤ 8 | pass |
| 5 AI customers at the window's end, window / no window | +38%, +39%, +43%, +36%, +80%, +32%, +30%, +56% (7 of 8 seeds in band) | +25–60% on ≥ 7 | pass |
| 5 information: early era / on schedule | +303%, +319%, +303%, +299%, +392%, +237%, +237%, +258% | none | information |
| 7 median ARR at 36 months, pitches / founder's steady + regions | 1.10 ($127M against $116M; the founder launched 2 regions on every seed) | ≤ 1.2 | pass |
| S2 | re-banded to < 65 worker-minutes on CI (product manager, 2026-11-03) | | band only |

Tuned keys:
- target 3: `pitch.region_capture` 1.7, `pitch.team_builders` 6, `pitch.team_ready_months` 3, `pitch.new_product_share` 0.04;
- target 5: `rnd.first_mover_cap` 5, `first_mover_brand` 6, `first_mover_appeal` 1;
- target 7: `pitch.base` 0.15, `per_ambition` 0.01, `chance_clamp` [0.05, 0.9].

Hit rates by kind, score 15 against score 8:

| Kind | Score 15 | Score 8 |
| --- | --- | --- |
| region | 10/12 | 0/12 |
| office | 4/4 | 4/5 |
| research | 2/2 | 2/2 |
| campaign | 1/1 | 4/4 |
| new product | 0/2 | 0/2 |

The per-kind table above was measured before the share calibration.

New-product calibration (2026-11-05). One pass at the pre-tuning pitch rate, for sample size: CPOs at scores 15, 12 and 8 on seeds 1-10.
- At share 0.25: 1/8, 0/7 and 0/6 hits, with the score-12 median of measured / central at 0.15.
- At **0.04** (shipped): 4/8 (50%), 2/7 and 2/6 (33%), with the score-12 median at 0.92.
- Score 8 is one hit over its ≤ 30% aim; that's an M15 follow-up.

Target 7 sweep (`pitch.base` / `per_ambition`): 0.45/0.04 ×1.54; 0.35/0.03 ×1.33; 0.25/0.02 ×1.26; 0.2/0.015 (floor 0.1) ×1.28; 0.15/0.01 (floor 0.05) ×1.10. Target 1 held at 8-9/10 throughout.

### M14b People and press (2026-11-05, lane B, merges before M14)

The full nightly suite on `m14b-press` (main at `44b9fe3` plus M14b): 30 passed, 1 xfailed (T2, the recorded known miss), 2 failed. One failure, the ten-year API run, came from a Replace 500 since fixed in `777f425`; it passes on its own. The other guard fails against `main`, and no M14b key fixes it:

| Guard | Band | main, seeds 1–10 | M14b, seeds 1–10 | main, seeds 11–40 | M14b, seeds 11–40 | M14b keys tried |
| --- | --- | --- | --- | --- | --- | --- |
| M10 20.5 target 3: blitz_debt seeds that breach a covenant | 20–60% | 60% (6/10) | 70% (7/10; seed 6 flips) | 70% (21/30) | 70% (21/30) | `press.max_per_quarter` 1: 7/10; `press.measured_brand` 0, `feud.target_mult` 1.0, `press.cred_hiring` 0: 7/10 each; only with press moments off (`max_per_quarter` 0) does it return to 6/10 |

Reading: over 30 seeds `main` and M14b agree (70%), above the band on both. On the standard seeds `main` sits at the band's top and M14b's press events (they join the event flow and move later draws) flip seed 6. **Ruling (product manager, 2026-11-04):** a pre-existing miss, not M14b's. It is a known miss (`M10.T3` in `backend/tst/balance/known_misses.py`, owner M15) that fails only at 90% or more of seeds, M10's original measured value; `test_3_covenants_bite_sometimes` xfails while the rate is above 60% and under 90%. See Known misses above.

M14b's own §29.7 targets (`tools/m14b_targets.py`, nightly), 10 seeds, all pass: T2 three kept promises +10.7 brand at 24 months (+5 to +15), three broken −11.1 (−10 to −25) with sentiment 10% lower (5–15%); T3 1.2 press moments a year (≤ 6); T4 rivalry on 7/10 bold steady runs (5–9), that rival's moves against the player +26% (20–60%); T5 Replace fills 50% sooner (30–50%). Tuned (`press.*` and `feud.*` only): `feud.bold_mention` 10 → 20, `feud.decay` 2 → 1, `press.statement_chance` 0.6, `press.jab_base` 0.3; releases count as speaking moves.

## M14: mergers and acquisitions (§28.9)

`tools/m14_targets.py`, nightly `tests/balance/test_m14_balance.py`, 10 seeds, measured 2026-11-05 on `m14-mna` after the product manager's ruling on target 4.
- **Scripted deals (targets 2-4):** each seed's steady game at month 36, funded for the deals, bids for up to three private companies (the displayed midpoint, then the counter; two integrated, which must have at most `integration.max_staff` staff; one kept as a brand) and one listed company (stepping the premium by 5 points until its board agrees, integrated if within the limit), then plays 12 months.
- **Target 5:** "steady + regions" against "acquirer" (plus one startup a year when cash covers 18 months), 120 months.
- **Target 6:** a deal at 40% combined share in January 2021, reviewed on each seed.
- **Target 7:** do-nothing games, 120 months.

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| 1 nothing moves without deals | golden snapshots unchanged; earlier targets as before (re-run on the combined code at the lane merge) | as before | pass |
| 2 private deals, price / V_f (median) | 1.37 | 1.0-1.6 | pass |
| 2 listed friendly deals, premium (median) | 35% | 25-50% | pass |
| 3 key people lost within 12 months, integrated (median) | 25% | 10-30% | pass |
| 3 the same, kept brands | 0% | <= 10% | pass |
| 4 payroll cut by integration, every integrated deal (median) | 24% (scripted 23%, the acquirer's startups 52%) | 15-35% | pass |
| 5 acquirer / steady + regions, median ARR at year 10 | 1.05 | 1.0-1.4 | pass |
| 6 deals at 40% blocked after review, after 2020 | 4 of 10 seeds (40%) | 15-50% | pass |
| 7 incumbents' startup purchases a decade (median) | 2 | 1-4 | pass |

**Tuned keys:**
- `integration.flight_brand` 0.03 -> 0.007;
- `integration.flight_base` 0.02 -> 0.01;
- `mna.rival_rate` 0.04 -> 0.008, then 0.005 at the lane merge: M12a's living-market guard read 0.97 launches per category (39 of 40) at 0.008 and passes at 0.005 (1.00, as `main`). The guard is on its floor on `main`, so it is not monotonic in the rate (0.004 and 0.006 read 0.97). The table above is measured at 0.005.

**Target 4 (2026-11-05 ruling).**
- **The rule:** each acquired product keeps its revenue share of the target's staff, less a synergy by function (sellers and marketers 0.40 where the acquirer already sells in the category, else 0.15; builders 0.10; other key people 0.30).
- **The limit:** only targets with at most 250 staff integrate.
- **Tuning:** none needed; the synergy keys land it in band as given.
- **Startups:** their figure mostly reflects departures, since they have few or no pool staff.
- **Before the ruling:** the maintenance-line rule cut 87% (scripted) and 51% (startups).

### v2 final (M15a, 2026-11-08): the combined code with M15b, final keys

Nine strategies × 10 seeds × 120 months (V1–V4), 30 seeds (V1), steady_regions and research_heavy × 10 seeds to December 2039 (V5), a 2039 stage-4 save (V6).

| Target | Value | Band |
| --- | --- | --- |
| V1 most wins of one founder-played strategy | research_heavy 4, acquirer 3, steady_regions 2, integrator 1 | ≤ 5 of 10 |
| V1 strategies with a win over 30 seeds | 4 (research_heavy 16, steady_regions 6, acquirer 6, integrator 2) | ≥ 4 |
| V2 research_heavy / steady_regions median ARR; wins | 1.17×; 4 of 10 | 1.0–1.4×; ≤ 4 |
| V3 integrator − steady_regions operating margin; ARR | −0.2 pts (66.7% vs 66.8%); 1.03× | ≥ −1 pt (re-banded); 0.85–1.25× |
| V3.ai integrator_ai − ai_regions margin | +0.9 pts | +3 to +10: known miss (M23) |
| V4 ceo / steady_regions median ARR | 1.39× | ≤ 1.4× (re-banded) |
| V5 era arrivals 2026–2039 (median) | 7, 7 | ≥ 5 |
| V5 total demand growth in the 2030s | 48.4%, 48.2% a year | ≥ 4% |
| V5 2026 rivals alive in 2039 | 64%, 65% | ≥ 30% |
| V5 cells with a rival launch | 77%, 68% | ≥ 75%: research_heavy a known miss (M23) |
| V5 steady_regions at stage 4 by 2039 | 10/10 | ≥ 5 |
| V6 2039 stage-4 turn time (113 staff) | 454 ms median (blocks 492, 454, 451) | ≤ 1.0 s |
| V7 covenant breaches while cash is positive | 60% (seeds 1–10 and 11–40) | 20–60% |

Earlier milestones on the final keys: v1's runner (`make balance`, CI) passes every gate; T7 39/39 incumbents and 49% of startups alive at five years; M5's living market 1 breach, launches per category above 1; M8 §18.9 seats, support and blitz (bound 1.2 → 1.14: rival fintech startups now launch with features, main 1.224, M15a 1.145); M10 §20.5 targets 2–5; M11 §21.8 targets 2, 3 and 5 (target 2 1.14 net); M13 §25.9 targets 2–5; M13b §27.5 targets 1–7; M14 §28.9 and M14b §29.7 (CI nightly, final head). S2 re-set 65 → 140 worker-minutes (nine strategies; CI measured 112.2).

Tuned in M15a (before → after): `rnd.rate` 0.4 → 0.3 (V2); `debt.venture.covenant_burn_months` 3 → 2 (V7); `rivals.startup.start_feature_share` new, 0.3 (V5); `rivals.startup.small_staff` 3 and `small_months` 24 new (V5); `rank.brand` stays 0 (0.5 moved V1–V4 out of band even with the tie-break fixed; an M23 follow-up).

