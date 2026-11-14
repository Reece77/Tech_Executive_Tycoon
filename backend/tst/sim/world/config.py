"""Schemas for M28's data and tunables (ADR-0008, docs/formulas.md 41): `chain_companies.yaml`
and `world.*` in balance.yaml.

Model definitions only (no file reads, no imports from the rest of the sim beyond config), so
`tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

import itertools
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import month_to_turn
from tst.sim.mining.config import Span

FOUNDRY_GOOD: Final = "foundry_wafer"  # tunable-exempt: the foundries' good (38.3)
PERSONALITIES: Final = ("aggressive", "premium", "fast_follower", "cost_leader")
type Personality = Literal["aggressive", "premium", "fast_follower", "cost_leader"]
type MandateKind = Literal["grow", "margin", "cash"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- chain_companies.yaml ---------------------------------------------------------------------


class ChainCompanyDef(_Frozen):
    """A named chain company (41.1): a suppliers.yaml supplier or a nodes.yaml foundry."""

    key: str = Field(min_length=1)
    personality: Personality
    cost: float = Field(ge=0, le=1)  # position on the good's cost curve, 0 lowest
    country: str | None = None  # where it operates when countries.yaml sites has none
    name: str | None = None  # its name when the supplier's or foundry's would clash


class OtherProducersDef(_Frozen):
    cost: float = Field(ge=0, le=1)
    country: str = Field(min_length=1)


class ChainCompaniesFile(_Frozen):
    foundry_other_share: float = Field(ge=0, lt=1)
    world_supply: dict[str, dict[int, float]]
    demand_growth: dict[str, float]
    build_months: dict[str, int]
    companies: tuple[ChainCompanyDef, ...] = Field(min_length=1)
    others: dict[str, OtherProducersDef]

    @model_validator(mode="after")
    def _check(self) -> ChainCompaniesFile:
        keys = [c.key for c in self.companies]
        if len(set(keys)) != len(keys):
            raise ValueError("chain_companies.yaml: duplicate company keys")
        for good, points in self.world_supply.items():
            if not points or any(v <= 0 for v in points.values()):
                raise ValueError(f"chain_companies.yaml: world_supply {good} needs positive points")
        return self

    def company(self, key: str) -> ChainCompanyDef | None:
        return next((c for c in self.companies if c.key == key), None)

    def supply_at(self, good: str, turn: int) -> float:
        """World output a year of `good` in `turn`: linear between the year points (each read
        as its January), held at the ends."""
        pts = sorted((month_to_turn(f"{y}-01"), v) for y, v in self.world_supply[good].items())
        if turn <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in itertools.pairwise(pts):
            if turn <= t1:
                return v0 + (v1 - v0) * (turn - t0) / (t1 - t0)
        return pts[-1][1]


# --- balance.yaml world.* ---------------------------------------------------------------------


class UtilisationBalance(_Frozen):
    lo: float = Field(gt=0, le=1)  # a good's producers run at least this share of capacity
    hi: float = Field(gt=0, le=1)  # and at most this


class CycleBalance(_Frozen):
    """A region's demand cycle after 2025 (41.6)."""

    phi: float = Field(ge=0, lt=1)  # monthly persistence of the AR(1) around 1
    sd: float = Field(ge=0)  # monthly shock sd
    recession_rate: float = Field(ge=0, le=1)  # chance a year a recession starts in a region
    recession_depth: Span  # demand falls by this share at the trough
    boom_rate: float = Field(ge=0, le=1)
    boom_depth: Span
    months: Span  # a recession or boom lasts this many months (whole)
    global_depth: Span  # a global shock's fall in every region


class BidBalance(_Frozen):
    """Bids for the player (41.4)."""

    view_sd: float = Field(ge=0)  # sd of a rival's view of the player's value (hidden)
    tilt: dict[str, float]  # personality -> its view's lean (aggressive values others higher)
    fund: float = Field(ge=1)  # the rival must hold this x the price in cash
    monthly: float = Field(ge=0, le=1)  # chance a month a qualifying rival bids
    premium: float = Field(ge=0)  # the bid over the share price


class GroupsBalance(_Frozen):
    """Rival groups (41.3)."""

    premium: float = Field(ge=0)  # a rival pays this over the target's value
    cash_months: int = Field(ge=0)  # a buyer needs cash above this many months of costs
    fit: dict[str, dict[str, float]]  # personality -> deal kind -> preference (41.3)
    review_months: Span  # a review lasts this many months (28.4's 3-6)
    mandate: dict[str, MandateKind]  # personality -> the mandate it sets a subsidiary
    security_cover: float = Field(ge=0, le=1)  # a device or chip rival signs below this cover
    security_target: float = Field(ge=0, le=1)  # up to this cover
    security_goods: tuple[str, ...]  # inputs device and chip rivals secure
    security_need: float = Field(ge=0, le=1)  # share of a good's world demand those rivals need
    security_years: int = Field(ge=1)


class WorldBalance(_Frozen):
    start: str  # the first month chain companies run (after the history)
    hurdle: float = Field(ge=0)
    max_leverage: float = Field(gt=0)  # net debt / EBITDA under which a company may expand
    expand_share: dict[str, float]  # personality -> an expansion's size, x its capacity
    mothball_months: int = Field(ge=1)
    close_months: int = Field(ge=1)
    restart_months: int = Field(ge=1)
    elasticity: float = Field(ge=0)
    factor_min: float = Field(gt=0, le=1)
    factor_max: float = Field(ge=1)
    utilisation: UtilisationBalance
    base_utilisation: float = Field(gt=0, le=1)  # what December 2025's output is of capacity
    other_tranches: int = Field(ge=1)  # an aggregate producer's facilities along the cost curve
    other_spread: float = Field(ge=0, le=1)  # their cost positions span its own +- this
    ev_multiple: float = Field(gt=0)  # a chain company's value: EBITDA a year x this, less net debt
    cost_range: Span  # cash cost a unit x the long-run price, lowest to highest cost position
    power_share: float = Field(ge=0, le=1)  # share of a unit's cash cost that is power
    fixed_share: float = Field(ge=0)  # fixed costs a year x capacity x the long-run price
    mothball_fixed: float = Field(ge=0, le=1)  # a mothballed facility's share of fixed costs
    capex_years: float = Field(gt=0)  # capex per unit of yearly capacity x the long-run price
    life_years: int = Field(ge=1)
    open_cash_months: float = Field(ge=0)  # opening cash, months of revenue
    open_leverage: float = Field(ge=0)  # opening debt x a year's EBITDA
    open_book: float = Field(ge=0, le=1)  # opening plant at this share of its replacement capex
    interest_spread: float = Field(ge=0)  # over the base rate, a year
    asset_lending: float = Field(ge=0, le=1)  # a shortfall may also borrow to this x net plant
    repay_cash_months: float = Field(ge=0)  # cash above this many months of costs repays debt
    insolvent_months: int = Field(ge=1)  # months of cash below zero before a company fails
    outlook_spot_weight: float = Field(ge=0, le=1)  # the 3-year outlook's weight on spot
    foundry_wafer_cents: int = Field(gt=0)  # a foundry wafer's price at index 1.0 (blended)
    executives: int = Field(ge=1)  # named executives a chain company has (the CEO first)
    ceo_change: float = Field(ge=0, le=1)  # chance a year a chain company's CEO changes
    rival_mna_rate: float = Field(ge=0, le=1)  # a candidate buyer's chance a quarter (41.3)
    spinoff_discount: float = Field(ge=0, le=1)
    bid_discount: float = Field(gt=0)  # 41.4: market cap under this x a rival's valuation
    bids: BidBalance
    groups: GroupsBalance
    china_catchup: float = Field(ge=0)  # generations a year a Chinese foundry gains under controls
    china_free_pace: float = Field(ge=0)  # generations a year it gains without them (a follower)
    china_subsidy: float = Field(ge=0)  # the catch-up's state-funded research, x its capex
    china_control_goods: tuple[str, ...]  # a biting rule on these goods to China binds it
    breach_distress: float = Field(ge=1)  # a supplier in distress breaches this much more often
    breach_healthy: float = Field(gt=0, le=1)  # a healthy one this much less
    cycle: CycleBalance
    global_shock_rate: float = Field(ge=0, le=1)
    news_months: int = Field(ge=1)  # months of World news kept in the live state

    @model_validator(mode="after")
    def _check(self) -> WorldBalance:
        month_to_turn(self.start)
        missing = set(PERSONALITIES) - set(self.expand_share)
        if missing:
            raise ValueError(f"world.expand_share lacks {sorted(missing)}")
        if self.utilisation.lo > self.utilisation.hi:
            raise ValueError("world.utilisation: lo above hi")
        return self

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)
