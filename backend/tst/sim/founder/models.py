"""M24 state (docs/formulas.md 32): the founder's stress, persona, personal book, foundation
and the company's influence by region. Everything here is public (32.8) except where marked:
an influence record's `risk` is hidden and never leaves the engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from tst.sim.errors import UnbalancedEntryError
from tst.sim.ledger import LedgerLine

type Cause = tuple[int, float, str]  # (turn, change, cause in words)
type TraitCause = tuple[int, str, float, str]  # (turn, trait, change, cause in words)

# The founder's own chart (32.2, ADR-0003): never used in a company's books.
PERSONAL_CASH: Final = "9100_personal_cash"
ENDOWMENT: Final = "9200_foundation_endowment"
PERSONAL_SPENDING: Final = "9300_personal_spending"
PERSONAL_INCOME: Final = "9400_personal_income"
PERSONAL_ACCOUNTS: Final = (PERSONAL_CASH, ENDOWMENT, PERSONAL_SPENDING, PERSONAL_INCOME)
PERSONAL_PREFIX: Final = "9"  # every personal account's code starts with this digit

type IncomeSource = Literal["secondary", "dividend", "exit", "salary"]
INCOME_SOURCES: Final = ("secondary", "dividend", "exit", "salary")


@dataclass(frozen=True, slots=True)
class PersonalEntry:
    """One balanced entry in a founder's own book (32.2): integer cents, personal accounts
    only. `source` names an income's source, or "gift" and "grant"."""

    turn: int
    person_id: int
    memo: str
    source: str
    lines: tuple[LedgerLine, ...]

    def __post_init__(self) -> None:
        if len(self.lines) < 2:  # tunable-exempt: double entry
            raise UnbalancedEntryError(f"personal entry {self.memo!r} needs two lines")
        for line in self.lines:
            if isinstance(line.amount, bool) or not isinstance(line.amount, int):
                raise UnbalancedEntryError(f"personal entry {self.memo!r}: int cents only")
            if line.account not in PERSONAL_ACCOUNTS:
                raise UnbalancedEntryError(
                    f"personal entry {self.memo!r} posts to {line.account}, not a personal account"
                )
        if sum(line.amount for line in self.lines) != 0:
            raise UnbalancedEntryError(f"personal entry {self.memo!r} does not balance")


@dataclass(frozen=True, slots=True)
class FounderLife:
    """A founder's life around the company (32.1, 32.4), kept across a serial founder's
    companies."""

    person_id: int
    stress: float
    visionary: float
    ruthless: float
    beloved: float
    reckless: float
    burnout: bool = False
    burnout_turn: int | None = None  # the month the current (or last) burnout began
    burnouts: int = 0
    recovered_turn: int | None = None  # the month the last burnout ended
    budget: int | None = None  # this month's energy budget when it reset
    rest_turn: int | None = None  # a month off taken at a burnout event
    causes: tuple[Cause, ...] = ()  # stress's last changes
    trait_causes: tuple[TraitCause, ...] = ()
    holiday_months: int = 0  # months on Holiday or off, for the record
    burn_year: int | None = None  # the calendar year of `burn_points` (runway_burn's cap)
    burn_points: float = 0.0  # runway_burn points raised that year
    headcount_mark: int | None = None  # headcount at the last December (headcount_doubled)

    def trait(self, key: str) -> float:
        value: float = getattr(self, key)
        return value


@dataclass(frozen=True, slots=True)
class Foundation:
    """The founder's foundation (32.3): its endowment is the personal book's 9200 balance."""

    person_id: int
    name: str
    cause: str  # config.CAUSES
    created_turn: int
    city: str | None = None  # local communities: a cities.yaml key
    region: str | None = None  # education: the founder's home region when created
    grants_cents: int = 0  # lifetime
    last_grant_cents: int = 0
    last_grant_turn: int | None = None
    gifts_cents: int = 0  # lifetime


@dataclass(frozen=True, slots=True)
class Influence:
    """A company's influence over one region's regulators (32.5)."""

    company_id: int
    region: str
    value: float = 0.0  # 0-100, public
    spend_cents: int = 0  # monthly lobbying, public
    risk: float = 0.0  # HIDDEN (32.5, 32.8): never in the API or a prompt
    scandal_turns: tuple[int, ...] = ()  # months a scandal broke, public once it has
    spent_cents: int = 0  # lifetime lobbying, public
    started_turn: int | None = None
    second_story: bool = False  # HIDDEN: fighting the last scandal would bring a second story
