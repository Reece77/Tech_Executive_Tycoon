"""Schemas for M37's tunables (ADR-0008, docs/formulas.md 52): `dynasty.*` in balance.yaml.
Model definitions only (no imports from the rest of the sim), so `tst.sim.data_models` can
import them without a cycle."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

LENGTHS: Final = ("standard", "dynasty")  # 52.1's Campaign length setting
HOWS: Final = ("heir", "insider", "outside")  # 52.3: a rival leader's successor


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
        if self.hi < self.lo:
            raise ValueError("a range's high end is below its low end")
        return self

    def at(self, u: float) -> float:
        return self.lo + (self.hi - self.lo) * u


class NodesRule(_Frozen):
    """52.2: seeded successors to nodes.yaml's last future node."""

    count: int = Field(ge=1)
    gap_years: float = Field(gt=0)
    gap_growth: float = Field(ge=0)
    window_months: int = Field(ge=1)
    density: Span  # the first step's transistor density gain (x)
    density_decay: float = Field(gt=0, le=1)
    wafer_mult: Span
    capital_mult: Span


class FrontierRule(_Frozen):
    """52.2: research generations continue with longer gaps and rising costs."""

    slowdown: float = Field(gt=0, le=1)
    cost_growth: float = Field(ge=0)


class MarketsRule(_Frozen):
    """52.2: category growth decays toward a mature rate."""

    mature_growth: dict[str, float] = Field(min_length=1)  # category -> fraction a year
    half_life_years: float = Field(gt=0)

    @model_validator(mode="after")
    def _default(self) -> MarketsRule:
        if "default" not in self.mature_growth:
            raise ValueError("dynasty.markets.mature_growth needs a default")
        return self

    def mature(self, category: str) -> float:
        return self.mature_growth.get(category, self.mature_growth["default"])


class CarbonRule(_Frozen):
    """52.2: carbon prices revert to a seeded long-run level (dollars a tonne)."""

    long_run: Span
    reversion: float = Field(gt=0, le=1)


class RivalsRule(_Frozen):
    """52.3: rival leaders age and hand over; entrants and relaunches."""

    retire_age: int = Field(ge=0)
    retire_rate: float = Field(ge=0, le=1)
    loss_rate: float = Field(ge=0, le=1)
    successor: dict[str, float]
    personality_change: dict[str, float]
    min_active: int = Field(ge=0)
    entrant_staff: tuple[int, int]
    entrant_cash_months: Span
    relaunch_share: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _hows(self) -> RivalsRule:
        for table in (self.successor, self.personality_change):
            if set(table) != set(HOWS):
                raise ValueError(f"dynasty.rivals: needs exactly {list(HOWS)}")
        if abs(sum(self.successor.values()) - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("dynasty.rivals.successor must sum to 1")
        return self


class MortalityRule(_Frozen):
    """52.4: the annual chance of death by age, lowered by wealth, low stress, family time."""

    from_age: int = Field(ge=0)
    by_age: dict[int, float] = Field(min_length=1)
    wealth: float = Field(gt=0, le=1)
    stress: Span  # x at stress 0 and at stress 100
    family_time: float = Field(gt=0, le=1)

    def base(self, age: int) -> float:
        """The latest entry at or below `age`; 0 below from_age."""
        if age < self.from_age:
            return 0.0
        keys = [k for k in sorted(self.by_age) if k <= age]
        return self.by_age[keys[-1]] if keys else 0.0


class DynastyBalance(_Frozen):
    start_year: int
    end_year: int
    nodes: NodesRule
    frontier: FrontierRule
    markets: MarketsRule
    carbon: CarbonRule
    rivals: RivalsRule
    mortality: MortalityRule

    @model_validator(mode="after")
    def _years(self) -> DynastyBalance:
        if self.end_year <= self.start_year:
            raise ValueError("dynasty.end_year must be after start_year")
        return self
