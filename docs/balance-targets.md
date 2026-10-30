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
| **blitzscale** | one product, a second at Series A | 15 staff by month 12, then hires while runway is above 12 months | every round as soon as allowed (seed, A, B), largest amount offered; bridges when offered | 40% of revenue, at least $25,000 a month |

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

## Target curves (bands)

| # | Measure | Band |
| --- | --- | --- |
| T4a | Median months to a closed seed (steady; blitzscale) | steady 6–24; blitzscale 1–12 (Reece, M7a B2: its seed has no gate, so it raises at once) |
| T4b | Median months to a closed Series A (steady; blitzscale) | steady 24–60; blitzscale 12–36 |
| T4c | Median months to a closed Series B (blitzscale) | 30–72, reached on at least 4/10 seeds |
| T4d | Median months to IPO | not in v1 (IPO is v2); printed as "–" |
| T5 | Bankruptcy rate by 120 turns | steady: easy ≤ 10%, standard 5–25% (Reece: it keeps 18 months of runway), hard 30–70%; blitzscale standard 10–40% (Reece, M7a B3: reached by round gates and investor appetite, so it fails when traction lags, not by its script); bootstrap-frugal standard ≤ 30% |
| T6 | Employee tenure (player staff, all strategies pooled) | median tenure of leavers 18–48 months; 10–25% of staff leave each year; at most 25% of hires leave in their first 12 months |
| T7 | Rival survival at turn 120 (do-nothing runs, so the player doesn't distort it) | incumbents: at least 10 of 12 in business on average; rival startups: 20–60% of those founded are alive 5 years later |
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
| S2 | The full balance run (4 strategies × 10 seeds × 120 turns, plus T5's 20 difficulty runs) | under 20 worker-minutes on CI (first measured run, M7a sub-task 2: 17.5 worker-minutes and 4m43s wall clock locally with 4 jobs; companies of 130+ staff cost about 0.5 s a turn) |

## Recorded results

_(Filled in by the balance pass, M7a sub-task 4: one row per target, measured value, pass or fail, and the `balance.yaml` keys changed.)_
