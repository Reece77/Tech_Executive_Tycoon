"""Schemas for M12b's chip tunables (ADR-0008, docs/formulas.md 26.3): the `chips.*` block
of balance.yaml. Model definitions only."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tst.sim.facilities.config import Range


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChipTypeDef(_Frozen):
    label: str = Field(min_length=1)
    per_wafer: int = Field(gt=0)  # chips per wafer
    wafer_cents: int = Field(gt=0)  # a wafer at the foundry_wafer index 1.0 (2010 $)
    advanced_node: bool = False  # short in the advanced-node crunch (26.3)


class FoundryDef(_Frozen):
    label: str = Field(min_length=1)
    price_mult: float = Field(gt=0)


class WaferContractBalance(_Frozen):
    """A wafer contract (26.3, as 22.4): wafer starts a month at a locked index."""

    energy: int = Field(ge=0)
    months: Range
    take_or_pay: float = Field(ge=0, le=1)  # share of unused wafer starts' value a month
    foundries: dict[str, FoundryDef] = Field(min_length=1)
    max_wafers: int = Field(gt=0)


class ChipYieldBalance(_Frozen):
    """yield = base + per_lead x chip-design lead, at most cap (26.3)."""

    base: float = Field(gt=0, le=1)
    per_lead: float = Field(ge=0)
    cap: float = Field(gt=0, le=1)
    domain: str  # tech_frontier.yaml domain whose lead raises yield


class GpuCapexBalance(_Frozen):
    """Own accelerators in own GPU data centres (26.3): capex x (floor + share x own unit
    cost / market chip price)."""

    floor: float = Field(ge=0, le=1)
    share: float = Field(ge=0, le=1)
    chip_type: str
    segment: str  # the chip market segment whose reference price is the market price
    compute_good: str  # compute.goods key of the data centres whose capex it cuts


class ChipsBalance(_Frozen):
    good: str  # components_history.yaml key of foundry wafers
    types: dict[str, ChipTypeDef] = Field(min_length=1)
    packaging_cents: int = Field(ge=0)  # packaging and test a chip
    chip_yield: ChipYieldBalance
    contract: WaferContractBalance
    gpu_capex: GpuCapexBalance
    price_segment: str  # the chip market segment whose reference price a bought chip costs
