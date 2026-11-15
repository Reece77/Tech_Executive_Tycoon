"""M34 property (docs/formulas.md 48.4): a structural order never arrives without its
preconditions and at least `structural.warning_months` of warning signs, whatever the history of
breaches and rulings. The order's chance is set to 1 so that every ruling that may be structural
is, and the property is checked at every ruling."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.platform_helpers import START
from tests.regulation_helpers import owner_state
from tst.loader import LoadedData, load_all
from tst.sim.data_models import Balance
from tst.sim.regulation import cases, duties, structural
from tst.sim.regulation import data as rdata
from tst.sim.regulation.models import Case
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

MONTHS = 96


@cache
def _loaded() -> LoadedData:
    from tests.conftest import DATA_DIR

    return load_all(DATA_DIR)


@cache
def _base() -> tuple[GameState, int]:
    state, _, platform = owner_state(_loaded(), turn=START)
    state = replace(
        state,
        companies=tuple(
            replace(c, mrr_history=(10**11,) * 12) if c.id == state.player.id else c
            for c in state.companies
        ),
    )
    return state, platform.id


def _always(balance: Balance) -> Balance:
    rb = balance.regulation
    structural_b = rb.structural.model_copy(update={"chance": 1.0})
    return balance.model_copy(
        update={"regulation": rb.model_copy(update={"structural": structural_b})}
    )


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(1, 10**6),
    breaching=st.lists(st.booleans(), min_size=MONTHS, max_size=MONTHS),
    rulings=st.sets(st.integers(0, MONTHS - 1), max_size=12),
)
def test_no_structural_order_without_preconditions_and_three_years_of_warnings(
    seed: int, breaching: list[bool], rulings: set[int]
) -> None:
    loaded = _loaded()
    d = loaded.game_data
    b = _always(loaded.balance)
    state, platform_id = _base()
    me = state.player.id
    eu = rdata.file(d).regulator("eu_commission")
    need = b.regulation.structural.warning_months
    for m in range(MONTHS):
        turn = START + m
        pref = "strong" if breaching[m] else "off"
        state = replace(
            state,
            turn=turn,
            platforms=tuple(
                replace(p, self_pref=pref) if p.id == platform_id else p  # type: ignore[arg-type]
                for p in state.platforms
            ),
        )
        state, _ = structural.watches_month(state, b, d)
        if m not in rulings:
            continue
        case = Case(
            id=cases.next_case_id(state), regulator=eu.key, company_id=me,
            conduct="self_preferencing", market="devices", opened_turn=turn, stage="objections",
            stage_turn=turn, due_turn=turn, contested=True, remedy="no_self_preferencing",
        )  # fmt: skip
        state = cases.with_case(state, case)
        held = structural.conditions(state, me, eu, "devices", b, d)
        watch = structural.watch_of(state, me, eu.key, "devices")
        before = len(state.reg_orders)
        state, _, _ = cases.rule(state, case, RngFactory(seed + m), b, d)
        if len(state.reg_orders) > before:
            order = state.reg_orders[-1]
            assert held, "an order without its preconditions"
            assert watch is not None and watch.signs, "an order without warning signs"
            assert turn - watch.first_turn >= need, "an order with under three years of warnings"
            assert order.ordered_turn - order.warned_from >= need
        if state.reg_orders:
            break
        # a ruling's remedy binds from now; the next month's breach is non-compliance
        assert duties.binding(state, me, eu.key, "no_self_preferencing") or not any(
            c.ruled_turn for c in state.reg_cases
        )


def test_the_harness_does_reach_orders() -> None:
    """Not vacuous: always breaching, a ruling every six months, an order comes on some seed, and
    only after three years of signs."""
    loaded = _loaded()
    d, b = loaded.game_data, _always(loaded.balance)
    eu = rdata.file(d).regulator("eu_commission")
    found = []
    for seed in range(1, 6):
        state, platform_id = _base()
        me = state.player.id
        for m in range(MONTHS):
            state = replace(
                state,
                turn=START + m,
                platforms=tuple(
                    replace(p, self_pref="strong") if p.id == platform_id else p
                    for p in state.platforms
                ),
            )
            state, _ = structural.watches_month(state, b, d)
            if m % 6:
                continue
            case = Case(
                id=cases.next_case_id(state), regulator=eu.key, company_id=me,
                conduct="self_preferencing", market="devices", opened_turn=state.turn,
                stage="objections", stage_turn=state.turn, due_turn=state.turn, contested=True,
                remedy="no_self_preferencing",
            )  # fmt: skip
            state = cases.with_case(state, case)
            state, _, _ = cases.rule(state, case, RngFactory(seed * 1000 + m), b, d)
            if state.reg_orders:
                found.append(state.reg_orders[0])
                break
    assert found
    assert all(
        o.ordered_turn - o.warned_from >= b.regulation.structural.warning_months for o in found
    )
