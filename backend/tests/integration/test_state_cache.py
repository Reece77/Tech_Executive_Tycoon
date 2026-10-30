"""The remembered state (M6 sub-task 0): after each action, turn and event write, the state a
process keeps for a save must equal what `load_state` reads back. TST_STATE_CACHE_CHECK=1 makes
every reuse load the save anyway and compare; the golden script exercises hiring, the org,
products, funding, rivals and events."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden.test_golden import play
from tst.db import repository
from tst.db.repository import load_state, open_session
from tst.loader import LoadedData


def test_the_remembered_state_is_what_the_save_holds(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    hits = 0
    original = repository.load_current

    def counting(session):  # type: ignore[no-untyped-def]
        nonlocal hits
        hits += session.info.get(repository.CACHED_STATE) is not None
        return original(session)

    monkeypatch.setattr(repository, "load_current", counting)
    path, _ = play(tmp_path, "cache", 3, loaded)
    assert hits > 100  # most actions and turns reused the remembered state
    with open_session(path) as session:
        assert repository._recall(path) == load_state(session)
