"""Group records (M16, docs/formulas.md 31). Frozen dataclasses; the state holds tuples of
them sorted by id."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

FULL_STAKE_BP = 10_000  # tunable-exempt: 100% in basis points

type EndReason = Literal["failed", "sold", "spun_off", "integrated", "transferred"]
# Ends that are transactions with the group's own shareholders or inside the group (a
# spin-off, a transfer to the holding company): their disposal balances to equity, not 4930.
EQUITY_ENDS: tuple[EndReason, ...] = ("spun_off", "transferred")


@dataclass(frozen=True, slots=True)
class Ownership:
    """One owner's holding of one company over a run of turns (31.1; Codex review 4 findings
    2 and 3). `from_turn` is the closing turn: the company's lines up to and including it are
    pre-acquisition and enter the owner's group as opening balances. `to_turn` is the turn
    the holding ended (a failure's disposal, a sale, a spin-off); None while it lasts. The
    company's lines up to and including `to_turn` belong to the owner's group.

    `book_cents` is the owner's 1810 investment at closing (the company's book equity then)
    and `equity_cents` the company's equity accounts' balance (debit positive) at the same
    moment: the investment the owner carries at any later turn is
    `book_cents - stake x (equity now - equity_cents)`, since a sweep, funding or dividend
    moves the company's equity and the owner's 1810 (by its stake) together (28.5, 31.4).

    `stake_bp` is the stake at `from_turn`. A stake change (a sale, a buyout, 31.5) adds a
    **rebase** (turn, stake_bp, book_cents, equity_cents): from that turn the stake, and the
    investment's basis, are the rebase's."""

    id: int
    company_id: int
    owner_id: int
    from_turn: int
    to_turn: int | None = None
    book_cents: int = 0
    equity_cents: int = 0
    stake_bp: int = FULL_STAKE_BP
    end_reason: EndReason | None = None
    # the goodwill this owner carries for the company; None: from the acquisition (28.3)
    goodwill_cents: int | None = None
    # a reorganization under common control (forming the holding company, 31.2): the group's
    # entry difference goes to equity, not goodwill
    common_control: bool = False
    rebases: tuple[tuple[int, int, int, int], ...] = ()  # (turn, stake_bp, book, equity)

    def basis(self, turn: int | None = None) -> tuple[int, int, int]:
        """(stake_bp, book_cents, equity_cents) in force at `turn` (now when None)."""
        out = (self.stake_bp, self.book_cents, self.equity_cents)
        for t, stake, book, equity in self.rebases:
            if turn is None or t <= turn:
                out = (stake, book, equity)
        return out

    def stake_at(self, turn: int | None = None) -> int:
        return self.basis(turn)[0]

    def covers(self, turn: int) -> bool:
        return self.from_turn <= turn and (self.to_turn is None or turn <= self.to_turn)

    @property
    def is_open(self) -> bool:
        return self.to_turn is None


@dataclass(frozen=True, slots=True)
class GroupMember:
    """A company inside a root's group for a run of turns (31.1): consolidation's input.
    `start` is when it entered the root's group (opening balances at the end of that turn);
    `end` the turn it left (a disposal posts then); None while it is still inside.
    `ownership` is the record that made it a member (its direct owner's)."""

    company_id: int
    parent_id: int
    start: int
    end: int | None
    ownership: Ownership
    depth: int  # 1 for the root's own subsidiaries, 2 for theirs, ...
    common_control: bool = False  # it entered through a reorganization (31.2)
    # the root's effective stake (product of stakes down the chain) as (from turn, stake bp
    # as a fraction of 10,000) steps, oldest first, inside the run (31.3: NCI is the rest)
    effective: tuple[tuple[int, Fraction], ...] = ()

    def effective_at(self, turn: int) -> Fraction:
        out = Fraction(1)
        for t, e in self.effective:
            if t <= turn:
                out = e
        return out


@dataclass(frozen=True, slots=True)
class Holding:
    """The player's holding company (31.2): formed over the operating company, which it owns
    with every kept brand. It holds the listing, the cap table and the board; the founder is
    its Chair and still works at the operating company."""

    company_id: int
    operating_id: int
    formed_turn: int
    chair_id: int


type StakeKind = Literal["market", "venture", "retained"]


@dataclass(frozen=True, slots=True)
class Stake:
    """A stake the group does not control (31.3, 31.5): bought on the market in a listed
    rival, a corporate venture investment in a startup's round, or what the group kept of a
    spin-off. 20-50% is an associate (equity method, 1820): its carrying amount grows by the
    group's share of the company's monthly operating result. Under 20% it is a financial
    investment (1830) marked to fair value each December (4920). `carrying_cents` is the
    owner's balance for this stake on the account its treatment uses."""

    id: int
    owner_id: int
    company_id: int
    stake_bp: int
    cost_cents: int
    carrying_cents: int
    from_turn: int
    kind: StakeKind = "market"
    to_turn: int | None = None
    disclosed_bp: int = 0  # the highest disclosure line crossed (31.5)

    @property
    def is_open(self) -> bool:
        return self.to_turn is None
