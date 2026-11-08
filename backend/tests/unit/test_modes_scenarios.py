"""M15b sub-task 4 (formulas.md 30.3): every historical scenario loads on the world as it stood,
and its goal check passes on a scripted success and fails on a scripted failure."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import DEFAULT_FOUNDER
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finance.models import FundingRound
from tst.sim.ledger import CASH, apply_entries
from tst.sim.modes import scenarios as sc
from tst.sim.modes.world import start_mode
from tst.sim.research.models import EraArrival
from tst.sim.rng import RngFactory
from tst.sim.setup import new_game
from tst.sim.state import GameState, with_company, with_era_arrival, with_product_segment

SEED = 7
KEYS = ("ai_lab", "mobile_first", "survive_2022", "chip_startup", "turnaround")


def _start(loaded: LoadedData, key: str):  # type: ignore[no-untyped-def]
    h = sc.scenario(loaded.game_data, key)
    state, entries = new_game(
        save_name="t",
        master_seed=SEED,
        scenario=loaded.game_data.scenario(h.background),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Kestrel",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    spec = sc.scenario_spec(key, loaded.game_data)
    world, opening = start_mode(
        state, entries, spec, DEFAULT_FOUNDER, RngFactory(SEED), loaded.balance, loaded.game_data
    )
    return world, apply_entries({}, opening)


@pytest.fixture(scope="module")
def starts(loaded: LoadedData) -> dict[str, tuple[GameState, dict]]:  # type: ignore[type-arg]
    return {key: _start(loaded, key) for key in KEYS}


def test_the_five_scenarios_are_the_30_3_list(loaded: LoadedData) -> None:
    assert tuple(h.key for h in loaded.game_data.historical) == KEYS


@pytest.mark.parametrize("key", KEYS)
def test_each_scenario_loads_on_its_years_world(loaded: LoadedData, starts, key: str) -> None:  # type: ignore[no-untyped-def]
    world, balances = starts[key]
    h = sc.scenario(loaded.game_data, key)
    assert world.turn == ym_to_turn(h.year, 1)
    assert world.mode is not None and world.mode.scenario == key and world.mode.result is None
    assert world.player.stage == h.stage
    staff = len(world.staff(world.player.id)) - 1  # the founder
    assert staff == sum(s.count for s in h.staff)
    assert len(world.company_products(world.player.id)) == len(h.products)
    debt = sum(x.principal_dollars for x in h.loans) * 100
    assert balances[(world.player.id, CASH)] == h.cash_dollars * 100 + debt
    from tst.sim.research.levels import historical_turn

    due = {e.key for e in loaded.game_data.eras.eras if historical_turn(e) < world.turn}
    assert due <= {a.key for a in world.era_arrivals}  # history has happened


def _at_deadline(state: GameState, key: str, loaded: LoadedData) -> GameState:
    h = sc.scenario(loaded.game_data, key)
    return replace(state, turn=sc.deadline_turn(h))


def _succeed(state: GameState, key: str, loaded: LoadedData) -> GameState:
    """A scripted success for each goal kind."""
    cid = state.player.id
    if key == "ai_lab":  # $100M ARR (playtest 4: Transformers first is only a bonus)
        mrr = 100_000_000 * 100 // 12 + 1
        return with_company(state, replace(state.player, mrr_history=(mrr,)))
    if key in ("mobile_first", "chip_startup"):
        if key == "chip_startup":  # the player's accelerator takes most of the units
            from tst.sim.products.models import Product, ProductSegment
            from tst.sim.state import with_product

            pid, ids = state.next_ids.take("product")
            state = replace(state, next_ids=ids)
            state = with_product(
                state,
                Product(
                    pid, cid, "chips_ai_accelerator", "Tensor", "live", 60, 100, 30, 0, state.turn
                ),
            )
            return with_product_segment(state, ProductSegment(pid, "hyperscalers", 150000, 10**6))
        product = state.company_products(cid)[0]
        seg = state.segments_of(product.id)[0]
        return with_product_segment(state, replace(seg, customers=2_000_000))
    profit = (5_000_000,) * 12
    company = replace(state.player, op_history=profit, mrr_history=(20_000_000,) * 12)
    return with_company(state, company)


@pytest.mark.parametrize("key", KEYS)
def test_each_goal_passes_and_fails(loaded: LoadedData, starts, key: str) -> None:  # type: ignore[no-untyped-def]
    world, balances = starts[key]
    b, d = loaded.balance, loaded.game_data
    # a scripted failure: nothing done by the deadline
    failed = sc.judge(_at_deadline(world, key, loaded), balances, b, d)
    assert failed.mode is not None and failed.mode.result == "failure"
    assert failed.save_meta.game_state == "scenario_done"
    # a scripted success, at the deadline
    won = sc.judge(_at_deadline(_succeed(world, key, loaded), key, loaded), balances, b, d)
    assert won.mode is not None and won.mode.result == "success", key
    # before the deadline nothing ends unless a reach goal holds
    assert sc.judge(world, balances, b, d).mode.result is None  # type: ignore[union-attr]


def test_the_ai_lab_wins_on_arr_and_transformers_is_a_bonus(  # type: ignore[no-untyped-def]
    loaded: LoadedData, starts
) -> None:
    """Playtest 4 (M15r addendum d): the goal is $100M ARR by December 2020. Causing the
    Transformers era first neither wins nor ends the game; it is a bonus the result screen
    shows."""
    world, balances = starts["ai_lab"]
    b, d = loaded.balance, loaded.game_data
    h = sc.scenario(d, "ai_lab")
    assert (h.goal.kind, h.goal.arr_dollars, h.deadline) == ("arr", 100_000_000, (2020, 12))
    assert h.goal.bonus_era == "transformers"
    cid = world.player.id
    first = with_era_arrival(world, EraArrival("transformers", world.turn, cid, 12))
    assert sc.bonus_reached(h.goal, world) is False
    assert sc.bonus_reached(h.goal, first) is True
    assert sc.judge(first, balances, b, d).mode.result is None  # type: ignore[union-attr]
    lost = sc.judge(_at_deadline(first, "ai_lab", loaded), balances, b, d)
    assert lost.mode is not None and lost.mode.result == "failure"
    won = sc.judge(_succeed(first, "ai_lab", loaded), balances, b, d)  # early, on ARR
    assert won.mode is not None and won.mode.result == "success"
    assert sc.bonus_reached(h.goal, won) is True
    from tst.api.finance_views import _scenario_fields

    fields = _scenario_fields(won, loaded)  # the result screen's fields
    assert fields["scenario_goal"] == "Reach $100M ARR"
    assert fields["scenario_bonus"] == "Cause the Transformers era first"
    assert fields["scenario_bonus_reached"] is True
    assert _scenario_fields(world, loaded)["scenario_bonus_reached"] is False


def test_a_down_round_fails_the_turnaround(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    world, balances = starts["turnaround"]
    won = _succeed(world, "turnaround", loaded)
    down = FundingRound(
        99,
        won.player.id,
        "b",
        "closed",
        1,
        world.turn,
        world.turn,
        closed_turn=world.turn + 3,
        down_round=True,
    )
    won = replace(won, rounds=(*won.rounds, down))
    out = sc.judge(
        _at_deadline(won, "turnaround", loaded), balances, loaded.balance, loaded.game_data
    )
    assert out.mode is not None and out.mode.result == "failure"


def test_insolvent_survivor_fails(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    world, balances = starts["survive_2022"]
    won = _succeed(world, "survive_2022", loaded)
    broke = {**balances, (world.player.id, CASH): -1}
    out = sc.judge(
        _at_deadline(won, "survive_2022", loaded), broke, loaded.balance, loaded.game_data
    )
    assert out.mode is not None and out.mode.result == "failure"
