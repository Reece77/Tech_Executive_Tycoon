"""M8r finding 1 (Codex review 1, P1): the state cache must be published while the save's
write lock is still held, so a later writer never builds on an older state stamped with a
newer file. A controlled two-writer interleaving: writer A commits a rename and pauses before
publishing its state; writer B moves an employee; then C gives that employee a raise. The
move must survive (no stale employment row merged back)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tests.integration.test_api_org import seed_staff
from tst.db import repository
from tst.db.repository import create_save, open_session, run_action
from tst.db.state_io import load_state
from tst.loader import LoadedData
from tst.sim.actions import CreateUnit, GiveRaise, MovePerson, RenameUnit
from tst.sim.errors import SaveBusyError

FOUNDER, EMPLOYEE = 1, 2
WAIT = 10.0


def test_a_paused_publisher_cannot_overwrite_a_later_write(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = create_save(
        "cache", 11, "funded_spinout", company_name="Cache Co", data=loaded,
        save_dir=tmp_path / "saves",
    )  # fmt: skip
    seed_staff(path, loaded, 1)
    run_action(path, loaded, CreateUnit(FOUNDER, "team", "Alpha"))
    run_action(path, loaded, CreateUnit(FOUNDER, "team", "Beta"))
    with open_session(path) as session:
        units = {u.name: u.id for u in load_state(session).units}
    alpha, beta = units["Alpha"], units["Beta"]

    paused, resume = threading.Event(), threading.Event()
    real = repository.remember

    def remember(*args: object, **kwargs: object) -> None:
        if threading.current_thread().name == "writer-a":
            paused.set()  # A has committed; it stops before publishing its state
            assert resume.wait(WAIT)
        real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repository, "remember", remember)
    errors: list[BaseException] = []

    def writer_a() -> None:
        try:
            run_action(path, loaded, RenameUnit(FOUNDER, alpha, "Alpha Two"))
        except BaseException as exc:  # reported by the main thread
            errors.append(exc)

    a = threading.Thread(target=writer_a, name="writer-a")
    a.start()
    assert paused.wait(WAIT)
    try:
        run_action(path, loaded, MovePerson(FOUNDER, EMPLOYEE, beta))  # writer B
    except SaveBusyError:  # A still holds the lock while it publishes: B waits its turn
        resume.set()
        a.join(WAIT)
        run_action(path, loaded, MovePerson(FOUNDER, EMPLOYEE, beta))
    resume.set()
    a.join(WAIT)
    assert not errors and not a.is_alive()

    run_action(path, loaded, GiveRaise(FOUNDER, EMPLOYEE, 9_900_000))  # writer C, from cache
    with open_session(path) as session:
        state = load_state(session)
    employment = state.employment_of(EMPLOYEE)
    assert employment is not None
    assert employment.unit_id == beta  # B's move survived C's write
    assert employment.salary_cents == 9_900_000
    assert next(u.name for u in state.units if u.id == alpha) == "Alpha Two"
