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
  group's lines still total zero, and the member's earlier periods keep its contributions;
- with outside holders (31.3), **non-controlling interest**: at each turn NCI is the sum over
  members of (1 - the root's effective stake) x the member's contributed net assets; its
  movement posts to 3500, the outsiders' share of the turn's profit to 4990 (shown below the
  net result: what is attributable to NCI), and the rest to equity, which also absorbs what
  the outsiders' side of a dividend or a stake sale leaves.

The total of the lines is zero at every turn."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from tst.sim.data_models import AccountType
from tst.sim.ledger import (
    COMMON_EQUITY,
    DISPOSAL,
    GOODWILL,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    INVESTMENT_SUBSIDIARIES,
    NCI,
    NCI_SHARE,
)
from tst.sim.money import BP_DENOMINATOR

type Line = tuple[int, str, int]  # (turn, account, amount): the statements' input
BALANCE_SHEET = ("asset", "liability")
INTERCOMPANY = (INTERCOMPANY_SALES, INTERCOMPANY_PURCHASES)


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
    # M16 (31.2): it entered through a reorganization (the entry difference is equity), or
    # left to the group's own shareholders or inside the group (its disposal is equity)
    common_control: bool = False
    equity_end: bool = False
    # (turn, stake_bp, book, equity) rebases of its holding (31.5), oldest first
    rebases: tuple[tuple[int, int, int, int], ...] = ()
    stake_bp: int = BP_DENOMINATOR  # its holding's stake at `owned_from` (10,000 = 100%)
    # the root's effective stake from each turn, oldest first (31.3); empty: 100% throughout
    effective: tuple[tuple[int, Fraction], ...] = ()

    def effective_at(self, turn: int) -> Fraction:
        out = Fraction(1)
        for t, e in self.effective:
            if t <= turn:
                out = e
        return out

    def basis_at(self, turn: int) -> tuple[int, int | None, int | None]:
        out = (self.stake_bp, self.book_cents, self.equity_cents)
        for t, stake, book, equity in self.rebases:
            if t <= turn:
                out = (stake, book, equity)
        return out


def _balances(
    lines: Sequence[Line], types: Mapping[str, AccountType], through: int, kinds: tuple[str, ...]
) -> int:
    return sum(a for t, acc, a in lines if t <= through and types.get(acc) in kinds)


def member_lines(member: Member, types: Mapping[str, AccountType]) -> list[Line]:
    """One member's contribution: opening balances, the entry goodwill, later lines, and the
    disposal at its end."""
    return contribution(member, types)[0]


def contribution(member: Member, types: Mapping[str, AccountType]) -> tuple[list[Line], int]:
    """member_lines, and the entry goodwill on the balance sheet (0 under common control,
    where the entry difference is equity): NCI leaves it out (31.3)."""
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
    stake, book_at, equity_at = member.basis_at(start)
    book = book_at if book_at is not None else _balances(lines, types, owned, BALANCE_SHEET)
    equity_then = (
        equity_at if equity_at is not None else _balances(lines, types, owned, ("equity",))
    )
    carried = book - round(Fraction(stake, BP_DENOMINATOR) * (equity_now - equity_then))
    # A partial holding at entry (31.3): the investment is against the group's share of the
    # net assets; the outsiders' share is NCI (nci_lines).
    share = round(Fraction(stake, BP_DENOMINATOR) * net)
    entry = 0
    if share != carried:
        out.append((start, COMMON_EQUITY if member.common_control else GOODWILL, carried - share))
        entry = 0 if member.common_control else carried - share
    out += later
    if end is not None:
        sheet: dict[str, int] = defaultdict(int)
        for _turn, account, amount in out:
            if types.get(account) in BALANCE_SHEET:
                sheet[account] += amount
        disposal = [(end, a, -v) for a, v in sorted(sheet.items()) if v != 0]
        total = sum(a for _, _, a in out) + sum(a for _, _, a in disposal)
        if total:
            disposal.append((end, COMMON_EQUITY if member.equity_end else DISPOSAL, -total))
        out += disposal
    return out, entry


def consolidated_lines(
    parent: Sequence[Line],
    brands: Sequence[tuple[Sequence[Line], int] | Member],
    types: Mapping[str, AccountType],
) -> list[Line]:
    """The group's lines: the root's without 1810, plus each member's (31.1), plus NCI where
    outsiders hold part of a member (31.3). A member given as (lines, closed turn) is a
    direct, still-held subsidiary bought at that turn (M14)."""
    out = [x for x in parent if x[1] != INVESTMENT_SUBSIDIARIES]
    if brands:  # intercompany sales and purchases inside the group cancel (ADR-0020 4, 31.6)
        out = [x for x in out if x[1] not in INTERCOMPANY]
    contributed: list[tuple[Member, list[Line], int]] = []
    for brand in brands:
        member = brand if isinstance(brand, Member) else Member(brand[0], brand[1])
        mine, entry = contribution(member, types)
        # NCI's share of profit is of the member's own profit, its intercompany sales and
        # purchases included (31.3; M23a, Codex review 5 finding 3): attribution reads the
        # whole contribution, and only the group's lines lose the intercompany accounts.
        contributed.append((member, mine, entry))
        out += [x for x in mine if x[1] not in INTERCOMPANY]
    if any(e < 1 for m, _, _ in contributed for _, e in m.effective):
        out += nci_lines(out, contributed, types)
    return out


def nci_by_turn(
    contributed: Sequence[tuple[Member, Sequence[Line], int]],
    types: Mapping[str, AccountType],
    turns: Sequence[int],
) -> dict[int, tuple[int, int]]:
    """(NCI balance, NCI's share of the turn's profit) at each turn (31.3): the sum over
    members inside the group of (1 - the root's effective stake) x the member's contributed
    net assets (its entry goodwill aside: that is the group's), and x its contributed profit
    that turn."""
    out: dict[int, tuple[int, int]] = {}
    sheets: list[dict[int, int]] = []
    profits: list[dict[int, int]] = []
    for _member, lines, _entry in contributed:
        sheet: dict[int, int] = defaultdict(int)
        profit: dict[int, int] = defaultdict(int)
        for t, account, amount in lines:
            kind = types.get(account)
            if kind in BALANCE_SHEET:
                sheet[t] += amount
            elif kind in ("revenue", "expense"):
                profit[t] -= amount
        sheets.append(sheet)
        profits.append(profit)
    running = [0] * len(contributed)
    for t in turns:
        balance = Fraction(0)
        share = Fraction(0)
        for i, (member, _, entry) in enumerate(contributed):
            running[i] += sheets[i].get(t, 0)
            inside = member.start <= t and (member.end is None or t < member.end)
            outside = 1 - member.effective_at(t)
            if outside and inside:
                balance += outside * (running[i] - entry)
                share += outside * profits[i].get(t, 0)
        out[t] = (round(balance), round(share))
    return out


def nci_lines(
    base: Sequence[Line],
    contributed: Sequence[tuple[Member, Sequence[Line], int]],
    types: Mapping[str, AccountType],
) -> list[Line]:
    """NCI's lines (31.3): its movement on 3500 (a credit as it grows), its share of profit
    on 4990, and the rest on equity, so each turn still totals zero."""
    by_turn: dict[int, int] = defaultdict(int)
    for t, _, amount in base:
        by_turn[t] += amount
    turns = sorted(set(by_turn) | {t for m, _, _ in contributed for t, _ in m.effective})
    nci = nci_by_turn(contributed, types, turns)
    out: list[Line] = []
    before = 0
    for t in turns:
        balance, share = nci[t]
        moved = balance - before
        before = balance
        residual = by_turn.get(t, 0)
        rest = moved - share - residual
        out += [
            x for x in ((t, NCI, -moved), (t, NCI_SHARE, share), (t, COMMON_EQUITY, rest)) if x[2]
        ]
    return out


def brand_lines(
    lines: Sequence[Line], types: Mapping[str, AccountType], closed_turn: int
) -> list[Line]:
    """A direct, still-held subsidiary's contribution from its closing (M14)."""
    return member_lines(Member(lines, closed_turn), types)
