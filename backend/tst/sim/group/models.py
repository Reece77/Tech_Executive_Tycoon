"""Group records (M16, docs/formulas.md 31). Frozen dataclasses; the state holds tuples of
them sorted by id."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FULL_STAKE_BP = 10_000  # tunable-exempt: 100% in basis points

type EndReason = Literal["failed", "sold", "spun_off", "integrated"]


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
    `book_cents - (equity now - equity_cents)`, since a sweep or funding moves the company's
    equity and the owner's 1810 by the same amount (28.5)."""

    id: int
    company_id: int
    owner_id: int
    from_turn: int
    to_turn: int | None = None
    book_cents: int = 0
    equity_cents: int = 0
    stake_bp: int = FULL_STAKE_BP
    end_reason: EndReason | None = None

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
