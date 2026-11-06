"""Consolidated statements for a group (docs/formulas.md 28.5, M14; ADR-0020): a parent and
its kept brands. A brand's revenue, costs and cash enter the parent's statements from the
month after closing.

As ledger lines: the parent's lines without its 1810 investment; for each brand, its
balance-sheet accounts as they stood at the end of its closing month (opening lines), then
its later lines without its equity accounts (a cash sweep debits the brand's equity and
credits the parent's 1810, so both sides drop out and the sweep stays inside the group).
The total of the lines stays zero: the parent's 1810 equals the brand's net assets at
closing less what has been swept."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from tst.sim.data_models import AccountType
from tst.sim.ledger import INVESTMENT_SUBSIDIARIES

type Line = tuple[int, str, int]  # (turn, account, amount): the statements' input
BALANCE_SHEET = ("asset", "liability")


def brand_lines(
    lines: Sequence[Line], types: Mapping[str, AccountType], closed_turn: int
) -> list[Line]:
    """One brand's contribution: opening balances at its closing month, then its later
    lines without equity accounts."""
    opening: dict[str, int] = defaultdict(int)
    later: list[Line] = []
    for turn, account, amount in lines:
        if turn <= closed_turn:
            if types.get(account) in BALANCE_SHEET:
                opening[account] += amount
        elif types.get(account) != "equity":
            later.append((turn, account, amount))
    start = [(closed_turn, a, v) for a, v in sorted(opening.items()) if v != 0]
    return [*start, *later]


def consolidated_lines(
    parent: Sequence[Line],
    brands: Sequence[tuple[Sequence[Line], int]],
    types: Mapping[str, AccountType],
) -> list[Line]:
    """The group's lines: the parent's without 1810, plus each brand's (lines, closed turn)."""
    out = [x for x in parent if x[1] != INVESTMENT_SUBSIDIARIES]
    for lines, closed in brands:
        out += brand_lines(lines, types, closed)
    return out
