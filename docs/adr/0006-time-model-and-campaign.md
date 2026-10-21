# ADR-0006: Time model and campaign length

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §4, §20

## Context

Reece chose a 2010 start (with a 2026 scenario later) and a 360-turn standard campaign. Severe events need finer time resolution without making every month slow.

## Decision

- **Turn 0 = January 2010.** `tst.sim.calendar.turn_to_ym(turn) -> (year, month)` and `ym_to_turn(year, month)`. A standard campaign ends after turn 359 (December 2039). Sandbox has no end.
- **Base turn = one calendar month.**
- **Crisis window:** a critical event opens up to 4 weekly sub-turns within the current month. Sub-turns are numbered `(turn, sub)` with `sub` in 1..4; only the crisis-relevant phases run in sub-turns (decisions, the crisis resolution, morale, cash). The remaining monthly phases run once when the window closes. Crisis windows arrive in M6; until then all turns are monthly and `sub` is always 0.
- **Turn pipeline order** (fixed, tested in `tests/unit/test_turn_order.py`):
  1. apply player decisions
  2. rival decisions (M5+)
  3. R&D progress (v2)
  4. production and capacity (v2)
  5. sales, revenue, churn (M3+)
  6. payroll and operating costs
  7. financing (interest, covenants) (M4+)
  8. people updates: morale, stress, growth, aging, relationships, resignations
  9. market and macro update
  10. stage checks
  11. snapshot and month-end report
  12. event director requests for next turn
  Phases not yet implemented are present as no-op functions so the order never changes.
- **Ages and dates:** people store `birth_turn` (may be negative, for births before 2010); age in years = `(turn - birth_turn) // 12`.
- **Era data:** seed data for rivals, salaries, and prices reflects 2010. A 2026 scenario will be a separate seed pack, not code branches.

## Consequences

- All time math goes through `calendar`; no `datetime` arithmetic in the sim.
- 360 turns × 8–12 rivals × hundreds of people sets the performance budget: one monthly turn should resolve in under 1 second at v1 scale on a laptop.

## Alternatives considered

- Weekly turns throughout: too slow for a 30-year campaign.
- Real dates (`datetime.date`) in state: invites clock use and time-zone bugs.
