"""The facilities phase (phase 4, production and capacity; docs/formulas.md 22).

In order: each market good's month (22.4); contracts that ended settle take-or-pay; each
facility's month by id (capex, going live, depreciation; 22.2); then each player company's
Cloud hosting product takes its quality and features (22.3); then hardware's month (M12b,
26.2): plants' yields, contracts ending, the contract-manufacturing product's quality.
Operating costs post with phase 6's monthly costs, and outages roll in phase 6 (22.5).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import cloud, goods, lifecycle
from tst.sim.hardware.phase import hardware_month
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, player_companies


def production_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    state = goods.supply_phase(state, rng, balance, data)
    state, entries, logs = lifecycle.settle_contracts(state, balance, data)
    for facility in state.facilities:
        if facility.status == "closed":
            continue
        state, more, notes = lifecycle.facility_month(state, facility, balance, data)
        entries += more
        logs += notes
    for company in player_companies(state):
        state = cloud.refresh_product(state, company.id, balance, data)
    state, notes = hardware_month(state, rng, balance, data)  # M12b (26.2)
    logs += notes
    return state, tuple(entries), tuple(logs)
