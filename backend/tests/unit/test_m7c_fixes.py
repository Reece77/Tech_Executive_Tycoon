"""M7c sub-task 4: regression tests for the bugs the agent playtest found."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.helpers import fresh_game
from tst.db import saves
from tst.loader import LoadedData
from tst.sim.events.render import placeholder_names, render


def test_an_unhappy_company_root_names_the_company(loaded: LoadedData) -> None:
    """unhappy_unit fires at the root with no unit id and no people: {unit} is the company
    (the playtest saw "{unit} asks for fewer meetings")."""
    state = fresh_game(loaded)
    names = placeholder_names(state, loaded.game_data, 1)
    title = loaded.game_data.event_template("unhappy_unit_process").title
    assert render(title, names) == f"{state.player.name} asks for fewer meetings"


def test_save_size_survives_a_vanishing_wal_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLite may delete `-wal` after it was listed and before `stat` (GET /saves gave a 500
    while the playtest's turn closed its connection)."""
    save = tmp_path / "a.tst.sqlite"
    save.write_bytes(b"x" * 10)
    wal = tmp_path / "a.tst.sqlite-wal"
    wal.write_bytes(b"y" * 5)
    real_stat = Path.stat

    def stat(self: Path, **kwargs: bool) -> os.stat_result:
        if self.name.endswith("-wal"):
            raise FileNotFoundError(self)  # exists() said yes; it is gone by now
        return real_stat(self, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    assert saves.file_size(save) == 10
    assert saves.last_played(save).timestamp() == pytest.approx(real_stat(save).st_mtime)
