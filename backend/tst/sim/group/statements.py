"""The group's members as consolidation input (31.1, 31.3): each company's run inside a root's
group with its ledger lines, its holding's basis and the root's effective stake."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tst.sim.finance.consolidation import Line, Member
from tst.sim.group.models import EQUITY_ENDS, GroupMember


def member_input(m: GroupMember, lines: Sequence[Line]) -> Member:
    o = m.ownership
    recorded = bool(o.id)
    return Member(
        lines,
        m.start,
        m.end,
        o.from_turn,
        o.book_cents if recorded else None,
        o.equity_cents if recorded else None,
        m.common_control,
        m.end is not None and o.end_reason in EQUITY_ENDS,
        o.rebases,
        o.stake_bp,
        m.effective,
    )


def members_input(
    members: Sequence[GroupMember], books: Mapping[int, Sequence[Line]]
) -> list[Member]:
    return [member_input(m, books.get(m.company_id, ())) for m in members]
