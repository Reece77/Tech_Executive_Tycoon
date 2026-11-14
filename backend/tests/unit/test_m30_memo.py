"""M30: values derived once per state (`tst.sim.state.derived`) and reads kept until the next
commit (`repository.read_memo`) equal a recompute. With MEMO_CHECK on, every remembered value
is recomputed where it is used and must be equal; a broken memo fails here."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tst.balance import m30
from tst.balance.game import start_game
from tst.balance.report import SCENARIO
from tst.db import repository
from tst.db.repository import create_save, read_session, read_state
from tst.loader import LoadedData
from tst.sim import state as st


def test_derived_values_match_a_recompute_while_a_group_plays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(st, "MEMO_CHECK", True)
    game = start_game(m30.loaded(), 2, SCENARIO)
    script = m30.strategy("full_integrator")
    for _ in range(30):
        script(game)
        game.turn()
    assert game.state.turn == 30


def test_a_new_state_starts_with_an_empty_memo() -> None:
    game = start_game(m30.loaded(), 1, SCENARIO)
    state = game.state
    first = state.company(1)
    assert state._memo  # the lookup built its index
    moved = replace(state, turn=state.turn + 1)
    assert not moved._memo and moved == replace(state, turn=state.turn + 1)
    assert moved.company(1) is first
    with pytest.raises(KeyError):
        state.company(999_999)


def test_a_broken_memo_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "MEMO_CHECK", True)
    state = start_game(m30.loaded(), 1, SCENARIO).state
    state.company(1)
    state._memo["companies_by_id"] = {}  # a stale index
    with pytest.raises(AssertionError, match="differs from a recompute"):
        state.company(1)


def test_reads_are_kept_until_the_next_commit(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TST_STATE_CACHE_CHECK", raising=False)
    path = create_save(
        "memo", 3, "funded_spinout", company_name="Memo Co", data=loaded, save_dir=tmp_path
    )
    with read_session(path) as session:
        first = repository.ledger_balances(session)
        state = read_state(session)
    calls: list[int] = []

    def counted() -> int:
        calls.append(1)
        return len(calls)

    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    with read_session(path) as session:
        assert repository.ledger_balances(session) == first  # kept, and equal to a recompute
    monkeypatch.delenv("TST_STATE_CACHE_CHECK")
    with read_session(path) as session:
        assert repository.read_memo(session, "n", counted) == 1
    with read_session(path) as session:
        assert repository.read_memo(session, "n", counted) == 1  # not recomputed
    repository.run_turn(path, loaded)  # a commit: what reads kept is gone
    with read_session(path) as session:
        assert repository.read_memo(session, "n", counted) == 2
        after = repository.ledger_balances(session)
        assert read_state(session).turn == state.turn + 1
    assert after != first
