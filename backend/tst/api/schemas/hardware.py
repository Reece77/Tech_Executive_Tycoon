"""Response and request schemas for the Hardware screen and the product BOM and manufacturing
panels (M12b, formulas.md 26.5).

Only what 26.5 allows: bills of materials and unit cost by line; contracts with volume, use
and take-or-pay; plants with size, utilization (own and sold), yield and staff coverage;
chips with type, yield, unit cost, internal use and market sales; wafer and component
indexes with history only. Never a person's skill, never a future index or a future era's
scheduled month.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.facilities import ComponentOut
from tst.api.schemas.people import EnergyOut


class BomLineOut(BaseModel):
    line: str = Field(description="Bill of materials, chip, assembly or packaging")
    detail: str = Field(description="Where the number comes from, in words")
    cents: int = Field(description="A unit")


class SourceOut(BaseModel):
    source: str = Field(description="plant or contract")
    label: str
    units: float = Field(description="Units made last month")
    available: float = Field(description="Units it could make last month")


class ManufacturingOut(BaseModel):
    """A device, server or chip product's bill of materials and manufacturing panel."""

    product_id: int
    name: str
    category: str
    category_label: str
    chip_type: str | None = Field(description="The product's chip type (chips) or the chip it uses")
    chip_label: str | None
    lines: list[BomLineOut]
    unit_cost_cents: int = Field(description="The sum of the lines")
    price_cents: int | None = Field(description="Its price in its first segment")
    gross_margin: float | None = Field(description="(price - unit cost) / price, 0-1")
    chip_source: str | None = Field(description="Own chip (at cost) or bought at market price")
    sources: list[SourceOut]
    units_sold: float = Field(description="Units sold last month")
    units_lost: float = Field(description="Demand last month above what it could make")
    internal_units: float = Field(description="A chip product: chips your own devices used")
    cogs_cents: int = Field(description="Last month's cost of goods")
    can_launch_source: bool = Field(description="It has a manufacturing source to launch")
    sells_units: bool = Field(
        default=True, description="False for a software product: no bill of materials (empty)"
    )


class PlantOut(BaseModel):
    facility_id: int
    name: str
    city: str | None
    city_label: str | None
    status: str = Field(description="building, live or closed")
    since: str
    units: int = Field(description="Units a month it is built for")
    live_units: int
    own_use: float = Field(description="Units run last month for your own products")
    sold_use: float = Field(description="Units run last month for contract-manufacturing customers")
    utilization: float = Field(description="Used / live units (0-1)")
    plant_yield: float | None = Field(description="Share of units run that are good (0-1)")
    staff: int
    staff_needed: int
    coverage: float
    unit_id: int | None
    unit_name: str | None
    monthly_cost_cents: int = Field(description="Fixed cost and depreciation a month")
    cost_per_good_unit_cents: int | None = Field(
        description="Last month's fixed, variable and depreciation per good unit"
    )
    contract_fee_cents: int = Field(
        description="A Shenzhen contract manufacturer's fee, to compare"
    )
    book_value_cents: int
    capex_cents: int
    build_progress: float | None
    ready: str
    sale_value_cents: int


class ProductionContractOut(BaseModel):
    contract_id: int
    kind: str = Field(description="assembly (contract manufacturing) or wafer")
    product_id: int
    product_name: str
    supplier: str
    supplier_label: str
    city_label: str | None
    units: int = Field(description="A month: units, or wafer starts")
    price_cents: int = Field(description="A unit's fee, or a wafer's locked price")
    signed: str
    ends: str
    status: str
    delivered: float = Field(description="Delivered last month after allocation")
    used: float
    take_or_pay_cents: int = Field(description="Last month's charge on unused volume")


class ChipOut(BaseModel):
    product_id: int
    name: str
    chip_type: str
    chip_label: str
    status: str
    chip_yield: float = Field(description="Good chips per chip on a wafer (0-1)")
    unit_cost_cents: int
    market_price_cents: int = Field(description="The device OEM reference price")
    per_wafer: int
    wafers: int = Field(description="Wafer starts a month under contract")
    made: float = Field(description="Good chips last month")
    internal_units: float = Field(description="Used by your own devices and servers, at cost")
    market_units: float = Field(description="Sold to the chip market")
    gpu_capex_factor: float | None = Field(
        description="AI accelerators: GPU data-centre capex x this while it is live"
    )


class CmOut(BaseModel):
    """Selling spare plant capacity (26.2)."""

    started: bool
    can_start: bool
    product_id: int | None
    customers: float
    units_sold: float = Field(description="Units a month sold to device makers")
    spare_units: float = Field(description="Run units left after your own products")
    revenue_cents: int = Field(description="A month at current customers and prices")
    quality: float | None = Field(description="Yield x reliability")


class OptionOut(BaseModel):
    key: str
    label: str


class HardwareOut(BaseModel):
    turn_label: str
    products: list[ManufacturingOut]
    plants: list[PlantOut]
    contracts: list[ProductionContractOut]
    chips: list[ChipOut]
    cm: CmOut
    components: list[ComponentOut] = Field(
        description="Device, server, equipment and wafer indexes"
    )
    manufacturers: list[OptionOut]
    foundries: list[OptionOut]
    cities: list[OptionOut]
    cheap_city: str
    plant_sizes: list[int]
    contract_months: list[int] = Field(description="[min, max] for contract manufacturing")
    wafer_months: list[int] = Field(description="[min, max] for wafer contracts")
    contract_take_or_pay: float
    wafer_take_or_pay: float
    contract_energy: int
    wafer_energy: int
    build_energy: int
    plant_capex_per_unit_cents: int = Field(description="At this month's equipment index")
    plant_build_months: int
    plant_staff_per: int = Field(description="Units a month per manufacturing engineer")


class CmContractIn(BaseModel):
    product_id: int
    manufacturer: str
    city: str
    units: int
    months: int


class WaferContractIn(BaseModel):
    product_id: int
    foundry: str
    wafers: int
    months: int


class PlantIn(BaseModel):
    city: str
    units: int


class PlantStaffIn(BaseModel):
    unit_id: int | None


class HardwareActionOut(BaseModel):
    hardware: HardwareOut
    energy: EnergyOut
    unread_inbox: int
