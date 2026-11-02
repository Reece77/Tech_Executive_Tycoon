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

### Status at the stop for the product manager (2026-11-02)

Work paused here, before any re-band, as instructed. Committed so far: sub-task 0's first speed fixes, and sub-task 1's morale and retention tuning.

| Item | Before (m10c-done) | Now | Target | State |
| --- | --- | --- | --- | --- |
| S2 worker-minutes, CI nightly | 28.2 | 30.3 | < 20 | fails; brief: set at CI need + 25% once tuning ends |
| S2 locally, balance run alone | 18.8 | 13.6 | - | `GameState.person` by bisect with a C key, seat cost memoized |
| Median morale, steady / blitzscale | 56.5 / 53.7 | 61.6 / 59.0 | 58-68 | pass (`morale.target_base` 50 to 56) |
| Executive retention (score-14 CTO, 6 months) | 7 of 10 | 8 of 10 | >= 8 of 10 | pass; xfail removed (`resign.morale_floor` 40 to 50 keeps underpaid misfits leaving more) |
| M8 seats | 1.097 (xfail) | passes (xpass) | >= 1.15 | pass |
| T2 wins | steady 7, frugal 3 | steady 9, frugal 1 | each <= 6 | fails |
| T3 blitzscale succeeds | 5/10 | 4/10 | >= 3 | pass |
| T5 blitzscale bankrupt | 0% | 0% | 10-40% | fails: 5 of 10 founders are removed by the board at turns 87-109 with cash near zero, before bankruptcy |
| Expansion (19.8 target 2) | 6.93x | 6.93x | 1.4-2.5x | fails: home-only blitzscale ends at ARR 0 on 5 of 10 seeds (founder removed); where both arms live it is 3.4x |
| T7 startups alive | 62% | 61% | 20-60% | fails narrowly (xfail) |
| M10 covenants breach | 90% | 90% | 20-60% | fails (xfail) |
| M10 debt saves dilution | +4.8 | passes (xpass) | +5 | pass |
| M5 launches; potential gap | 0.925; 2.83 | unchanged (xfail) | 1.0; 3.0 | fail narrowly |
| §23.7 critical events per 18 months, 20+ staff | 1.08 | 0.88 | >= 1 | **new miss**: happier staff, fewer key exits |
| M5 poaching accepted | in band | 12.6% | 20-60% | **new miss**: the poach score's `morale_mid` 55 now sits below the median |
| Founder energy, hands-on | - | steady never below 5 in years 2-5 (0 of 480 months); blitzscale 15 of 480 | runs out >= 1 month in 3 | fails; no script plays like a hands-on human |
| Founder energy, delegated (§24.5 target 4) | 94% unspent | 94% | >= 60% | pass |

Root causes and what each needs (proposals for the product manager):
1. **Blitzscale's money runs out after its Series B.** The script raises seed, A and B only (written before M10's Series C and D). It burns into zero cash around turns 87-109, and the board removes the founder before bankruptcy. That one fact drives T2 (blitzscale never wins), T5 (removed, not bankrupt), T3's margin and the expansion ratio (zeros in the home arm), and plausibly the covenant breaches (blitzscale with debt). Proposal: the blitzscale script raises a Series C (say $50M, inside the $30-80M typical band) once its gate is met. This changes a strategy definition in `docs/balance-targets.md`, so it needs approval. Then re-measure T2, T3, T5, expansion and covenants before tuning any key.
2. **Morale vs poaching and crises.** Raising morale (the brief's sub-task 1) lowers poaching acceptance (12.6%) and key-exit crises (0.88). Options: (a) move `rivals.poach.morale_mid` to 61 with the median (acceptance returns, but executives at ordinary morale read "might go" again, undoing the retention fix); (b) keep it at 55 and raise acceptance for non-executives through `rivals.poach.offer_mult` or `leave_penalty`; (c) re-band M5 target 4 to 10-50% and §23.7 target 1 to 0.8. Recommendation: (b) for poaching, plus a small rise in `events.crisis.breach_chance`/`outage_chance` for crises.
3. **Founder energy "hands-on".** No balance script spends energy the way a hands-on player does (steady uses about 9 of 60 a month). Either define the measurement (for example, a hands-on script that interviews every candidate and sets prices and marketing monthly), or re-band it to a manual check. Cutting energy until steady runs out would refuse the scripts' own actions and move every other target.
4. **Near misses** (T7 61%, M5 launches 0.925, potential 2.83): the M9 reasons stand (startups founded abroad; the city talent bonus). Proposal: re-band T7 to 20-65%, M5 launches to >= 0.9 and the potential gap to >= 2.8, with those reasons; or leave them for after item 1.
5. **S2:** CI needs about 30 worker-minutes after this round; the brief sets the bound at that plus 25% (about 38) once tuning ends.

## Follow-ups

_(Agent fills in.)_
