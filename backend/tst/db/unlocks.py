"""Unlock announcements (docs/formulas.md 42.1; M29).

A system is announced by one inbox item of template `unlock` whose link is ("guide", the
system's stable id in `tst.sim.unlocks.SYSTEMS`). Nothing else is stored: what is shown is
what holds now (`unlocks.conditions`) plus what was ever announced, so a screen never hides
again and a save from before M29 shows every screen it already uses without an item.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.db.models import InboxItemRow
from tst.loader import LoadedData
from tst.sim import unlocks
from tst.sim.state import GameState

TEMPLATE = "unlock"
LINK_KIND = "guide"


@dataclass(frozen=True, slots=True)
class Announced:
    key: str
    turn: int
    item_id: int


def announced(session: Session, company_id: int) -> dict[str, Announced]:
    rows = session.scalars(
        select(InboxItemRow)
        .where(InboxItemRow.company_id == company_id, InboxItemRow.template == TEMPLATE)
        .order_by(InboxItemRow.id)
    )
    out: dict[str, Announced] = {}
    for row in rows:
        system = unlocks.BY_ID.get(row.link_id or 0)
        if system is not None and system.key not in out:
            out[system.key] = Announced(system.key, row.turn, row.id)
    return out


def _row(company_id: int, turn: int, system: unlocks.System, reason: str) -> InboxItemRow:
    return InboxItemRow(
        turn=turn,
        company_id=company_id,
        template=TEMPLATE,
        title=f"New: {system.label}",
        body=(
            f"{system.label} is open now because {reason}. It is in the side bar; its guide "
            "says what it does and where to start."
        ),
        link_kind=LINK_KIND,
        link_id=system.id,
        read=False,
        archived=False,
        bookmarked=False,
    )


def announce(session: Session, before: GameState, after: GameState, data: LoadedData) -> int:
    """In the turn's transaction: one item per system that unlocked this month."""
    player = after.player.id
    seen = frozenset(announced(session, player))
    fresh = unlocks.newly_unlocked(before, after, seen, data.balance, data.game_data)
    for system, reason in fresh:
        session.add(_row(player, after.turn, system, reason))
    return len(fresh)


def open_early(session: Session, state: GameState, key: str) -> bool:
    """The player opened an opt-in system before its condition held ("Explore for minerals"
    from Markets, 42.1). False when it was already announced."""
    system = unlocks.BY_KEY[key]
    if key not in unlocks.OPT_IN:
        raise KeyError(key)
    if key in announced(session, state.player.id):
        return False
    session.add(_row(state.player.id, state.turn, system, "you opened it from Markets"))
    return True
