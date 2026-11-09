"""Schemas for M21's tunables and data (ADR-0008, docs/formulas.md 38): `fab.*` in balance.yaml
and `nodes.yaml` (process nodes, future nodes' windows, rival foundries, EUV supply).

Model definitions only (no file reads, no imports from the rest of the sim beyond other
config modules), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn

HISTORY_END: Final = "2025-12"  # tunable-exempt: the last month of history (ADR-0019 15)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


# --- balance.yaml: fab.* -------------------------------------------------------------------


class BuildMonths(_Frozen):
    leading: int = Field(gt=0)
    mature: int = Field(gt=0)


class UpgradeBalance(_Frozen):
    capex_share: float = Field(gt=0, le=1)
    months: int = Field(gt=0)
    energy: int = Field(ge=0)


class YieldBalance(_Frozen):
    """38.2: yield learns from `start` toward `mature` with months of production."""

    start_leading: float = Field(gt=0, lt=1)
    start_mature: float = Field(gt=0, lt=1)
    mature: float = Field(gt=0, lt=1)
    learn: float = Field(gt=0, lt=1)
    skill_ref: float = Field(gt=0)
    lead_bonus: float = Field(ge=0)
    lead_cap: float = Field(ge=0)
    noise_sd: float = Field(ge=0)
    bounds: Range

    @model_validator(mode="after")
    def _check(self) -> YieldBalance:
        if not self.start_leading <= self.start_mature <= self.mature:
            raise ValueError("fab.yield: start_leading <= start_mature <= mature")
        return self


class DuvBalance(_Frozen):
    yield_mult: float = Field(gt=0, le=1)
    cost_mult: float = Field(ge=1)


class MaterialsBalance(_Frozen):
    substrate_good: str  # refining.goods key: the 300 mm wafer a start uses
    chemicals_share: float = Field(ge=0)
    mix: dict[str, float] = Field(min_length=1)  # M17 commodity -> weight (sums to 1)

    @model_validator(mode="after")
    def _check(self) -> MaterialsBalance:
        if abs(sum(self.mix.values()) - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("fab.materials.mix weights must sum to 1")
        return self


class PowerMwhBalance(_Frozen):
    base: float = Field(ge=0)
    per_generation: float = Field(ge=0)


class SlotBalance(_Frozen):
    discount: float = Field(gt=0, le=1)
    take: float = Field(ge=0, le=1)


class CapacityBalance(_Frozen):
    growth: Range  # a year, after 2025
    elasticity: float = Field(ge=0)
    bounds: Range


class EuvBalance(_Frozen):
    wafers_per_tool: int = Field(gt=0)
    open_share: float = Field(gt=0, le=1)
    lead_months: int = Field(ge=0)
    shortage_lead_months: int = Field(ge=0)
    install_months: int = Field(ge=0)


class FabBalance(_Frozen):
    capex_scale: float = Field(gt=0)
    overrun: Range
    build_months: BuildMonths
    mature_age_months: int = Field(gt=0)
    preorder_months: int = Field(ge=0)
    node_level: float = Field(ge=0)
    build_energy: int = Field(ge=0)
    upgrade: UpgradeBalance
    yield_: YieldBalance = Field(alias="yield")
    duv: DuvBalance
    fixed_share: float = Field(ge=0)
    materials: MaterialsBalance
    power_mwh: PowerMwhBalance
    slot: SlotBalance
    price_decay: float = Field(ge=0, lt=1)
    median_lag_months: int = Field(ge=0)
    node_quality: float = Field(ge=0)
    capacity: CapacityBalance
    future_wafer_mult: Range
    future_capital_mult: Range
    euv: EuvBalance
    history_months: int = Field(gt=0)


# --- nodes.yaml ----------------------------------------------------------------------------


class NodeDef(_Frozen):
    """A historical process node (38.1, dossier 4). Its position in `nodes` is its generation."""

    key: str
    label: str = Field(min_length=1)
    first: dict[str, str] = Field(min_length=1)  # foundry key -> first-volume month
    euv: bool
    duv_route: bool = False  # 7 nm: a DUV route at fab.duv's yield and cost
    capital_cents: int = Field(gt=0)  # capital per wafer-per-year
    wafer_cents: int = Field(gt=0)  # a 300 mm wafer's market price at price_month
    price_month: str
    tag: str

    @model_validator(mode="after")
    def _check(self) -> NodeDef:
        for month in (*self.first.values(), self.price_month):
            month_to_turn(month)
        return self


class FutureNodeDef(_Frozen):
    """A node after 2025 (38.1): a public window; its month is drawn from the seed."""

    key: str
    label: str = Field(min_length=1)
    window: tuple[str, str]

    @model_validator(mode="after")
    def _check(self) -> FutureNodeDef:
        start, end = (month_to_turn(m) for m in self.window)
        if end < start or start <= month_to_turn(HISTORY_END):
            raise ValueError(f"future node {self.key!r}: a window after 2025, start before end")
        return self

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.window[0])

    @property
    def months(self) -> int:
        return month_to_turn(self.window[1]) - self.start_turn + 1


class OpenFrom(_Frozen):
    month: str
    share: float = Field(ge=0, le=1)


class FoundryDef(_Frozen):
    """A rival foundry (38.3)."""

    key: str
    name: str = Field(min_length=1)
    region: str
    contract: str  # chips.contract.foundries key it backs
    reaches: dict[str, str] = Field(default_factory=dict)  # node -> month (else nodes' first)
    stops_at: str | None = None  # the last node it goes to
    duv_only: bool = False
    euv_gate: str | None = None  # without EUV it goes no further than this node
    capacity: dict[int, float] = Field(min_length=1)  # year -> thousand wafer starts a month
    open_share: float = Field(ge=0, le=1)
    open_from: OpenFrom | None = None
    lag: Range  # months behind the first to a node after 2025


class EuvSupplyDef(_Frozen):
    supplier: str
    shipments: dict[int, int] = Field(min_length=1)  # year -> tools shipped
    shipments_growth: float
    tool_cents: int = Field(gt=0)
    first_month: str


class NodesFile(_Frozen):
    nodes: tuple[NodeDef, ...] = Field(min_length=1)
    future: tuple[FutureNodeDef, ...] = ()
    foundries: tuple[FoundryDef, ...] = Field(min_length=1)
    euv: EuvSupplyDef

    @model_validator(mode="after")
    def _check(self) -> NodesFile:
        keys = [n.key for n in self.nodes] + [n.key for n in self.future]
        if len(set(keys)) != len(keys):
            raise ValueError("nodes.yaml: node keys must be unique")
        known = set(keys)
        fkeys = [f.key for f in self.foundries]
        if len(set(fkeys)) != len(fkeys):
            raise ValueError("nodes.yaml: foundry keys must be unique")
        for n in self.nodes:
            bad = set(n.first) - set(fkeys)
            if bad:
                raise ValueError(f"node {n.key!r}: unknown foundries {sorted(bad)}")
        for f in self.foundries:
            for k in (*f.reaches, f.stops_at, f.euv_gate):
                if k is not None and k not in known:
                    raise ValueError(f"foundry {f.key!r}: unknown node {k!r}")
        starts = [n.start_turn for n in self.future]
        if starts != sorted(starts):
            raise ValueError("nodes.yaml: future nodes' windows must be in order")
        return self

    def node_keys(self) -> tuple[str, ...]:
        return tuple(n.key for n in self.nodes) + tuple(n.key for n in self.future)

    def generation(self, key: str) -> int:
        return self.node_keys().index(key)

    def foundry(self, key: str) -> FoundryDef:
        for f in self.foundries:
            if f.key == key:
                return f
        raise KeyError(key)

    def node(self, key: str) -> NodeDef | None:
        for n in self.nodes:
            if n.key == key:
                return n
        return None

    def future_node(self, key: str) -> FutureNodeDef | None:
        for n in self.future:
            if n.key == key:
                return n
        return None
