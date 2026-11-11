"""M23b: the v3 scripts (tst.balance.strategies_v3) and the group P&L the v3 targets read
(tst.balance.game). Short runs only; the targets themselves are weekly
(tests/balance/test_v3_balance.py)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m18, m21, strategies_v3
from tst.balance.game import PLAYER, Game, start_game
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.models import Hole, Project
from tst.sim.ledger import CASH, COMMON_EQUITY, INTERCOMPANY_PURCHASES, INTERCOMPANY_SALES
from tst.sim.state import reach_stage, with_company


def _stage_3(seed: int = 1, cash: int = 10**12) -> Game:
    """A new game's player at stage 3 with `cash` more in the bank and two geologists."""
    loaded = m21.loaded()
    game = start_game(loaded, seed)
    state = with_company(game.state, reach_stage(game.state.player, 3, 0))
    game.state = m18.add_geologists(state, loaded, 12.0, 2)
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) + cash
    game.balances[(PLAYER, COMMON_EQUITY)] = game.balances.get((PLAYER, COMMON_EQUITY), 0) - cash
    return game


def _project(game: Game, **fields: object) -> Project:
    """A licence on block 0 of Oceania, then `fields` set as a stage's results would."""
    assert game.act(xp.TakeLicence(game.founder_id, "oceania", 0))
    p = replace(game.state.projects[-1], **fields)  # type: ignore[arg-type]
    game.state = xp.with_project(game.state, p)
    return p


def _holes(game: Game, p: Project, n: int) -> None:
    holes = tuple(Hole(p.id, i + 1, game.state.turn, 0.02, 1.0, 0) for i in range(n))
    game.state = replace(game.state, holes=(*game.state.holes, *holes))


def _stage_of(game: Game, pid: int) -> str | None:
    return xp.project_of(game.state, pid).stage


@pytest.mark.parametrize(
    ("fields", "holes", "expected"),
    [
        ({}, 0, "survey"),
        ({"reading": "strong", "commodity": "lithium_carbonate"}, 0, "sampling"),
    ],
)
def test_exploration_starts_the_next_stage(
    fields: dict[str, object], holes: int, expected: str
) -> None:
    game = _stage_3()
    p = _project(game, **fields)
    _holes(game, p, holes)
    strategies_v3._advance(game, xp.project_of(game.state, p.id), "lithium_carbonate")
    assert _stage_of(game, p.id) == expected


def test_exploration_drills_to_forty_holes_after_sampling() -> None:
    game = _stage_3()
    p = _project(
        game, reading="strong", commodity="lithium_carbonate", sample_center=-4.0, sample_hw=0.5
    )
    _holes(game, p, 10)
    strategies_v3._advance(game, xp.project_of(game.state, p.id), "lithium_carbonate")
    assert xp.project_of(game.state, p.id).holes_left == strategies_v3.HOLES - 10


def test_exploration_gives_up_on_an_empty_survey_and_a_negative_study() -> None:
    game = _stage_3()
    empty = _project(game, reading="none")
    strategies_v3._advance(game, empty, "lithium_carbonate")
    assert xp.project_of(game.state, empty.id).status == "relinquished"

    game = _stage_3()
    p = _project(
        game,
        reading="strong",
        commodity="lithium_carbonate",
        sample_center=-4.0,
        sample_hw=0.5,
        category="indicated",
        level="scoping",
        npv_mid_cents=-1,
    )
    _holes(game, p, strategies_v3.HOLES)
    p = replace(xp.project_of(game.state, p.id), est_holes=strategies_v3.HOLES)
    game.state = xp.with_project(game.state, p)
    strategies_v3._advance(game, p, "lithium_carbonate")
    assert xp.project_of(game.state, p.id).status == "relinquished"


def test_the_ladder_waits_for_stage_3_and_cash() -> None:
    game = start_game(m21.loaded(), 1)
    assert not strategies_v3.ready_for(game, 1)
    game = _stage_3(cash=0)
    assert not strategies_v3.ready_for(game, 10**12)
    assert strategies_v3.ready_for(_stage_3(), 10**9)


def test_full_integrator_starts_its_device_line_and_exploration() -> None:
    game = _stage_3()
    for _ in range(3):
        strategies_v3.full_integrator(game)
        game.turn()
    assert strategies_v3.rung(game, "devices") == 0
    products = {p.category for p in game.state.company_products(PLAYER)}
    assert "devices" in products
    assert any(s.company_id == PLAYER for s in game.state.desk_studies)


def test_the_scripts_are_deterministic() -> None:
    def notes(seed: int) -> dict[str, int]:
        game = _stage_3(seed)
        for _ in range(4):
            strategies_v3.full_integrator(game)
            game.turn()
        return dict(game.notes)

    assert notes(3) == notes(3)


def test_group_month_eliminates_intercompany_sales() -> None:
    """A subsidiary's sale to the parent counts once in the group's revenue (31.6): its 4xxx
    intercompany sale and the parent's intercompany purchase both drop out."""
    game = _stage_3()
    types = {a.code: a.type for a in game.loaded.game_data.accounts}
    game._group = frozenset({PLAYER, 99})
    t = game.state.turn
    revenue = next(code for code, kind in types.items() if kind == "revenue")
    game.group_lines = [
        (t, 99, INTERCOMPANY_SALES, -5_000),
        (t, 99, CASH, 5_000),
        (t, 99, revenue, -1_000),
        (t, 99, CASH, 1_000),
    ]
    player = [(t, INTERCOMPANY_PURCHASES, 5_000), (t, CASH, -5_000)]
    game.pnl[t] = (0, 0)
    rev, _ = game._group_month(player, types, t)
    assert rev == 1_000
