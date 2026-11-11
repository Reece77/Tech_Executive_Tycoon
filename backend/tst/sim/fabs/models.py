"""M21 records (docs/formulas.md 38.2): a fab's own state beside its generic facility.

A fab is a `Facility` of kind `fab` (ADR-0020: one facility model; module `fabs`): the
facility row carries the company, region, capacity (wafer starts a month), the true capex
(with the hidden overrun), what has been paid and depreciated, and when it goes live. `Fab`
holds what only fabs have, keyed by the facility's id. Every record belongs to a `company_id`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FabMonth:
    """One month of a fab (38.2), as the Fabs screen shows it. Starts are wafer starts; cents
    are the month's totals; `cost_per_start_cents` is the full cost of a start (depreciation,
    fixed, materials, power and the lead engineers' pay) at the month's starts run."""

    turn: int
    available: float = 0.0  # starts it could run (live capacity x staff coverage)
    own: float = 0.0  # starts run for the company's own chips
    sold: float = 0.0  # starts sold as foundry slots
    yield_: float = 0.0
    reliability: float = 0.0
    depreciation_cents: int = 0
    fixed_cents: int = 0
    materials_cents: int = 0
    power_cents: int = 0
    staff_cents: int = 0
    revenue_cents: int = 0  # foundry slots
    slot_price_cents: float = 0.0  # a slot's price this month (the node's market price x 0.9)
    market_cents: float = 0.0  # the node's market wafer price this month
    cost_per_start_cents: float = 0.0
    customers: tuple[tuple[str, float], ...] = ()  # (rival designer, starts bought)
    # M23a: starts run for each group company's chips, (company, starts, transfer cents, market
    # cents); the fab's own company at cost
    group: tuple[tuple[int, float, float, float], ...] = ()

    @property
    def run(self) -> float:
        return self.own + self.sold

    @property
    def utilization(self) -> float:
        return self.run / self.available if self.available > 0 else 0.0

    @property
    def cost_cents(self) -> int:
        return (
            self.depreciation_cents
            + self.fixed_cents
            + self.materials_cents
            + self.power_cents
            + self.staff_cents
        )


@dataclass(frozen=True, slots=True)
class CapexPart:
    """A part of a fab's capex and the month it went live: the build, then each upgrade.
    Each part depreciates straight-line over the kind's life from `live_turn`."""

    cents: int
    live_turn: int


@dataclass(frozen=True, slots=True)
class Fab:
    """A fab's own state (38.2). `estimate_cents` is the quoted capex the player saw; the
    facility's `capex_cents` carries the hidden overrun (revealed as it is paid). `tools_turn`
    is when its EUV tools arrive (None for a fab that needs none); it goes live at the later of
    construction, the tools plus installation, and the node's first volume. An upgrade converts
    it to `upgrade_node` while offline until `upgrade_ready`."""

    facility_id: int
    company_id: int
    node: str  # nodes.yaml key
    estimate_cents: int
    build_months: int
    duv: bool = False  # 7 nm by DUV (38.1)
    tools: int = 0  # EUV tools it needs
    tools_turn: int | None = None
    live_turn: int = 0  # the month it starts (or started) production
    yield_: float = 0.0
    months_run: int = 0
    parts: tuple[CapexPart, ...] = ()  # capex that has gone live (depreciating)
    upgrade_node: str | None = None
    upgrade_ready: int | None = None
    upgrade_cents: int = 0  # the conversion's capex (with overrun)
    upgrade_paid_cents: int = 0
    upgrade_started: int | None = None
    month: FabMonth | None = None  # the latest month
    history: tuple[
        tuple[int, float, float, float, float], ...
    ] = ()  # (turn, yield, use, cost/start, market)

    def upgrading(self, turn: int) -> bool:
        return self.upgrade_ready is not None and turn < self.upgrade_ready
