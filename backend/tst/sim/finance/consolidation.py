"""Consolidated statements for a group (docs/formulas.md 28.5 and 31.1, M14 and M16;
ADR-0020): a root and every company it controlled, at any depth, each over the periods it was
inside the group (Codex review 4 findings 2 and 3).

As ledger lines:

- the root's lines without its 1810 investment;
- for each member, from the turn it entered the group (`start`): its balance-sheet accounts
  as they stood at the end of that turn (opening lines), then its later lines up to the turn
  it left (`end`), without its equity accounts and without its own 1810 (intercompany
  investments are eliminated at every level: what a member owns enters as its own member).
  A cash sweep debits the member's equity and credits its owner's 1810, so both sides drop
  out and the sweep stays inside the group;
- at `start`, a goodwill line for the difference between the member's net assets then and
  the investment its owner carried: zero for a company bought by the group itself, the
  profit it made since its own closing for one that came in with its owner (a grandchild);
- at `end`, a **disposal**: the member's balance-sheet lines and its goodwill line reversed,
  the rest to 4930. The owner's own books carry its side (tst.sim.group.ownership), so the
  group's lines still total zero, and the member's earlier periods keep its contributions.

The total of the lines is zero at every turn."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tst.sim.data_models import AccountType
from tst.sim.ledger import DISPOSAL, GOODWILL, INVESTMENT_SUBSIDIARIES

type Line = tuple[int, str, int]  # (turn, account, amount): the statements' input
BALANCE_SHEET = ("asset", "liability")


@dataclass(frozen=True, slots=True)
class Member:
    """One company's run inside the group: its ledger lines, the turns it entered and left
    (None: still inside), the turn its holding opened (`owned_from`, the closing), and the
    investment its owner booked then (`book_cents`, None when unrecorded: the net assets at
    the end of `owned_from`) with the member's equity balance then (`equity_cents`)."""

    lines: Sequence[Line]
    start: int
    end: int | None = None
    owned_from: int | None = None
    book_cents: int | None = None
    equity_cents: int | None = None


def _balances(
    lines: Sequence[Line], types: Mapping[str, AccountType], through: int, kinds: tuple[str, ...]
) -> int:
    return sum(a for t, acc, a in lines if t <= through and types.get(acc) in kinds)


def member_lines(member: Member, types: Mapping[str, AccountType]) -> list[Line]:
    """One member's contribution: opening balances, the entry goodwill, later lines, and the
    disposal at its end."""
    start, end, lines = member.start, member.end, member.lines
    opening: dict[str, int] = defaultdict(int)
    later: list[Line] = []
    for turn, account, amount in lines:
        if account == INVESTMENT_SUBSIDIARIES:
            continue
        kind = types.get(account)
        if turn <= start:
            if kind in BALANCE_SHEET:
                opening[account] += amount
        elif (end is None or turn <= end) and kind != "equity":
            later.append((turn, account, amount))
    out = [(start, a, v) for a, v in sorted(opening.items()) if v != 0]
    # The entry goodwill: net assets at `start` (1810 included: what it owns enters as its
    # own member) less the investment its owner carried at `start` (28.5 sweeps and
    # funding move both by the same amount).
    owned = member.owned_from if member.owned_from is not None else start
    net = _balances(lines, types, start, BALANCE_SHEET)
    equity_now = _balances(lines, types, start, ("equity",))
    book = (
        member.book_cents
        if member.book_cents is not None
        else _balances(lines, types, owned, BALANCE_SHEET)
    )
    equity_then = (
        member.equity_cents
        if member.equity_cents is not None
        else _balances(lines, types, owned, ("equity",))
    )
    carried = book - (equity_now - equity_then)
    if net != carried:
        out.append((start, GOODWILL, carried - net))
    out += later
    if end is not None:
        sheet: dict[str, int] = defaultdict(int)
        for _turn, account, amount in out:
            if types.get(account) in BALANCE_SHEET:
                sheet[account] += amount
        disposal = [(end, a, -v) for a, v in sorted(sheet.items()) if v != 0]
        total = sum(a for _, _, a in out) + sum(a for _, _, a in disposal)
        if total:
            disposal.append((end, DISPOSAL, -total))
        out += disposal
    return out


def consolidated_lines(
    parent: Sequence[Line],
    brands: Sequence[tuple[Sequence[Line], int] | Member],
    types: Mapping[str, AccountType],
) -> list[Line]:
    """The group's lines: the root's without 1810, plus each member's (31.1). A member given as
    (lines, closed turn) is a direct, still-held subsidiary bought at that turn (M14)."""
    out = [x for x in parent if x[1] != INVESTMENT_SUBSIDIARIES]
    for brand in brands:
        member = brand if isinstance(brand, Member) else Member(brand[0], brand[1])
        out += member_lines(member, types)
    return out


def brand_lines(
    lines: Sequence[Line], types: Mapping[str, AccountType], closed_turn: int
) -> list[Line]:
    """A direct, still-held subsidiary's contribution from its closing (M14)."""
    return member_lines(Member(lines, closed_turn), types)
