"""Frozen medical-device records (docs/formulas.md 50). GameState holds them; persisted in
`medical_record` (migration 0058). Ids are max + 1 within each collection.

Hidden values (50.7): a submission's `due_turn` and `more_info` are drawn at filing and never
shown (the API shows the route's range); a study's, a review's, a coverage decision's, an
inspection's and a recall's outcomes are drawn when they happen, never before, so no stored
field holds a future result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.medical.config import Finding, QualityLevel, RecallClass, StudyKind

type SubmissionStatus = Literal["review", "more_info", "cleared", "refused", "withdrawn"]
type StudyStatus = Literal["running", "succeeded", "failed"]
type CoverageStatus = Literal["pending", "covered", "denied"]


@dataclass(frozen=True, slots=True)
class Design:
    """A medical product's design choices (50.2): its intended use, whether its filings carry a
    predetermined change control plan (SaMD), its monthly clinical education per region and
    whether it runs post-market surveillance."""

    product_id: int
    use: str
    pccp: bool = False
    training_cents: int = 0  # a month in each region it sells in
    surveillance: bool = False
    evidence: float = 0.0  # 0-1, from studies read out (50.3)
    cleared_features: float = 0.0  # SaMD: feature points at its last US clearance
    redesign_until: int = -1  # after a failed study, no new study before this turn


@dataclass(frozen=True, slots=True)
class Submission:
    id: int
    company_id: int
    product_id: int
    regulator: str
    route: str
    filed_turn: int
    due_turn: int  # drawn at filing; never shown
    more_info: bool  # drawn at filing; shown only once its month comes
    status: SubmissionStatus = "review"
    info_turn: int | None = None  # the month a request for more information arrived
    decided_turn: int | None = None
    pccp: bool = False


@dataclass(frozen=True, slots=True)
class Clearance:
    """A product cleared by a regulator, or by reliance in a region (50.2)."""

    product_id: int
    authority: str  # a health regulator key, or "rely:<region>"
    region: str
    from_turn: int
    route: str
    submission_id: int | None = None


@dataclass(frozen=True, slots=True)
class Study:
    id: int
    company_id: int
    product_id: int
    kind: StudyKind
    patients: int
    start_turn: int
    due_turn: int  # its planned readout (the design, shown)
    cost_cents: int  # in all, spent evenly to the readout
    spent_cents: int = 0
    status: StudyStatus = "running"
    read_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Coverage:
    product_id: int
    region: str
    requested_turn: int
    status: CoverageStatus = "pending"
    due_turn: int = 0  # drawn at the request from the shown range by evidence; never shown
    decided_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Adoption:
    product_id: int
    region: str
    share: float  # clinicians using it, 0-1


@dataclass(frozen=True, slots=True)
class PlantQuality:
    facility_id: int
    level: QualityLevel


@dataclass(frozen=True, slots=True)
class Inspection:
    id: int
    company_id: int
    regulator: str
    turn: int
    finding: Finding
    until_turn: int  # sales stopped there (an import ban, a consent decree) or a hold to here
    fine_cents: int = 0
    for_cause: bool = False


@dataclass(frozen=True, slots=True)
class Recall:
    id: int
    company_id: int
    product_id: int
    turn: int
    klass: RecallClass
    units: int  # installed units affected
    cost_cents: int
    caught_early: bool
    block_until: int


@dataclass(frozen=True, slots=True)
class Drift:
    """A regulator's review-time factor this year (seeded after 2025)."""

    regulator: str
    year: int
    factor: float
