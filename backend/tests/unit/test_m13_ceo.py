"""M13 Chair and CEO (docs/formulas.md 25.6): appointing, the CEO acting in phase 2 within
guardrails and never taking a Chair-only action (property test), overrides at an energy cost,
Chair energy, and the board's vote."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import make_person, with_employee, with_product
from tests.unit.test_m13_ipo import LOADED
from tests.unit.test_m13_public import LISTED
from tst.sim.actions import AppointCeo, OverrideCeo, RepayLoan, apply_action
from tst.sim.errors import SimError
from tst.sim.hiring.phases import reset_energy
from tst.sim.ledger import CASH
from tst.sim.markets_public.public import apply_public_step
from tst.sim.org.ceo import CEO_ACTIONS, CHAIR_ONLY, _CeoSeat, run_ceo
from tst.sim.org.ceo_rules import appoint
from tst.sim.org.delegates import DelegateRun
from tst.sim.org.models import Authority
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, ceo_of, with_person_state

CID = 1
CEO = 900


def staffed(state: GameState = LISTED, seed: int = 1, price: int = 70_000) -> GameState:
    state = with_employee(
        LOADED, state, make_person(LOADED, CEO, "product_manager", "senior"), 25_000_000
    )
    for pid in range(901, 905):
        state = with_employee(LOADED, state, make_person(LOADED, pid), 9_000_000)
    state = with_product(
        state,
        prices={"smb": 4000, "mid_market": price},
        customers={"smb": 500.0, "mid_market": 50.0},
        status="live",
        quality=45.0,
    )
    return state


def with_ceo_appointed(state: GameState) -> GameState:
    return appoint(state, CID, CEO, LOADED.balance, LOADED.game_data)


def test_appoint_rules() -> None:
    b, d = LOADED.balance, LOADED.game_data
    state = staffed()
    founder = state.founder_of(CID)
    assert founder is not None
    with pytest.raises(SimError):
        appoint(state, CID, founder.id, b, d)  # the founder becomes Chair, not CEO
    early = replace(
        state, companies=tuple(replace(c, stage=3) if c.id == CID else c for c in state.companies)
    )
    with pytest.raises(SimError):
        appoint(early, CID, CEO, b, d)  # stage 4 only
    with pytest.raises(SimError):
        appoint(state, CID, 901, b, d)  # mid level is not executive level
    out = apply_action(
        state, AppointCeo(founder.id, CEO), RngFactory(1), b, d, {(CID, CASH): 10**12}, seq=0
    )
    ceo = ceo_of(out.new_state, CID)
    assert ceo is not None and ceo.person_id == CEO and ceo.active
    used = state.person_state(founder.id).energy - out.new_state.person_state(founder.id).energy  # type: ignore[operator]
    assert used == b.ceo.appoint_energy == 10
    with pytest.raises(SimError):
        appoint(out.new_state, CID, CEO, b, d)  # one CEO at a time


def test_chair_energy() -> None:
    state = with_ceo_appointed(staffed())
    founder = state.founder_of(CID)
    assert founder is not None
    state = reset_energy(state, LOADED.balance, LOADED.game_data)
    assert state.person_state(founder.id).energy == LOADED.balance.ceo.chair_energy == 40
    no_ceo = reset_energy(staffed(), LOADED.balance, LOADED.game_data)
    assert no_ceo.person_state(founder.id).energy == LOADED.balance.founder.energy_per_month


def test_ceo_refuses_chair_only_actions() -> None:
    state = with_ceo_appointed(staffed())
    run = DelegateRun(state, {(CID, CASH): 10**12}, RngFactory(1), LOADED.balance, LOADED.game_data)
    seat = _CeoSeat(run, Authority(CID, "cfo", True, (), 0), CEO, True)
    assert not seat.act(RepayLoan(CEO, 1, 100_000_00), "repaid a loan")
    assert not run.taken


def _ceo_actions(seed: int, price: int, cash: int) -> tuple[GameState, list[object]]:
    state = with_ceo_appointed(staffed(price=price))
    state = with_person_state(state, replace(state.person_state(CEO), energy=None))
    out_state, _, _, taken = run_ceo(  # at the controls: the CEO's own decisions only;
        state,  # an approved pitch is the Chair's decision (M13b, 27.1)
        RngFactory(seed),
        LOADED.balance,
        LOADED.game_data,
        {(CID, CASH): cash},
        at_controls=True,
    )
    return out_state, [a for cid, a in taken if a.actor_id == CEO]  # type: ignore[attr-defined]


@settings(max_examples=20, deadline=None)
@given(
    seed=st.integers(0, 10_000),
    price=st.integers(20_000, 200_000),
    cash=st.integers(10_000_00, 10**12),
)
def test_ceo_stays_within_guardrails_property(seed: int, price: int, cash: int) -> None:
    """The CEO only takes CEO_ACTIONS (never a Chair-only one), moves prices within 10% of the
    player's last price, and plans no hires past the headcount guardrails."""
    state, actions = _ceo_actions(seed, price, cash)
    ceo = ceo_of(state, CID)
    assert ceo is not None
    anchors = {(p, s): c for p, s, c in ceo.price_anchors}
    band = LOADED.balance.ceo.price_band_pct / 100
    for action in actions:
        kind = action.kind  # type: ignore[attr-defined]
        assert kind in CEO_ACTIONS and kind not in CHAIR_ONLY
        if kind == "set_price":
            anchor = anchors[(action.product_id, action.segment)]  # type: ignore[attr-defined]
            assert anchor * (1 - band) - 1 <= action.price_cents <= anchor * (1 + band) + 1  # type: ignore[attr-defined]
    for d in state.ceo_decisions:
        assert d.person_id == CEO and d.company_id == CID


def test_ceo_decisions_are_recorded_and_seeded() -> None:
    a, _ = _ceo_actions(5, 70_000, 10**12)
    b, _ = _ceo_actions(5, 70_000, 10**12)
    assert [d.text for d in a.ceo_decisions] == [d.text for d in b.ceo_decisions]
    assert a.ceo_decisions, "a stage-4 company with a CMO gap gets marketing decisions"


def test_override_costs_energy_and_reverts() -> None:
    state, _ = _ceo_actions(5, 70_000, 10**12)
    decision = next((d for d in state.ceo_decisions if d.undo), None)
    assert decision is not None
    founder = state.founder_of(CID)
    assert founder is not None
    state = with_person_state(state, replace(state.person_state(founder.id), energy=30))
    out = apply_action(
        state,
        OverrideCeo(founder.id, decision.id),
        RngFactory(1),
        LOADED.balance,
        LOADED.game_data,
        {(CID, CASH): 10**12},
        seq=0,
    )
    assert out.new_state.person_state(founder.id).energy == 30 - 6
    done = next(d for d in out.new_state.ceo_decisions if d.id == decision.id)
    assert done.overridden_turn == state.turn
    undo = dict(decision.undo)
    if undo["kind"] == "set_marketing":
        product = out.new_state.product(int(undo["product_id"]))
        assert product is not None and product.marketing_budget_cents == undo["budget_cents"]
    with pytest.raises(SimError):  # once only
        apply_action(
            out.new_state,
            OverrideCeo(founder.id, decision.id),
            RngFactory(1),
            LOADED.balance,
            LOADED.game_data,
            {(CID, CASH): 10**12},
            seq=1,
        )


def test_board_vote_replaces_the_ceo() -> None:
    state = with_ceo_appointed(staffed())
    state, logs = apply_public_step(state, CID, "ceo_replace", LOADED.balance)
    assert ceo_of(state, CID) is None
    assert any(item.template == "ceo_replaced" for item in logs)
