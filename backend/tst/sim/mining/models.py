"""Mining records (docs/formulas.md 35, M19).

A mine is a facility of kind `mine` (ADR-0020 2): its `Facility` row holds the shared record
(owner, region, capacity, status, the staffing unit); `Mine` holds what only mines have, keyed
by the facility's id. Fields named `hidden_*` are true values the API never shows (ADR-0007):
the capex overrun until the cost is revised, the deposit's tonnage, grade and recovery, and so
the reserves left. Everything else is revealed: the estimate, the revised cost once revised,
each month's reconciled grade, output, costs and sales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

type MineStatus = Literal["building", "producing", "care", "restarting", "seized", "closed"]
type CloseReason = Literal["depleted", "chosen", "sold_to_state", "seized", "sold"]
type DealKind = Literal["contract", "offtake"]
OPEN_STATUSES: Final = ("building", "producing", "care", "restarting")
HISTORY_MONTHS: Final = 24  # tunable-exempt: months of a mine's history kept for the screen


@dataclass(frozen=True, slots=True)
class MineMonth:
    """A month of a producing mine, public (35.3)."""

    turn: int
    output_t: float  # product
    grade: float  # reconciled grade (fraction)
    price_usd_t: float  # spot that month
    cost_usd_t: float  # cash cost a t (operating + royalty + sustaining): the all-in sustaining
    revenue_cents: int
    margin_cents: int  # revenue - cash costs


@dataclass(frozen=True, slots=True)
class Mine:
    id: int  # the facility's id
    company_id: int
    project_id: int
    region: str
    block: int
    commodity: str  # geology.yaml commodity (an M17 good)
    subtype: str  # open_pit, underground, brine
    level: str  # the feasibility study's level it was built on
    capacity_t: float  # product a year at the design grade
    design_grade: float  # the study's grade centre (revealed)
    design_recovery: float  # the study's recovery centre (revealed)
    ordered_turn: int
    ready_turn: int  # the first production month
    estimate_cents: int  # the study's capex for this capacity (public)
    hidden_overrun: float  # share over the estimate (hidden until revised)
    hidden_ore_mt: float  # the deposit's true tonnage (hidden)
    hidden_grade: float  # its true grade (hidden; months reveal it as mined)
    hidden_recovery: float  # its true recovery (hidden)
    status: MineStatus = "building"
    revised_cents: int | None = None  # the whole capex once the cost to complete is revised
    capex_paid_cents: int = 0
    moved_cents: int = 0  # M18's exploration and study spend moved to 1520 at the build
    depleted_cents: int = 0  # 1520 credited so far (depletion, write-offs, state stake)
    ore_mined_mt: float = 0.0
    product_t: float = 0.0  # cumulative output
    first_output_turn: int | None = None
    # sales (35.3): None sells at spot; a group company buys at the transfer price
    buyer_id: int | None = None
    price_kind: str = "market"
    margin: float | None = None
    safety: str = "normal"
    # reclamation (35.3)
    aro_cents: int = 0  # provisioned so far (2610)
    aro_paid_cents: int = 0
    closed_turn: int | None = None
    close_reason: CloseReason | None = None
    # price crash (35.4)
    below_months: int = 0
    crash_turn: int | None = None  # the month a crash event is shown, until answered
    crash_answered: bool = False  # no new crash event until the price is above cost again
    care_since: int | None = None
    restart_due: int | None = None
    # accidents (35.4)
    stopped_until: int | None = None  # stop and investigate: no output through this month
    accident_turn: int | None = None  # an accident event shown this month, until answered
    accidents: int = 0
    # protests (35.4, M18's choices)
    protest_turn: int | None = None  # a protest event shown this month, until answered
    protests: int = 0
    benefit: bool = False  # a benefit agreement with the community is signed
    # nationalization and export bans (35.4)
    state_share: float = 0.0  # a state partner's stake
    ban_until: int | None = None  # sales only inside the region through this month
    takeover_turn: int | None = None  # a takeover event shown, until answered
    arbitration_due: int | None = None  # the award's month while fighting a seizure
    seized_book_cents: int = 0
    history: tuple[MineMonth, ...] = ()

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def capex_cents(self) -> int:
        """What the build costs as known now: the revised cost once revealed, else the
        estimate (the overrun stays hidden until then)."""
        return self.revised_cents if self.revised_cents is not None else self.estimate_cents

    @property
    def hidden_total_cents(self) -> int:
        return round(self.estimate_cents * (1 + self.hidden_overrun))

    @property
    def book_cents(self) -> int:
        return self.capex_paid_cents + self.moved_cents - self.depleted_cents

    @property
    def ore_capacity_mt(self) -> float:
        """Ore a year the mill takes: capacity at the design grade and recovery."""
        mt = 1e6  # tunable-exempt: t to Mt
        return self.capacity_t / (self.design_grade * self.design_recovery) / mt

    @property
    def hidden_ore_left_mt(self) -> float:
        return max(0.0, self.hidden_ore_mt - self.ore_mined_mt)


@dataclass(frozen=True, slots=True)
class MineDeal:
    """A sale the mine signs as seller (35.3): a fixed-price contract, or an offtake with a
    buyer inside a collar around the price at signing. Prices in dollars a t of product."""

    id: int
    mine_id: int
    kind: DealKind
    buyer: str  # a name (a supplier or trader)
    signed_turn: int
    end_turn: int  # the last month it covers
    volume_t_year: float
    signing_usd_t: float
    floor_usd_t: float
    ceiling_usd_t: float
    delivered_t: float = 0.0
    last_usd_t: float = 0.0

    def running(self, turn: int) -> bool:
        return self.signed_turn <= turn <= self.end_turn

    def price_for(self, spot: float) -> float:
        return min(self.ceiling_usd_t, max(self.floor_usd_t, spot))


@dataclass(frozen=True, slots=True)
class RivalBid:
    """A rival's offer for one of the group's permitted projects or mines (35.5), open until
    `expires_turn`."""

    id: int
    company_id: int
    supplier: str  # suppliers.yaml key
    project_id: int | None
    mine_id: int | None
    cents: int
    turn: int
    expires_turn: int
    status: Literal["open", "accepted", "declined", "lapsed"] = "open"
