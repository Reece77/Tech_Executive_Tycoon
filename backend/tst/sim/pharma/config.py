"""Schemas for M42's data and tunables (ADR-0008, docs/formulas.md 55): `pharma.yaml` and
`pharma.*` in balance.yaml.

Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
Money in pharma.yaml is real US dollars (or cents where a key says so); the engine converts it to
the game's economy with `pharma.scale` (M42 decision 2).
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

type Area = Literal[
    "oncology",
    "metabolic",
    "immunology",
    "neuroscience",
    "infectious_disease",
    "cardiovascular",
    "rare_disease",
]
type Modality = Literal["small_molecule", "biologic", "cell_and_gene"]
type Stage = Literal[
    "discovery", "preclinical", "phase1", "phase2", "phase3", "submission", "approved"
]
type TrialStage = Literal["phase1", "phase2", "phase3"]
type Design = Literal["lean", "standard", "large"]
type PlantKind = Literal["api", "biologics"]
type Rights = Literal["license", "acquire"]

AREAS: Final = (
    "oncology",
    "metabolic",
    "immunology",
    "neuroscience",
    "infectious_disease",
    "cardiovascular",
    "rare_disease",
)
MODALITIES: Final = ("small_molecule", "biologic", "cell_and_gene")
TRIALS: Final = ("phase1", "phase2", "phase3")
STAGES: Final = (
    "discovery",
    "preclinical",
    "phase1",
    "phase2",
    "phase3",
    "submission",
    "approved",
)
DESIGNS: Final = ("lean", "standard", "large")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _lohi(r: tuple[float, float], what: str) -> None:
    if r[0] > r[1] or r[0] < 0:
        raise ValueError(f"{what}: a range must be [lo, hi] with 0 <= lo <= hi")


# --- pharma.yaml ----------------------------------------------------------------------------


class Transitions(_Frozen):
    """Published phase transition rates (55.1): the share of programmes in a phase that move on
    (phase3: to a submission; submission: to approval)."""

    phase1: float = Field(gt=0, lt=1)
    phase2: float = Field(gt=0, lt=1)
    phase3: float = Field(gt=0, lt=1)
    submission: float = Field(gt=0, lt=1)

    def of(self, stage: str) -> float:
        return float(getattr(self, stage))

    @property
    def loa(self) -> float:
        """Likelihood of approval from Phase I: the product of the four."""
        return self.phase1 * self.phase2 * self.phase3 * self.submission


class AreaDef(_Frozen):
    key: Area
    label: str = Field(min_length=1)
    category: str = Field(min_length=1)  # categories.yaml key (family pharma)
    transitions: Transitions
    cost_mult: float = Field(gt=0)  # x the stages' cost per patient (oncology trials cost most)
    months_mult: float = Field(gt=0)  # x the stages' months
    gross_to_net: float = Field(ge=0, lt=1)  # US list-to-net discount (rebates, 340B)
    region_share: dict[str, float]  # treated patients by region, shares of the world
    sales_cents: int = Field(ge=0)  # real: a month a region of full commercial support


class StageDef(_Frozen):
    """A stage's design (55.1): its months, patients and costs in real dollars."""

    months: tuple[float, float]
    patients: tuple[int, int] = (0, 0)  # lean to large; standard is the midpoint
    cost_per_patient: float = Field(default=0, ge=0)  # real USD, before area and modality
    fixed: float = Field(default=0, ge=0)  # real USD a stage (or a month: discovery)

    @model_validator(mode="after")
    def _check(self) -> StageDef:
        _lohi(self.months, "months")
        if self.patients[0] > self.patients[1]:
            raise ValueError("patients: [lo, hi]")
        return self


class Stages(_Frozen):
    discovery: StageDef
    preclinical: StageDef
    phase1: StageDef
    phase2: StageDef
    phase3: StageDef

    def of(self, stage: str) -> StageDef:
        out: StageDef = getattr(self, stage)
        return out


class Erosion(_Frozen):
    """The cliff (55.4): the brand keeps `floor + (1 - floor) x exp(-m / months)` of its
    patients m months after exclusivity ends; generics or biosimilars sell at `price_share`
    of the brand's price."""

    floor: float = Field(ge=0, le=1)
    months: float = Field(gt=0)
    price_share: float = Field(gt=0, le=1)


class ModalityDef(_Frozen):
    key: Modality
    label: str = Field(min_length=1)
    cost_mult: float = Field(gt=0)  # trials' cost per patient
    us_data_years: int = Field(ge=0)  # NCE 5, BPCIA 12
    biologic: bool  # BLA in the US; IRA's 13 years; a biologics plant
    cogs_share: float = Field(ge=0, lt=1)  # own plant: cost of goods, x net price
    cmo_share: float = Field(ge=0, lt=1)  # through a contract manufacturer
    erosion: Erosion


class IndicationDef(_Frozen):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    area: Area
    orphan: bool = False
    prevalence_m: float = Field(gt=0)  # people living with it (or new cases a year), millions
    market_b: dict[int, float] = Field(min_length=1)  # branded sales a year, world, real $B
    growth_after: float = Field(ge=-0.05, le=0.2)  # tunable-exempt: the market a year after
    price_year: float = Field(gt=0)  # real USD: a branded therapy's US list price a year
    brands: float = Field(gt=0)  # the standard of care's weight: comparable branded therapies
    soc: float = Field(ge=0, le=1)  # the standard of care's efficacy score
    medicare_share: float = Field(ge=0, le=1)  # of US patients
    source: str = Field(min_length=1)


class UsRules(_Frozen):
    patent_years: int = Field(gt=0)  # from filing
    pte_max_years: float = Field(ge=0)  # term restoration
    pte_cap_years: float = Field(gt=0)  # at most this many years after approval
    pte_trial_share: float = Field(ge=0, le=1)  # of the IND-to-filing months restored
    orphan_years: int = Field(ge=0)


class EuRules(_Frozen):
    data_years: int = Field(ge=0)
    market_years: int = Field(ge=0)  # after data: 8 + 2
    extra_years: int = Field(ge=0)  # + 1 for a new indication (granted if efficacy is high)
    spc_max_years: float = Field(ge=0)
    spc_offset_years: float = Field(ge=0)  # SPC = approval - patent filing - this, at most max
    spc_cap_years: float = Field(gt=0)
    orphan_years: int = Field(ge=0)


class OtherRules(_Frozen):
    data_years: int = Field(ge=0)  # elsewhere: the patent and this much data protection


class Exclusivity(_Frozen):
    us: UsRules
    eu: EuRules
    other: OtherRules


class IraRound(_Frozen):
    year: int  # negotiated prices take effect in January
    drugs: int = Field(ge=0)  # selected that round
    discount: float = Field(ge=0, lt=1)  # net savings on the Medicare price


class Ira(_Frozen):
    """The 2022 Inflation Reduction Act's Medicare negotiation (55.4)."""

    small_molecule_years: int = Field(gt=0)  # from approval to a negotiated price
    biologic_years: int = Field(gt=0)
    rounds: tuple[IraRound, ...] = Field(min_length=1)
    selected: tuple[str, ...] = ()  # history's rival drugs negotiated (names), first round
    source: str = Field(min_length=1)


class RegionPrice(_Frozen):
    region: str
    price_index: float = Field(gt=0)  # a brand's net price there, x the US net price
    hta: bool  # health-technology assessment sets the price (55.4)


class Pricing(_Frozen):
    regions: tuple[RegionPrice, ...] = Field(min_length=1)
    hta_max_premium: float = Field(ge=0)  # a price above the value cap by more is not reimbursed
    hta_months: tuple[float, float]  # an HTA's months from approval to a decision
    source: str = Field(min_length=1)

    def region(self, key: str) -> RegionPrice:
        for r in self.regions:
            if r.region == key:
                return r
        raise KeyError(key)


class ReviewDef(_Frozen):
    """A health regulator's drug review (55.3): months standard and priority, and which of the
    expedited programmes it runs (from a month)."""

    regulator: str  # regulation.yaml health_regulators key
    application: str  # NDA/BLA, MAA, J-NDA, ...
    standard_months: tuple[float, float]
    priority_months: tuple[float, float] | None = None
    priority_from: str | None = None
    breakthrough_from: str | None = None  # FDASIA, July 2012
    accelerated_from: str | None = None
    adcom_share: float = Field(default=0, ge=0, le=1)  # novel filings sent to an advisory committee
    source: str = Field(min_length=1)


class Approval(_Frozen):
    reviews: tuple[ReviewDef, ...] = Field(min_length=1)
    crl_resubmit_months: tuple[float, float]  # a complete response answered and refiled
    reliance_months: tuple[float, float]  # other regions register on an FDA or EU approval
    source: str = Field(min_length=1)


class AiEvidence(_Frozen):
    phase1: float = Field(gt=0, lt=1)  # AI-discovered molecules' Phase I success (Jayatunga 2024)
    phase2: float = Field(gt=0, lt=1)
    from_month: str  # AlphaFold 2's CASP14 (November 2020): AI discovery is possible from here
    source: str = Field(min_length=1)


class RivalDrug(_Frozen):
    name: str = Field(min_length=1)
    indication: str  # an indication key
    modality: Modality
    approved: int  # year
    loe_us: int  # year US exclusivity ends
    revenue: dict[int, float]  # real USD billions by year (world)
    ira_year: int | None = None  # a negotiated Medicare price from this January


class PharmaRival(_Frozen):
    """A rival's pharmaceutical business (55.5): an incumbents.yaml company's revenue to 2025,
    its key drugs and the rest of its portfolio, and how its pipeline approves drugs after 2025."""

    company: str  # incumbents.yaml name
    generics: bool = False  # Teva, Sandoz, Viatris, Sun: the generic and biosimilar makers
    revenue: dict[int, float]  # real USD billions by year, the pharmaceutical business
    drugs: tuple[RivalDrug, ...] = ()
    focus: tuple[Area, ...] = ()  # where its seeded approvals after 2025 fall
    pipeline: tuple[str, ...] = ()  # public late-stage pipeline in 2025 (names, shown)
    source: str = Field(min_length=1)


class CmoDef(_Frozen):
    name: str = Field(min_length=1)
    region: str
    capacity: dict[PlantKind, float] = Field(min_length=1)  # real thousand patient-years a year

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self.capacity)

    quality: Literal["low", "standard", "high"] = "standard"
    revenue_2024_b: float = Field(gt=0)
    source: str = Field(min_length=1)


class PlantDef(_Frozen):
    kind: PlantKind
    label: str = Field(min_length=1)
    capex: float = Field(gt=0)  # real USD
    build_months: int = Field(gt=0)
    capacity: float = Field(gt=0)  # real thousand patient-years a year
    fixed_month: float = Field(ge=0)  # real USD a month to run it
    source: str = Field(min_length=1)


class DealTerms(_Frozen):
    """Licensing terms by stage (55.5): real USD upfront and milestones, and royalties."""

    stage: Stage
    upfront: float = Field(ge=0)
    milestones: float = Field(ge=0)  # in all, paid at Phase II, Phase III and approval
    royalty: float = Field(ge=0, lt=1)


class Licensing(_Frozen):
    terms: tuple[DealTerms, ...] = Field(min_length=1)
    acquire_mult: float = Field(
        gt=1
    )  # buying a programme outright costs this x upfront + milestones
    source: str = Field(min_length=1)

    def at(self, stage: str) -> DealTerms:
        for t in self.terms:
            if t.stage == stage:
                return t
        return self.terms[-1]


class DatedFact(_Frozen):
    month: str
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)


class PharmaFile(_Frozen):
    history_end: str
    preclinical_success: float = Field(gt=0, lt=1)  # preclinical to Phase I (no area split)
    preclinical_source: str = Field(min_length=1)
    areas: tuple[AreaDef, ...] = Field(min_length=1)
    stages: Stages
    modalities: tuple[ModalityDef, ...] = Field(min_length=1)
    indications: tuple[IndicationDef, ...] = Field(min_length=1)
    exclusivity: Exclusivity
    ira: Ira
    pricing: Pricing
    approval: Approval
    ai: AiEvidence
    rivals: tuple[PharmaRival, ...] = Field(min_length=1)
    cmos: tuple[CmoDef, ...] = Field(min_length=1)
    plants: tuple[PlantDef, ...] = Field(min_length=1)
    licensing: Licensing
    history: tuple[DatedFact, ...] = ()  # dated records shown on the Pharma screen

    def area(self, key: str) -> AreaDef:
        for a in self.areas:
            if a.key == key:
                return a
        raise KeyError(key)

    def modality(self, key: str) -> ModalityDef:
        for m in self.modalities:
            if m.key == key:
                return m
        raise KeyError(key)

    def indication(self, key: str) -> IndicationDef:
        for i in self.indications:
            if i.key == key:
                return i
        raise KeyError(key)

    def plant(self, kind: str) -> PlantDef:
        for p in self.plants:
            if p.kind == kind:
                return p
        raise KeyError(kind)

    def rival(self, company: str) -> PharmaRival | None:
        return next((r for r in self.rivals if r.company == company), None)

    @model_validator(mode="after")
    def _check(self) -> PharmaFile:
        if {a.key for a in self.areas} != set(AREAS):
            raise ValueError("pharma.yaml areas must be the seven of formulas 55.1")
        if {m.key for m in self.modalities} != set(MODALITIES):
            raise ValueError("pharma.yaml modalities must be the three of formulas 55.1")
        keys = [i.key for i in self.indications]
        if len(set(keys)) != len(keys):
            raise ValueError("pharma.yaml: an indication is listed twice")
        for a in self.areas:
            if not any(i.area == a.key for i in self.indications):
                raise ValueError(f"pharma.yaml: area {a.key} has no indication")
            if abs(sum(a.region_share.values()) - 1) > 1e-6:  # tunable-exempt: rounding tolerance
                raise ValueError(f"pharma.yaml: area {a.key} region shares must sum to 1")
        known = set(keys)
        for r in self.rivals:
            for d in r.drugs:
                if d.indication not in known:
                    raise ValueError(f"{r.company}'s {d.name}: unknown indication {d.indication}")
        return self


# --- balance.yaml pharma.* ------------------------------------------------------------------


class ScoreBalance(_Frozen):
    """A molecule's hidden efficacy and safety (55.1): normal around `mean` with `sd`, clamped
    to [0, 1]; the drug_discovery level lifts efficacy's mean."""

    mean: float = Field(ge=0, le=1)
    sd: float = Field(gt=0)
    level_lift: float = Field(ge=0)  # efficacy mean + this x (level - baseline) / 100
    ai_lift: float = Field(ge=0)  # efficacy mean + this with AI discovery


class ReadoutBalance(_Frozen):
    efficacy_weight: dict[str, float]  # by stage: logit + this x (efficacy - mean) / sd
    safety_weight: dict[str, float]  # by stage: logit + this x (safety - mean) / sd
    design_logit: dict[str, float]  # lean, standard, large
    design_months: dict[str, float]  # x months
    noise: dict[str, float]  # an observed effect's sd by stage
    shown_band: float = Field(ge=0)  # +/- around the chance shown (55.7)
    bounds: tuple[float, float]


class AiBalance(_Frozen):
    min_quality: float = Field(ge=0, le=100)  # an ai_models product at least this good
    min_level: float = Field(ge=0)  # or a drug_discovery level of at least this
    preclinical_cut: float = Field(ge=0, lt=1)  # 55.2: x (1 - this) preclinical months
    transition_lift: float = Field(ge=0)  # logit added at Phase I and II readouts
    platform_fee_cents: int = Field(ge=0)  # real: a licensee's month for the AI platform
    platform_months: int = Field(gt=0)


class DiscoveryBalance(_Frozen):
    roles: tuple[str, ...] = Field(min_length=1)  # roles.yaml keys that count as research staff
    slots_base: int = Field(ge=0)  # programmes in discovery at once with no researchers
    researchers_per_slot: int = Field(gt=0)
    level_slots: float = Field(ge=0)  # + this x (level - baseline) / 100 slots
    ai_slots: float = Field(ge=0)  # x (1 + this) with AI discovery


class DemandBalance(_Frozen):
    efficacy_weight: float = Field(ge=0)  # share weight exp(this x (efficacy - soc))
    safety_weight: float = Field(ge=0)  # exp(-this x (1 - safety))
    ramp_months: float = Field(gt=0)  # uptake 1 - exp(-m / this)
    support_floor: float = Field(ge=0, le=1)  # weight x this with no commercial support
    price_elasticity: float = Field(ge=0)  # weight x (reference / price)^this
    value_premium: float = Field(ge=0)  # the HTA's value cap: x (1 + this x (est - soc) / sd)
    horizon_years: int = Field(gt=0)  # rNPV: years of sales counted (Explain)


class ApprovalBalance(_Frozen):
    efficacy_weight: float = Field(ge=0)  # logit of the submission rate + this x (est - soc)
    priority_margin: float = Field(ge=0)  # efficacy estimate above soc for priority review
    breakthrough_margin: float = Field(ge=0)  # Phase II estimate above soc for breakthrough
    breakthrough_cut: float = Field(ge=0, lt=1)  # Phase III months x (1 - this)
    accelerated_areas: tuple[str, ...] = ()  # file after Phase II (confirmatory trial owed)
    accelerated_margin: float = Field(ge=0)  # a Phase II estimate this far above soc
    eu_extra_margin: float = Field(ge=0)  # +1 year in the EU for a significant benefit
    adcom_negative: float = Field(ge=0, le=1)  # a negative vote's chance at the mean estimate
    adcom_weight: float = Field(ge=0)  # logit lost after a negative vote
    resubmit_factor: float = Field(gt=0, le=1)  # a resubmission's chance x this


class RivalBalance(_Frozen):
    approvals_per_b: float = Field(ge=0)  # seeded approvals a year per real $B of revenue
    peak_median_b: float = Field(gt=0)  # a seeded drug's peak revenue, real $B (lognormal)
    peak_sd: float = Field(gt=0)
    ramp_years: float = Field(gt=0)
    exclusivity_years: float = Field(gt=0)  # approval to LOE for a seeded drug
    rest_decay: float = Field(ge=0, lt=1)  # the rest of a portfolio a year after 2025
    generics_base_growth: float  # a generic maker's base business a year after 2025
    cost_shares: dict[str, float]  # account -> share of revenue posted each month
    generics_cost_shares: dict[str, float]
    generics_share: float = Field(ge=0, le=1)
    modality_weights: dict[str, float]  # a seeded approval's modality
    assets_a_year: int = Field(ge=0)  # biotech programmes listed for licence each January
    asset_stages: dict[str, float]  # their stages' weights


class SupplyBalance(_Frozen):
    quality_cost_share: dict[str, float]  # low, standard, high: x the plant's running cost
    inspection_chance_year: float = Field(ge=0, le=1)
    recall_chance_year: dict[str, float]  # by quality level
    recall_cost_share: float = Field(ge=0)  # a recall: x a month's revenue of the drug
    recall_block_months: int = Field(ge=0)
    depreciation_years: int = Field(gt=0)  # own plants' straight-line life


class RulesBalance(_Frozen):
    """Seeded rules after 2025 (55.4): each January a chance that the IRA's small-molecule
    window moves to the biologics' (the 'pill penalty' fix), and the drugs selected a year."""

    pill_fix_chance: float = Field(ge=0, le=1)
    drugs_after: tuple[int, int]  # drugs selected a year after the data's rounds
    discount_after: tuple[float, float]
    ira_min_b: float = Field(ge=0)  # a modelled drug's US sales a year (real $B) to be selected


class PharmaBalance(_Frozen):
    scale: float = Field(gt=0)  # game patients and money = real x this
    scale_basis: str = Field(min_length=1)
    efficacy: ScoreBalance
    safety: ScoreBalance
    readout: ReadoutBalance
    ai: AiBalance
    discovery: DiscoveryBalance
    demand: DemandBalance
    approval: ApprovalBalance
    rivals: RivalBalance
    supply: SupplyBalance
    rules: RulesBalance
    redesign_cost_share: float = Field(ge=0)  # re-running a failed phase: x its cost (A)
    history_months: int = Field(gt=0)  # drug months kept
    co_develop_share: float = Field(gt=0, lt=1)  # a co-development partner's share
    energy: dict[str, int]  # founder energy by action
    discount_rate: float = Field(gt=0)  # rNPV: a year (Explain)
