"""M25 sub-task 3: achievements. Each condition kind fires on a scripted state and not
below it; the data file is validated; scenario wins count only in scenario mode."""

from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest

from tst.loader import LoadedData
from tst.profile.data import (
    FLAG_KINDS,
    NUMBER_KINDS,
    SET_KINDS,
    AchievementDef,
    AchievementsFile,
    earned,
)
from tst.profile.kinds import Facts
from tst.sim.modes.models import GameMode


def _def(kind: str, threshold: float | None = None, param: str | None = None) -> AchievementDef:
    return AchievementDef(
        key="x", title="X", description="X", kind=kind, threshold=threshold, param=param
    )


@pytest.mark.parametrize("kind", sorted(NUMBER_KINDS))
def test_each_number_kind_fires_at_its_threshold(kind: str) -> None:
    a = _def(kind, threshold=5)
    assert not earned(a, Facts())
    assert not earned(a, replace(Facts(), **{kind: 4}))
    assert earned(a, replace(Facts(), **{kind: 5}))


@pytest.mark.parametrize("kind", sorted(FLAG_KINDS))
def test_each_flag_kind_fires_when_true(kind: str) -> None:
    a = _def(kind)
    assert not earned(a, Facts())
    assert earned(a, replace(Facts(), **{kind: True}))


@pytest.mark.parametrize("kind", sorted(SET_KINDS))
def test_each_set_kind_fires_on_its_param(kind: str) -> None:
    a = _def(kind, param="a")
    assert not earned(a, Facts())
    assert not earned(a, replace(Facts(), **{kind: frozenset({"b"})}))
    assert earned(a, replace(Facts(), **{kind: frozenset({"a", "b"})}))


def test_the_kinds_are_every_fact() -> None:
    names = {f.name for f in dataclasses.fields(Facts)}
    assert names == NUMBER_KINDS | FLAG_KINDS | SET_KINDS
    assert not (NUMBER_KINDS & FLAG_KINDS) and not (FLAG_KINDS & SET_KINDS)


def test_the_file_is_validated() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        _def("being_nice")
    with pytest.raises(ValueError, match="takes a threshold"):
        _def("arr_cents")
    with pytest.raises(ValueError, match="takes a param"):
        _def("rounds_closed", threshold=1)
    with pytest.raises(ValueError, match="duplicate"):
        AchievementsFile(achievements=(_def("listed"), _def("listed")))


def test_about_forty_achievements_and_every_kind_used(loaded: LoadedData) -> None:
    assert 35 <= len(loaded.achievements) <= 50
    used = {a.kind for a in loaded.achievements}
    assert used == NUMBER_KINDS | FLAG_KINDS | SET_KINDS
    scenarios = {a.param for a in loaded.achievements if a.kind == "scenario_won"}
    assert scenarios == {s.key for s in loaded.game_data.historical}


def test_sandbox_and_modded_games_earn_none(loaded: LoadedData) -> None:
    from tests.helpers import fresh_game
    from tst.profile.check import why_none

    state = fresh_game(loaded)
    assert why_none(state, None) is None
    assert why_none(state, "big-ai") is not None and "Modded" in str(why_none(state, "big-ai"))
    sandbox = replace(state, mode=GameMode(kind="sandbox"))
    assert "Sandbox" in str(why_none(sandbox, None))
    scenario = replace(state, mode=GameMode(kind="scenario", scenario="ai_lab"))
    assert why_none(scenario, None) is None
