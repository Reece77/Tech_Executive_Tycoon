"""A facility build's public construction figures (ADR-0007; formulas.md 49.7; M43r, Codex review
9 finding 3): what the facility screens show of a build, never its hidden overrun.

A fab, a refinery, a power plant and a cell plant are quoted at the order; the facility's
`capex_cents` carries the hidden overrun, which is revealed only as it is paid, so their screens
show the quote (`estimate_cents`) and the payments made. A mine shows its study's estimate until
the cost to complete is revised (`Mine.capex_cents`), and keeps its payments on the mine. Every
other kind is priced in the open: its screen shows the facility's `capex_cents`.

`committed_cents` is the capital still to pay as those screens project it: the shown total less
what has been paid, never below 0 (a build paid past its quote shows nothing more to come)."""

from __future__ import annotations

from tst.sim.facilities.models import Facility
from tst.sim.state import GameState


def shown_capex(state: GameState, facility: Facility) -> tuple[int, int]:
    """(the build's total as its screen shows it, what has been paid)."""
    fid = facility.id
    mine = state.mine(fid)
    if mine is not None:
        return mine.capex_cents, mine.capex_paid_cents
    quotes = (
        *(f.estimate_cents for f in state.fabs if f.facility_id == fid),
        *(r.estimate_cents for r in state.refineries if r.facility_id == fid),
        *(p.estimate_cents for p in state.plants if p.facility_id == fid),
    )
    if quotes:
        return quotes[0], facility.capex_paid_cents
    cell = state.cell_plant(fid)
    if cell is not None:
        return cell.estimate_cents, facility.capex_paid_cents
    return facility.capex_cents, facility.capex_paid_cents


def committed_cents(state: GameState, facility: Facility) -> int:
    total, paid = shown_capex(state, facility)
    return max(0, total - paid)
