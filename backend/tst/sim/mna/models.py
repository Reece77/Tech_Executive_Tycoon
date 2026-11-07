"""Frozen M&A records (docs/formulas.md section 28, M14). Hidden values (a target's
problems before diligence or closing, a board's bar, a counter's draw) live here and never
reach the API (28.8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type Problem = Literal["tech_debt", "key_person_risk", "customer_concentration"]
PROBLEMS: tuple[Problem, ...] = ("tech_debt", "key_person_risk", "customer_concentration")
type DealStatus = Literal[
    "accepted",  # agreed; closes after closing_months
    "review",  # under antitrust review
    "blocked",  # blocked at the block line; open while a remedy can still be accepted
    "refused",  # blocked after a review (final)
    "closed",
    "abandoned",  # the acquirer walked away (fees only)
    "failed",  # a hostile tender that failed
]
OPEN_DEALS: tuple[DealStatus, ...] = ("accepted", "review", "blocked")
type Mode = Literal["brand", "integrate"]
type Directive = Literal["grow", "harvest", "defend"]
# A brand's directive decides with the rival personality it maps to (28.5).
DIRECTIVE_PERSONALITY: dict[str, str] = {
    "grow": "aggressive",
    "harvest": "cost_leader",
    "defend": "premium",
}


@dataclass(frozen=True, slots=True)
class RivalListing:
    """A listed rival's sentiment S (28.1): its market cap is V_f x S."""

    company_id: int
    sentiment: float = 1.0


@dataclass(frozen=True, slots=True)
class TargetFile:
    """What one acquirer knows and has done about one target (28.2-28.3).

    `problems` is drawn when the target is first looked at and stays hidden until
    diligence finishes or the deal closes; `board_bar` is drawn once per approach to a
    listed target; `counter_cents` is a private target's one counter."""

    acquirer_id: int
    target_id: int
    problems: tuple[Problem, ...] = ()
    diligence_turn: int | None = None  # diligence started
    diligence_done_turn: int | None = None  # findings revealed from this turn
    board_bar: float | None = None
    counter_cents: int | None = None  # the counter as shown: rounded up (M15b negotiation)
    blocked_until: int | None = None  # no new bid before this turn (talks ended, tender failed)
    # M15b (negotiation, playtest 3): the counter before rounding (hidden), the rounds of
    # counters so far, and the lowballs that used up the target's patience
    counter_exact: int | None = None
    rounds: int = 0
    strikes: int = 0

    @property
    def diligenced(self) -> bool:
        return self.diligence_done_turn is not None


@dataclass(frozen=True, slots=True)
class Deal:
    """An agreed (or tendered) acquisition on its way to closing (28.3-28.4)."""

    id: int
    acquirer_id: int
    target_id: int
    price_cents: int
    cash_share: float  # 1 = all cash; the rest in the acquirer's new shares
    made_turn: int
    status: DealStatus = "accepted"
    hostile: bool = False
    close_turn: int | None = None  # due to close this turn (after review, if any)
    review_end_turn: int | None = None
    combined_share: float = 0.0  # the highest S_c (shown: the review is public)
    market: str = ""  # the market that share is in, "category/segment/region"
    blocked_draw: float | None = None  # the review's uniform, hidden; blocked if below p
    remedy_product_id: int | None = None  # the overlapping product a remedy would divest
    own_remedy_product_id: int | None = None  # M15b: the acquirer's own overlapping product
    mode: Mode | None = None  # chosen at closing
    resolved_turn: int | None = None
    loan_cents: int = 0  # a bank loan taken first to pay the cash part (20.3)


@dataclass(frozen=True, slots=True)
class Acquisition:
    """A closed deal and what followed (28.5): a kept brand (the target company stays, with
    parent_id) or an integration (its products and people moved to the acquirer)."""

    deal_id: int
    acquirer_id: int
    target_id: int
    mode: Mode
    closed_turn: int
    price_cents: int
    directive: Directive = "grow"
    distance: float = 0.0  # personality distance at closing (0-1)
    cost_before_cents: int = 0  # the target's monthly cost base before closing
    key_people: int = 0  # acquired key people at closing
    pool_kept: int = 0  # pool staff who became individuals
    let_go: int = 0  # pool staff let go with severance
    departed: int = 0  # acquired key people who have left since
    problems: tuple[Problem, ...] = ()  # discovered by closing at the latest
    product_ids: tuple[int, ...] = ()  # integrated products (now the acquirer's)
    unit_ids: tuple[int, ...] = ()  # the acquirer's units created for them
    person_ids: tuple[int, ...] = ()  # everyone who came over: key people and pool staff kept


@dataclass(frozen=True, slots=True)
class AcquiredPerson:
    """An acquired key person during culture clash (28.5): the flight draw runs until
    `until_turn`; `flight_mult` is 2 for the key_person_risk problem's person."""

    person_id: int
    deal_id: int
    until_turn: int
    brand: bool = False
    flight_mult: float = 1.0
