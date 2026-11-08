"""Named mods in `<saves>/mods/<name>.yaml` (M25 section 3), and the data a save plays with.

A mod file is YAML: `mod_format: 1`, a `description` and `files`, the overlay of changed
values (tst.mods.overlay). A save started with a mod keeps a copy of the overlay in
`save_meta.mod_overlay` and the merged data's hash in `save_meta.mod_hash`; it always loads
with that copy, so editing or deleting the mod file later never changes the save."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import yaml

from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.errors import NotFoundError, SimError

log = logging.getLogger(__name__)

MODS_DIR: Final = "mods"
MOD_FORMAT: Final = 1
NAME_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
DESCRIPTION_MAX: Final = 300  # characters in a mod's description


class InvalidModError(SimError):
    code = "invalid_mod"


class UnknownModError(NotFoundError):
    code = "unknown_mod"


@dataclass(frozen=True)
class Mod:
    name: str
    description: str = ""
    files: dict[str, Any] = field(default_factory=dict)

    def as_yaml(self) -> str:
        body = {"mod_format": MOD_FORMAT, "description": self.description, "files": self.files}
        return yaml.safe_dump(body, sort_keys=False, allow_unicode=True)


def mods_dir(save_dir: Path) -> Path:
    return save_dir / MODS_DIR


def check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise InvalidModError(
            "a mod name is 1 to 48 lower-case letters, digits, - or _, starting with a letter "
            "or digit"
        )
    return name


def mod_path(save_dir: Path, name: str) -> Path:
    return mods_dir(save_dir) / f"{check_name(name)}.yaml"


def parse(name: str, text: str) -> Mod:
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise InvalidModError(f"mod {name!r}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("files", {}), dict):
        raise InvalidModError(f"mod {name!r}: expected mod_format, description and files")
    if raw.get("mod_format", MOD_FORMAT) != MOD_FORMAT:
        raise InvalidModError(f"mod {name!r}: mod_format must be {MOD_FORMAT}")
    if extra := sorted(set(raw) - {"mod_format", "description", "files"}):
        raise InvalidModError(f"mod {name!r}: unknown keys {extra}")
    description = str(raw.get("description") or "")
    if len(description) > DESCRIPTION_MAX:
        raise InvalidModError(f"a mod description has at most {DESCRIPTION_MAX} characters")
    return Mod(name, description, dict(raw.get("files") or {}))


def read_mod(save_dir: Path, name: str) -> Mod:
    path = mod_path(save_dir, name)
    if not path.is_file():
        raise UnknownModError(f"no mod named {name!r}")
    return parse(name, path.read_text(encoding="utf-8"))


def list_mods(save_dir: Path) -> list[Mod]:
    found = []
    for path in sorted(mods_dir(save_dir).glob("*.yaml")):
        if NAME_RE.match(path.stem):
            try:
                found.append(parse(path.stem, path.read_text(encoding="utf-8")))
            except InvalidModError:
                log.warning("Skipping unreadable mod %s", path.name)
    return found


def validate(data_dir: Path, mod: Mod) -> LoadedData:
    """The merged data, validated exactly as the base files are; InvalidModError carries the
    loader's own message."""
    try:
        return with_overlay(data_dir, mod.name, mod.files)
    except DataLoadError as exc:
        raise InvalidModError(str(exc)) from exc


def write_mod(save_dir: Path, data_dir: Path, mod: Mod) -> LoadedData:
    """Validate, then save atomically. An invalid mod is refused and nothing is written."""
    check_name(mod.name)
    loaded = validate(data_dir, mod)
    path = mod_path(save_dir, mod.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{mod.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(mod.as_yaml())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return loaded


def delete_mod(save_dir: Path, name: str) -> None:
    path = mod_path(save_dir, name)
    if not path.is_file():
        raise UnknownModError(f"no mod named {name!r}")
    path.unlink()


@lru_cache(maxsize=8)
def _cached(data_dir: str, name: str, overlay_json: str) -> LoadedData:
    return load_all(Path(data_dir), json.loads(overlay_json), name)


def with_overlay(data_dir: Path, name: str, overlay: dict[str, Any]) -> LoadedData:
    """The base data with `overlay` merged in (cached by its content)."""
    return _cached(str(data_dir), name, json.dumps(overlay, sort_keys=True))


@dataclass(frozen=True, slots=True)
class SaveMod:
    name: str
    hash: str | None
    overlay: dict[str, Any]


def save_mod(path: Path) -> SaveMod | None:
    """The mod a save was started with (its stored copy), or None. Reads save_meta directly,
    so it works before the save is opened and on saves from before M25."""
    if not path.is_file():
        return None
    uri = f"file:{path}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(save_meta)")}
            if "mod_name" not in cols:
                return None
            row = conn.execute(
                "SELECT mod_name, mod_hash, mod_overlay FROM save_meta WHERE id = 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None or row[0] is None:
        return None
    overlay = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or {})
    return SaveMod(str(row[0]), row[1], dict(overlay))


def data_for_save(path: Path, data_dir: Path, base: LoadedData) -> LoadedData:
    """The data a save plays with: `base` for a game without a mod (unchanged, so it is
    byte-identical to before), else the base files with the save's own overlay copy."""
    mod = save_mod(path)
    if mod is None:
        return base
    loaded = with_overlay(data_dir, mod.name, mod.overlay)
    if mod.hash is not None and loaded.mod_hash != mod.hash:
        log.warning(
            "Data files changed since %s was created with mod %r: %s", path.name, mod.name, mod.hash
        )
    return loaded
