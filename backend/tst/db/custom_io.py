"""The custom scenario a save was started from (M52, ADR-0026 point 4; migration 0068): its
canonical YAML and hash in table `custom_scenario`, and the data such a save plays with (the
base data with the save's own copy of the entry, so editing or deleting the file later never
changes the game)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from tst.db.models import CustomScenarioRow
from tst.loader import LoadedData
from tst.sim.modes.custom import with_custom
from tst.sim.modes.custom_config import CustomScenario

ROW_ID = 1


@dataclass(frozen=True, slots=True)
class StoredCustom:
    slug: str
    sha256: str
    yaml: str


def write_custom(session: Session, spec: CustomScenario, text: str, sha256: str) -> None:
    session.merge(CustomScenarioRow(id=ROW_ID, slug=spec.key, sha256=sha256, yaml=text))


def stored_custom(path: Path) -> StoredCustom | None:
    """The save's custom scenario copy, or None (read directly: works before the save is
    opened and on saves from before M52, which have no table)."""
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
            found = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'custom_scenario'"
            ).fetchone()
            if found is None:
                return None
            row = conn.execute(
                "SELECT slug, sha256, yaml FROM custom_scenario WHERE id = ?", (ROW_ID,)
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return StoredCustom(str(row[0]), str(row[1]), str(row[2]))


@lru_cache(maxsize=16)
def _spec(text: str) -> CustomScenario:
    from tst.scenario_files import parse

    return parse(text)


def spec_of(stored: StoredCustom) -> CustomScenario:
    """The stored spec (structure checked; the editor's ranges were checked when it began, and
    a later change to them never stops an existing game)."""
    return _spec(stored.yaml)


def data_with(base: LoadedData, spec: CustomScenario) -> LoadedData:
    return replace(base, game_data=with_custom(base.game_data, spec))


_DATA: dict[tuple[int, str], tuple[LoadedData, LoadedData]] = {}
_DATA_MAX = 8


def _cached(base: LoadedData, text: str) -> LoadedData:
    """`base` with the entry, kept for the base object it was made from (by identity)."""
    hit = _DATA.get((id(base), text))
    if hit is not None and hit[0] is base:
        return hit[1]
    if len(_DATA) >= _DATA_MAX:
        _DATA.clear()
    made = data_with(base, _spec(text))
    _DATA[(id(base), text)] = (base, made)
    return made


def data_for_custom(path: Path, base: LoadedData) -> LoadedData:
    """`base` for a save not started from a custom scenario (unchanged), else `base` with the
    save's own entry."""
    stored = stored_custom(path)
    if stored is None:
        return base
    return _cached(base, stored.yaml)
