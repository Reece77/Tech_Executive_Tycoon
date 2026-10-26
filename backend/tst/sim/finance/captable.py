"""Reading the cap table (docs/formulas.md 14.2): fully diluted shares, the unallocated pool,
holdings, and the share price of the latest priced round."""

from __future__ import annotations

from fractions import Fraction

from tst.sim.finance.models import CapEntry, FundingRound
from tst.sim.state import GameState


def fd_shares(state: GameState, company_id: int) -> int:
    """Fully diluted shares: every cap-table entry (the unallocated pool included) plus
    every outstanding option."""
    entries = sum(e.shares for e in state.company_cap(company_id))
    options = sum(g.outstanding for g in state.company_grants(company_id))
    return entries + options


def pool_entry(state: GameState, company_id: int) -> CapEntry | None:
    for e in state.company_cap(company_id):
        if e.holder_kind == "pool":
            return e
    return None


def unallocated(state: GameState, company_id: int) -> int:
    entry = pool_entry(state, company_id)
    return entry.shares if entry else 0


def person_shares(state: GameState, company_id: int, person_id: int) -> int:
    """Shares held directly by a person (the founder's common)."""
    return sum(
        e.shares
        for e in state.company_cap(company_id)
        if e.holder_kind == "person" and e.person_id == person_id
    )


def closed_rounds(state: GameState, company_id: int) -> tuple[FundingRound, ...]:
    return tuple(r for r in state.company_rounds(company_id) if r.status == "closed")


def last_round(state: GameState, company_id: int) -> FundingRound | None:
    """The latest closed priced round, if any."""
    done = closed_rounds(state, company_id)
    return max(done, key=lambda r: (r.closed_turn or 0, r.id)) if done else None


def share_price(state: GameState, company_id: int) -> Fraction:
    """Cents per share of the latest priced round, or 0 before any (14.2)."""
    latest = last_round(state, company_id)
    price = latest.price if latest else None
    return price if price is not None else Fraction(0)


def open_round(state: GameState, company_id: int) -> FundingRound | None:
    for r in state.company_rounds(company_id):
        if r.status in ("open", "accepted"):
            return r
    return None
