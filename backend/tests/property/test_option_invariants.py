"""Option invariants under random hires, departures and months (formulas.md 14.2): holdings
always sum to FD, vested never exceeds granted, and the unallocated pool never goes negative.
Without a priced round FD never changes: grants and forfeits only move shares in and out of
the pool."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.finance.captable import fd_shares, unallocated
from tst.sim.finance.options import grant_on_hire, settle_leavers, vest
from tst.sim.state import GameState, with_employment

STEPS = st.lists(
    st.one_of(
        st.tuples(st.just("hire"), st.integers(min_value=0, max_value=200)),
        st.tuples(st.just("leave"), st.integers(min_value=0, max_value=30)),
        st.tuples(st.just("month"), st.integers(min_value=1, max_value=20)),
    ),
    max_size=40,
)


def check(state: GameState, fd: int) -> None:
    entries = sum(e.shares for e in state.cap_entries)
    options = sum(g.outstanding for g in state.grants)
    assert entries + options == fd_shares(state, 1) == fd
    assert unallocated(state, 1) >= 0
    for g in state.grants:
        assert 0 <= g.vested <= g.granted and 0 <= g.forfeited <= g.granted
        assert g.vested + g.forfeited <= g.granted


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(STEPS)
def test_holdings_sum_to_fd(loaded: LoadedData, steps: list[tuple[str, int]]) -> None:
    state = fresh_game(loaded)
    fd = fd_shares(state, 1)
    next_pid = 2
    for kind, n in steps:
        if kind == "hire":
            person = make_person(loaded, next_pid)
            next_pid += 1
            state = with_employee(loaded, state, person, 9_000_000, equity_bp=n)
            state = grant_on_hire(state, state.employments[-1])
        elif kind == "leave":
            staff = [e for e in state.employments if e.counts_as_staff and e.person_id != 1]
            if staff:
                gone = staff[n % len(staff)]
                state = with_employment(state, replace(gone, status="ended", end_turn=state.turn))
                state = settle_leavers(state)
        else:
            for _ in range(n):
                state = vest(replace(state, turn=state.turn + 1), loaded.balance)
        check(state, fd)
