"""M13b sub-task 2 (formulas.md 27.1): the CPO seat takes authority with its guardrails (a
headcount cap for new product teams, the categories it may enter, the products it may not
sunset); with authority it launches products that are ready, and the CEO leaves product
priorities to it."""

from __future__ import annotations

import pytest

from tests.helpers import with_product
from tests.unit.test_m10c_executives import EXEC, _company, _give, _right_seed, _run
from tst.loader import LoadedData
from tst.sim.actions.authority import SetAuthority, guardrails_for
from tst.sim.errors import OrgRuleError
from tst.sim.state import GameState


def _ready(loaded: LoadedData) -> GameState:
    state = _company(loaded, "cpo", "product_manager")
    return with_product(state, status="in_development", quality=60.0, feature_points=500.0)


def test_cpo_guardrails_default_and_validate(loaded: LoadedData) -> None:
    b = loaded.balance
    state = _ready(loaded)
    rails = dict(guardrails_for(None, "cpo", (), state, 1, b, loaded.game_data))
    assert rails == {"headcount_cap": 12, "categories": (), "protected_products": ()}
    product = state.company_products(1)[0].id
    ok = dict(
        guardrails_for(
            None,
            "cpo",
            (("categories", ("fintech", "dev_tools")), ("protected_products", (product,))),
            state,
            1,
            b,
            loaded.game_data,
        )
    )
    assert ok["categories"] == ("dev_tools", "fintech") and ok["protected_products"] == (product,)
    with pytest.raises(OrgRuleError, match="unknown categories"):
        guardrails_for(None, "cpo", (("categories", ("alchemy",)),), state, 1, b, loaded.game_data)
    with pytest.raises(OrgRuleError, match="the company's products"):
        guardrails_for(None, "cpo", (("protected_products", (999,)),), state, 1, b)


def test_cpo_with_authority_launches_a_ready_product(loaded: LoadedData) -> None:
    from tst.sim.actions.products import launch_problems

    state = _ready(loaded)
    product = state.company_products(1)[0]
    assert launch_problems(state, product, loaded.balance, loaded.game_data) == []
    state = _give(state, "cpo", loaded.balance)
    seed = _right_seed(loaded, state, "cpo", right=True)
    out, _, _, taken = _run(loaded, state, seed)
    assert out.product(product.id).status == "live"  # type: ignore[union-attr]
    assert [a.kind for _, a in taken] == ["launch_product"]
    assert [a.actor_id for _, a in taken] == [EXEC]
    (decision,) = out.exec_decisions
    assert decision.seat == "cpo" and decision.text == f"launched {product.name}"
    wrong = _right_seed(loaded, state, "cpo", right=False)
    late, _, _, _ = _run(loaded, state, wrong)
    assert late.product(product.id).status == "in_development"  # a misstep waits a month


def test_without_authority_the_cpo_does_nothing(loaded: LoadedData) -> None:
    state = _ready(loaded)
    out, entries, _logs, taken = _run(loaded, state)
    assert (out, entries, taken) == (state, (), ())


def test_set_authority_on_the_cpo_seat(loaded: LoadedData) -> None:
    from tests.unit.test_hiring_phases import Game

    game = Game(loaded, _ready(loaded))
    game.act(SetAuthority(game.state.founder_of(1).id, "cpo", True, (("headcount_cap", 6),)))  # type: ignore[union-attr]
    a = game.state.authority(1, "cpo")
    assert a is not None and a.enabled and a.number("headcount_cap") == 6
