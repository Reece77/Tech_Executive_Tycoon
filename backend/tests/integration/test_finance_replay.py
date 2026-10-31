"""Replay reproduces a save with a SAFE, two rounds and a bridge (ADR-0014, M4a brief).

Everything goes through logged actions: a SAFE, a seed round left to lapse, a second seed
round accepted, then a marketing budget the company cannot pay, which makes it insolvent;
the seed lead's director offers a bridge, which is accepted.
"""

from __future__ import annotations

from pathlib import Path

from tests.golden.test_golden import ledger_rows, snapshots
from tests.helpers import play_turn
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    replay_save,
    run_action,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AcceptBridge,
    AcceptTermSheet,
    CreateProduct,
    RaiseSafe,
    SetMarketing,
    StartRound,
)
from tst.sim.state import GameState

SEED = 16  # investors answer this garage's seed rounds (see test_fundraising)
BURN_MARKETING = 200_000_000  # $2M a month: more than the company has


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def build(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "finrep", SEED, "garage_bootstrap", company_name="Rep Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, RaiseSafe(1, 30_000_000, 100_000_000))
    run_action(path, loaded, StartRound(1, "seed", 150_000_000))
    for _ in range(3):  # the first round's term sheets arrive and lapse unaccepted
        play_turn(path, loaded)
    for _ in range(4):  # start again until a round brings term sheets
        run_action(path, loaded, StartRound(1, "seed", 150_000_000))
        play_turn(path, loaded)
        state = _state(path)
        sheets = [t for t in state.term_sheets if t.status == "offered"]
        if sheets:
            break
    best = max(sheets, key=lambda t: t.pre_money_cents)
    run_action(path, loaded, AcceptTermSheet(1, best.id))
    play_turn(path, loaded)  # the seed closes; the board forms
    run_action(path, loaded, CreateProduct(1, "Pipeline", "b2b_saas", ("smb",)))
    # M8: Square (March 2010) may take an id first, so the product's id is read back.
    product = max(p.id for p in _state(path).company_products(1))
    run_action(path, loaded, SetMarketing(1, product, BURN_MARKETING))
    for _ in range(3):
        play_turn(path, loaded)
        state = _state(path)
        offers = [s for s in state.safes if s.kind == "bridge" and s.status == "offered"]
        if offers:
            break
    run_action(path, loaded, AcceptBridge(1, offers[0].id))
    run_action(path, loaded, SetMarketing(1, product, 0))
    play_turn(path, loaded)
    play_turn(path, loaded)
    return path


def test_replay_reproduces_safes_rounds_and_a_bridge(tmp_path: Path, loaded: LoadedData) -> None:
    original = build(tmp_path / "a", loaded)
    state = _state(original)
    assert [s.kind for s in state.safes if s.status in ("converted", "outstanding")] == [
        "safe",
        "bridge",
    ]
    assert [r.status for r in state.rounds][:1] == ["lapsed"]
    assert any(r.status == "closed" for r in state.rounds)
    assert not state.ended
    copy = replay_save(original, tmp_path / "b", "finrep-copy", loaded)
    replayed = _state(copy)
    assert snapshots(copy) == snapshots(original)
    assert [r[1:] for r in ledger_rows(copy)] == [r[1:] for r in ledger_rows(original)]
    for name in ("cap_entries", "grants", "safes", "rounds", "term_sheets", "seats"):
        assert getattr(replayed, name) == getattr(state, name), name
    assert replayed.people == state.people
