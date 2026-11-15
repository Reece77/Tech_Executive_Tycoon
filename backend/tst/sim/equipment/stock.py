"""Tools a company holds and has not yet put in a fab (docs/formulas.md 47.2, 47.4): bought from
ASML into stock (paid at delivery, cash to 1530) or made by its own line (at cost, cash to 1530).
A fab takes stock first: the tools' value moves 1530 -> 1500 and its capex falls by it (at most
`programme.tool_capex_share` of it)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.equipment.models import ToolSource, ToolStock
from tst.sim.ledger import TOOL_INVENTORY
from tst.sim.state import GameState

TOOLS_ACCOUNT: Final = TOOL_INVENTORY


def _find(
    state: GameState, company_id: int, generation: str, source: ToolSource
) -> ToolStock | None:
    for s in state.tool_stock:
        if s.company_id == company_id and s.generation == generation and s.source == source:
            return s
    return None


def held(
    state: GameState, company_id: int, generation: str, source: ToolSource | None = None
) -> int:
    return sum(
        s.tools
        for s in state.tool_stock
        if s.company_id == company_id
        and s.generation == generation
        and (source is None or s.source == source)
    )


def _put(state: GameState, rec: ToolStock) -> GameState:
    rest = [
        s
        for s in state.tool_stock
        if not (
            s.company_id == rec.company_id
            and s.generation == rec.generation
            and s.source == rec.source
        )
    ]
    if rec.tools > 0:
        rest.append(rec)
    return replace(state, tool_stock=tuple(rest))


def add(
    state: GameState,
    company_id: int,
    generation: str,
    tools: int,
    source: ToolSource,
    value_cents: int,
) -> GameState:
    cur = _find(state, company_id, generation, source) or ToolStock(
        company_id, generation, 0, source
    )
    return _put(
        state, replace(cur, tools=cur.tools + tools, value_cents=cur.value_cents + value_cents)
    )


def take(
    state: GameState, company_id: int, generation: str, tools: int, source: ToolSource
) -> tuple[GameState, int, int]:
    """Take up to `tools` of a source: (state, tools taken, their value at average cost)."""
    cur = _find(state, company_id, generation, source)
    if cur is None or tools <= 0:
        return state, 0, 0
    n = min(cur.tools, tools)
    value = cur.value_cents if n == cur.tools else cur.value_cents * n // cur.tools
    return (
        _put(state, replace(cur, tools=cur.tools - n, value_cents=cur.value_cents - value)),
        n,
        value,
    )
