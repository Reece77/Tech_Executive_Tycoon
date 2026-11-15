"""M33's state (docs/formulas.md 47). Persisted as `equipment_record` rows (tst.db.equipment_io).

Hidden fields (never in the API or a prompt, 47.6): an order's `jitter` (part of its allocation
weight), a programme's `success_u`, `overrun` and `work`, and a supplier's planned capacity
before December announces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type OrderStatus = Literal["open", "done", "lost", "cancelled"]
type ProgrammeStatus = Literal["running", "succeeded", "failed", "stopped"]
type ToolSource = Literal["asml", "own"]


@dataclass(frozen=True, slots=True)
class ToolOrder:
    """An order in ASML's queue (47.2). `buyer` is a nodes.yaml foundry key, `memory` or `other`
    for a rival, or `player` for one of the player's group companies (`company_id`)."""

    id: int
    buyer: str
    generation: str
    tools: int
    placed_turn: int
    company_id: int | None = None
    facility_id: int | None = None  # the fab it equips (None: into the company's stock)
    country: str | None = None  # where the tools go (the controls read it)
    delivered: int = 0
    price_cents: int = 0  # a tool's price, locked at the order
    prepaid: bool = False
    prepaid_cents: int = 0  # a stock order's prepayment, held in 1530 until delivery
    jitter: float = 0.0  # hidden
    status: OrderStatus = "open"
    done_turn: int | None = None

    @property
    def remaining(self) -> int:
        return self.tools - self.delivered


@dataclass(frozen=True, slots=True)
class Delivery:
    """Tools delivered to a buyer in a quarter (the history the weight reads)."""

    turn: int
    buyer: str
    generation: str
    tools: int
    company_id: int | None = None
    source: ToolSource = "asml"


@dataclass(frozen=True, slots=True)
class SupplierYear:
    """A generation's capacity (tools a year) from `equipment.start`: set each December for the
    next year by ASML's rule (47.1); the announced year is public once set."""

    generation: str
    year: int
    capacity: int
    price_mult: float = 1.0  # ASML's response to the player's sales (47.4)


@dataclass(frozen=True, slots=True)
class ToolStock:
    """Tools a company holds, not yet in a fab, by generation and source."""

    company_id: int
    generation: str
    tools: int
    source: ToolSource = "asml"
    value_cents: int = 0  # what they cost (1530's balance for them)


@dataclass(frozen=True, slots=True)
class Programme:
    """A stage of the player's lithography programme (47.4). `work` is the months of work it
    needs at reference funding, x (1 + overrun): hidden, as are `success_u` and `overrun`."""

    company_id: int
    stage: str
    attempt: int
    started_turn: int
    funding: float
    work: float  # hidden
    overrun: float  # hidden
    success_u: float  # hidden
    progress: float = 0.0  # months of work done
    spent_cents: int = 0
    status: ProgrammeStatus = "running"
    ended_turn: int | None = None
    throughput: float = 0.0  # a first tool's throughput x ASML's, drawn at success (then public)
    yield_cut: float = 0.0  # yield points a first tool loses, drawn at success (then public)


@dataclass(frozen=True, slots=True)
class OwnTools:
    """The player's own tool line for a succeeded stage: what it has made and how mature its
    installed tools are (47.4)."""

    company_id: int
    stage: str
    generation: str
    made: int = 0
    carry: float = 0.0  # a part-made tool
    tool_months: float = 0.0  # installed tool-months so far (the learning curve)
    sold: int = 0
    sales_cents: int = 0


@dataclass(frozen=True, slots=True)
class FabTools:
    """Which tools a fab runs on (an own-tool fab's penalties read it)."""

    facility_id: int
    generation: str
    tools: int
    source: ToolSource = "asml"
