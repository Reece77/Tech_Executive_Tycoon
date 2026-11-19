"""Frozen government records (docs/formulas.md 57). GameState holds the tenders (seeded and
historical, announced or not), the player's bids, protests, contracts, staff and facility
clearances, controlled (ITAR-style) products, each company's defence record (reputation), staff
reactions, and the game-wide `GovernmentWorld` (budgets' seeded growth after 2025). Persisted in
`government_record` (migration 0064_m44), one row a record.

Hidden values (57.7): a tender before its announcement month (`announce_turn > turn`), a pending
clearance's `due_turn` and `outcome`, a pending facility clearance's `due_turn`, a bid's exact
`score` (the API shows its band) and a protest's outcome before it is decided are engine-only.
Rivals' bids, award tie-breaks and every draw are never stored: they are drawn from stream
`defence` when the award is made and discarded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.government.config import Area, Buyer, ContractType, Level

type TenderStatus = Literal["open", "evaluating", "protested", "awarded", "cancelled"]
type BidStatus = Literal["submitted", "won", "lost", "disqualified", "withdrawn"]
type ContractStatus = Literal["active", "completed", "terminated", "defaulted"]
type ClearanceStatus = Literal["pending", "cleared", "denied", "lapsed"]


@dataclass(frozen=True, slots=True)
class Tender:
    """A government's tender (57.1). `value_cents` is the ceiling over the whole term at the
    game's scale; `awards` the number of awardees (an IDIQ vehicle's may be several)."""

    id: int
    government: str
    area: Area
    buyer: Buyer
    title: str
    announce_turn: int
    close_turn: int
    award_turn: int
    value_cents: int
    term_months: int
    base_months: int  # then options to term_months
    contract: ContractType
    clearance: Level
    awards: int = 1
    key: str = ""  # a historical tender's government.yaml key ("" when seeded)
    status: TenderStatus = "open"
    winners: tuple[str, ...] = ()  # published once awarded
    winner_ids: tuple[int, ...] = ()  # game companies among the winners
    winning_band: int | None = None  # the lowest awardee's score band, published
    round: int = 0  # a sustained protest re-competes it (round 1)
    protest_until: int | None = None


@dataclass(frozen=True, slots=True)
class ScoreTerms:
    """A bid's score terms (57.2), each 0-100 before weights."""

    price: float
    technical: float
    past_performance: float
    weighted: float


@dataclass(frozen=True, slots=True)
class Bid:
    """The player's bid (57.2): a product's technical proposal at a price over the term, staffed
    by a capture team. `score` is HIDDEN (the API shows its band and terms' bands)."""

    id: int
    tender_id: int
    company_id: int
    product_id: int
    price_cents: int
    team: tuple[int, ...]
    turn: int
    status: BidStatus = "submitted"
    terms: ScoreTerms | None = None
    reasons: tuple[str, ...] = ()  # requirements the bid did not meet
    protested: bool = False


@dataclass(frozen=True, slots=True)
class Protest:
    """A protest of an award (57.2): by a losing bidder (a name; the player's company id when the
    player protests). `outcome` is HIDDEN until `until`."""

    tender_id: int
    by: str
    company_id: int | None
    turn: int
    until: int
    outcome: Literal["pending", "denied", "sustained"] = "pending"
    sustain: bool = False  # HIDDEN until decided: drawn when filed


@dataclass(frozen=True, slots=True)
class ContractMonth:
    turn: int
    revenue_cents: int
    cost_cents: int
    performance: float


@dataclass(frozen=True, slots=True)
class Contract:
    """The player's government contract (57.2): delivered month by month from `start_turn`;
    options run from `base_end_turn` to `end_turn` if exercised."""

    id: int
    tender_id: int
    company_id: int
    product_id: int
    government: str
    area: Area
    buyer: Buyer
    contract: ContractType
    value_cents: int  # the awarded price over the whole term
    start_turn: int
    base_end_turn: int
    end_turn: int
    awards: int = 1  # an IDIQ vehicle's awardees share its orders
    status: ContractStatus = "active"
    performance: float = 100.0  # 0-100, the running mean of months delivered
    months: int = 0
    unable_months: int = 0
    options: Literal["pending", "exercised", "declined"] = "pending"
    revenue_cents: int = 0
    cost_cents: int = 0
    month: ContractMonth | None = None


@dataclass(frozen=True, slots=True)
class Clearance:
    """A staff clearance (57.3). `due_turn` and `outcome` are HIDDEN while pending."""

    person_id: int
    company_id: int
    level: Level
    requested_turn: int
    due_turn: int
    outcome: Literal["cleared", "denied"]
    status: ClearanceStatus = "pending"
    decided_turn: int | None = None


@dataclass(frozen=True, slots=True)
class FacilityClearance:
    """A site's facility clearance (57.3). `due_turn` is HIDDEN while pending."""

    facility_id: int
    company_id: int
    requested_turn: int
    due_turn: int
    status: ClearanceStatus = "pending"


@dataclass(frozen=True, slots=True)
class ControlledProduct:
    """A product built for defence (57.3): a controlled item from `from_turn`."""

    product_id: int
    company_id: int
    from_turn: int


@dataclass(frozen=True, slots=True)
class DefenceRecord:
    """A company's defence work (57.4): defence awards, the blocs whose militaries it supplies,
    brand lost to it by turn, staff reactions."""

    company_id: int
    awards: int = 0
    first_turn: int | None = None
    blocs: tuple[str, ...] = ()
    brand_lost: tuple[tuple[int, float], ...] = ()  # (turn, points)
    reactions: tuple[int, ...] = ()  # months a staff reaction happened
    letter_turn: int | None = None  # a queued open letter's month (its event's)
    objectors: tuple[int, ...] = ()  # people who objected to the last award
    contract_id: int | None = None  # the award the last letter is about


@dataclass(frozen=True, slots=True)
class GovernmentWorld:
    """Game-wide: budgets' seeded growth after 2025, (government, year, growth), HIDDEN before
    the year begins (57.7); the last year whose tenders were drawn; id counters."""

    growth: tuple[tuple[str, int, float], ...] = ()
    drawn_year: int | None = None
    next_tender: int = 1
    next_bid: int = 1
    next_contract: int = 1

    def growth_of(self, government: str, year: int) -> float | None:
        return next((g for k, y, g in self.growth if k == government and y == year), None)
