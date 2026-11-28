"""The custom scenario a save was started from (M52, ADR-0026 point 4; migration 0068): its
canonical YAML and hash in table `custom_scenario`, and the data such a save plays with (the
base data with the save's own copy of the entry, so editing or deleting the file later never
changes the game)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from tst.db.models import CustomScenarioRow
from tst.loader import LoadedData
from tst.sim.errors import SimError
from tst.sim.modes.custom import with_custom
from tst.sim.modes.custom_config import CustomScenario

ROW_ID = 1


class CustomScenarioMismatchError(SimError):
    """M57r-B (review 10 item 33): a custom scenario's game whose stored copy is missing or
    no longer matches the hash its mode record names: it would otherwise play the base world
    without a word. The save is not opened; restore it from a backup."""

    code = "custom_scenario_mismatch"


@dataclass(frozen=True, slots=True)
class StoredCustom:
    slug: str
    sha256: str
    yaml: str


def write_custom(session: Session, spec: CustomScenario, text: str, sha256: str) -> None:
    session.merge(CustomScenarioRow(id=ROW_ID, slug=spec.key, sha256=sha256, yaml=text))


def stored_custom(path: Path) -> StoredCustom | None:
    """The save's custom scenario copy, or None for a save not started from one (read
    directly: works before the save is opened and on saves from before M52, which have no
    table).

    M57r-B (review 10 item 33): only "no table" or "no custom mode" means not custom. When the
    mode record names a scenario hash, the copy must be there and hash to it (its own
    recorded hash too), else CustomScenarioMismatchError; a read error is raised, not taken
    for "not custom"."""
    if not path.is_file():
        return None
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('custom_scenario', 'game_mode')"
            )
        }
        expected = _mode_hash(conn) if "game_mode" in tables else None
        if "custom_scenario" not in tables:
            if expected is not None:
                raise CustomScenarioMismatchError(
                    "this game was started from a custom scenario whose copy is missing"
                )
            return None
        row = conn.execute(
            "SELECT slug, sha256, yaml FROM custom_scenario WHERE id = ?", (ROW_ID,)
        ).fetchone()
    if row is None:
        if expected is not None:
            raise CustomScenarioMismatchError(
                "this game was started from a custom scenario whose copy is missing"
            )
        return None
    stored = StoredCustom(str(row[0]), str(row[1]), str(row[2]))
    actual = hashlib.sha256(stored.yaml.encode("utf-8")).hexdigest()
    if actual != stored.sha256 or (expected is not None and actual != expected):
        raise CustomScenarioMismatchError(
            "this game's custom scenario copy does not match the one it was started from"
        )
    return stored


def _mode_hash(conn: sqlite3.Connection) -> str | None:
    found = conn.execute("SELECT data FROM game_mode WHERE id = 1").fetchone()
    if found is None:
        return None
    data = json.loads(found[0]) if isinstance(found[0], str) else found[0]
    value = data.get("scenario_sha256") if isinstance(data, dict) else None
    return str(value) if value else None


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
