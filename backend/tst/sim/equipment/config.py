"""Schemas for M33's data and tunables (ADR-0008, docs/formulas.md 47): `equipment.yaml` and
`equipment.*` in balance.yaml.

Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn

FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0 is January 2010 (CLAUDE.md 7)
MONTHS: Final = 12  # tunable-exempt: calendar
MIN_YEAR: Final = 2000  # tunable-exempt: a model year is at least this (data sanity)
SHARE_TOLERANCE: Final = 1e-6  # tunable-exempt: buyers' shares sum to 1 within this
EPS: Final = 1e-9  # tunable-exempt: float tolerance on a whole tool


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


def year_series(points: dict[int, float], year: float) -> float:
    """Linear between year points, held at the ends."""
    ys = sorted(points)
    if year <= ys[0]:
        return float(points[ys[0]])
    if year >= ys[-1]:
        return float(points[ys[-1]])
    for a, b in pairwise(ys):
        if a <= year <= b:
            w = (year - a) / (b - a)
            return float(points[a]) + w * (float(points[b]) - float(points[a]))
    return float(points[ys[-1]])  # pragma: no cover


# --- equipment.yaml ---------------------------------------------------------------------------


class SupplierDef(_Frozen):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    makes: tuple[str, ...] = ()
    tag: str
    source: str


class ModelDef(_Frozen):
    model: str = Field(min_length=1)
    year: int = Field(ge=MIN_YEAR)
    wph: float = Field(gt=0)  # rated wafers an hour
    tag: str


class GenerationDef(_Frozen):
    """A tool family (47.1)."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    maker: str
    queued: bool
    nodes: tuple[str, ...] = Field(min_length=1)
    first_shipment: str
    first_volume: str
    models: tuple[ModelDef, ...] = Field(min_length=1)
    uptime: dict[int, float] = Field(min_length=1)
    price_cents: dict[int, int] = Field(min_length=1)
    shipments: dict[int, int] = Field(min_length=1)
    rival_shipments: dict[str, dict[int, int]] = Field(default_factory=dict)
    capacity_plan: dict[int, int] = Field(default_factory=dict)
    buyers: dict[str, float] = Field(min_length=1)

    @property
    def first_shipment_turn(self) -> int:
        return month_to_turn(self.first_shipment)

    @property
    def first_volume_turn(self) -> int:
        return month_to_turn(self.first_volume)

    @property
    def last_year(self) -> int:
        return max(self.shipments)

    def shipments_in(self, year: int) -> int:
        """The history's tools a year (0 before its first point; the last point held)."""
        if year < min(self.shipments):
            return 0
        if year in self.shipments:
            return self.shipments[year]
        return round(year_series({k: float(v) for k, v in self.shipments.items()}, year))

    def model_in(self, year: int) -> ModelDef:
        best = self.models[0]
        for m in self.models:
            if m.year <= year:
                best = m
        return best

    def uptime_in(self, year: float) -> float:
        return year_series(self.uptime, year)

    def price_in(self, year: float) -> float:
        return year_series({k: float(v) for k, v in self.price_cents.items()}, year)

    @model_validator(mode="after")
    def _check(self) -> GenerationDef:
        if abs(sum(self.buyers.values()) - 1.0) > SHARE_TOLERANCE:
            raise ValueError(f"generation {self.key}: buyers' shares must sum to 1")
        if any(not 0 < u <= 1 for u in self.uptime.values()):
            raise ValueError(f"generation {self.key}: uptime must be in (0, 1]")
        return self


class ToolControlDef(_Frozen):
    """A dated rule the queue applies on top of M22's (47.3)."""

    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    month: str
    generation: str
    to: tuple[str, ...] = Field(min_length=1)
    tag: str
    source: str

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class ChinaToolsDef(_Frozen):
    window: tuple[str, str]
    tag: str

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.window[0])

    @property
    def months(self) -> int:
        return month_to_turn(self.window[1]) - self.start_turn + 1


class ProgrammeDef(_Frozen):
    """One generation of the player's lithography programme (47.4)."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    generation: str
    needs: str | None = None
    cost: int = Field(gt=0)  # estimate before the hidden overrun, cents
    months: tuple[int, int]
    level: float = Field(ge=0)
    staff: int = Field(gt=0)
    tool_cents: int = Field(gt=0)
    tools_per_year: int = Field(gt=0)
    tag: str


class EquipmentFile(_Frozen):
    suppliers: tuple[SupplierDef, ...] = Field(min_length=1)
    note_other_tools: str = ""
    generations: tuple[GenerationDef, ...] = Field(min_length=1)
    buyer_countries: dict[str, str] = Field(min_length=1)
    controls: tuple[ToolControlDef, ...] = ()
    china_tools: ChinaToolsDef
    history_note: str = ""
    programme: tuple[ProgrammeDef, ...] = Field(min_length=1)

    def generation(self, key: str) -> GenerationDef:
        for g in self.generations:
            if g.key == key:
                return g
        raise KeyError(key)

    def queued(self) -> tuple[GenerationDef, ...]:
        return tuple(g for g in self.generations if g.queued)

    def supplier(self, key: str) -> SupplierDef:
        for s in self.suppliers:
            if s.key == key:
                return s
        raise KeyError(key)

    def stage(self, key: str) -> ProgrammeDef:
        for p in self.programme:
            if p.key == key:
                return p
        raise KeyError(key)

    def generation_for(self, node: str) -> GenerationDef | None:
        """The queued generation a fab at `node` needs (None: no queued tools)."""
        for g in self.queued():
            if node in g.nodes:
                return g
        return None

    @model_validator(mode="after")
    def _check(self) -> EquipmentFile:
        keys = {g.key for g in self.generations}
        makers = {s.key for s in self.suppliers}
        for g in self.generations:
            if g.maker not in makers:
                raise ValueError(f"generation {g.key}: unknown maker {g.maker!r}")
        for g in self.generations:
            if g.queued and not set(g.buyers) <= set(self.buyer_countries):
                raise ValueError(f"generation {g.key}: a buyer without a country")
        for c in self.controls:
            if c.generation not in keys:
                raise ValueError(f"control {c.key}: unknown generation {c.generation!r}")
        stages = {p.key for p in self.programme}
        for p in self.programme:
            if p.generation not in keys:
                raise ValueError(f"programme {p.key}: unknown generation")
            if p.needs is not None and p.needs not in stages:
                raise ValueError(f"programme {p.key}: unknown stage {p.needs!r}")
            if not 0 < p.months[0] <= p.months[1]:
                raise ValueError(f"programme {p.key}: months must be an increasing range")
        seen: set[str] = set()
        for g in self.queued():
            if seen & set(g.nodes):
                raise ValueError(f"generation {g.key}: a node served by two queued generations")
            seen |= set(g.nodes)
        return self


# --- balance.yaml: equipment.* ----------------------------------------------------------------


class QueueBalance(_Frozen):
    """47.2: who gets the quarter's tools (queue order, moved by the buyer's weight)."""

    history_months: float = Field(ge=0)  # a buyer at full history moves up this many months
    history_tools: int = Field(gt=0)
    history_years: int = Field(gt=0)
    jitter_months: float = Field(ge=0)  # +/- half this, seeded: tie-breaks, never shown
    prepay_share: float = Field(gt=0, lt=1)
    prepay_months: float = Field(ge=0)  # a prepaid order moves up this many months
    rival_order_share: float = Field(gt=0)
    china_share: float = Field(ge=0, le=1)
    estimate_months: float = Field(ge=0)  # the lead range: the place -/+ this many months
    energy: int = Field(ge=0)
    max_order: int = Field(gt=0)


class PriceBalance(_Frozen):
    scarcity: float = Field(ge=0)  # price x (1 + this x max(0, backlog years - 1))
    growth: float = Field(ge=0)  # a year after the data's last price
    max_scarcity: float = Field(ge=1)


class CapacityRuleBalance(_Frozen):
    """47.1: ASML's December rule from 2026."""

    expand_backlog_years: float = Field(gt=0)
    plan_growth: float = Field(ge=0)  # the plan's growth a year after its last point
    hold_growth: float = Field(ge=0)
    accelerate: float = Field(ge=0)  # extra growth of the next generation when the player sells


class ProgrammeBalance(_Frozen):
    """47.4: the player's lithography programme."""

    min_stage: int = Field(ge=1)
    domain: str = Field(min_length=1)
    funding: Range  # funding as a multiple of the stage's reference monthly budget
    overrun: Range  # hidden: months and cost x (1 + this)
    work_scale: float = Field(gt=0)
    success_base: float = Field(ge=0, le=1)
    success_funding: float = Field(ge=0)  # + this x (funding - 1)
    success_skill: float = Field(ge=0)  # + this x (mean skill - 10) / 10
    success_range: Range
    start_energy: int = Field(ge=0)
    stop_energy: int = Field(ge=0)
    throughput: Range  # a first prototype's throughput, x ASML's
    uptime_start: float = Field(gt=0, le=1)
    yield_cut: Range  # points of fab yield lost at first
    learn_tool_months: float = Field(gt=0)  # installed tool-months that close 63% of the gap
    tool_capex_share: float = Field(ge=0, le=1)
    duv_capex_cut: float = Field(ge=0, lt=1)  # litho_1 tools cut a non-EUV fab's capex by this


class SalesBalance(_Frozen):
    """47.4: the player's tools sold to rival foundries."""

    min_backlog_years: float = Field(ge=0)
    discount: float = Field(ge=0, lt=1)  # the player's price below ASML's
    share: float = Field(ge=0, le=1)  # of rivals' unmet orders, at full advantage
    min_quality: float = Field(ge=0, le=1)  # a buyer wants at least this tool maturity
    asml_cut: float = Field(ge=0, lt=1)  # ASML's price cut a year after the player sells
    asml_cut_max: float = Field(ge=0, lt=1)


class EquipmentBalance(_Frozen):
    start: str  # the first month ASML's December rule and rivals' living orders run (47.1)
    queue: QueueBalance
    price: PriceBalance
    capacity: CapacityRuleBalance
    service_ban_uptime_cut: float = Field(ge=0, le=1)
    programme: ProgrammeBalance
    sales: SalesBalance

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)
