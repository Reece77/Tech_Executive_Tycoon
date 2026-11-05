"""Balance models for mergers and acquisitions (docs/formulas.md section 28, M14): the
`mna`, `antitrust` and `integration` sections of balance.yaml, validated at load (ADR-0008).
Kept here, as research/data.py, so the shared data_models.py gains only three fields."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PERSONALITIES = ("aggressive", "premium", "fast_follower", "cost_leader")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FounderPremium(_Frozen):
    base: float = Field(ge=0)  # a startup founder's premium at ambition `neutral`
    per_ambition: float  # added per attribute point of true ambition above `neutral`
    neutral: float = Field(ge=1, le=20)  # tunable-exempt: attribute scale


class DiligenceBalance(_Frozen):
    energy: int = Field(ge=0)
    months: int = Field(ge=0)
    cost_bp: int = Field(ge=0)  # bp of the target's estimated value
    min_cents: int = Field(ge=0)
    range: float = Field(ge=0, lt=1)  # the narrowed value range, a fraction
    product_range: float = Field(ge=0)  # quality and feature score shown as +- this


class ProblemsBalance(_Frozen):
    p: float = Field(ge=0, le=1)  # each hidden problem's probability per target
    tech_debt_quality: float = Field(ge=0)  # quality points lost over the first year
    tech_debt_months: int = Field(gt=0)
    key_person_flight_mult: float = Field(ge=1)
    churn_mult: float = Field(ge=1)  # customer_concentration
    churn_months: int = Field(gt=0)


class BoardBalance(_Frozen):
    bar: float = Field(ge=0)  # a listed target's board accepts a premium at least this
    sd: float = Field(ge=0)  # + N(0, sd), drawn once per approach


class TenderBalance(_Frozen):
    energy: int = Field(ge=0)
    floor: float  # chance = clamp((premium - floor) / span, 0, cap) - defence
    span: float = Field(gt=0)
    cap: float = Field(ge=0, le=1)
    defence: float = Field(ge=0, le=1)  # an aggressive target's defence
    fee_bp: int = Field(ge=0)  # a failed tender's fees, bp of the price
    block_months: int = Field(ge=0)


class MnaBalance(_Frozen):
    min_arr_cents: int = Field(ge=0)  # below this ARR a company is valued as an acqui-hire
    min_value_per_builder_cents: int = Field(ge=0)
    range: float = Field(ge=0, lt=1)  # a private company's displayed value range, +-
    diligence: DiligenceBalance
    problems: ProblemsBalance
    offer_energy: int = Field(ge=0)
    premium: dict[str, float]  # reservation premium by rival personality
    founder_premium: FounderPremium
    distress_discount: float = Field(ge=0)
    distress_months: float = Field(ge=0)  # cash covering fewer months of costs than this
    counter_sd: float = Field(ge=0)
    talks_block_months: int = Field(ge=0)
    board: BoardBalance
    tender: TenderBalance
    closing_months: int = Field(ge=0)
    sweep_months: float = Field(ge=0)  # a brand's cash above this many months of costs
    directive_energy: int = Field(ge=0)
    acquired_flag_months: int = Field(ge=0)  # Org flags acquired units this long
    rival_rate: float = Field(ge=0, le=1)  # an incumbent's quarterly chance to buy a startup
    rival_cash_months: float = Field(ge=0)
    cpo_limit_mult: float = Field(ge=0)  # the CPO pitches startups under limit x this
    pitch_synergy: float = Field(ge=0, le=1)  # an integration pitch's saving, of monthly costs
    pitch_bid_premium: float = Field(ge=0)  # a pitched bid over a listed target's market cap

    @model_validator(mode="after")
    def _personalities(self) -> Self:
        if sorted(self.premium) != sorted(PERSONALITIES):
            raise ValueError(f"mna.premium needs exactly {PERSONALITIES}")
        return self


class StrictnessStep(_Frozen):
    from_year: int
    strictness: float = Field(ge=0)


class AntitrustBalance(_Frozen):
    review: float = Field(gt=0, lt=1)  # combined share from which a deal is reviewed
    block: float = Field(gt=0, le=1)  # combined share from which it is blocked
    review_months: tuple[int, int]  # uniform, inclusive
    strictness: tuple[StrictnessStep, ...]  # by year; the last step holds after it

    @model_validator(mode="after")
    def _order(self) -> Self:
        if not self.review < self.block:
            raise ValueError("antitrust.review must be below antitrust.block")
        lo, hi = self.review_months
        if not 0 < lo <= hi:
            raise ValueError("antitrust.review_months must be 0 < low <= high")
        years = [s.from_year for s in self.strictness]
        if not years or years != sorted(years):
            raise ValueError("antitrust.strictness steps must be in year order")
        return self

    def strictness_in(self, year: int) -> float:
        steps = [s for s in self.strictness if s.from_year <= year]
        return (steps[-1] if steps else self.strictness[0]).strictness


class IntegrationBalance(_Frozen):
    months: int = Field(gt=0)  # culture clash and flight last this long
    flight_brand: float = Field(ge=0, le=1)  # a kept brand's key people, a month
    flight_base: float = Field(ge=0, le=1)  # an integrated key person, a month
    flight_per_distance: float = Field(ge=0)  # + this x personality distance
    clash: float = Field(ge=0, le=1)  # morale moves this x distance of the gap a month
    distance_span: float = Field(gt=0)  # attribute points of mean trait gap = distance 1
    max_per_product: int = Field(ge=0)  # pool staff kept per function per product
    severance_months: float = Field(ge=0)
    churn_mult: float = Field(ge=1)
    churn_months: int = Field(ge=0)
    brand_blend: float = Field(ge=0, le=1)  # brand moves this share toward the player's
    tech_lower_share: float = Field(ge=0, le=1)  # + this x the lower research lead
