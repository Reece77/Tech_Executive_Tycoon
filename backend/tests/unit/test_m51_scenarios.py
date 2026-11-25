"""M51 sub-task 1 (formulas.md 63.1): the six new scenarios' starts as `apply_start` builds them
(a running fab, a contract, a prototype, a family and an older founder), and each goal kind
passing on a scripted success and failing on a scripted failure.

The starts here skip the dormant world (the turn is moved to the start month without playing
it, which `play_world` covers in test_modes_scenarios): they test what the scenario adds."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import DEFAULT_FOUNDER
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.fabs.models import FabMonth
from tst.sim.finance.models import FundingRound
from tst.sim.ledger import CASH, apply_entries
from tst.sim.modes import scenarios as sc
from tst.sim.modes.models import GameMode
from tst.sim.platforms.models import Platform, PlatformRegion
from tst.sim.rng import RngFactory
from tst.sim.setup import new_game
from tst.sim.state import GameState, with_company
from tst.sim.vehicles.models import VehicleMonth

SEED = 51
NEW = ("the_crash", "failing_chipmaker", "ev_maker", "under_controls", "platform_war", "the_dynasty")


def _fast_start(loaded: LoadedData, key: str) -> tuple[GameState, dict[tuple[int, str], int]]:
    """The scenario's company on an unplayed world moved to its start month."""
    d = loaded.game_data
    h = sc.scenario(d, key)
    state, entries = new_game(
        save_name="t",
        master_seed=SEED,
        scenario=d.scenario(h.background),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Kestrel",
        founder=sc.founder_spec(h, DEFAULT_FOUNDER),
        balance=loaded.balance,
        data=d,
        hq_city=h.hq_city,
        family=sc.family_spec(h),
        start_year=sc.world_year(h),
    )
    state = replace(state, turn=ym_to_turn(h.year, 1))
    state, extra = sc.apply_start(state, key, RngFactory(SEED), loaded.balance, d)
    state = replace(state, mode=GameMode(kind="scenario", start_turn=state.turn, scenario=key))
    return state, dict(apply_entries({}, (*entries, *extra)))


@pytest.fixture(scope="module")
def starts(loaded: LoadedData) -> dict[str, tuple[GameState, dict[tuple[int, str], int]]]:
    return {key: _fast_start(loaded, key) for key in NEW}


def test_the_new_scenarios_follow_the_five(loaded: LoadedData) -> None:
    keys = tuple(h.key for h in loaded.game_data.historical)
    assert keys[5:] == ("the_crash", "platform_war", "ev_maker", "failing_chipmaker", "under_controls", "the_dynasty")  # fmt: skip


@pytest.mark.parametrize("key", NEW)
def test_each_start_is_built_and_balanced(loaded: LoadedData, starts, key: str) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts[key]
    h = sc.scenario(loaded.game_data, key)
    cid = state.player.id
    assert state.player.stage == h.stage
    assert len(state.staff(cid)) - 1 == sum(s.count for s in h.staff)
    named = {s.unit for s in h.staff if s.unit is not None}
    assert named <= {u.name for u in state.units}
    assert sum(balances.values()) == 0  # double entry: the books balance
    founder = state.founder_of(cid)
    assert founder is not None
    if h.founder_age is not None:
        assert founder.age(state.turn) == h.founder_age


def test_the_chipmaker_runs_a_mature_fab_on_its_books(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["failing_chipmaker"]
    (fab,) = [f for f in state.fabs if f.company_id == state.player.id]
    facility = state.facility(fab.facility_id)
    assert facility is not None and facility.status == "live" and fab.node == "n65"
    assert fab.yield_ == loaded.balance.fab.yield_.mature
    crew = next(u for u in state.units if u.name == "Fab crew 1")
    assert facility.unit_id == crew.id
    book = balances[(state.player.id, "1500_ppe")] + balances.get(
        (state.player.id, "1510_accumulated_depreciation"), 0
    )
    assert book == facility.capex_cents - facility.depreciated_cents > 0
    # the fab is on the books against equity, not paid in cash (the fast start's cash is the
    # background's; start_mode posts the scenario's)
    background = loaded.balance.scenario["funded_spinout"].starting_cash_cents
    assert balances[(state.player.id, CASH)] == background


def test_under_controls_is_a_chinese_foundry(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, _ = starts["under_controls"]
    assert state.player.hq_city == "shenzhen"
    (fab,) = [f for f in state.fabs if f.company_id == state.player.id]
    assert fab.node == "n16"


def test_the_phone_maker_has_a_contract_and_the_ev_maker_a_prototype(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    phones, _ = starts["platform_war"]
    (phone,) = phones.company_products(phones.player.id)
    (contract,) = [c for c in phones.production_contracts if c.product_id == phone.id]
    assert (contract.supplier, contract.units, contract.end_turn) == ("foxconn", 60_000, 17)
    cars, _ = starts["ev_maker"]
    (car,) = cars.company_products(cars.player.id)
    assert car.status == "in_development" and car.launched_turn is None


def test_the_dynasty_founder_has_three_children(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, _ = starts["the_dynasty"]
    h = sc.scenario(loaded.game_data, "the_dynasty")
    assert state.family is not None and h.length == "dynasty"
    kids = [m for m in state.family_members if m.relation == "child"]
    assert len(kids) == 3
    # built in 2010 (the world's first year), 20 years younger: the dormant years age them
    assert sorted(state.person(m.person_id).age(0) for m in kids) == [9, 13, 16]


# --- Goals -----------------------------------------------------------------------------------


def _judge(state: GameState, balances, loaded: LoadedData, final: bool) -> str | None:  # type: ignore[no-untyped-def]
    h = sc.scenario(loaded.game_data, state.mode.scenario)  # type: ignore[union-attr,arg-type]
    if final:
        state = replace(state, turn=sc.deadline_turn(h))
    out = sc.judge(state, balances, loaded.balance, loaded.game_data)
    return out.mode.result  # type: ignore[union-attr]


def test_the_crash_needs_a_series_a_and_cash(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["the_crash"]
    assert _judge(state, balances, loaded, final=True) == "failure"
    a = FundingRound(90, state.player.id, "a", "closed", 1, state.turn, state.turn, closed_turn=-4)
    raised = replace(state, rounds=(*state.rounds, a))
    assert _judge(raised, balances, loaded, final=False) is None  # judged at the deadline
    assert _judge(raised, balances, loaded, final=True) == "success"
    broke = {**balances, (state.player.id, CASH): -1}
    assert _judge(raised, broke, loaded, final=True) == "failure"


def test_the_platform_war_wins_on_developers(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["platform_war"]
    own = Platform(
        id=100, key="own", name="Kestrel OS", store="Store", kind="device",
        owner_id=state.player.id, owner_label="Kestrel", regions=("north_america",),
        launched_turn=state.turn,
    )  # fmt: skip
    for share, want in ((0.05, None), (0.12, "success")):
        rows = (PlatformRegion(100, "north_america", 0.0, share, 0.0),)
        s2 = replace(state, platforms=(*state.platforms, own), platform_regions=rows)
        assert _judge(s2, balances, loaded, final=False) == want
    assert _judge(state, balances, loaded, final=True) == "failure"


def _cars(state: GameState, per_month: float) -> GameState:
    (car,) = state.company_products(state.player.id)
    rows = tuple(
        VehicleMonth(state.turn - i, car.id, per_month, 0, 0, 0, 0, 0, 0.0, 0, 0, "l2", 400.0)
        for i in range(12)
    )
    return replace(state, vehicle_months=rows)


def test_the_ev_maker_wins_on_cars_a_year(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["ev_maker"]
    assert sc.cars_a_year(_cars(state, 5_000), state.player.id) == 60_000
    assert _judge(_cars(state, 5_000), balances, loaded, final=False) is None
    assert _judge(_cars(state, 6_000), balances, loaded, final=False) == "success"
    assert _judge(state, balances, loaded, final=True) == "failure"


def _running(state: GameState, node: str) -> GameState:
    fab = next(f for f in state.fabs if f.company_id == state.player.id)
    month = FabMonth(turn=state.turn, available=10_000, sold=9_000)
    return replace(state, fabs=(replace(fab, node=node, month=month),))


def test_the_chipmaker_must_catch_up_and_profit(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["failing_chipmaker"]
    at = replace(state, turn=ym_to_turn(2016, 1))  # 16 nm leads (Intel 2014, TSMC 2015)
    profit = with_company(at, replace(at.player, op_history=(1_000,) * 12))
    b, d = loaded.balance, loaded.game_data
    assert sc.best_node_gap(_running(profit, "n20"), profit.player.id, b, d) == 1
    assert _judge(_running(profit, "n28"), balances, loaded, final=False) is None
    assert _judge(_running(at, "n20"), balances, loaded, final=False) is None  # no profit
    assert _judge(_running(profit, "n20"), balances, loaded, final=False) == "success"


def test_under_controls_needs_7nm_volume(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["under_controls"]
    assert _judge(_running(state, "n10"), balances, loaded, final=False) is None
    assert _judge(_running(state, "n7"), balances, loaded, final=False) == "success"
    idle = _running(state, "n7")
    fab = idle.fabs[0]
    idle = replace(idle, fabs=(replace(fab, month=FabMonth(turn=state.turn)),))
    assert _judge(idle, balances, loaded, final=False) is None  # 7 nm built but running nothing


def test_the_dynasty_needs_an_heir_at_the_head_and_control(loaded: LoadedData, starts) -> None:  # type: ignore[no-untyped-def]
    state, balances = starts["the_dynasty"]
    assert state.family is not None
    assert _judge(state, balances, loaded, final=True) == "failure"  # the founder still heads it
    heir = next(m for m in state.family_members if m.relation == "child")
    handed = replace(state, family=replace(state.family, head_id=heir.person_id))
    assert _judge(handed, balances, loaded, final=False) is None  # judged at the deadline
    # the heir must hold control with the family: move the founder's shares to them
    from tst.sim.family import rules

    assert rules.family_bp(handed) >= loaded.balance.family.control_bp
    assert _judge(handed, balances, loaded, final=True) == "success"
    pro = replace(handed, family=replace(handed.family, head_mode="family_head"))  # type: ignore[arg-type]
    assert _judge(pro, balances, loaded, final=True) == "failure"  # a professional CEO runs it
