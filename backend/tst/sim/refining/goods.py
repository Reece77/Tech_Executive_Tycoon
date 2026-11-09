"""What refining's goods cost (docs/formulas.md 36.1): M17's commodities at their monthly price,
and the goods M20 derives from them (concentrates, solar polysilicon, 300 mm wafers;
`refining.goods`). Prices are cents a volume unit (t, kg, wafer); allocation is the share a spot
buyer gets this month.
"""

from __future__ import annotations

from tst.sim.commodities import commodity
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import goods as components
from tst.sim.refining import formulas as rf
from tst.sim.state import GameState

CENTS = 100  # tunable-exempt: cents a dollar


def is_commodity(good: str, data: GameData) -> bool:
    return data.commodities is not None and good in {g.key for g in data.commodities.goods}


def volume_unit(good: str, balance: Balance, data: GameData) -> str:
    if good in balance.refining.goods:
        return balance.refining.goods[good].volume_unit
    assert data.commodities is not None
    return data.commodities.good(good).volume_unit


def label(good: str, balance: Balance, data: GameData) -> str:
    if good in balance.refining.goods:
        return balance.refining.goods[good].label
    assert data.commodities is not None
    return data.commodities.good(good).label


def commodity_cents(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """An M17 commodity's price this month, cents a volume unit."""
    assert data.commodities is not None
    usd = data.commodities.good(good).usd_per_unit
    return commodity.price(state, good, state.turn, data, balance) * usd * CENTS


def price_cents(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """Any refining good's market price this month, cents a volume unit."""
    spec = balance.refining.goods.get(good)
    if spec is None:
        return commodity_cents(state, good, balance, data)
    source = commodity_cents(state, spec.source, balance, data)
    index = commodity.index_now(state, spec.source, data)
    return rf.derived_price_cents(
        spec.priced_by, spec.value, source, index, spec.per_source, spec.base_cents
    )


def allocation(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """A spot buyer's share this month: the commodity's, or a derived good's source's (or its
    `allocation_from` component good's)."""
    spec = balance.refining.goods.get(good)
    if spec is not None and spec.allocation_from is not None:
        return components.allocation_now(state, spec.allocation_from, data)
    key = spec.source if spec is not None else good
    return commodity.current(state, key, data).allocation


def shortage_start(state: GameState, good: str, balance: Balance, data: GameData) -> int | None:
    """The first month of the shortage running now, if any: a contract signed before it keeps
    100% allocation (as 22.4)."""
    if allocation(state, good, balance, data) >= 1:
        return None
    spec = balance.refining.goods.get(good)
    if spec is not None and spec.allocation_from is not None:
        month = components.current(state, spec.allocation_from, data)
        hist = data.components.good(spec.allocation_from) if data.components else None
        start = hist.shortage_start(state.turn) if hist is not None else None
        return start if start is not None else month.shock_turn
    key = spec.source if spec is not None else good
    return commodity.current(state, key, data).shock_turn
