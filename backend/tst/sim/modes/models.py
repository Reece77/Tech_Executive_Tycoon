"""M15b records (docs/formulas.md 30): pure data, no state imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from tst.sim.calendar import HISTORY_START_TURN, turn_to_ym


@dataclass(frozen=True, slots=True)
class CompanyScore:
    """One company's score at a turn, with its parts (each part 0-1 except value)."""

    company_id: int
    turn: int
    score: int
    value_cents: int  # market cap, else the displayed value range's midpoint
    growth: float
    profit: float
    leadership: float
    reputation: float
    revenue_cents: int  # trailing 12 months, for the next snapshots' growth


type ModeKind = Literal["campaign", "sandbox", "scenario"]
type RivalsOption = Literal["all", "half", "none"]
type ErasOption = Literal["historical", "seeded"]
type ListKind = Literal["revenue", "places", "innovative"]
# M37 (52.1); M52 (66.3): endless, a sandbox with no end (a dynasty game continued past 2069,
# a Sandbox or a custom scenario begun so)
type CampaignLength = Literal["standard", "dynasty", "endless"]


@dataclass(frozen=True, slots=True)
class GameMode:
    """How a save plays (30.2-30.3). A save without one is a standard campaign."""

    kind: ModeKind
    start_turn: int = 0
    scenario: str | None = None  # a scenarios.yaml key
    rivals: RivalsOption = "all"
    eras: ErasOption = "historical"
    result: Literal["success", "failure"] | None = None  # a scenario's verdict at its deadline
    result_turn: int | None = None
    # M37 (52.1): standard ends in December 2039; dynasty runs to December 2069. A save
    # without a mode is a standard campaign.
    length: CampaignLength = "standard"
    # M51 (63.2): the challenge rules this game plays under (modes.challenges.RULES)
    challenges: tuple[str, ...] = ()
    # M52 (ADR-0026 point 4): a custom scenario's game (kind "scenario", `scenario` the
    # "custom/<slug>" key) keeps the SHA-256 of the scenario's canonical YAML; None otherwise
    scenario_sha256: str | None = None
    # M52 (66.1): a custom scenario's category growth changes, (category, + fraction a year)
    growth_delta: tuple[tuple[str, float], ...] = ()

    @property
    def custom(self) -> bool:
        """A custom scenario's game (66.2): kept out of M51's results and the comparisons."""
        return self.scenario_sha256 is not None

    @property
    def endless(self) -> bool:
        """A sandbox with no end (66.3): its score is shown, kept out of comparisons."""
        return self.length == "endless"


MONTH_NAMES: Final = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip


def began_in(system: str, mode: GameMode | None) -> str:
    """An LLM system prompt's "began in January 2010" for a game begun earlier (M50): the save's
    start month, whatever the mode (M57r-A, review 10 item 30: a 2008 Sandbox or custom game was
    told January 2010). The text is unchanged for a 2010 game or a later start."""
    if mode is None or mode.start_turn >= 0:
        return system
    year, month = turn_to_ym(mode.start_turn)
    return system.replace("January 2010", f"{MONTH_NAMES[month - 1]} {year}")


def world_start_turn(mode: GameMode | None) -> int:
    """The month the save's world began (ADR-0024, M50): January 2008 (turn -24) for a game
    begun before 2010 (a 2008 campaign, or a Sandbox in 2008-2009 built on the 2008 world), else
    turn 0 (a 2010 campaign, and a later start, whose world is played from 2010)."""
    if mode is not None and mode.start_turn < 0:
        return HISTORY_START_TURN
    return 0


@dataclass(frozen=True, slots=True)
class Ranking:
    """One place in one January's list (30.4)."""

    turn: int  # the January it was published
    kind: ListKind
    place: int  # 1 = first
    company_id: int
    value: float  # the list's measure: revenue cents, or the 0-1 composite


@dataclass(frozen=True, slots=True)
class QuarterMark:
    """A product's quality and customers when the last quarterly reports were written: the
    next reports' starting values ("41 -> 47"; an M13b follow-up)."""

    product_id: int
    turn: int
    quality: float
    customers: float


type VentureOutcome = Literal["exit"]


@dataclass(frozen=True, slots=True)
class Venture:
    """A company the player ran and sold (M15b addendum 10): History, the score and the Hall
    of Fame show each apart."""

    company_id: int
    name: str
    founded_turn: int
    ended_turn: int
    outcome: VentureOutcome
    buyer_id: int | None = None
    price_cents: int = 0  # the sale price, every share
    proceeds_cents: int = 0  # the founder's share of it
    kept_cents: int = 0  # what the founder kept rather than put into the next company
