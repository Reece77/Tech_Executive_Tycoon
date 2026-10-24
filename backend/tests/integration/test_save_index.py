"""The save index upgrades older saves instead of failing on them (ADR-0004)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tst.db import migrate
from tst.db.backup import backup_dir
from tst.db.repository import create_save, list_saves, refresh_index
from tst.loader import LoadedData

M1A_HEAD = "0002_people"


def test_index_upgrades_an_m1a_save(
    tmp_path: Path, loaded: LoadedData, caplog: pytest.LogCaptureFixture
) -> None:
    path = create_save(
        "test", 4, "garage_bootstrap", company_name="Old Co", data=loaded, save_dir=tmp_path
    )
    migrate.downgrade(path, M1A_HEAD)
    assert migrate.current_revision(path) == M1A_HEAD

    with caplog.at_level(logging.WARNING):
        saves = refresh_index(tmp_path)
    assert [(s.slug, s.company_name) for s in saves] == [("test", "Old Co")]
    assert migrate.current_revision(path) == migrate.head_revision()
    backups = [p.name for p in backup_dir(path).iterdir()]
    assert backups == [f"test.turn-000.pre-migration-{M1A_HEAD}.sqlite"]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [s.slug for s in list_saves(tmp_path)] == ["test"]


def test_unreadable_save_is_one_line_not_a_traceback(
    tmp_path: Path, loaded: LoadedData, caplog: pytest.LogCaptureFixture
) -> None:
    create_save("good", 1, "garage_bootstrap", company_name="Good", data=loaded, save_dir=tmp_path)
    (tmp_path / "test.tst.sqlite").write_bytes(b"this is not a database")

    with caplog.at_level(logging.WARNING):
        saves = refresh_index(tmp_path)
    assert [s.slug for s in saves] == ["good"]
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].getMessage().startswith("Skipping save test: needs upgrade")
    assert warnings[0].exc_info is None and "\n" not in warnings[0].getMessage()
