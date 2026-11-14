"""M28 sub-task 2's property test: every chain company's ledger balances, whatever their costs,
cash and the months they run (docs/formulas.md 41.1). Each company's accounts sum to zero, its
plant is never depreciated past its cost, and a company that fails has closed every plant."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.world_helpers import world_state
from tst.balance.m28 import loaded as m28_loaded
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    PPE,
    LedgerEntry,
    LedgerLine,
    apply_entries,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.world import decide, groups, operate


@cache
def _start() -> tuple[GameState, dict[tuple[int, str], int]]:
    state, balances = world_state(m28_loaded(), seed=7, turn=200)
    return state, dict(balances)


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    costs=st.lists(st.floats(0, 1), min_size=1, max_size=8),
    drain=st.lists(st.integers(0, 4), min_size=1, max_size=8),
    months=st.integers(1, 5),
)
def test_chain_ledgers_balance(costs: list[float], drain: list[int], months: int) -> None:
    loaded = m28_loaded()
    b, d = loaded.balance, loaded.game_data
    state, balances = _start()
    # perturb cost positions and take cash away (a drain of 4 leaves some companies short)
    facilities = tuple(
        replace(f, cost=costs[i % len(costs)]) for i, f in enumerate(state.world_facilities)
    )
    state = replace(state, world_facilities=facilities)
    extra: list[LedgerEntry] = []
    for i, rec in enumerate(state.chain_companies):
        cash = balances.get((rec.company_id, CASH), 0)
        take = cash * drain[i % len(drain)] // 3
        if take:
            extra.append(
                LedgerEntry(
                    state.turn,
                    rec.company_id,
                    "test drain",
                    (LedgerLine(CASH, -take), LedgerLine("3000_common_equity", take)),
                )
            )
    balances = dict(apply_entries(balances, extra))
    rng = RngFactory(7)
    for m in range(months):
        turn = 203 if m == months - 1 else state.turn  # end on a December
        state = replace(state, turn=turn)
        state, entries, _ = operate.operate(state, b, d, balances)
        balances = dict(apply_entries(balances, entries))
        state, entries, _ = decide.decide(state, rng, b, d, balances)
        balances = dict(apply_entries(balances, entries))
        state, entries, _ = groups.groups_month(state, rng, b, d, balances)
        balances = dict(apply_entries(balances, entries))
        state = replace(state, turn=state.turn + 1)
    for rec in state.chain_companies:
        cid = rec.company_id
        assert sum(v for (c, _), v in balances.items() if c == cid) == 0
        plant = balances.get((cid, PPE), 0)
        assert plant >= -balances.get((cid, ACCUMULATED_DEPRECIATION), 0) >= 0
        if not state.company(cid).alive:
            assert all(f.status == "closed" for f in state.world_facilities if f.company_id == cid)
