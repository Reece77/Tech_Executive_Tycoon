"""M18 (formulas.md 34.1-34.4): geology at game start and the exploration pipeline."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from tst.balance import m18
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.errors import ExplorationRuleError
from tst.sim.events.models import GameEvent
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.geology import cell_deviations, generate_blocks
from tst.sim.exploration.phase import exploration_month, exploration_step
from tst.sim.exploration.pipeline import (
    OrderDrilling,
    RenewLicence,
    SellProject,
    StartDeskStudy,
    StartStage,
    TakeLicence,
)
from tst.sim.ledger import CASH, DISPOSAL, EXPLORATION
from tst.sim.rng import RngFactory
from tst.sim.state import life_of


def _run(loaded: LoadedData, seed: int = 3, skill: float = 12.0) -> m18.Run:
    state, balances = m18.explorer(loaded, seed, skill, geologists=3)
    return m18.Run(loaded, state, balances)


def _deposit(run: m18.Run, commodity: str = "copper") -> tuple[str, int]:
    """A free block holding `commodity`, for driving a project through every stage."""
    for b in run.state.geo_blocks:
        if b.true_commodity == commodity and xp.holder_of(run.state, b.region, b.index) is None:
            return b.region, b.index
    raise AssertionError("no free deposit")


def test_geology_is_drawn_at_start_and_seeded(loaded: LoadedData) -> None:
    gb = loaded.balance.geology
    a = start_game(loaded, 5).state
    b = start_game(loaded, 5).state
    c = start_game(loaded, 6).state
    assert len(a.geo_blocks) == gb.blocks_per_region * len(loaded.game_data.region_keys)
    assert a.geo_blocks == b.geo_blocks and a.geo_blocks != c.geo_blocks
    assert a.supplier_licences == b.supplier_licences
    held = {(x.region, x.block) for x in a.supplier_licences}
    assert len(held) == len(a.supplier_licences)  # one licence a block
    # one stream per block: the same generator, keyed by block, whatever the order
    again = generate_blocks(RngFactory(5), loaded.balance, loaded.game_data)
    assert again == a.geo_blocks
    assert sum(1 for x in a.geo_blocks if x.true_commodity) > 0
    assert any(x.true_commodity is None for x in a.geo_blocks)


def test_cell_deviations_are_standardised() -> None:
    devs = cell_deviations(RngFactory(1), 0, 0, 66)
    assert len(devs) == 66
    assert sum(devs) / 66 == pytest.approx(0.0, abs=1e-12)
    assert math.sqrt(sum(d * d for d in devs) / 66) == pytest.approx(1.0)


def test_gate_and_geologists(loaded: LoadedData) -> None:
    game = start_game(loaded, 2)
    run = m18.Run(loaded, game.state, dict(game.balances))
    with pytest.raises(ExplorationRuleError, match="stage 3"):
        xp.apply_exploration(
            run.state,
            StartDeskStudy(run.founder, "oceania", "lithium_carbonate"),
            RngFactory(2),
            run.balances,
            loaded.balance,
            loaded.game_data,
        )
    state, balances = m18.explorer(loaded, 2, 12.0, geologists=0)
    with pytest.raises(ExplorationRuleError, match="geologist"):
        xp.apply_exploration(
            state,
            StartDeskStudy(run.founder, "oceania", "lithium_carbonate"),
            RngFactory(2),
            balances,
            loaded.balance,
            loaded.game_data,
        )


def test_geologists_are_a_capacity(loaded: LoadedData) -> None:
    run = _run(loaded)
    for region in ("oceania", "africa", "europe"):
        assert run.act(StartDeskStudy(run.founder, region, "copper")) is not None
    assert run.act(StartDeskStudy(run.founder, "east_asia", "copper")) is None
    assert run.log["refused start_desk_study"] == 1


def test_desk_study_bands(loaded: LoadedData) -> None:
    run = _run(loaded)
    assert run.act(StartDeskStudy(run.founder, "latin_america", "copper")) is not None
    cost = loaded.balance.exploration.desk.cost_cents
    assert run.spent == cost
    for _ in range(loaded.balance.exploration.desk.months):
        assert not run.state.desk_studies[0].done
        run.month()
    study = run.state.desk_studies[0]
    n = loaded.balance.geology.blocks_per_region
    assert len(study.bands) == n
    assert study.bands.count("high") == round(loaded.balance.exploration.desk.high_share * n)


def test_a_project_through_every_stage(loaded: LoadedData) -> None:
    run = _run(loaded)
    region, block = _deposit(run, "copper")
    me = run.founder
    cash0 = run.balances[(1, CASH)]
    out = run.act(TakeLicence(me, region, block))
    assert out is not None
    pid = run.state.projects[0].id
    assert run.act(TakeLicence(me, region, block)) is None  # held already
    assert xp.holder_of(run.state, region, block) == 1

    def finish() -> None:
        for _ in range(30):
            p = xp.project_of(run.state, pid)
            if p.stage is None or not p.is_open:
                return
            run.month()
        raise AssertionError("stage never finished")

    assert run.act(StartStage(me, pid, "survey")) is not None
    finish()
    p = xp.project_of(run.state, pid)
    assert p.reading in ("none", "weak", "strong")
    assert run.act(StartStage(me, pid, "sampling", commodity="copper")) is not None
    finish()
    p = xp.project_of(run.state, pid)
    assert p.sample_center is not None and p.sample_hw is not None
    with pytest.raises(ExplorationRuleError):  # an estimate needs holes first
        xp.apply_exploration(
            run.state, StartStage(me, pid, "estimate"), RngFactory(3), run.balances,
            loaded.balance, loaded.game_data,
        )
    assert run.act(OrderDrilling(me, pid, 40)) is not None
    finish()
    holes = xp.holes_of(run.state, pid)
    assert [h.n for h in holes] == list(range(1, 41))
    assert all(h.cost_cents > 0 for h in holes)
    assert run.act(StartStage(me, pid, "estimate")) is not None
    finish()
    p = xp.project_of(run.state, pid)
    assert p.category == "measured" and p.est_tonnage_hw is not None
    assert run.act(StartStage(me, pid, "definitive")) is not None
    finish()
    p = xp.project_of(run.state, pid)
    assert p.level == "definitive"
    assert p.npv_lo_cents is not None and p.npv_mid_cents is not None
    assert p.npv_lo_cents <= p.npv_mid_cents <= (p.npv_hi_cents or 0)
    assert run.act(StartStage(me, pid, "permitting")) is not None
    for _ in range(12 * 15):
        if xp.project_of(run.state, pid).status != "active":
            break
        run.month()
    p = xp.project_of(run.state, pid)
    assert p.status in ("permitted", "refused") and p.permit_turn is not None
    # every cent spent left the bank as exploration
    assert cash0 - run.balances[(1, CASH)] == run.spent
    assert run.spent == p.spent_cents  # nothing else was explored
    if p.status == "permitted":
        price = xp.sale_price_cents(run.state, p, loaded.balance, loaded.game_data)
        if price > 0:
            before = run.balances[(1, CASH)]
            assert run.act(SellProject(me, pid)) is not None
            assert run.balances[(1, CASH)] - before == price
            assert run.balances[(1, DISPOSAL)] == -price
            assert xp.project_of(run.state, pid).status == "sold"
            assert any(x.block == block for x in run.state.supplier_licences)


def test_licences_lapse_and_renew(loaded: LoadedData) -> None:
    run = _run(loaded)
    region, block = _deposit(run, "copper")
    assert run.act(TakeLicence(run.founder, region, block)) is not None
    pid = run.state.projects[0].id
    years = loaded.balance.exploration.licence.years
    for _ in range(years * 12 - 1):
        run.month()
    assert run.act(RenewLicence(run.founder, pid)) is not None
    assert run.act(RenewLicence(run.founder, pid)) is None  # renewable once
    for _ in range(years * 12 + 1):  # to the renewed term's last month (turn 119)
        run.month()
    assert xp.project_of(run.state, pid).status == "active"
    run.month()
    assert xp.project_of(run.state, pid).status == "lapsed"
    assert xp.holder_of(run.state, region, block) is None


def test_a_game_that_never_explores_skips_the_phase(loaded: LoadedData) -> None:
    state = start_game(loaded, 4).state
    out = exploration_month(state, RngFactory(4), loaded.balance, loaded.game_data)
    assert out == (state, (), ())


def _permitting(loaded: LoadedData) -> tuple[m18.Run, int]:
    run = _run(loaded)
    region, block = _deposit(run, "copper")
    assert run.act(TakeLicence(run.founder, region, block)) is not None
    pid = run.state.projects[0].id
    p = replace(
        xp.project_of(run.state, pid),
        commodity="copper",
        level="definitive",
        stage="permitting",
        permit_start=run.state.turn,
        hidden_due_turn=run.state.turn + 24,
        protest_turn=run.state.turn + 1,
    )
    run.state = xp.with_project(run.state, p)
    return run, pid


def _event(run: m18.Run, pid: int) -> GameEvent:
    p = xp.project_of(run.state, pid)
    assert p.protest_turn is not None
    return GameEvent(0, 1, p.protest_turn, "community_blockade", "exploration", "critical",
                     "exploration", 1.0)


@pytest.mark.parametrize("step", ["consult", "benefit", "push_on"])
def test_protest_answers(loaded: LoadedData, step: str) -> None:
    run, pid = _permitting(loaded)
    pb = loaded.balance.exploration.permitting
    event = _event(run, pid)
    founder = run.founder
    before = life_of(run.state, founder)
    ruthless = before.ruthless if before else loaded.balance.persona.start
    state, entries, _ = exploration_step(
        replace(run.state, turn=event.turn), event, step, loaded.balance, loaded.game_data
    )
    p = xp.project_of(state, pid)
    assert p.protest_turn is None
    paid = sum(x.amount for e in entries for x in e.lines if x.account == EXPLORATION)
    if step == "consult":
        assert paid == pb.consult_cents
        assert p.hidden_due_turn == run.state.turn + 24 + pb.consult_months
    elif step == "benefit":
        assert paid == pb.benefit_cents and p.benefit
    else:
        assert p.pushes == 1
        life = life_of(state, founder)
        assert life is not None and life.ruthless == pytest.approx(ruthless + pb.push_ruthless)
    for e in entries:
        assert sum(x.amount for x in e.lines) == 0  # balanced


def test_the_decision_waits_for_an_open_protest(loaded: LoadedData) -> None:
    run, pid = _permitting(loaded)
    p = replace(xp.project_of(run.state, pid), hidden_due_turn=run.state.turn)
    run.state = xp.with_project(run.state, p)
    run_state, _, _ = exploration_month(
        run.state, RngFactory(3), loaded.balance, loaded.game_data
    )
    assert xp.project_of(run_state, pid).status == "active"  # still waiting for the answer
