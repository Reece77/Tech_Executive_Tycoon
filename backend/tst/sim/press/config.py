"""Schemas for M14b's tunables (ADR-0008, docs/formulas.md 29): `press.*`, `promise.*`,
`feud.*` and `recruit.*` in balance.yaml. Model definitions only (no imports from the rest of
the sim), so `tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 29.1: the triggers, highest stakes first (the quarterly cap keeps the first ones).
MOMENT_TRIGGERS: Final = (
    "breach",  # a security breach (23.3)
    "outage",  # a critical data-centre outage (22.5)
    "layoffs",  # 10% or more of staff fired in a month
    "earnings",  # a quarterly report once listed (25.4)
    "era",  # an era the company caused (27.3)
    "launch",  # a product launch
    "acquisition",  # M14 adds it when it merges (queue_moment)
    "jab",  # a rival CEO's public jab (29.4)
    "rivalry",  # a feud reaches rivalry (29.4, storyline)
)
REMINDER: Final = "reminder"  # "you said ..." after a broken promise: outside the cap
PROMISE_KINDS: Final = ("ship", "beat", "research", "no_layoffs", "no_price_rise")
TONES: Final = ("bold", "measured", "deflect")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AudienceBalance(_Frozen):
    """a by stage: 0.5 at stages 1-2, 1.0 at stage 3, 1.5 once listed (29.1)."""

    early: float = Field(gt=0)
    scaleup: float = Field(gt=0)
    listed: float = Field(gt=0)


class PressBalance(_Frozen):
    max_per_quarter: int = Field(ge=0)
    bold_brand: float = Field(ge=0)  # % on the brand target for bold_months
    bold_months: int = Field(ge=1)
    measured_brand: float = Field(ge=0)
    measured_months: int = Field(ge=1)
    deflect_cred: float = Field(le=0)
    bold_backfire: float = Field(ge=0)  # credibility lost when results contradict a bold claim
    backfire_months: int = Field(ge=1)
    audience: AudienceBalance
    layoff_share: float = Field(gt=0, le=1)  # fired / staff in one month for a layoffs moment
    cred_start: float = Field(ge=0, le=100)
    cred_drift: float = Field(ge=0)  # points a month toward cred_start
    cred_hiring: float = Field(ge=0)  # offer-score points at credibility 100
    cred_hiring_cap: float = Field(ge=0)
    cred_history: int = Field(ge=1)
    statement_chance: float = Field(ge=0, le=1)  # a rival CEO speaks at its own launch or cut
    jab_base: float = Field(ge=0, le=1)  # chance that statement is a jab at the player
    jab_feud: float = Field(ge=0)  # + this x feud / 100
    reminder_months: tuple[int, int]  # a reminder comes this many months after a break

    @model_validator(mode="after")
    def _check(self) -> PressBalance:
        lo, hi = self.reminder_months
        if not 1 <= lo <= hi:
            raise ValueError("press.reminder_months must be 1 <= lo <= hi")
        return self


class PromiseBalance(_Frozen):
    max_open: int = Field(ge=1)
    energy: int = Field(ge=0)
    months: tuple[int, int]  # a ship, beat or research promise's deadline, months out
    fixed_months: int = Field(ge=1)  # no layoffs and no price rise run this long
    kept_brand: float = Field(ge=0)
    kept_cred: float = Field(ge=0)
    kept_months: int = Field(ge=1)
    kept_morale: float = Field(ge=0)  # no layoffs kept
    broken_brand: float = Field(ge=0)
    broken_cred: float = Field(ge=0)
    broken_months: int = Field(ge=1)
    broken_sentiment: float = Field(ge=0)
    broken_morale: float = Field(ge=0)  # no layoffs broken
    broken_trust: float = Field(ge=0)  # relationship points with the founder
    beat_span: float = Field(gt=0)  # displayed quality points of gap for ambition 1
    research_span: float = Field(gt=0)  # displayed lead points for ambition 1
    fixed_ambition: float = Field(ge=0, le=1)  # no layoffs and no price rise

    @model_validator(mode="after")
    def _check(self) -> PromiseBalance:
        lo, hi = self.months
        if not 1 <= lo < hi:
            raise ValueError("promise.months must be 1 <= lo < hi")
        return self


class FeudBalance(_Frozen):
    bold_mention: float = Field(ge=0)
    head_to_head: float = Field(ge=0)
    poach: float = Field(ge=0)
    hostile_bid: float = Field(ge=0)  # M14's hook
    decay: float = Field(ge=0)  # points a month
    rivalry: float = Field(gt=0, le=100)
    target_mult: float = Field(ge=1)
    causes_kept: int = Field(ge=1)


class RecruitBalance(_Frozen):
    replace_speed: float = Field(gt=0, le=1)  # Replace's time to fill over a normal search's
    normal_months: int = Field(ge=1)  # a plan's months from opening to a hire
    replace_window: int = Field(ge=1)  # months after a departure that Replace is offered
    replace_ratio_bp: int = Field(gt=0)
    interest_fee_bp: int = Field(ge=0)  # of the role's mid salary, per search
    interest_pool: int = Field(ge=1)  # candidates drawn per kept candidate to find the interest
    fit_weights: dict[str, float]  # leadership fit from these revealed values (29.5)
    fit_stars: tuple[int, int]

    @model_validator(mode="after")
    def _check(self) -> RecruitBalance:
        if abs(sum(self.fit_weights.values()) - 1) > 1e-9:  # tunable-exempt: tolerance
            raise ValueError("recruit.fit_weights must sum to 1")
        return self
