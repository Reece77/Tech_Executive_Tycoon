"""M26 state (docs/formulas.md 37): the founder's own investments. Startups' rounds, angel
stakes, public holdings and trades, the family office, the market index and net worth.
Everything here is public (37.7) except where marked HIDDEN: a trade's regulatory risk and
its investigation's draw and timing, a concealed conflict's discovery, and the family office
manager's true skill (a person's hidden attribute) never leave the engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

STAKE_FULL: Final = 1_000_000  # tunable-exempt: stakes are kept in millionths (ppm)

type RoundSource = Literal["founded", "funded", "venture", "angel", "backed"]
type StakeStatus = Literal["open", "acquired", "listed", "failed"]
type Mandate = Literal["conservative", "balanced", "aggressive"]
MANDATES: Final = ("conservative", "balanced", "aggressive")


@dataclass(frozen=True, slots=True)
class StartupRound:
    """A rival startup's funding round (15.4, 37.2): its founding money, a later round, a
    corporate venture investment (31.5) or a founder's cheque. Post-money is the round's
    price: `raised / angel.round_dilution`, or the venture's price when M16 set it."""

    id: int
    company_id: int
    turn: int
    raised_cents: int
    post_cents: int
    source: RoundSource


@dataclass(frozen=True, slots=True)
class AngelStake:
    """The founder's stake in one private startup (37.2), in millionths. `cost_cents` is the
    book cost (9110); `last_post_cents` the latest round's post-money, the stake's value at
    `stake_ppm x last_post / STAKE_FULL`."""

    id: int
    person_id: int
    company_id: int
    stake_ppm: int
    cost_cents: int
    from_turn: int
    last_post_cents: int
    backed: bool = False  # the founder backed it at founding (a network founder)
    founder_known: bool = False  # backed with a founder whose skills were revealed
    status: StakeStatus = "open"
    closed_turn: int | None = None
    proceeds_cents: int = 0  # cash received at an acquisition
    coi_turn: int | None = None  # a conflict-of-interest event was raised this turn
    coi_answer: str | None = None  # "disclose" or "conceal"
    coi_found_turn: int | None = None  # HIDDEN: the month a concealed conflict comes out


@dataclass(frozen=True, slots=True)
class PublicHolding:
    """Shares the founder holds in a listed company other than through the founder's own cap
    entry (37.3). `cost_cents` is the book cost (9120) of the shares held."""

    person_id: int
    company_id: int
    shares: int
    cost_cents: int


@dataclass(frozen=True, slots=True)
class PersonalTrade:
    """One buy or sell of listed shares (37.3). `sensitive_target_id` names the company of
    a deal the founder knew of at the trade (public: the founder's own knowledge); the rest
    of the insider fields are HIDDEN."""

    id: int
    person_id: int
    company_id: int
    turn: int
    side: Literal["buy", "sell"]
    shares: int
    price_cents: int
    cost_cents: int  # the 0.1% trading cost
    filed: bool = False  # a public filing (an own-company sale above personal.filing_share)
    sensitive_target_id: int | None = None
    # HIDDEN (37.3, 37.7): the regulatory risk, and the investigation drawn when the news
    # went public (the month it opens; None: never), and what the trade gained
    risk: float = 0.0
    public_turn: int | None = None  # the month the news went public
    investigate_turn: int | None = None
    gain_cents: int = 0
    resolved: bool = False  # past its window, or investigated
    investigated_turn: int | None = None  # public once it opens
    finding_turn: int | None = None


@dataclass(frozen=True, slots=True)
class FamilyOffice:
    """The founder's family office (37.4): a personal company outside the group. Its balance
    is the personal book's 9130; the manager is a generated person whose true skill is
    hidden (the API shows the revealed range)."""

    person_id: int
    formed_turn: int
    manager_id: int
    mandate: Mandate
    returns: tuple[tuple[int, float], ...] = ()  # (turn, the month's return), the last 240


@dataclass(frozen=True, slots=True)
class WealthPoint:
    """The founder's net worth at a month end (37.5), with its parts, for the history."""

    person_id: int
    turn: int
    cash_cents: int
    angel_cents: int
    public_cents: int
    family_office_cents: int
    own_stake_cents: int

    @property
    def total_cents(self) -> int:
        return (
            self.cash_cents
            + self.angel_cents
            + self.public_cents
            + self.family_office_cents
            + self.own_stake_cents
        )


@dataclass(frozen=True, slots=True)
class IndexPoint:
    """The market index at a month end (37.4): the value-weighted return of every listed
    company that month, chained from 1.0 in January 2010, and the month's return."""

    turn: int
    level: float
    month_return: float
    caps: tuple[tuple[int, int], ...] = ()  # (company_id, market cap) of every listed company


@dataclass(frozen=True, slots=True)
class NetworkEntry:
    """Someone who left the player's companies (37.2): in the founder's network from `turn`,
    the last angel.network_size kept. Their person record stays loaded while they are."""

    person_id: int
    turn: int
