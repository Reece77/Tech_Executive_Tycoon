"""The Equipment API (M33, docs/formulas.md 47.6): tool generations, published prices and
throughput, the player's orders with their queue place as a lead-time range, deliveries, stock,
controls and the lithography programme. Never an allocation weight, a programme's hidden draws
(work, overrun, success) or ASML's capacity before its December announcement."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class ToolShipmentOut(BaseModel):
    year: int
    tools: int


class ToolGenerationOut(BaseModel):
    key: str
    label: str
    maker: str
    queued: bool = Field(description="Ordered through ASML's queue (else inside a fab's capex)")
    nodes: list[str]
    node_labels: list[str]
    first_shipment_label: str
    first_volume_label: str
    model: str = Field(description="The current model")
    wph: float = Field(description="Rated wafers an hour")
    uptime: float
    price_cents: int = Field(description="Today's price, with scarcity")
    list_cents: int = Field(description="The list price before scarcity")
    shipments: list[ToolShipmentOut] = Field(description="Tools a year to the last full year")
    capacity_next: int | None = Field(description="Next year's capacity, once announced")
    book: str = Field(description="ASML's order book: thin, a year deep, or long")
    shipping: bool


class ToolOrderOut(BaseModel):
    id: int
    generation: str
    generation_label: str
    tools: int
    delivered: int
    placed_label: str
    status: str = Field(description="open | done | lost | cancelled")
    prepaid: bool
    price_cents: int
    fab_id: int | None
    fab: str | None
    lead_low: int | None = Field(description="Months to the last tool, the fast end")
    lead_high: int | None = Field(description="... the slow end (None: beyond the queue's view)")
    lead_label: str
    prepay_cents: int | None = Field(description="What prepaying would cost (an open order)")


class ToolStockOut(BaseModel):
    generation: str
    generation_label: str
    source: str = Field(description="asml | own")
    tools: int
    book_cents: int = Field(description="What they cost (tool inventory)")


class ToolControlOut(BaseModel):
    key: str
    title: str
    month_label: str
    generation_labels: list[str]
    destinations: list[str]
    in_force: bool
    source: str | None


class LithoStageOut(BaseModel):
    key: str
    label: str
    generation_label: str
    after_stage: str | None = Field(description="The stage that must work first")
    cost_cents: int = Field(description="The estimate (programmes often run over)")
    months_low: int
    months_high: int
    level: float = Field(description="Lithography level needed to start")
    staff: int = Field(description="Researchers needed on a lithography project")
    reference_cents: int = Field(description="The reference budget a month")
    status: str = Field(description="locked | open | running | succeeded | failed | stopped")
    attempt: int
    started_label: str | None
    months_running: int | None
    funding: float | None
    spent_cents: int
    end_window_label: str | None = Field(description="Public estimate of when it ends")
    why_not: str | None
    throughput: float | None = Field(description="First tools' throughput x ASML's (succeeded)")
    yield_cut: float | None = Field(description="First tools' yield points lost (succeeded)")


class OwnToolsOut(BaseModel):
    stage: str
    generation_label: str
    made: int
    in_stock: int
    installed: int
    sold: int
    sales_cents: int
    maturity: float = Field(description="0 at first, towards 1 with installed use")
    throughput: float = Field(description="x ASML's")
    yield_cut: float = Field(description="Yield points lost now")
    per_year: int


class LithoProgrammeOut(BaseModel):
    unlocked: bool
    unlock_reason: str | None
    level: float
    researchers: int
    funding_low: float
    funding_high: float
    stages: list[LithoStageOut]
    own_tools: list[OwnToolsOut]


class EquipmentOut(BaseModel):
    turn: int
    supplier: str
    generations: list[ToolGenerationOut]
    orders: list[ToolOrderOut]
    stock: list[ToolStockOut]
    controls: list[ToolControlOut]
    programme: LithoProgrammeOut
    prepay_share: float
    max_order: int
    order_energy: int
    note: str = Field(description="What the queue is, in words")


class OrderToolsIn(BaseModel):
    generation: str
    tools: int
    prepay: bool = False


class PrepayIn(BaseModel):
    order_id: int


class LithoStartIn(BaseModel):
    stage: str
    funding: float


class LithoStageIn(BaseModel):
    stage: str


class EquipmentActionOut(BaseModel):
    equipment: EquipmentOut
    energy: EnergyOut
    unread_inbox: int
