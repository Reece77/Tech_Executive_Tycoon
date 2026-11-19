"""Frozen pharmaceutical records (docs/formulas.md 55). GameState holds them; persisted in
`pharma_record` (migration 0062). Ids are max + 1 within each collection.

Hidden values (55.7, CLAUDE.md 8): a programme's and a licensable asset's `efficacy` and
`safety` are drawn when the molecule is found and never shown (the API shows the estimate's
range, from readouts so far). A trial's, a review's, an inspection's and a seeded rule's outcomes
are drawn when they happen, never before, so no other stored field holds a future result. A
submission's `due_turn` is drawn at filing and never shown (the API shows the review's range)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.pharma.config import Area, Design, Modality, PlantKind, Stage

type ProgrammeStatus = Literal[
    "active", "ready", "failed", "stopped", "marketed", "withdrawn", "out"
]
type ReviewStatus = Literal["review", "approved", "crl", "withdrawn"]
type DealKind = Literal["in_license", "acquire", "out_license", "co_develop", "platform"]
type Finding = Literal["none", "observations", "warning_letter", "import_ban", "consent_decree"]


@dataclass(frozen=True, slots=True)
class Programme:
    """A molecule aimed at an indication (55.1). `stage` is where it is; `due_turn` its current
    stage's planned end (the design, shown). After a failed readout it waits (status failed) to
    be redesigned or stopped."""

    id: int
    company_id: int
    name: str
    indication: str
    area: Area
    modality: Modality
    stage: Stage
    start_turn: int  # the stage's start
    due_turn: int  # the stage's planned end (shown)
    efficacy: float  # HIDDEN: 0-1, never shown (55.7)
    safety: float  # HIDDEN: 0-1, never shown
    status: ProgrammeStatus = "active"
    design: Design = "standard"
    patients: int = 0  # the current trial's
    cost_cents: int = 0  # the current stage's in all (game cents), spent evenly to due_turn
    spent_cents: int = 0
    ai: bool = False  # found with AI discovery (55.2)
    origin: Literal["own", "in_license", "acquire"] = "own"
    attempt: int = 0  # re-runs of the current stage (a redesign's draws use a fresh key)
    obs_n: int = 0  # readouts so far (each one observes efficacy with noise)
    obs_eff: float = 0.0  # their mean observed efficacy (shown as a range)
    obs_safety: float = 0.0
    patent_turn: int | None = None  # the composition patent's filing (preclinical's start)
    ind_turn: int | None = None  # Phase I's first start (Hatch-Waxman's testing period)
    filed_turn: int | None = None  # the first US filing
    approved_turn: int | None = None  # the first approval anywhere
    breakthrough: bool = False  # FDA breakthrough therapy designation (after Phase II)
    accelerated: bool = False  # filed after Phase II under accelerated approval
    confirm_start: int = 0  # its confirmatory Phase III (55.3), started at approval
    confirm_due: int | None = None
    confirm_cost: int = 0
    confirm_spent: int = 0
    partner_id: int | None = None  # a co-development partner (55.5)
    partner_share: float = 0.0  # its share of costs and revenue
    ended_turn: int | None = None  # stopped, failed for good, withdrawn or licensed out


@dataclass(frozen=True, slots=True)
class Readout:
    """A stage read out (55.1): drawn at its month from the hidden values and the design."""

    id: int
    programme_id: int
    stage: Stage
    turn: int
    success: bool
    chance_lo: float  # the range shown before the readout
    chance_hi: float
    observed: float  # this readout's observed efficacy (public once read out)
    design: Design = "standard"


@dataclass(frozen=True, slots=True)
class Review:
    """A marketing application with a health regulator (55.3)."""

    id: int
    programme_id: int
    regulator: str
    application: str
    filed_turn: int
    due_turn: int  # drawn at filing; never shown
    priority: bool = False
    adcom: bool = False  # drawn at filing; shown only once the committee meets (mid-review)
    adcom_turn: int | None = None
    adcom_positive: bool | None = None
    status: ReviewStatus = "review"
    decided_turn: int | None = None
    resubmission: int = 0


@dataclass(frozen=True, slots=True)
class Authorisation:
    """A drug approved by a regulator, or registered by reliance in a region (55.3)."""

    programme_id: int
    authority: str  # a health regulator key, or "rely:<region>"
    region: str
    from_turn: int


@dataclass(frozen=True, slots=True)
class Drug:
    """A marketed drug's commercial choices (55.4): its US list price a year (real cents) and
    its commercial support (medical affairs and the sales force, 1.0 = the area's full level)."""

    programme_id: int
    list_cents: int  # real US list price a patient-year
    support: float = 1.0
    launched_turn: int = 0
    blocked_until: int = -1  # a recall stops shipments to here


@dataclass(frozen=True, slots=True)
class Hta:
    """A health-technology assessment in a region (55.4; coverage reuses 50.4's rule)."""

    programme_id: int
    region: str
    requested_turn: int
    due_turn: int  # drawn at the request; never shown
    status: Literal["pending", "covered", "refused"] = "pending"
    decided_turn: int | None = None


@dataclass(frozen=True, slots=True)
class DrugMonth:
    """A marketed drug's month (55.4): patients (real) and revenue (game cents), the US part."""

    turn: int
    programme_id: int
    company_id: int
    patients: float
    revenue_cents: int
    us_cents: int
    generic: bool = False  # exclusivity has ended somewhere it sells


@dataclass(frozen=True, slots=True)
class MarketLevel:
    """An area's market level in a region under M43a's ceiling (ceilings.py): x its data path."""

    category: str
    region: str
    level: float = 1.0


@dataclass(frozen=True, slots=True)
class SeededDrug:
    """A rival's approval after 2025 (55.5): seeded, public once approved."""

    id: int
    company_id: int
    name: str
    area: Area
    modality: Modality
    approved_turn: int
    peak_cents: int  # game cents a year at peak
    loe_turn: int


@dataclass(frozen=True, slots=True)
class Rule:
    """A seeded rule after 2025 (55.4), recorded the January it happens: `pill_fix` (the IRA's
    small-molecule window moves to the biologics') or `ira_round` (drugs selected that year)."""

    year: int
    kind: Literal["pill_fix", "ira_round"]
    drugs: int = 0
    discount: float = 0.0


@dataclass(frozen=True, slots=True)
class IraPick:
    """A drug selected for a negotiated Medicare price from January of `year`."""

    year: int
    programme_id: int | None  # the player's drug, or None for a rival's
    name: str
    discount: float


@dataclass(frozen=True, slots=True)
class Plant:
    """An own API or biologics plant (55.5)."""

    id: int
    company_id: int
    kind: PlantKind
    region: str
    ordered_turn: int
    ready_turn: int
    capex_cents: int
    quality: Literal["low", "standard", "high"] = "standard"
    closed: bool = False


@dataclass(frozen=True, slots=True)
class Supply:
    """A contract manufacturer's capacity reserved for the company (55.5)."""

    id: int
    company_id: int
    cmo: str  # pharma.yaml cmos name
    kind: PlantKind
    capacity: float  # real thousand patient-years a year
    from_turn: int
    cmo_company_id: int | None = None  # the CMO's company once it exists (2026)
    ended_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Inspection:
    id: int
    company_id: int
    regulator: str
    turn: int
    finding: Finding
    until_turn: int
    fine_cents: int = 0


@dataclass(frozen=True, slots=True)
class Recall:
    id: int
    programme_id: int
    turn: int
    cost_cents: int
    block_until: int


@dataclass(frozen=True, slots=True)
class Asset:
    """A programme a biotech offers for licence (55.5), listed each January. Its efficacy and
    safety are HIDDEN like a programme's; the estimate shown is from its readouts so far."""

    id: int
    name: str
    indication: str
    area: Area
    modality: Modality
    stage: Stage
    efficacy: float  # HIDDEN
    safety: float  # HIDDEN
    obs_n: int
    obs_eff: float
    upfront_cents: int  # game cents
    milestones_cents: int
    royalty: float
    listed_turn: int
    until_turn: int
    taken_by: int | None = None


@dataclass(frozen=True, slots=True)
class Deal:
    """A licence, partnership or platform deal (55.2, 55.5)."""

    id: int
    kind: DealKind
    company_id: int  # the player's side
    counterparty_id: int | None  # a rival company, or None for a biotech outside the game
    counterparty: str
    turn: int
    programme_id: int | None = None
    upfront_cents: int = 0
    milestones_cents: int = 0  # still to pay or receive, in all
    milestones_paid: int = 0  # how many of the three have been paid
    royalty: float = 0.0  # on the drug's revenue
    share: float = 0.0  # a co-development partner's share of costs and revenue
    fee_cents: int = 0  # a platform licence's month
    until_turn: int | None = None
