"""Exploration records (docs/formulas.md 34, M18).

`GeoBlock` holds a block's hidden truth (ADR-0007: true values live in the state and the
database, read only by the sim; every `true_*` field is hidden). Every other record holds only
what has been revealed: desk-study bands, survey readings, assays, estimate ranges and study
results, which the API may show. Ranges are stored as a centre and a half-width in log space
(grades and tonnages are lognormal), with the stated confidence of balance.yaml."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

type ProjectStatus = Literal["active", "permitted", "refused", "sold", "relinquished", "lapsed"]
type StageKey = Literal[
    "survey",
    "sampling",
    "drilling",
    "estimate",
    "scoping",
    "pre_feasibility",
    "definitive",
    "permitting",
]
STAGES: Final = (
    "survey",
    "sampling",
    "drilling",
    "estimate",
    "scoping",
    "pre_feasibility",
    "definitive",
    "permitting",
)
OPEN: Final = "active"
GEOLOGY_STAGES: Final = ("survey", "sampling", "drilling", "estimate")


@dataclass(frozen=True, slots=True)
class GeoBlock:
    """One exploration block and its hidden deposit (34.1). `true_commodity` None: nothing of
    any explored commodity lies under it (the API never says so before it is tested)."""

    region: str
    index: int  # 0 .. geology.blocks_per_region - 1
    depth_m: float  # to the top of the ore; empty blocks have one too (drilling costs)
    true_commodity: str | None = None
    true_kind: str | None = None
    true_tonnage_mt: float = 0.0
    true_grade: float = 0.0  # fraction of ore that is saleable product
    true_recovery: float = 0.0
    true_infra_km: float = 0.0
    true_difficulty: float = 1.0  # permitting difficulty, x the region's permit years
    true_sensitivity: float = 0.5  # community sensitivity, 0-1


@dataclass(frozen=True, slots=True)
class SupplierLicence:
    """A supplier's exploration licence from the game's start (34.4): visible to everyone."""

    region: str
    block: int
    supplier: str  # suppliers' key (M17 suppliers.yaml)
    name: str


@dataclass(frozen=True, slots=True)
class DeskStudy:
    """A desk study of one commodity in one region (34.2). `bands`: one per block, in block
    order, once done; empty while it runs."""

    id: int
    company_id: int
    region: str
    commodity: str
    start_turn: int
    done_turn: int
    factor: float  # the range factor of the team that ran it
    bands: tuple[str, ...] = ()

    @property
    def done(self) -> bool:
        return bool(self.bands)


@dataclass(frozen=True, slots=True)
class Hole:
    """A drill hole's assay (34.2): public once drilled."""

    project_id: int
    n: int  # 1, 2, ... within the project
    turn: int
    assay: float  # grade, a fraction of ore
    factor: float  # the team's range factor when it was drilled
    cost_cents: int


@dataclass(frozen=True, slots=True)
class Project:
    """A licensed block and its pipeline (34.2). Everything here is revealed except
    `hidden_due_turn` (the month a permit is decided, drawn from the block's hidden
    difficulty), which the API never shows."""

    id: int
    company_id: int
    region: str
    block: int
    licence_turn: int
    expires_turn: int  # the licence's last month + 1
    renewals: int = 0
    status: ProjectStatus = "active"
    commodity: str | None = None  # what is being explored for (the anomaly's, or chosen)
    stage: str | None = None  # the stage running now
    stage_start: int | None = None
    stage_due: int | None = None  # the month it reports (None for drilling)
    holes_left: int = 0  # holes still to drill in the programme
    paused_until: int | None = None  # a drilling accident's pause
    spent_cents: int = 0
    # survey
    reading: str | None = None  # none, weak or strong
    kind: str | None = None  # the deposit type the survey reads (revealed)
    # sampling: the first grade range (log centre, half-width)
    sample_center: float | None = None
    sample_hw: float | None = None
    # resource estimate
    category: str | None = None
    est_holes: int = 0
    est_grade_center: float | None = None
    est_grade_hw: float | None = None
    est_tonnage_center: float | None = None  # log Mt
    est_tonnage_hw: float | None = None
    est_turn: int | None = None
    # feasibility (the latest study)
    level: str | None = None
    capex_center: float | None = None  # log dollars
    capex_hw: float | None = None
    opex_center: float | None = None  # log dollars a tonne of product
    opex_hw: float | None = None
    recovery_center: float | None = None
    recovery_hw: float | None = None
    npv_lo_cents: int | None = None
    npv_mid_cents: int | None = None
    npv_hi_cents: int | None = None
    study_turn: int | None = None
    # permitting
    permit_start: int | None = None
    hidden_due_turn: int | None = None
    benefit: bool = False  # a benefit agreement is signed
    pushes: int = 0  # times the company pushed on through a protest
    protest_turn: int | None = None  # the month an unanswered protest event is shown
    protests: int = 0
    permit_turn: int | None = None  # the month a permit or refusal came
    # sale
    sold_to: str | None = None
    sale_cents: int = 0
    ended_turn: int | None = None

    @property
    def is_open(self) -> bool:
        return self.status == OPEN

    @property
    def busy(self) -> bool:
        """A geologist is on it: the geology stages (34.2's geologist-months). Feasibility is
        engineers' work and permitting lawyers' (M18 decision)."""
        return self.is_open and self.stage in GEOLOGY_STAGES


def log_range(center: float, hw: float) -> tuple[float, float]:
    return math.exp(center - hw), math.exp(center + hw)
