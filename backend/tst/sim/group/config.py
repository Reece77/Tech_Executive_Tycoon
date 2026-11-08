"""Schema for M16's tunables (ADR-0008, docs/formulas.md 31): `group.*` in balance.yaml. Model
definitions only (no imports from the rest of the sim), so `tst.sim.data_models` can import
them without a cycle."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

MANDATES: Final = ("grow", "margin", "return_cash")  # 31.4
FLOWS: Final = ("cost", "cost_plus", "market")  # 31.6 transfer-price kinds
# 31.4: a kept brand's directive (28.5) as a mandate
DIRECTIVE_MANDATE: Final = {"grow": "grow", "harvest": "return_cash", "defend": "margin"}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MandateBalance(_Frozen):
    """31.4: a subsidiary CEO's targets by mandate, and what each steers."""

    energy: int = Field(ge=0)  # to set a mandate
    grow_target: float = Field(gt=0)  # yearly revenue growth a "grow" CEO is judged on
    margin_target: float = Field(gt=-1, lt=1)  # operating margin a "margin" CEO is judged on
    payout_target: float = Field(ge=0, le=1)  # share of profit a "return cash" CEO pays out
    grow_keep_months: float = Field(ge=0)  # costs a "grow" subsidiary keeps before sweeping
    margin_keep_months: float = Field(ge=0)
    return_keep_months: float = Field(ge=0)
    review_misses: int = Field(ge=1)  # missed Decembers in a row before a replacement proposal
    pitch_chance: float = Field(ge=0, le=1)  # a subsidiary CEO's capital request each quarter
    pitch_months: float = Field(gt=0)  # months of its costs a request asks for

    def keep_months(self, kind: str) -> float:
        return {
            "grow": self.grow_keep_months,
            "margin": self.margin_keep_months,
            "return_cash": self.return_keep_months,
        }[kind]


class DiscountBalance(_Frozen):
    """31.7: d = clamp(base + per_segment x (segments - 1) - synergy x intra-group share)."""

    base: float = Field(ge=0, lt=1)
    per_segment: float = Field(ge=0, lt=1)
    synergy: float = Field(ge=0, lt=1)
    min: float = Field(ge=0, lt=1)
    max: float = Field(ge=0, lt=1)

    @model_validator(mode="after")
    def _check(self) -> DiscountBalance:
        if self.min > self.max:
            raise ValueError("group.discount.min must not exceed max")
        return self


class GroupBalance(_Frozen):
    """31.2-31.7: the holding company, stakes, capital actions and transfer prices."""

    stage5_revenue_cents: int = Field(gt=0)  # group revenue a year that opens the gate
    stage5_subsidiaries: int = Field(ge=1)  # or this many subsidiaries
    form_energy: int = Field(ge=0)
    form_fee: float = Field(ge=0, lt=1)  # share of market cap paid in fees (6900)
    office_monthly_cents: int = Field(ge=0)  # the holding company's group office
    control: float = Field(gt=0, le=1)  # a stake from here is consolidated
    influence: float = Field(gt=0, le=1)  # from here, the equity method; below, fair value
    seat_per_stake: float = Field(gt=0, le=1)  # one board seat per this share held by minorities
    private_discount: float = Field(ge=0, lt=1)  # a stake sale below value, unless listed
    buyout_premium: float = Field(ge=0)  # over value, buying out minorities
    max_sale: float = Field(gt=0, lt=1)  # most of a subsidiary sold while keeping control
    carve_out: tuple[float, float]  # share of a subsidiary listed at a carve-out
    spin_keep: float = Field(ge=0, lt=1)  # most of a spun-off company the group may keep
    stake_max: float = Field(gt=0, lt=1)  # most of a listed rival bought on the market
    stake_impact: float = Field(ge=0)  # price paid rises this much per 1% of the target bought
    disclosures: tuple[float, ...]  # stakes in a listed rival that are disclosed publicly
    offer_at: float = Field(gt=0, lt=1)  # from here, a full offer or no more buying
    venture: tuple[float, float]  # share of a startup bought in a funding round
    cost_plus: float = Field(ge=0)  # the margin of a "cost plus" transfer price
    fairness_band: float = Field(ge=0)  # a transfer price this far from market is unfair
    fairness_months: int = Field(ge=1)  # months unfair before the minority complaint
    complaint_discount: float = Field(ge=0, lt=1)  # on the subsidiary's value until corrected
    complaint_legal: float = Field(ge=0, lt=1)  # share of the subsidiary's revenue a year
    mandate: MandateBalance
    discount: DiscountBalance

    @model_validator(mode="after")
    def _check(self) -> GroupBalance:
        if not 0 < self.influence < self.control:
            raise ValueError("group.influence must be below group.control")
        low, high = self.carve_out
        if not 0 < low <= high <= self.max_sale:
            raise ValueError("group.carve_out must be within (0, group.max_sale]")
        low, high = self.venture
        if not 0 < low <= high < self.control:
            raise ValueError("group.venture must be within (0, group.control)")
        if list(self.disclosures) != sorted(self.disclosures):
            raise ValueError("group.disclosures must be ascending")
        return self
