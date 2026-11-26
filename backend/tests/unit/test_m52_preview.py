"""M52 sub-task 3 (formulas.md 66.1): the preview (the start month built in memory, nothing
played or saved) and the difficulty estimate (the sensible script on editor.preview_seeds, in a
background thread, rated with M51's bands)."""

from __future__ import annotations

import time
from dataclasses import replace

from tst import scenario_preview as pv
from tst.balance import m51
from tst.balance.strategies import steady
from tst.loader import LoadedData
from tst.sim.modes import custom


def _spec(loaded: LoadedData, key: str = "platform_war"):  # type: ignore[no-untyped-def]
    return custom.from_historical(loaded.game_data.historical_scenario(key))  # type: ignore[arg-type]


def test_the_preview_shows_the_start(loaded: LoadedData) -> None:
    spec = _spec(loaded)
    p = pv.preview(loaded, spec)
    assert p.start_label == "Jan 2010"
    assert p.cash_cents == spec.cash_dollars * 100
    assert sum(p.staff.values()) == 1 + sum(s.count for s in spec.staff)
    assert [x.name for x in p.products] == [x.name for x in spec.products]
    assert p.rivals and all(r.category in {x.category for x in spec.products} for r in p.rivals)
    assert p.goal == spec.goal.text  # type: ignore[union-attr]


def test_the_script_is_the_scenarios_own_else_steady(loaded: LoadedData) -> None:
    assert pv.script_for(_spec(loaded)) is m51.platform_sensible
    assert pv.script_for(custom.blank(2010, loaded.balance, loaded.game_data)) is steady


def test_the_difficulty_runs_in_the_background(loaded: LoadedData) -> None:
    ed = loaded.balance.editor.model_copy(update={"preview_months": 2, "preview_seeds": (1, 2)})
    quick = replace(loaded, balance=loaded.balance.model_copy(update={"editor": ed}))
    spec = _spec(loaded).model_copy(update={"label": "quick estimate"})
    job = pv.start_job(quick, spec)
    assert pv.start_job(quick, spec) is job  # the same text rejoins its job
    deadline = time.monotonic() + 300
    while job.status == "running" and time.monotonic() < deadline:
        time.sleep(0.5)
    assert job.status == "done", job.error
    assert [r.seed for r in job.results] == [1, 2]
    assert all(r.result is None for r in job.results)  # no verdict within 2 months
    assert job.difficulty(quick) is None
    assert pv.job(job.id) is job and pv.job("nope") is None


def test_difficulty_bands_scale_to_the_seeds(loaded: LoadedData) -> None:
    job = pv.Job("x", "h", (1, 2, 3), status="done")
    job.results = [pv.SeedResult(s, "failure", "Jan 2011", 10) for s in (1, 2, 3)]
    assert job.difficulty(loaded) == "hard"
    job.results = [pv.SeedResult(s, "success", "Jan 2011", 10) for s in (1, 2, 3)]
    assert job.difficulty(loaded) == "easy"
    job.results[0] = pv.SeedResult(1, "failure", "Jan 2011", 10)
    assert job.difficulty(loaded) == "easy"  # 2 of 3 is 6.7 of 10: above medium's 6
    job.results[1] = pv.SeedResult(2, "failure", "Jan 2011", 10)
    assert job.difficulty(loaded) == "medium"  # 1 of 3 is 3.3 of 10: above 3, at most 6
