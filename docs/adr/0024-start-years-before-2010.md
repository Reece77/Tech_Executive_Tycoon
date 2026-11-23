# ADR-0024: Start years before 2010

**Status:** accepted (2026-11-23, product manager, from Reece's v6 decisions of 2026-11-22) · **Milestone:** M50 · **Formulas:** §60

## Context

CLAUDE.md §7 fixes turn 0 at January 2010, and every system's data starts in 2010. v6 adds earlier start years (2008 first, then 2000 and 1995). A 2010 game, its golden snapshots and every guard must not change.

## Decision

1. **Turn 0 stays January 2010.** Earlier months are negative turns (January 2008 is −24). `tst.sim.calendar` converts both ways; nothing else does date arithmetic.
2. **Each save records its start turn** (0 for a 2010 game). Turn-indexed state and history tables accept negative turns; a migration widens nothing else.
3. **RNG streams accept negative turns** with the same derivation, so a 2010 game's draws are unchanged.
4. **Data series gain earlier entries** in the same files (years 2008 and 2009 first); the loader rejects a series that has a gap between the earliest start year offered and 2010.
5. **Start years are offered only when every system's data covers them:** 2010 always, 2008 from M50, and 2000 and 1995 when their milestones add the data.

## Consequences

- CLAUDE.md §7's "Turn 0 = January 2010" still holds; M50 adds a sentence about negative turns.
- Displays and the API show dates, never raw turns, so negative turns are invisible to the player.
