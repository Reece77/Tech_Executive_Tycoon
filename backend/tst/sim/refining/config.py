"""Schemas for M20's tunables (ADR-0008, docs/formulas.md 36): `refining.*` in balance.yaml.

Model definitions only (no file reads, no imports from the rest of the sim), so
`tst.sim.data_models` can import them without a cycle.

- **Goods.** A refinery buys and sells goods. M17's commodities (silicon metal, semiconductor
  polysilicon, lithium carbonate, cobalt, NdPr oxide, gallium, germanium) are priced by M17; the
  goods M20 adds (`refining.goods`: concentrates, solar polysilicon and 300 mm wafers) are
  **derived**: a share of a commodity's price (concentrates, 36.1), its price over a divisor
  (solar polysilicon, 33.1's multiple), or a base price scaled by a commodity's index (wafers).
  A derived good's allocation in a shortage is its source commodity's (or `allocation_from`).
- **Recipes.** One per facility kind (and one per by-product of `byproduct_recovery`): the
  input good and how much of it a unit of output takes, the yield, power per unit, other
  variable cost, fixed cost and staffing (36.1).
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range

TOLERANCE: Final = 1e-9  # tunable-exempt: float tolerance

type PricedBy = Literal["share", "divisor", "index"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DerivedGoodDef(_Frozen):
    """A good M20 adds (36.1). `share`: price = `value` x the source commodity's price in
    cents a volume unit, per `per_source` source units (a concentrate: 36.1's
    `concentrate_share`). `divisor`: the source's price / `value` (solar polysilicon). `index`:
    `base_cents` x ((1 - value) + value x the source's index) (wafers)."""

    label: str = Field(min_length=1)
    volume_unit: str = Field(min_length=1)  # what one unit of the good is (t, kg, wafer)
    source: str  # commodities.yaml key it is priced off
    priced_by: PricedBy
    value: float = Field(gt=0)
    per_source: float = Field(default=1.0, gt=0)  # source volume units in one unit of this good
    base_cents: int = Field(default=0, ge=0)  # `index` goods: cents a unit at index 1.0
    allocation_from: str | None = None  # a components_history.yaml good whose allocation it shares
    note: str = ""  # where the number comes from (cited or "assumption")

    @model_validator(mode="after")
    def _check(self) -> DerivedGoodDef:
        if self.priced_by == "index" and (self.base_cents <= 0 or self.value > 1):
            raise ValueError("an index-priced good needs base_cents and a value of at most 1")
        return self


class RecipeDef(_Frozen):
    """A refinery's recipe (36.1). Output is in the output good's volume units; capacity in
    `capacity_unit`s of `per_capacity_unit` output units a year. The input a unit of output
    takes is `input_per_output` (at the stated `yield_`; a lower effective yield takes more and
    makes less, 36.3). Costs are 2010 cents: power `mwh_per_unit` x `refining.power_cents_per_mwh`
    x the region's power index (33.5); `other_cents` a unit (reagents, electrodes, consumables);
    `fixed_cents` a capacity unit a year (site, maintenance) while live."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    kind: str  # balance.facility.kinds key of the plant that runs it
    label: str = Field(min_length=1)
    input_good: str | None  # None: a by-product line takes its host plant's stream
    output_good: str
    per_capacity_unit: float = Field(default=1.0, gt=0)  # output units in one capacity unit
    yield_: float = Field(alias="yield", gt=0, le=1)  # the yield the table states (36.1)
    input_per_output: float = Field(ge=0)  # input volume units a unit of output, at yield_
    mwh_per_unit: float = Field(ge=0)  # MWh a unit of output at power index 1.0
    other_cents: int = Field(ge=0)
    fixed_cents: int = Field(ge=0)  # a capacity unit a year
    ramp_months: int = Field(ge=0)  # months from completion to full output (linear)
    semi_grade: bool = False  # needs process research (36.3)
    curbs: bool = False  # power curbs hit it (36.4)
    incident_rate: float = Field(default=0.0, ge=0, le=1)  # a plant-year at average safety (36.4)
    margin: Range  # the operating-margin band its numbers are set for (36.5 target 1)
    source_note: str = ""  # sources for the numbers, or "assumption"


class CurbHistory(_Frozen):
    """A historical power curb (36.4): plants of the curbed kinds in `region` run at `run` of
    capacity from `start` through `end` (YYYY-MM)."""

    label: str = Field(min_length=1)
    region: str
    start: str
    end: str
    run: float = Field(gt=0, le=1)
    source: str = ""


class CurbBalance(_Frozen):
    history: tuple[CurbHistory, ...] = ()
    after: str  # YYYY-MM: seeded curbs start in this month or later (after history)
    monthly: dict[str, float]  # region -> a plant's chance a month of a curb starting
    run: Range  # share of capacity run while curbed
    months: Range  # how long a seeded curb lasts (whole months)


class IncidentBalance(_Frozen):
    """Plant incidents (36.4), a critical event; the rate as M19's accidents (35.4):
    `rate x (skill_base - skill_slope x staff skill) x (cover_base - coverage)` a year."""

    skill_base: float = Field(gt=0)
    skill_slope: float = Field(ge=0)
    cover_base: float = Field(gt=0)
    fine_cents: int = Field(ge=0)  # always
    brand_points: float = Field(ge=0)  # always: brand lost on each of the company's segments
    credibility_points: float = Field(ge=0)  # always
    stop_months: int = Field(ge=0)  # stop and investigate: months at zero output
    stop_fine_share: float = Field(ge=0, le=1)  # ...and the fine is this share of the usual
    compensate_cents: int = Field(ge=0)  # compensate
    compensate_beloved: float = Field(ge=0)
    contest_ruthless: float = Field(ge=0)  # contest
    contest_legal: float = Field(ge=0, le=1)  # chance the contest costs legal_cents
    contest_legal_cents: int = Field(ge=0)


class DealBalance(_Frozen):
    energy: int = Field(ge=0)
    months: Range  # whole months a refinery contract runs
    take_or_pay: float = Field(ge=0, le=1)  # a buy contract pays this share of untaken volume


class WaferBalance(_Frozen):
    """Wafers for chips (36.2): the good a wafer plant makes, and the share of each chip
    product's wafer starts the group's own wafers can be."""

    good: str  # refining.goods key of 300 mm wafers


class RefiningBalance(_Frozen):
    goods: dict[str, DerivedGoodDef] = Field(min_length=1)
    recipes: dict[str, RecipeDef] = Field(min_length=1)
    order: tuple[str, ...] = Field(min_length=1)  # recipes run in this order (upstream first)
    power_cents_per_mwh: int = Field(gt=0)  # North America's industrial price, index 1.0
    build_energy: int = Field(ge=0)
    overrun: Range  # hidden capex overrun (fraction), drawn once at the order (M19's rule)
    semi_min_level: float = Field(ge=0)  # process level semiconductor grades need (36.3)
    semi_low_yield: float = Field(gt=0, le=1)  # the yield x this below it ("halves")
    domain: str  # tech_frontier.yaml key of the process domain
    curb: CurbBalance
    incident: IncidentBalance
    deal: DealBalance
    wafer: WaferBalance
    history_months: int = Field(gt=0)  # months of a plant's history the API shows

    @model_validator(mode="after")
    def _check(self) -> RefiningBalance:
        if sorted(self.order) != sorted(self.recipes):
            raise ValueError("refining.order must list every recipe once")
        if self.wafer.good not in self.goods:
            raise ValueError("refining.wafer.good must be a refining good")
        for key, r in self.recipes.items():
            if r.input_good is None and r.input_per_output:
                raise ValueError(f"recipe {key}: no input good, so no input_per_output")
        return self

    def recipes_of(self, kind: str) -> tuple[str, ...]:
        return tuple(k for k, r in self.recipes.items() if r.kind == kind)

    @property
    def kinds(self) -> tuple[str, ...]:
        seen: list[str] = []
        for r in self.recipes.values():
            if r.kind not in seen:
                seen.append(r.kind)
        return tuple(seen)
