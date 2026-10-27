"""Finance state (docs/formulas.md section 14, ADR-0018): the cap table in shares, option
grants, SAFEs, priced rounds and their term sheets, and board seats.

GameState holds all of these for the player company (a few dozen rows at most), so every
share-count invariant can be checked in the sim without the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal

from tst.sim.data_models import Series

type HolderKind = Literal["person", "firm", "group", "pool"]
type ShareClass = Literal[
    "common", "preferred_seed", "preferred_a", "preferred_b", "safe_conversion", "option_pool"
]
type GrantStatus = Literal["active", "ended"]
type SafeKind = Literal["safe", "bridge"]
# safe: pending -> outstanding | declined; bridge: offered -> accepted -> outstanding | lapsed;
# an outstanding SAFE converts at the next priced round.
type SafeStatus = Literal[
    "pending", "declined", "offered", "accepted", "lapsed", "outstanding", "converted"
]
type RoundStatus = Literal["open", "accepted", "closed", "failed", "lapsed"]
type SheetStatus = Literal["offered", "accepted", "lapsed"]
type SeatKind = Literal["common", "investor", "independent"]
type GameOutcome = Literal["active", "bankrupt", "founder_removed"]

GAME_STATES: Final[tuple[GameOutcome, ...]] = ("active", "bankrupt", "founder_removed")
PREFERRED_CLASS: Final[dict[Series, ShareClass]] = {
    "seed": "preferred_seed",
    "a": "preferred_a",
    "b": "preferred_b",
}
SERIES_LABELS: Final[dict[Series, str]] = {"seed": "Seed", "a": "Series A", "b": "Series B"}
POOL_NAME: Final = "Option pool (unallocated)"
SAFE_HOLDERS: Final = "SAFE holders"
BRIDGE_HOLDERS: Final = "Bridge investors"


@dataclass(frozen=True, slots=True)
class CapEntry:
    """One holding on the cap table. Option grants live on OptionGrant; the unallocated
    pool is the one entry with holder_kind "pool"."""

    id: int
    company_id: int
    holder_kind: HolderKind
    share_class: ShareClass
    shares: int
    acquired_turn: int
    person_id: int | None = None  # holder_kind "person": the founder
    firm: str | None = None  # holder_kind "firm": investors.yaml key
    name: str | None = None  # holder_kind "group": e.g. "Former colleagues", "SAFE holders"
    round_id: int | None = None  # the priced round that issued these shares


@dataclass(frozen=True, slots=True)
class OptionGrant:
    """Options granted on hire from the unallocated pool (14.2)."""

    id: int
    company_id: int
    person_id: int
    employment_id: int
    granted: int
    start_turn: int  # the hire turn: vesting counts from here
    vested: int = 0
    forfeited: int = 0  # unvested options returned to the pool when the person left
    status: GrantStatus = "active"

    @property
    def outstanding(self) -> int:
        """Options still held (vested or not): granted minus forfeited."""
        return self.granted - self.forfeited

    @property
    def unvested(self) -> int:
        return self.outstanding - self.vested if self.status == "active" else 0


@dataclass(frozen=True, slots=True)
class Safe:
    """A post-money SAFE (cap only, ADR-0018 section 2), or a bridge from existing investors."""

    id: int
    company_id: int
    kind: SafeKind
    amount_cents: int
    cap_cents: int
    status: SafeStatus
    raised_turn: int  # the turn it was raised, or offered (bridge)
    resolved_turn: int | None = None  # answered, funded, lapsed
    expires_turn: int | None = None  # bridge: last turn it can be accepted
    converted_round_id: int | None = None


@dataclass(frozen=True, slots=True)
class FundingRound:
    """A priced round (14.5). Closing data is set when it closes."""

    id: int
    company_id: int
    series: Series
    status: RoundStatus
    target_cents: int
    opened_turn: int
    expires_turn: int  # last turn a term sheet can be accepted
    accepted_sheet_id: int | None = None
    closed_turn: int | None = None
    lead_firm: str | None = None
    pre_money_cents: int | None = None
    amount_cents: int | None = None
    fd_before: int | None = None
    pool_shares: int | None = None  # X
    safe_shares: int | None = None  # C
    new_shares: int | None = None  # N
    fd_pre: int | None = None  # E + X + C
    down_round: bool = False

    @property
    def price(self) -> Fraction | None:
        """Cents per share: V_pre / FD_pre."""
        if self.pre_money_cents is None or not self.fd_pre:
            return None
        return Fraction(self.pre_money_cents, self.fd_pre)

    @property
    def post_money_cents(self) -> int | None:
        if self.pre_money_cents is None or self.amount_cents is None:
            return None
        return self.pre_money_cents + self.amount_cents


@dataclass(frozen=True, slots=True)
class TermSheet:
    id: int
    round_id: int
    firm: str
    pre_money_cents: int
    amount_cents: int
    status: SheetStatus
    offered_turn: int
    expires_turn: int


@dataclass(frozen=True, slots=True)
class BoardSeat:
    """A director (14.6). Common seats hold no confidence: they always back the founder."""

    id: int
    company_id: int
    kind: SeatKind
    person_id: int  # the founder, or a generated director (role board_member)
    seated_turn: int
    firm: str | None = None  # investor seats
    round_id: int | None = None  # the round that created the seat
    confidence: float | None = None  # investor and independent seats, 0..100
    months_below: int = 0  # consecutive month ends below the removal threshold
    history: tuple[float, ...] = ()  # confidence at the last month ends, oldest first (M4b)

    @property
    def votes(self) -> bool:
        """Investor and independent directors can vote to remove the founder."""
        return self.kind != "common"
