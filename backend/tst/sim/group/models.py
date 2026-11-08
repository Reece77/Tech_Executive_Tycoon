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


type StakeKind = Literal["market", "venture", "retained", "founder"]


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


type MandateKind = Literal["grow", "margin", "return_cash"]


@dataclass(frozen=True, slots=True)
class Mandate:
    """What a subsidiary's CEO runs it for (31.4): grow (revenue growth), margin (operating
    margin) or return cash (dividends), with a yearly capex limit (0: none) and the categories
    and regions it may enter (empty: any). Each December its board scores the CEO against it;
    `misses` counts Decembers missed in a row, and at `group.mandate.review_misses` the board
    proposes a new CEO (`proposal`). `equity_cents` is the subsidiary's equity balance at the
    last review (what it has paid up since is the change)."""

    company_id: int
    kind: MandateKind
    set_turn: int
    capex_limit_cents: int = 0
    categories: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    misses: int = 0
    last_review_turn: int | None = None
    last_result: str = ""  # "met" or "missed", with the measure, for the Group screen
    equity_cents: int = 0
    proposal: bool = False


type GroupPitchStatus = Literal["pending", "approved", "declined", "lapsed"]


@dataclass(frozen=True, slots=True)
class GroupPitch:
    """A subsidiary CEO's request to the group for capital (31.4, M13b's quarterly cadence):
    judged against its mandate; approved, the owner funds it (a mirror sweep, 28.5)."""

    id: int
    company_id: int
    person_id: int
    turn: int
    amount_cents: int
    fits_mandate: bool
    status: GroupPitchStatus = "pending"
    resolved_turn: int | None = None


@dataclass(frozen=True, slots=True)
class GroupListing:
    """A company the group listed (31.5): a carve-out (its parent keeps control) or a
    spin-off (independent). Its shares trade like a listed rival's (28.1: V_f x S)."""

    company_id: int
    listed_turn: int
    kind: Literal["carve_out", "spin_off"]
    shares: int  # shares outstanding at listing


@dataclass(frozen=True, slots=True)
class PersonalStake:
    """Shares the founder holds personally in a spun-off company (31.5): their pro-rata part
    of the distribution, a holding in their own name, not cash (M24's book holds cash only)."""

    person_id: int
    company_id: int
    stake_bp: int
    turn: int


@dataclass(frozen=True, slots=True)
class TransferFlow:
    """One company of the group supplying another (31.6): `good` (compute or chips) at a
    transfer price the holding company sets: cost, cost plus a margin, or market. Each month
    the buyer's spend on the good is supplied in-group instead: the seller's cost is
    `group.supply_cost` of it, and the buyer pays the seller the transfer price
    (4300/5900, removed on consolidation). Where either side has minorities, a price more than
    `group.fairness_band` from market for `group.fairness_months` raises a complaint."""

    id: int
    seller_id: int
    buyer_id: int
    good: str
    kind: str = "cost"
    margin: float | None = None  # cost plus: the margin (None: group.cost_plus)
    set_turn: int = 0
    unfair_months: int = 0
    complaint: bool = False
    complaint_turn: int | None = None
    trailing: tuple[int, ...] = ()  # the transfer price paid at the last month ends (12)
    ended_turn: int | None = None
