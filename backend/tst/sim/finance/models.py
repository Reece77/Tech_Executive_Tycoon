"""Finance state (docs/formulas.md section 14, ADR-0018): the cap table in shares, option
grants, SAFEs, priced rounds and their term sheets, and board seats.

GameState holds all of these for the player company (a few dozen rows at most), so every
share-count invariant can be checked in the sim without the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal

from tst.sim.data_models import Instrument, Series

type HolderKind = Literal["person", "firm", "group", "pool"]
type ShareClass = Literal[
    "common",
    "preferred_seed",
    "preferred_a",
    "preferred_b",
    "preferred_c",  # M10 (20.2)
    "preferred_d",
    "safe_conversion",
    "option_pool",
    "warrant",  # M10 (20.3): a venture lender's warrants
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
type GameOutcome = Literal["active", "bankrupt", "founder_removed", "exit"]  # exit: M14
type LoanStatus = Literal["active", "repaid", "called"]  # M10 (20.3)

GAME_STATES: Final[tuple[GameOutcome, ...]] = ("active", "bankrupt", "founder_removed", "exit")
PREFERRED_CLASS: Final[dict[Series, ShareClass]] = {
    "seed": "preferred_seed",
    "a": "preferred_a",
    "b": "preferred_b",
    "c": "preferred_c",
    "d": "preferred_d",
}
SERIES_LABELS: Final[dict[Series, str]] = {
    "seed": "Seed",
    "a": "Series A",
    "b": "Series B",
    "c": "Series C",
    "d": "Series D",
}
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
    nominee_id: int | None = None  # the founder's choice for a new common seat (M4c, 14.6)

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
    person_id: int | None  # the founder, a nominee employee, a generated director; None: empty
    seated_turn: int
    firm: str | None = None  # investor seats
    round_id: int | None = None  # the round that created the seat
    confidence: float | None = None  # investor and independent seats, 0..100
    months_below: int = 0  # consecutive month ends below the removal threshold
    history: tuple[float, ...] = ()  # confidence at the last month ends, oldest first (M4b)

    @property
    def vacant(self) -> bool:
        """An empty common seat: its nominee left, or none was named (M4c). It still votes no."""
        return self.person_id is None

    @property
    def votes(self) -> bool:
        """Investor and independent directors can vote to remove the founder."""
        return self.kind != "common"


@dataclass(frozen=True, slots=True)
class Loan:
    """Venture debt or a bank loan (M10, formulas.md 20.3). The rate is fixed at signing
    (base rate + spread) and rises only by a breach's higher-rate choice. Principal is
    re-amortized each month over the months left, so equal principal holds until a partial
    repayment shortens what is owed, never the term."""

    id: int
    company_id: int
    instrument: Instrument
    lender: str  # investors.yaml lenders key
    principal_cents: int  # the amount borrowed
    balance_cents: int  # principal still owed
    rate_bp: int  # a year
    signed_turn: int
    term_months: int
    interest_only_months: int
    round_id: int | None = None  # venture debt: the round it follows
    warrant_shares: int = 0
    status: LoanStatus = "active"
    closed_turn: int | None = None  # repaid or called
    interest_paid_cents: int = 0
    principal_paid_cents: int = 0
    breach_turn: int | None = None  # the latest covenant breach
    breaches: int = 0

    @property
    def active(self) -> bool:
        return self.status == "active"

    def month_index(self, turn: int) -> int:
        """1 in the month it was signed (phase 7 charges that month's interest)."""
        return turn - self.signed_turn + 1

    @property
    def last_turn(self) -> int:
        return self.signed_turn + self.term_months - 1
