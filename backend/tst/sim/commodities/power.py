"""Regional power (docs/formulas.md 33.5): a data centre's operating cost (22.2) x its
region's industrial power index, North America 1.0 (so M12a's North American tuning and
22.7 target 4 are unchanged). The index is history to 2025, then seeded (commodity.py)."""

from __future__ import annotations

from tst.sim.commodities import commodity
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.models import Facility
from tst.sim.money import Cents
from tst.sim.state import GameState


def index(state: GameState, region: str, data: GameData) -> float:
    """The region's power index this month (1.0 when M17's data is not loaded)."""
    if data.power_history is None:
        return 1.0
    return commodity.index_now(state, commodity.power_key(region), data)


def opex_cents(base_cents: float, power_index: float) -> float:
    """33.5: a GPU data centre's $200 a CU-month costs $170 at 0.85."""
    return base_cents * power_index


def kind_index(state: GameState, kind: str, region: str, balance: Balance, data: GameData) -> float:
    """The multiple on a facility kind's operating cost in `region` (1.0 for kinds that do not
    pay regional power yet, such as assembly plants)."""
    return index(state, region, data) if kind in balance.power.paid_by else 1.0


def operating_cents(
    state: GameState, facility: Facility, balance: Balance, data: GameData
) -> Cents:
    """A facility's operating cost this month (22.2, 26.2) with regional power (33.5)."""
    kind = balance.facility.kinds[facility.kind]
    live = facility.live_capacity(state.turn)
    if live <= 0:
        return 0
    mult = kind_index(state, facility.kind, facility.region, balance, data)
    return round(opex_cents(live * kind.opex_per_unit_cents, mult)) + kind.fixed_opex_cents
