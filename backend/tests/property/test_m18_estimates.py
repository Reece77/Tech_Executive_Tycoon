"""M18 (formulas.md 34.2, acceptance): every estimate range contains the truth at its stated
confidence, over 30 seeds; and exploration's ledger entries balance."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m18
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.models import Project
from tst.sim.exploration.phase import exploration_month
from tst.sim.exploration.pipeline import OrderDrilling, StartDeskStudy, StartStage, TakeLicence
from tst.sim.ledger import CASH
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

SEEDS = range(1, 31)
HOLES = (8, 20, 40)
SKILL = 10.0
TOLERANCE = 0.03  # binomial slack on a few thousand ranges at 90%


def _holes(state: GameState, project: Project, n: int, loaded: LoadedData) -> GameState:
    holes = tuple(
        xp.drill_hole(
            replace(state, turn=i),
            project,
            i,
            RngFactory(state.save_meta.master_seed),
            loaded.balance,
            loaded.game_data,
        )
        for i in range(1, n + 1)
    )
    return replace(state, holes=holes)


@pytest.fixture(scope="module")
def coverage(loaded: LoadedData) -> dict[str, list[bool]]:
    """Every deposit of every seed, drilled by a skill-10 team: whether each range holds the
    truth (grade after 8, 20 and 40 holes; the sample's grade; the estimate's tonnage)."""
    b, d = loaded.balance, loaded.game_data
    out: dict[str, list[bool]] = {"grade": [], "sample": [], "tonnage": []}
    for seed in SEEDS:
        state, _ = m18.explorer(loaded, seed, SKILL, geologists=2)
        rng = RngFactory(seed)
        for block in state.geo_blocks:
            if block.true_commodity is None:
                continue
            project = Project(
                id=1 + block.index,
                company_id=1,
                region=block.region,
                block=block.index,
                licence_turn=0,
                expires_turn=60,
                commodity=block.true_commodity,
            )
            sampled = xp.sample_result(state, project, rng, b, d)
            assert sampled.sample_center is not None and sampled.sample_hw is not None
            out["sample"].append(
                abs(math.log(block.true_grade) - sampled.sample_center) <= sampled.sample_hw
            )
            for n in HOLES:
                drilled = _holes(state, project, n, loaded)
                est = xp.running_estimate(drilled, project, b, d)
                assert est is not None
                out["grade"].append(abs(math.log(block.true_grade) - est[0]) <= est[1])
            estimated = xp.estimate_result(drilled, project, rng, b, d)
            assert estimated.est_tonnage_center is not None
            assert estimated.est_tonnage_hw is not None
            out["tonnage"].append(
                abs(math.log(block.true_tonnage_mt) - estimated.est_tonnage_center)
                <= estimated.est_tonnage_hw
            )
    return out


@pytest.mark.parametrize("kind", ["grade", "sample", "tonnage"])
def test_ranges_contain_the_truth_at_their_confidence(
    loaded: LoadedData, coverage: dict[str, list[bool]], kind: str
) -> None:
    hits = coverage[kind]
    stated = loaded.balance.exploration.confidence
    share = sum(hits) / len(hits)
    assert len(hits) > 300
    assert share >= stated - TOLERANCE, f"{kind}: {share:.3f} of {len(hits)} ranges"
    assert share <= stated + TOLERANCE + 0.04  # and not merely wide


ACTIONS = st.lists(
    st.tuples(st.integers(0, 6), st.integers(0, 59), st.integers(1, 40)), min_size=1, max_size=25
)


@settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(script=ACTIONS, seed=st.integers(1, 30))
def test_exploration_ledger_balances(
    loaded: LoadedData, script: list[tuple[int, int, int]], seed: int
) -> None:
    """Any sequence of exploration actions and months: every entry balances, and cash falls by
    exactly what was spent on exploration less what projects sold for."""
    run = m18.Run(loaded, *m18.explorer(loaded, seed, 11.0, geologists=2))
    cash0 = run.balances[(1, CASH)]
    regions = loaded.game_data.region_keys
    stages = ("survey", "sampling", "estimate", "scoping", "definitive", "permitting")
    sold = 0
    for kind, a, b in script:
        me = run.founder
        projects = [p for p in run.state.projects if p.is_open]
        if kind == 0:
            run.act(StartDeskStudy(me, regions[a % len(regions)], "copper"))
        elif kind == 1:
            run.act(TakeLicence(me, regions[b % len(regions)], a))
        elif kind == 2 and projects:
            p = projects[a % len(projects)]
            run.act(
                StartStage(
                    me,
                    p.id,
                    stages[b % len(stages)],
                    commodity="copper" if b % len(stages) == 1 else None,
                )
            )
        elif kind == 3 and projects:
            run.act(OrderDrilling(me, projects[a % len(projects)].id, b))
        elif kind == 4 and projects:
            p = projects[a % len(projects)]
            out = run.act(xp.SellProject(me, p.id))
            if out is not None:
                sold += xp.project_of(run.state, p.id).sale_cents
        else:
            run.month()
    for e in run.state.projects:
        assert e.spent_cents >= 0
    assert cash0 - run.balances[(1, CASH)] == run.spent - sold


def test_entries_balance_through_a_month(loaded: LoadedData) -> None:
    run = m18.Run(loaded, *m18.explorer(loaded, 7, 12.0, geologists=2))
    region, block = next(
        (x.region, x.index)
        for x in run.state.geo_blocks
        if x.true_commodity and xp.holder_of(run.state, x.region, x.index) is None
    )
    assert run.act(TakeLicence(run.founder, region, block)) is not None
    pid = run.state.projects[0].id
    run.state = xp.with_project(
        run.state,
        replace(
            xp.project_of(run.state, pid),
            commodity=run.state.geo_blocks[0].true_commodity or "copper",
        ),
    )
    assert run.act(OrderDrilling(run.founder, pid, 12)) is not None
    state, entries, _ = exploration_month(
        run.state, RngFactory(7), loaded.balance, loaded.game_data
    )
    assert entries and all(sum(x.amount for x in e.lines) == 0 for e in entries)
    assert start_game(loaded, 7).state.geo_blocks == state.geo_blocks  # truth never moves
