"""Research state records (docs/formulas.md 21). Every record belongs to a company
(ADR-0020): leads, projects and licences are per company; era arrivals are the world's."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ProjectStatus = Literal["active", "stopped"]
type ProjectEvent = Literal["breakthrough", "dead_end"]


@dataclass(frozen=True, slots=True)
class ResearchLead:
    """R_c,d (21.1): what a company knows beyond the baseline in one domain, >= 0."""

    company_id: int
    domain: str
    lead: float


@dataclass(frozen=True, slots=True)
class ResearchProject:
    """A research project (21.3). The player's (and later any company's) has an org unit;
    a rival's research action (21.6) has none and runs until `end_turn`."""

    id: int
    company_id: int
    domain: str
    unit_id: int | None
    start_turn: int
    status: ProjectStatus = "active"
    budget_cents: int | None = None  # a month; None = whatever full funding needs
    end_turn: int | None = None  # the last month it ran (stopped) or will run (a rival's)
    recent: tuple[float, ...] = ()  # lead gained in the last months, oldest first
    gained: float = 0.0  # lead gained in total, before decay
    last_event: ProjectEvent | None = None
    last_event_turn: int | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True, slots=True)
class EraArrival:
    """An era that has arrived (21.4): when, who caused it (None on its historical date) and
    how many months before its historical date."""

    key: str
    turn: int
    company_id: int | None = None
    months_early: int = 0


@dataclass(frozen=True, slots=True)
class License:
    """A licence (21.5): `points` of the licensor's lead in a domain, granted to the
    licensee. Licensing in pays `price_cents` once; licensing out earns `royalty_bp` of the
    licensee's revenue in the domain's categories each month through `royalty_end_turn`."""

    id: int
    licensor_id: int
    licensee_id: int
    domain: str
    points: float
    turn: int
    price_cents: int = 0
    royalty_bp: int = 0
    royalty_end_turn: int | None = None

    def involves(self, a: int, b: int) -> bool:
        return {self.licensor_id, self.licensee_id} == {a, b}
