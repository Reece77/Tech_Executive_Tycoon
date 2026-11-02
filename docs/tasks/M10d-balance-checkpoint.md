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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
