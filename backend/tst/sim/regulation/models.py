"""Frozen regulation records (docs/formulas.md 48). GameState holds designations, designation
warnings, duties, cases, structural watches and orders; persisted in `regulation_record`
(migration 0055). History's designations and cases to 2025 are data (regulation.yaml), read by
`tst.sim.regulation.data`, not state, so a do-nothing game's history posts and logs nothing.

A case's stage end (`due_turn`) and every outcome are drawn (stream `regulation`); the API shows
a stage's window as the range it was drawn from, never the month or the chance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.regulation.config import Conduct, DutyKind

type CaseStage = Literal["inquiry", "objections", "ruling", "appeal", "closed"]
type CaseOutcome = Literal[
    "open", "settled", "dismissed", "fined", "remedied", "structural", "annulled"
]
type DutySource = Literal["designation", "remedy", "commitment"]
type WarningSign = Literal["press", "report", "political", "board"]
type OrderStatus = Literal["open", "appealing", "spun_off", "sold", "overturned", "lapsed"]
type UnitKind = Literal["platform", "company", "products"]


@dataclass(frozen=True, slots=True)
class Designation:
    """A company designated under a regime from the model (48.1)."""

    regime: str
    company_id: int
    from_turn: int
    duties_from: int  # the duties apply from here (the regime's comply_months later)


@dataclass(frozen=True, slots=True)
class DesignationWarning:
    """A year-ahead warning of a likely designation (48.1)."""

    regime: str
    company_id: int
    turn: int


@dataclass(frozen=True, slots=True)
class Duty:
    """A duty on a company in a regulator's reach (48.2): from a designation, a ruling's
    behavioural remedy, or a settlement's commitment."""

    id: int
    company_id: int
    regulator: str
    kind: DutyKind
    from_turn: int
    source: DutySource
    regime: str | None = None
    case_id: int | None = None


@dataclass(frozen=True, slots=True)
class Case:
    """An investigation (48.3) with visible stages."""

    id: int
    regulator: str
    company_id: int
    conduct: Conduct
    market: str  # the category it is about (a platform's: "devices")
    opened_turn: int
    stage: CaseStage
    stage_turn: int  # when the stage began
    due_turn: int  # when it ends (drawn; never shown)
    outcome: CaseOutcome = "open"
    fine_cents: int = 0
    remedy: DutyKind | None = None
    contested: bool = False
    lobbied: int = 0  # times the company lobbied
    asked_turn: int | None = None  # the month the player's event on this stage is shown
    asked_template: str | None = None
    ruled_turn: int | None = None  # a ruling against the company
    closed_turn: int | None = None
    noncompliant: bool = False  # it kept a forbidden setting when opened (48.2)
    steps: tuple[tuple[str, int], ...] = ()  # (stage or outcome, turn), the visible record


@dataclass(frozen=True, slots=True)
class Watch:
    """Warning signs of a structural remedy (48.4), from the month the conditions first held."""

    company_id: int
    regulator: str
    market: str
    first_turn: int
    signs: tuple[tuple[WarningSign, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Order:
    """A structural order (48.4): separate a unit within `window_months`."""

    id: int
    company_id: int
    regulator: str
    case_id: int
    unit_kind: UnitKind
    unit_id: int | None  # the platform's or the subsidiary's id
    product_ids: tuple[int, ...]
    unit_label: str
    ordered_turn: int
    deadline_turn: int
    status: OrderStatus = "open"
    appeal_until: int | None = None  # drawn; never shown
    asked_turn: int | None = None
    asked_template: str | None = None
    closed_turn: int | None = None
    warned_from: int = 0  # the first warning sign's month (48.5 target 3)
