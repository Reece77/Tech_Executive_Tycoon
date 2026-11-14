"""Schemas for M36's tunables (ADR-0008, docs/formulas.md 45): `family.*` and
`estate_tax.*` in balance.yaml. Model definitions only (no imports from the rest of the sim),
so `tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

SETTINGS: Final = ("none", "partner", "children")  # 45.1's Family setting
SCHOOLS: Final = ("standard", "elite")  # 45.3, at 12
UNIVERSITIES: Final = ("none", "standard", "top")  # 45.3, at 18
DEGREES: Final = ("engineering", "business", "design", "science", "medicine")
READINESS: Final = ("not_ready", "developing", "ready", "strong")  # 45.4's bands


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Span(_Frozen):
    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _pair(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value

    @model_validator(mode="after")
    def _order(self) -> Span:
        if self.lo > self.hi:
            raise ValueError("a span's lo must not exceed its hi")
        return self


class EducationBalance(_Frozen):
    """45.3: the education multiplier `e` and each tier's one-off cost (cents)."""

    school_age: int = Field(ge=1)
    university_age: int = Field(ge=1)
    mba_from: int = Field(ge=1)
    graduate_age: int = Field(ge=1)  # university's multiplier applies until this age
    mult: dict[str, float]  # school_*, uni_*, mba
    cents: dict[str, int]  # elite_school, uni_standard, uni_top, mba (standard school: 0)
    degree_mult: float = Field(ge=1)  # a degree's skills grow x this more at university
    degree_skills: dict[str, tuple[str, ...]]
    mba_skills: tuple[str, ...] = Field(min_length=1)
    reveal: float = Field(ge=0, lt=1)  # share of a child's range half-width an education removes

    @model_validator(mode="after")
    def _check(self) -> EducationBalance:
        need = {f"school_{s}" for s in SCHOOLS} | {f"uni_{u}" for u in UNIVERSITIES} | {"mba"}
        if set(self.mult) != need:
            raise ValueError(f"family.education.mult must define {sorted(need)}")
        if any(v <= 0 for v in self.mult.values()):
            raise ValueError("family.education.mult values must be positive")
        costs = {"elite_school", "uni_standard", "uni_top", "mba"}
        if set(self.cents) != costs:
            raise ValueError(f"family.education.cents must define {sorted(costs)}")
        if any(v < 0 for v in self.cents.values()):
            raise ValueError("family.education.cents must not be negative")
        if set(self.degree_skills) != set(DEGREES):
            raise ValueError(f"family.education.degree_skills must define {list(DEGREES)}")
        if not self.school_age < self.university_age < self.mba_from <= self.graduate_age + 1:
            raise ValueError("family.education ages must rise: school, university, MBA")
        return self


class ReadyBalance(_Frozen):
    """45.4: readiness points from displayed fit, years, seats and the board's confidence."""

    per_year: float = Field(ge=0)  # points per year in the group
    years_cap: float = Field(ge=0)  # years that count
    per_seat: float = Field(ge=0)  # points per executive seat held
    board_divisor: float = Field(gt=0)  # (board confidence - 50) / this
    bands: tuple[float, float, float]  # developing, ready, strong (points)

    @model_validator(mode="after")
    def _check(self) -> ReadyBalance:
        if list(self.bands) != sorted(self.bands):
            raise ValueError("family.ready.bands must rise")
        return self


class FamilyBalance(_Frozen):
    """45.1-45.7: the founder's family, children growing up, heirs, succession, the dynasty."""

    default_time: int = Field(ge=0)
    max_time: int = Field(gt=0)
    calm: float = Field(ge=0)  # stress points a month at max_time
    bond: float = Field(ge=0)  # relationship points a month at the extremes
    bond_pivot: float = Field(gt=0)  # family time that holds the relationship steady
    burnout_strain: float = Field(ge=0)  # relationship points lost a burnout month
    relationship_start: float = Field(ge=0, le=100)
    closeness_start: float = Field(ge=0, le=100)
    strain_below: float = Field(ge=0, le=100)
    strain_cooldown: int = Field(ge=1)  # months between strain events
    strain_time: int = Field(ge=0)  # "more time": family time at least this ...
    strain_months: int = Field(ge=1)  # ... for this many months
    counselling_cents: int = Field(ge=0)
    counselling_gain: float = Field(ge=0)
    carry_on_loss: float = Field(ge=0)
    divorce_below: float = Field(ge=0, le=100)
    divorce_months: int = Field(ge=1)
    divorce_share: float = Field(ge=0, le=1)
    divorce_beloved: float = Field(ge=0)
    inherit: float = Field(ge=0, le=1)
    trait_noise_sd: float = Field(ge=0)
    parent_interest: float = Field(ge=0, le=1)  # chance each interest comes from a parent
    partner_rate: float = Field(ge=0)  # a year
    partner_ages: Span
    partner_stress_below: float = Field(ge=0, le=100)
    partner_age_sd: float = Field(ge=0)
    marriage_months: int = Field(ge=0)  # months after meeting until the proposal
    child_rate: float = Field(ge=0)  # a year
    child_parent_age_max: int = Field(ge=1)
    max_children: int = Field(ge=0)
    start_child_ages: Span  # the setup's allowed ages
    child_pa: Span  # potential ability, uniform (hidden)
    child_skill_birth: float = Field(ge=1)  # every skill at birth
    child_skill_year: float = Field(ge=0)  # a year of childhood before develop_from
    child_skill_sd: float = Field(ge=0)
    child_growth: float = Field(ge=0)  # x growth.rate for a child's development
    develop_from: int = Field(ge=0)
    milestones: tuple[int, ...]
    reveal_rate: float = Field(ge=0, lt=1)  # hw x (1 - this x time / max_time) a month
    pa_hw_floor: float = Field(gt=0)  # potential's range never narrows below this (CLAUDE.md 8)
    mba_months: int = Field(ge=1)
    education: EducationBalance
    join_age: int = Field(ge=1)
    join_closeness: float = Field(ge=0, le=100)
    own_way_rate: float = Field(ge=0, le=1)  # a refused offer: chance the child goes their own way
    mentor_energy: int = Field(ge=0)
    mentor_growth: float = Field(ge=0)
    mentor_closeness: float = Field(ge=0)
    mentor_skills: tuple[str, ...] = Field(min_length=1)
    ready: ReadyBalance
    nepotism_morale: float = Field(le=0)
    merit_morale: float = Field(ge=0)
    step_back_from: int = Field(ge=1)
    step_back_rate: float = Field(ge=0, le=1)
    step_back_delays: int = Field(ge=0)
    heir_min_age: int = Field(ge=1)
    heir_stress: float = Field(ge=0, le=100)
    heir_persona_start: float = Field(ge=0, le=100)
    heir_persona_share: float = Field(ge=0, le=1)
    adviser_retire_age: int = Field(ge=1)
    adviser_oppose: float = Field(ge=0)  # board confidence points
    adviser_memory: int = Field(ge=1)  # opinions kept
    control_bp: int = Field(ge=0, le=10_000)  # tunable-exempt: basis points
    trust_setup_cents: int = Field(ge=0)
    trust_energy: int = Field(ge=0)
    gift_energy: int = Field(ge=0)
    dynasty_points: float = Field(ge=0)
    dynasty_unit_dollars: int = Field(gt=0)
    control_loss_points: float = Field(ge=0)
    history: int = Field(ge=1)  # family events kept for History

    @model_validator(mode="after")
    def _check(self) -> FamilyBalance:
        if self.default_time > self.max_time:
            raise ValueError("family.default_time must not exceed family.max_time")
        if self.strain_time > self.max_time:
            raise ValueError("family.strain_time must not exceed family.max_time")
        if self.divorce_below >= self.strain_below:
            raise ValueError("family.divorce_below must be below family.strain_below")
        if list(self.milestones) != sorted(set(self.milestones)):
            raise ValueError("family.milestones must rise")
        return self


class EstateYear(_Frozen):
    """One change of a region's rules: from `year` (calendar) on."""

    year: int
    rate: float = Field(ge=0, lt=1)
    exemption_cents: int = Field(ge=0)


class EstateRegion(_Frozen):
    """45.6: a home region's estate tax (the M36 dossier, docs/v5-research/estate-tax.md)."""

    rate: float = Field(ge=0, lt=1)  # the latest rate (the last history row's)
    exemption_cents: int = Field(ge=0)
    gift_tax: bool  # lifetime gifts count against the exemption and pay at the same rate
    history: tuple[EstateYear, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> EstateRegion:
        years = [h.year for h in self.history]
        if years != sorted(set(years)):
            raise ValueError("estate_tax history years must rise")
        last = self.history[-1]
        if (last.rate, last.exemption_cents) != (self.rate, self.exemption_cents):
            raise ValueError("estate_tax rate and exemption must equal the last history row")
        return self
