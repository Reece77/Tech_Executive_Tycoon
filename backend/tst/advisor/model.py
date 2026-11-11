"""What an explanation holds (M25): the number, its breakdown, its trend and its drivers.
Every value here is one the player can already see on a screen (ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

type Unit = Literal["cents", "count", "points", "percent", "months"]
type Scope = Literal[
    "company", "product", "person", "account", "market", "project", "mine", "fab", "refinery"
]


@dataclass(frozen=True, slots=True)
class Item:
    """One line of a breakdown."""

    label: str
    amount: float
    unit: Unit


@dataclass(frozen=True, slots=True)
class Point:
    """One month of the trend."""

    turn: int
    value: float


@dataclass(frozen=True, slots=True)
class Driver:
    """Something that moved the number.

    `effect` is its share of the number's change, in the number's own unit, when the
    breakdown can size it (an additive line, or a factor whose share is apportioned); None
    when only the input's own move is known. `change` is the input's own move in `unit`
    (a quality fall of 6 points). A "level" driver is a term of the number as it stands
    now (a morale term), named when the number has no month-by-month split."""

    label: str
    effect: float | None = None
    change: float | None = None
    unit: Unit | None = None
    kind: Literal["change", "level"] = "change"

    @property
    def size(self) -> float:
        """What ranks drivers: the effect, else the input's move."""
        return abs(self.effect if self.effect is not None else (self.change or 0.0))


@dataclass(frozen=True, slots=True)
class MetricDef:
    key: str
    label: str
    unit: Unit
    scope: Scope
    description: str


@dataclass(frozen=True, slots=True)
class Explanation:
    metric: MetricDef
    entity: str | None
    subject: str  # what the number belongs to: the company, a product's or person's name
    value: float | None
    items: tuple[Item, ...] = ()
    note: str | None = None
    trend: tuple[Point, ...] = ()
    drivers: tuple[Driver, ...] = ()
    trend_note: str | None = None  # what the trend measures, when it differs from the value
    related: tuple[str, ...] = field(default=())  # public event lines in the last months

    @property
    def before(self) -> float | None:
        return self.trend[-2].value if len(self.trend) >= 2 else None

    @property
    def after(self) -> float | None:
        return self.trend[-1].value if self.trend else self.value
