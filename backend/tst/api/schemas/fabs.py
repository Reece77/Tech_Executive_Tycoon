"""Request and response models for the Fabs screen and the node timeline (M21, formulas.md 38).

Hidden values never appear: a fab shows its quoted capex and what has been paid, never the true
capex with its hidden overrun; a future node shows its window until it arrives, never its drawn
month; rival foundries show the nodes they have reached, never their lags. Staff show as counts
and coverage, never skill (ADR-0007).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class FabMonthOut(BaseModel):
    turn: int
    available: float = Field(description="Wafer starts it could run (live capacity x coverage)")
    own: float = Field(description="Starts run for the company's own chips")
    sold: float = Field(description="Starts sold as foundry slots")
    utilization: float
    yield_: float = Field(alias="yield")
    reliability: float
    depreciation_cents: int
    fixed_cents: int
    materials_cents: int
    power_cents: int
    staff_cents: int
    revenue_cents: int
    slot_price_cents: float
    market_cents: float = Field(description="The node's market wafer price this month")
    cost_per_start_cents: float
    die_cost_cents: float | None = Field(
        description="An own AI accelerator's cost per good die at this month's cost a start"
    )
    die_market_cents: float | None = Field(
        description="The same die on a foundry slot at the node's market price"
    )

    model_config = {"populate_by_name": True}


class FabCustomerOut(BaseModel):
    name: str
    starts: float


class FabHistoryOut(BaseModel):
    turn: int
    label: str
    yield_: float = Field(alias="yield")
    utilization: float
    cost_per_start_cents: float
    market_cents: float

    model_config = {"populate_by_name": True}


class FabOut(BaseModel):
    id: int
    company_id: int
    company: str
    name: str
    node: str
    node_label: str
    duv: bool
    region: str
    region_label: str
    status: str = Field(description="building | waiting_tools | converting | live | closed")
    size: int = Field(description="Wafer starts a month")
    ready_turn: int
    ready_label: str
    estimate_cents: int
    capex_paid_cents: int
    book_value_cents: int
    tools: int
    tools_label: str | None
    staff: int
    staff_needed: int
    coverage: float
    unit_id: int | None
    yield_: float = Field(alias="yield")
    months_run: int
    upgrade_node: str | None
    upgrade_label: str | None
    upgrade_ready_label: str | None
    next_node: str | None
    upgrade_estimate_cents: int | None
    upgrade_allowed: bool
    upgrade_reason: str | None
    month: FabMonthOut | None
    customers: list[FabCustomerOut]
    chips: list[str] = Field(description="The company's chip products its starts supply")
    history: list[FabHistoryOut]

    model_config = {"populate_by_name": True}


class FoundryNodeOut(BaseModel):
    foundry: str
    name: str
    turn: int
    label: str


class NodeOut(BaseModel):
    key: str
    label: str
    generation: int
    euv: bool
    duv_route: bool
    arrived: bool
    first_turn: int | None = Field(description="First volume anywhere; None for a future node")
    first_label: str | None
    window_label: str | None = Field(description="A future node's public window")
    reached: list[FoundryNodeOut] = Field(description="Foundries in volume at it, by month")
    market_cents: float | None = Field(description="Its market wafer price now, once in volume")
    capital_cents: float | None = Field(description="Capital per wafer-per-year, once known")
    need_level: float
    orderable: bool
    tag: str | None


class FoundryOut(BaseModel):
    key: str
    name: str
    region_label: str
    newest: str | None
    newest_label: str | None
    capacity_k: float = Field(description="Thousand wafer starts a month")
    open_share: float
    stopped: bool


class NodesOut(BaseModel):
    turn: int
    leading: str
    leading_label: str
    median: str
    median_label: str
    price_factor: float
    allocation_factor: float
    nodes: list[NodeOut]
    foundries: list[FoundryOut]
    euv_supplier: str
    euv_tool_cents: float
    euv_short: bool


class FabsOut(BaseModel):
    fabs: list[FabOut]
    timeline: NodesOut
    process_level: float
    sizes: list[int]
    regions: list[str]
    build_energy: int
    upgrade_energy: int


class FabQuoteOut(BaseModel):
    node: str
    node_label: str
    region: str
    size: int = Field(description="Wafer starts a month")
    duv: bool
    euv: bool
    capex_cents: int
    monthly_capex_cents: int
    build_months: int
    tools: int
    tools_label: str | None
    ready_label: str
    staff_needed: int
    need_level: float
    level: float
    allowed: bool
    reason: str | None
    market_cents: float | None
    cost_per_start_cents: float = Field(
        description="A start's cost at full use: depreciation, fixed, materials and power"
    )


class BuildFabIn(BaseModel):
    node: str
    region: str
    size: int
    duv: bool = False
    city: str | None = None
    country: str | None = None  # M23a: a countries.yaml key in the region
    company_id: int | None = None  # M23a: a group company to build it for


class FoundryContractIn(BaseModel):
    """M23a: sell a fab's starts to a rival designer for months at a price."""

    fab_id: int
    customer: str
    monthly_starts: float
    months: int
    price_cents: float


class StaffFabIn(BaseModel):
    unit_id: int | None


class FabsActionOut(BaseModel):
    fabs: FabsOut
    energy: EnergyOut
    unread_inbox: int
