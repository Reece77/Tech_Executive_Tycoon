"""Schemas for M24's tunables (ADR-0008, docs/formulas.md 32): `stress.*`, `personal.*`,
`foundation.*`, `persona.*` and `influence.*` in balance.yaml. Model definitions only (no
imports from the rest of the sim), so `tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

TRAITS: Final = ("visionary", "ruthless", "beloved", "reckless")  # 32.4, in display order
CAUSES: Final = ("education", "climate", "health", "local")  # 32.3
# 32.4: what raises each trait, as persona.sources keys (points per occurrence).
SOURCES: Final[dict[str, str]] = {
    "era_caused": "visionary",  # causing an era (21.4)
    "bold_answer": "visionary",  # a bold press answer (29.1)
    "new_category": "visionary",  # a launch in a category the company had not sold in
    "innovative_top": "visionary",  # a top place in Most innovative (30.4)
    "layoffs": "ruthless",  # persona.layoff_share or more of staff fired in a month
    "hostile_bid": "ruthless",  # a hostile tender (28.3)
    "poach": "ruthless",  # hiring a rival's person through a poach search (15.6)
    "broke_no_layoffs": "ruthless",  # breaking a no-layoffs promise (29.2)
    "kept_promise": "beloved",  # a kept public promise (29.2)
    "places_top": "beloved",  # a top place in Best places to work (30.4)
    "raises": "beloved",  # raises across the company: persona.raise_share of staff in a month
    "broken_promise": "reckless",  # a broken public promise (29.2)
    "covenant_breach": "reckless",  # a covenant breach (20.3)
    "failed_tender": "reckless",  # a hostile tender that failed (28.3)
    "pushed_on": "reckless",  # pushing on through a burnout month (32.1)
    # Product manager's ruling (2026-11-07, 32.7 target 3):
    "runway_burn": "reckless",  # a month burning cash with runway under persona.burn_runway_months
    "down_round": "reckless",  # a priced round closed below the last one (14.5)
    "headcount_doubled": "reckless",  # December: headcount up more than persona.headcount_growth
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StressBalance(_Frozen):
    """32.1: stress 0-100 from the share of the month's energy spent."""

    start: float = Field(ge=0, le=100)
    comfort: float = Field(gt=0, le=1)  # energy share used without strain
    load: float = Field(ge=0)  # stress per unit of share above comfort
    recover: float = Field(ge=0)  # a month at or below comfort
    holiday: float = Field(ge=0)  # a month on Holiday (or the month off a burnout grants)
    critical: float = Field(ge=0)  # each critical event answered in the month
    burnout_at: float = Field(gt=0, le=100)
    recover_below: float = Field(ge=0, le=100)  # burnout ends below this
    burnout_cut: float = Field(ge=0, lt=1)  # share of the monthly energy budget lost
    backfire_mult: float = Field(ge=1)  # a bold claim made during burnout backfires x this
    push_on: float = Field(ge=0)  # stress for pushing on at the burnout event
    history: int = Field(ge=1)  # months of causes shown

    @model_validator(mode="after")
    def _check(self) -> StressBalance:
        if self.recover_below >= self.burnout_at:
            raise ValueError("stress.recover_below must be below stress.burnout_at")
        return self


class PersonalBalance(_Frozen):
    """32.2: the founder's own book; 37.3: public shares and insider trading (M26)."""

    tax_rate: float = Field(ge=0, lt=1)  # on the founder's salary
    trade_energy: int = Field(ge=0)  # to buy or sell listed shares
    trade_cost: float = Field(ge=0, lt=1)  # share of a trade's value paid in costs
    rival_shares: int = Field(gt=0)  # notional shares outstanding of a listed rival
    filing_share: float = Field(gt=0, le=1)  # own-company sales above this share in a month
    filing_sentiment: float = Field(le=0)  # a public filing's sentiment change
    insider_months: int = Field(ge=1)  # news this soon after a trade makes it an insider trade
    sec_p: float = Field(ge=0, le=1)  # an insider trade's investigation probability
    investigation_months: int = Field(ge=1)  # an investigation opens within this many months
    finding_months: int = Field(ge=1)  # months from an investigation to its finding
    risk_per_trade: float = Field(ge=0)  # hidden regulatory risk an insider trade adds
    fine_mult: float = Field(ge=0)  # a finding's fine: this x the gain
    finding_cred: float = Field(le=0)  # credibility points
    finding_reckless: float = Field(ge=0)  # trait points
    finding_board: float = Field(le=0)  # board confidence points on every seat
    coi_cred: float = Field(le=0)  # an undisclosed conflict found later: credibility
    coi_board: float = Field(le=0)  # and board confidence on every seat
    coi_found_p: float = Field(ge=0, le=1)  # chance an undisclosed conflict is found
    coi_found_months: int = Field(ge=1)  # found within this many months
    deny_cred: float = Field(le=0)  # denying a finding: credibility points more
    dividend_yield: float = Field(ge=0, lt=1)  # a profitable listed rival's yearly dividend
    legacy_points: float = Field(ge=0)  # 37.5: legacy points per decade of net worth
    legacy_unit_dollars: int = Field(gt=0)  # net worth per unit in the legacy log term


class AngelBalance(_Frozen):
    """37.2: the founder's angel and venture investing (M26)."""

    energy: int = Field(ge=0)  # to join a startup's round
    back_energy: int = Field(ge=0)  # to back a new startup
    min_cheque_cents: int = Field(gt=0)  # the smallest cheque backing a new startup
    round_min_cents: int = Field(gt=0)  # the smallest cheque into a round
    round_window_months: int = Field(ge=1)  # a round stays open to the founder this long
    round_dilution: float = Field(gt=0, lt=1)  # a round sells this share: post = raised / this
    seed_stake: tuple[float, float]  # backing a new startup: the stake, by cheque size
    seed_full_cents: int = Field(gt=0)  # a cheque this large takes the top of seed_stake
    known_hw: float = Field(gt=0)  # a person's mean skill half-width at or below this: known
    skill_runway: float = Field(ge=0)  # a backed founder's true skill above 10: share of cash
    team: tuple[int, int]  # a backed startup's team, besides its founder

    @model_validator(mode="after")
    def _check(self) -> AngelBalance:
        lo, hi = self.seed_stake
        if not 0 < lo <= hi < 1:
            raise ValueError("angel.seed_stake must be 0 < low <= high < 1")
        if self.seed_full_cents <= self.min_cheque_cents:
            raise ValueError("angel.seed_full_cents must be above angel.min_cheque_cents")
        if not 0 <= self.team[0] <= self.team[1]:
            raise ValueError("angel.team must be 0 <= low <= high")
        return self


class MandateBalance(_Frozen):
    """One family-office mandate (37.4): its share in the market index (the rest in cash at
    the base rate) and its monthly noise."""

    index: float = Field(ge=0, le=2)
    vol: float = Field(ge=0)  # sd of the month's noise


class FamilyOfficeBalance(_Frozen):
    """37.4: the family office (M26)."""

    min_cents: int = Field(gt=0)  # personal wealth needed to form one
    energy: int = Field(ge=0)  # to form one
    move_energy: int = Field(ge=0)  # to move cash in or out
    fee: float = Field(ge=0, lt=1)  # a year, on the balance
    alpha: float  # a month per skill point above alpha_mid
    alpha_mid: float = Field(ge=1, le=20)
    mandates: dict[str, MandateBalance]
    index_months: int = Field(ge=1)  # months of the index and returns kept

    @model_validator(mode="after")
    def _check(self) -> FamilyOfficeBalance:
        if sorted(self.mandates) != sorted(("conservative", "balanced", "aggressive")):
            raise ValueError("family_office.mandates must be conservative, balanced, aggressive")
        return self


class FoundationBalance(_Frozen):
    """32.3: the founder's foundation and its yearly grants."""

    min_cents: int = Field(gt=0)  # personal cash needed to create one
    energy: int = Field(ge=0)  # to create one
    payout: float = Field(gt=0, le=1)  # share of the endowment granted each December
    beloved_cap: float = Field(ge=0)  # Beloved from a year's grants: min(cap, k x log10(g/unit))
    beloved_k: float = Field(ge=0)
    beloved_unit_dollars: int = Field(gt=0)
    hiring: float = Field(ge=0)  # education: hiring appeal in the founder's home region
    hiring_full_dollars: int = Field(gt=0)  # a year's grants reaching the full hiring effect
    brand: float = Field(ge=0)  # climate: brand-target points on consumer products
    morale: float = Field(ge=0)  # health: staff morale-target points
    pool: float = Field(ge=0)  # local: the city's hiring pools (share)
    effect_months: int = Field(ge=1)
    legacy_unit_dollars: int = Field(gt=0)  # lifetime grants per unit in the legacy log term


class PersonaBalance(_Frozen):
    """32.4: four public traits, their sources and their effects at `effect_at` or more."""

    start: float = Field(ge=0, le=100)
    drift: float = Field(ge=0)  # points a month toward start
    effect_at: float = Field(ge=0, le=100)
    history: int = Field(ge=1)  # causes shown
    sources: dict[str, float]  # points per event, by source key (persona.SOURCES)
    raise_share: float = Field(gt=0, le=1)  # raises across the company: this share of staff
    layoff_share: float = Field(gt=0, le=1)  # layoffs of this share of staff or more in a month
    builder_hiring: float = Field(ge=0)  # Visionary: offer-score points for builder roles
    feud_mult: float = Field(ge=1)  # Ruthless: rival feuds build x this
    ruthless_morale: float = Field(le=0)  # Ruthless: staff morale-target points
    antitrust_mult: float = Field(ge=1)  # Ruthless: antitrust strictness x this
    resign_mult: float = Field(gt=0, le=1)  # Beloved: resignation chance x this
    bold_brand: float = Field(ge=0)  # Beloved: brand-target points after a bold answer
    reckless_cred_target: float = Field(ge=0, le=100)  # Reckless: credibility drifts here
    bold_months: int = Field(ge=1)  # Beloved's bold-answer brand effect lasts this long
    burn_runway_months: float = Field(gt=0)  # runway_burn: a burning month under this runway
    burn_year_cap: float = Field(ge=0)  # runway_burn points at most in a calendar year
    headcount_growth: float = Field(gt=0)  # headcount_doubled: growth over the year above this

    @model_validator(mode="after")
    def _check(self) -> PersonaBalance:
        if sorted(self.sources) != sorted(SOURCES):
            raise ValueError(f"persona.sources must define exactly {sorted(SOURCES)}")
        return self


class InfluenceBalance(_Frozen):
    """32.5: lobbying, influence by region, the hidden scandal risk and scandals."""

    energy: int = Field(ge=0)  # to set a region's monthly lobbying
    rate: float = Field(ge=0)  # influence a month per sqrt(spend / unit)
    unit_dollars: int = Field(gt=0)
    decay: float = Field(ge=0, lt=1)  # share of influence lost a month
    cap: float = Field(gt=0, le=100)
    antitrust: float = Field(ge=0, le=1)  # block probability x (1 - this x I / 100)
    risk_rate: float = Field(ge=0)  # hidden risk per $1k of spend a month
    risk_ruthless: float = Field(ge=1)  # x this while Ruthless is at the effect line
    risk_decay: float = Field(ge=0, lt=1)
    risk_scale: float = Field(gt=0)  # a month's scandal chance = min(cap, risk / this)
    chance_cap: float = Field(ge=0, le=1)
    exposure: tuple[float, float]  # risk at which exposure reads medium, then high
    max_monthly_dollars: int = Field(gt=0)  # the most one region's lobbying may be set to
    scandal_cred: float = Field(le=0)
    scandal_brand: float = Field(le=0)  # brand points on every product
    scandal_fine: float = Field(ge=0, lt=1)  # share of the trailing 12 months' revenue
    scandal_ruthless: float = Field(ge=0)
    scandal_reckless: float = Field(ge=0)
    apologize_cred: float = Field(le=0)
    apologize_stress: float = Field(ge=0)
    fight_chance: float = Field(ge=0, le=1)  # fighting it brings a second story

    @model_validator(mode="after")
    def _check(self) -> InfluenceBalance:
        lo, hi = self.exposure
        if not 0 < lo < hi:
            raise ValueError("influence.exposure must be 0 < medium < high")
        return self
