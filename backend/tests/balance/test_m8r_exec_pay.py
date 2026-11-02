"""M8r (product manager, 2026-10-31): an executive appointed at the default salary (the exec
market rate) stays. In real stage-3 companies (the 18.9 harness's steady games, 10 seeds), a
score-14 CTO appointed at the default salary is either not approached in the next six months
or every approach reads "likely to stay", and they still hold the seat: on at least 8 of 10
seeds (the M10d brief's target)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.api.rival_views import band
from tst.balance import m8
from tst.balance.game import PLAYER
from tst.sim.actions import AppointExecutive
from tst.sim.state import with_person_state

MONTHS = 6


def _check(seed: int) -> str | None:
    game = m8.steady_at_stage_3(seed)
    if game is None:
        return None
    (cto,) = m8.add_staff(game, "software_engineer", "senior", 1, skill=14.0)
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    assert game.act(AppointExecutive(game.founder_id, "cto", cto))
    for _ in range(MONTHS):
        for a in game.state.approaches:
            if a.person_id == cto and a.status == "pending":
                shown = band(game.state, a, game.loaded)
                if shown != "likely to stay":
                    return f"seed {seed}: an approach read {shown!r}"
        m8.steady(game, appoint=False)
        game.turn()
    if game.state.seat_holder(PLAYER, "cto") != cto:
        return f"seed {seed}: the CTO left"
    return None


STAY_NEEDED = 8  # M10d brief: stays 6 months on at least 8 of 10 seeds


@pytest.mark.nightly
def test_an_executive_at_the_default_salary_stays() -> None:
    """M10d (morale.target_base 56): 9 of 10 seeds keep their CTO (7 of 10 before)."""
    problems = [p for p in (_check(s) for s in m8.SEEDS) if p]
    print(
        f"executive retention: {len(m8.SEEDS) - len(problems)} of {len(m8.SEEDS)} stay; {problems}"
    )
    assert len(m8.SEEDS) - len(problems) >= STAY_NEEDED, problems
