"""Schemas for M12b's hardware tunables (ADR-0008, docs/formulas.md 26.1-26.2): the
`hardware.*` block of balance.yaml. Model definitions only, so `tst.sim.data_models` can
import them without a cycle."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BomDef(_Frozen):
    """A unit-sale category's bill of materials (26.2): `base_cents` x the good's index, plus
    the chip of `chip_type` (bought at its market price, or the company's own at cost)."""

    good: str  # components_history.yaml key
    base_cents: int = Field(gt=0)  # 2010 dollars at index 1.0
    chip_type: str  # chips.types key
    contract_fee_cents: int = Field(gt=0)  # a contract manufacturer's fee a unit in Shenzhen
    plant_slots: int = Field(default=1, ge=1)  # plant capacity units one unit takes


class ManufacturerDef(_Frozen):
    label: str = Field(min_length=1)
    fee_mult: float = Field(gt=0)


class ContractBalance(_Frozen):
    """Contract manufacturing (26.2)."""

    energy: int = Field(ge=0)
    months: Range  # a contract's term, whole months
    take_or_pay: float = Field(ge=0, le=1)  # share of the fee charged on unused volume a month
    cheap_city: str  # cities.yaml key where the fee is the base fee (Shenzhen)
    city_fee_mult: float = Field(ge=1)  # the fee elsewhere, x the base
    manufacturers: dict[str, ManufacturerDef] = Field(min_length=1)
    max_units: int = Field(gt=0)  # the most units a month one contract may cover


class YieldBalance(_Frozen):
    """An assembly plant's yield (26.2): base + skill_share x mean manufacturing skill / 20,
    times monthly noise on stream `manufacturing`, within bounds."""

    base: float = Field(gt=0, le=1)
    skill_share: float = Field(ge=0, le=1)
    noise_sd: float = Field(ge=0)
    bounds: Range


class HardwareBalance(_Frozen):
    plant_kind: str  # facility.kinds key of assembly plants
    output_good: str  # what a plant's capacity produces (not a compute good)
    capacity_category: str  # categories.yaml key of the market for spare plant capacity
    bom: dict[str, BomDef] = Field(min_length=1)  # by unit-sale category key (chips excluded)
    contract: ContractBalance
    plant_yield: YieldBalance

    @model_validator(mode="after")
    def _check(self) -> HardwareBalance:
        y = self.plant_yield
        if y.base + y.skill_share > 1:
            raise ValueError("hardware.plant_yield: base + skill_share must be at most 1")
        return self
