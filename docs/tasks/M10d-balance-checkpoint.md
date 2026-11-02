# M10d: Balance checkpoint

**Goal:** one balance pass over v1 plus M8–M10c before M11 and M12a add more. Clear the accumulated misses, fix the known structural problems, and make the nightly run green again.

**Spec sections:** §16 · **ADRs:** 0008 · **Formulas:** §9 (morale), §15.6 (poaching), §18, §19, §20, §23, §24; `docs/balance-targets.md` (all) · **Depends on:** M10c (`m10c-done`)

## Context

Since M8, balance targets have been recorded as expected failures (xfail) one at a time, with "rebalance later". That point has come. Known problems:
- **Morale:** staff morale sits about 50, so any market-rate offer reads "might go". Rivals pick off appointed executives, which weakens seats and blitzscale. This is the root of the T3, M8 seats and executive-retention misses.
- **Expansion:** too strong (7.0× against a 1.4× target; home-only blitzscale fails every seed).
- **Steady dominance:** steady wins 8–10 of 10 seeds (T2).
- **Covenants:** they breach on 90% of seeds (M10 target 3, band 20–60%).
- **Near misses:** T7 startups alive (62%), M5 launches (0.925), debt saves dilution (+4.8), potential spotting (2.83).
- **Founder energy:** it doesn't bind; Reece barely noticed spending it, and executive authority (M10c) frees more.
- **Speed:** the nightly speed target fails on CI (28 worker-minutes against 20) as each milestone adds work per turn.
- **Events:** event balance must be re-checked after M10b's modifiers and critical events.

The product manager may re-band a target where the design changed (with the reason written down). Silent xfails are not allowed.

## Out of scope

New features. Changing formulas' shape. This pass tunes keys in `balance.yaml` and data files. A formula change needs a one-line proposal in the report first.

## Sub-tasks (commit after each)

0. **Speed:**
   - profile a 120-turn persisted run and the pure balance run (as M7a did), and fix the hot spots;
   - then set S2 for v2 at what CI actually needs plus 25% headroom (record before and after);
   - refresh `tests/durations.json`;
   - a third CI shard if any job passes 17 minutes.
1. **Morale and retention:**
   - tune the §9 morale terms so the median employee sits at 58–68 in the steady and blitzscale strategies;
   - tune executive retention: a score-14 executive at the default exec salary stays 6 months on at least 8 of 10 seeds;
   - then remove the executive-retention xfail.
2. **Expansion:** tune regional keys (`markets.*`, `geo.*`) so blitzscale with expansion reaches 1.4–2.5× home-only blitzscale's median turn-120 ARR, and home-only blitzscale succeeds on at least 3 of 10 seeds.
3. **Strategy balance:** T2 (no strategy wins more than 6 of 10) and T3 (each succeeds at least 3 of 10); M8 seats (≥ 1.15); M10 covenants (20–60%) and debt (+5 points).
4. **Near misses:** T7, M5 launches and potential spotting. Each passes or is re-banded with a written reason the product manager approves in the report.
5. **Founder energy:** tune monthly energy and action costs so a hands-on founder without executive authority runs out of energy in at least 1 month in 3 during years 2–5, and a founder with full executive authority leaves at least 60% unspent (§24.5 target 4).
6. **Events:** §16.10 and §23.7 still met with modifiers and critical events.
7. **Report:**
   - `docs/balance-targets.md` gets one table with every target, its value before and after, and pass or fail;
   - **every xfail in the suite is removed or carries an approved re-band;**
   - close out the CHANGELOG and golden snapshots (with the reason).

## Acceptance criteria

- [ ] The nightly workflow is green on `main` after merge, S2 included.
- [ ] Median morale 58–68; executive retention met; its xfail removed.
- [ ] Expansion within 1.4–2.5×; home-only blitzscale viable.
- [ ] T2, T3, M8 seats, M10 covenants and debt pass; near misses pass or have approved re-bands.
- [ ] Founder energy binds when hands-on and frees up when delegated.
- [ ] No xfail remains without an approved, written reason.
- [ ] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m10d-done`.

## Manual check (Reece, after merge)

A short game of 3 years hands-on, then 3 years delegated on `quick-stage3`. Does morale feel healthier, do executives stay, and does expanding abroad feel strong but not automatic?

## Decisions made

Product manager decisions (2026-11-02), after the stop report: (1) blitzscale raises Series C and D as soon as allowed; (2) keep `morale.target_base` 56 and the poach morale midpoint, re-band poaching acceptance to 10–40%, add a target for staff lost to rivals, raise crisis chances; (3) founder energy when hands-on becomes a manual check; (4) re-measure the near misses after (1), re-bands approved where still missing; S2 at CI's measured need plus 25%; then, after a second question: a rival's poach target is drawn by CA with seat holders ×0.4, T5 blitzscale re-banded to 0–40%, and the regional market sizes may shrink.

- **Speed (0).** `GameState.person` by binary search with a C key (`operator.attrgetter`), the flexible-seat cost memoized, and the tests' `answer_critical` loads the state only when a critical event is open: a profiled 120-turn balance game 36 s to 27.8 s; S2 locally 18.8 to 14.9. CI's nightly is three matrix jobs: `make balance` alone (gates S2) and `make nightly-ci SHARD=1..4`, the nightly tests in four shards balanced by `tests/durations.json` (refreshed with the nightly tests), 60 minutes each (the single 45-minute job was cancelled at its limit, and so were two shards). S2's budget for v2 is 43 worker-minutes: CI's highest reading, 34.2, plus 25% (CI read 30.3, 18.0, 33.5 and 34.2 over four runs). Inside the parallel nightly, `test_balance_targets` prints S2 but does not gate it (60 locally under load; M10b recorded the same). No check job passes 17 minutes, so no third check shard.
- **Morale and retention (1).** `morale.target_base` 56 (median 62.3 steady, 60.2 blitzscale). `resign.morale_floor` 40 to 50, so the floor stays about ten points below the median and underpaid misfits still leave more (`test_underpaid_misfits_lose_morale_and_resign_more`: 17 to 17 at 56 and 40; 19 to 17 at 50). Executive retention 8/10. The worked examples of §9 and §10 keep 50 and 40, and their tests use them, as M7a did for `resign.base_bp`.
- **Poaching (2, formula change approved).** `player_target` draws among the top 30% by CA without a pending approach, weighted by CA with current seat holders ×`rivals.poach.seat_holder_weight` (0.4), on stream `poach` key `(new approach id, 1)` through the stream's one call site `poaching.poach_draw` (the answer keeps `(approach id,)`; ADR-0013's table updated). Before, it was always the single highest-CA employee, so any rise in approach frequency fell on the executives. `rivals.poach.leave_penalty` −0.5 to −0.3 brings acceptance in the fast-growth script to 14% (7% without) at 4.00 approaches a year; `poach_gain` stays 0.007 (0.005 and 0.006 pushed the approaches over 4 a year). New target 15.7.6 (`tst/balance/m10d.py`, `tests/balance/test_m10d_balance.py`): 0.58 (steady) and 1.05 (blitzscale) staff a year lost to rivals with 30+ staff. `test_rival_replay` moved from seed 7 to seed 3 (seed 7 saw no approach in its 24 turns once targets are drawn). §15.8's Priya example keeps −0.5.
- **Strategy balance (3).** With C and D, blitzscale succeeds on 10/10 but ends at 8–12% ownership, far behind steady; the frugal strategy was within a few percent of steady. The ARR multiple now weighs growth more (`4 + 4 g` to `2.5 + 5.5 g`): T2 steady 6, frugal 4. §14 worked example updated (9.112, $16.49M).
- **Expansion (2).** Rivals enter regions more readily (`geo.region_entry.unserved` 0.6, `cooldown_turns` 6) and localization is slower and dearer (6 months, $80,000): 3.45x to 2.65x; then Europe 0.55 and East Asia 0.45 of North America's demand (approved): 2.18x with every home arm alive. §19.5's table and worked examples updated; the geo tests follow the new values.
- **Covenants (3).** Every breach was on the venture debt signed against the seed, as blitzscale spent to zero before its Series A; `covenant_burn_months` barely moved it. `debt.venture.max_of_round_bp` 3000 to 5000 carries it nearer the A: 80% to 60% of seeds breach (band 20–60%). §20.6's example keeps 30%.
- **Crises (6).** Raising `breach_chance` and `outage_chance` (0.004 to 0.008, 0.003 to 0.006, as decided) did not move the rate alone (0.96–1.01): steady's teams keep security coverage near full and quality above the outage line. `events.crisis.key_exit_top_fraction` 0.10 to 0.20 counts more departures as key exits: 1.19 per 18 months.
- **Near misses (4).** After the strategy change: M5 launches 1.02 (passes; no re-band), T7 startups 61% (re-banded to 20–65%), potential spotting at the approved >= 2.8.
- **Founder energy (5).** Hands-on: a manual check for Reece's next playtest, no scripted target. Delegated: §24.5 target 4, 94% unspent.
- **Golden snapshots** regenerated at each tuning commit (CHANGELOG).
- Every value is in `docs/balance-targets.md` (M10d); every xfail is gone.

## Follow-ups

- **Late-round sizing (M15, product manager):** blitzscale ends with $1.5–2.9B idle cash because it takes the largest Series C/D offered regardless of need. Check whether investors should size late rounds to the company's burn and plan (e.g. at most 24 months of runway), and whether blitzscale should raise only what it can deploy.
- **Narrow margins** (deterministic, so they hold, but small changes may tip them): poaching approaches 4.00 a year (cap 4), steady's staff lost 0.58 (floor 0.5), executive retention 8/10, T2 steady 6 (cap 6), covenants 60% (cap 60%).
- **S2 varies on CI** (18.0 to 34.2 worker-minutes for the same work); if it drifts toward 43, a dedicated runner or a wall-clock measure would be steadier.
- **Hands-on founder energy** needs Reece's playtest verdict; a hands-on script could make it measurable.
