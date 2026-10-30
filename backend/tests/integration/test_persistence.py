from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text

from tests.helpers import event_cash_cents
from tst.db import migrate, repository
from tst.db.backup import periodic_backups
from tst.db.models import (
    SCHEMA_VERSION,
    Base,
    DecisionLogRow,
    LedgerEntryRow,
    TurnLogRow,
    TurnSnapshotRow,
)
from tst.db.repository import (
    create_save,
    latest_snapshot,
    ledger_balances,
    list_saves,
    load_state,
    open_session,
    run_turn,
)
from tst.db.session import make_engine
from tst.loader import LoadedData
from tst.sim import turn as turn_module
from tst.sim.errors import (
    InvalidSaveNameError,
    InvalidSeedError,
    SaveExistsError,
    ScenarioUnavailableError,
    UnknownScenarioError,
)
from tst.sim.state import company_cash
from tst.sim.turn import TurnContext

GARAGE_CASH = 5_000_000
OVERHEAD = 110_000  # M1b solo founder: $500 base overhead + $600 office


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def save(save_dir: Path, loaded: LoadedData) -> Path:
    return create_save(
        "dev",
        42,
        "garage_bootstrap",
        company_name="Test Co",
        data=loaded,
        save_dir=save_dir,
    )


def dump(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def test_create_save(save: Path, loaded: LoadedData) -> None:
    assert save.name == "dev.tst.sqlite"
    with open_session(save) as session:
        state = load_state(session)
        meta = repository.read_meta(session)
        assert state.turn == 0
        assert state.player.name == "Test Co"
        assert meta.master_seed == 42
        assert meta.data_hashes == loaded.hashes
        assert meta.schema_version == SCHEMA_VERSION == 18
        assert company_cash(ledger_balances(session), state.player.id) == GARAGE_CASH


@pytest.mark.parametrize(("sync", "expected"), [(None, 1), ("OFF", 0)])
def test_pragmas(
    save: Path, monkeypatch: pytest.MonkeyPatch, sync: str | None, expected: int
) -> None:
    """The game syncs NORMAL; the test suite sets TST_SQLITE_SYNC=OFF (M6 sub-task 0)."""
    if sync is None:
        monkeypatch.delenv("TST_SQLITE_SYNC", raising=False)
    else:
        monkeypatch.setenv("TST_SQLITE_SYNC", sync)
    engine = make_engine(save)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert conn.execute(text("PRAGMA synchronous")).scalar() == expected
    finally:
        engine.dispose()


def test_run_turn_writes_everything(save: Path, loaded: LoadedData) -> None:
    result = run_turn(save, loaded)
    assert result.new_state.turn == 1
    with open_session(save) as session:
        assert repository.read_meta(session).current_turn == 1
        assert company_cash(ledger_balances(session), 1) == GARAGE_CASH - OVERHEAD
        snap = latest_snapshot(session, 1)
        assert snap is not None
        assert snap.cash_cents == GARAGE_CASH - OVERHEAD
        assert snap.monthly_burn_cents == OVERHEAD
        for row_type in (TurnLogRow, TurnSnapshotRow):  # the player's (rivals log too, M5)
            count = select(func.count()).select_from(row_type).where(row_type.company_id == 1)
            if row_type is TurnLogRow:  # the month's Market news is logged too (M5)
                count = count.where(TurnLogRow.kind != "market_news")
            assert session.scalar(count) == 1
        # the new-game choices (for replay) plus this turn's decisions
        player_log = select(func.count()).select_from(DecisionLogRow)
        assert session.scalar(player_log.where(DecisionLogRow.source != "rival")) == 2
        # starting cash + one overhead entry
        entries = select(func.count()).select_from(LedgerEntryRow)
        assert session.scalar(entries.where(LedgerEntryRow.company_id == 1)) == 2


def test_cash_equals_ledger_every_turn(save: Path, loaded: LoadedData) -> None:
    for expected_turn in range(1, 25):
        result = run_turn(save, loaded)
        played = result.snapshot.turn
        with open_session(save) as session:
            balances = ledger_balances(session, played)
            snap = result.snapshot.for_company(1)
            assert snap.cash_cents == company_cash(balances, 1)
            # Overheads, plus any event the month brought (M6: answered at Continue).
            events = event_cash_cents(save, 1, played)
            assert snap.cash_cents == GARAGE_CASH - OVERHEAD * expected_turn + events
            # Double entry: every company's balances sum to zero at every turn.
            assert sum(v for (cid, _), v in balances.items() if cid == 1) == 0
    with open_session(save) as session:
        assert load_state(session).turn == 24


def _boom(_ctx: TurnContext) -> TurnContext:
    raise RuntimeError("injected failure in phase 9")


def test_exception_in_phase_9_leaves_save_unchanged(
    save: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_turn(save, loaded)
    before = dump(save)
    phases = list(turn_module.PHASES)
    assert phases[8][0] == "market_and_macro_update"
    phases[8] = (phases[8][0], _boom)
    monkeypatch.setattr(turn_module, "PHASES", tuple(phases))
    with pytest.raises(RuntimeError, match="phase 9"):
        run_turn(save, loaded)
    assert dump(save) == before


def test_exception_during_write_rolls_back(
    save: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail after ledger rows are added but before the turn commits."""
    before = dump(save)

    def broken_snapshot_rows(_snapshot: object) -> list[object]:
        raise RuntimeError("injected failure while writing")

    monkeypatch.setattr(repository, "snapshot_to_rows", broken_snapshot_rows)
    with pytest.raises(RuntimeError, match="while writing"):
        run_turn(save, loaded)
    assert dump(save) == before


def test_25_turns_leave_two_periodic_backups(save: Path, loaded: LoadedData) -> None:
    for _ in range(25):
        run_turn(save, loaded)
    backups = periodic_backups(save)
    assert [b.name for b in backups] == ["dev.turn-012.sqlite", "dev.turn-024.sqlite"]
    with open_session(backups[0]) as session:
        assert load_state(session).turn == 12


def test_periodic_backups_are_pruned(save: Path, loaded: LoadedData) -> None:
    small = loaded.balance.model_copy(
        update={
            "backup": loaded.balance.backup.model_copy(
                update={"every_n_turns": 2, "keep_periodic": 3}
            )
        }
    )
    data = LoadedData(balance=small, game_data=loaded.game_data, hashes=loaded.hashes)
    for _ in range(10):
        run_turn(save, data)
    assert [b.name for b in periodic_backups(save)] == [
        "dev.turn-006.sqlite",
        "dev.turn-008.sqlite",
        "dev.turn-010.sqlite",
    ]


def test_older_save_is_backed_up_then_upgraded(save: Path) -> None:
    assert migrate.ensure_current(save) is None  # already at head: no backup
    migrate.downgrade(save, "base")
    assert migrate.current_revision(save) is None
    backup = migrate.ensure_current(save)
    assert backup is not None
    assert backup.name == "dev.turn-000.pre-migration-base.sqlite"
    assert migrate.current_revision(save) == migrate.head_revision()


def test_migration_matches_models(tmp_path: Path) -> None:
    path = tmp_path / "empty.tst.sqlite"
    migrate.upgrade_new(path)
    engine = make_engine(path)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_create_save_errors(save: Path, save_dir: Path, loaded: LoadedData) -> None:
    kwargs = {"company_name": "X", "data": loaded, "save_dir": save_dir}
    with pytest.raises(SaveExistsError):
        create_save("dev", 1, "garage_bootstrap", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(InvalidSaveNameError):
        create_save("Bad Name", 1, "garage_bootstrap", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(InvalidSeedError):
        create_save("big", 2**63, "garage_bootstrap", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(UnknownScenarioError):
        create_save("nope", 1, "nope", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ScenarioUnavailableError):
        create_save("v3", 1, "mineral_first_prospector", **kwargs)  # type: ignore[arg-type]
    assert sorted(p.name for p in save_dir.glob("*.tst.sqlite")) == ["dev.tst.sqlite"]


def test_list_saves_uses_index(save: Path, save_dir: Path, loaded: LoadedData) -> None:
    run_turn(save, loaded)
    saves = list_saves(save_dir)
    assert [(s.slug, s.company_name, s.current_turn) for s in saves] == [("dev", "Test Co", 1)]
    (save_dir / "index.json").write_text("not json")
    assert [s.slug for s in list_saves(save_dir)] == ["dev"]  # rebuilt from files
