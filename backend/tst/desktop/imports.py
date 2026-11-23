"""First run: offer to import the saves of the repository version (M58 sub-task 2).

Before the installer, Reece played from a clone of the repository (M29's launcher), with
saves in its `saves` folder. On the first run the window offers to copy them into
Documents/Tech Startup Tycoon/saves. Candidates, in order: `TST_IMPORT_FROM`, then GitHub
Desktop's default clone folder (`Documents/GitHub/<repo>`) and a few usual places. Nothing is
moved or overwritten: the copies are new files, an existing save of the same name is kept,
and save files are copied with SQLite's backup API, so a save's `-wal` journal is included.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

SAVE_SUFFIX = ".tst.sqlite"  # tst.db.backup.SAVE_SUFFIX (not imported: no DB at module load)
IMPORT_ENV = "TST_IMPORT_FROM"
REPO_NAMES = ("Tech_Executive_Tycoon", "Tech-Executive-Tycoon", "tech_executive_tycoon")
SKIP_SUFFIXES = ("-wal", "-shm", "-journal", ".partial", ".log")
SKIP_NAMES = frozenset({"launcher-error.html", ".gitkeep"})
# Periodic and manual backups stay where they are (hundreds of MB each by the 2030s); the
# saves themselves, settings and mods are copied.
SKIP_DIRS = frozenset({"backups"})


@dataclass(frozen=True, slots=True)
class ImportOffer:
    folder: Path
    saves: tuple[str, ...]  # slugs found there and not already in the target


def candidates(documents: Path, home: Path, env: Mapping[str, str] | None = None) -> list[Path]:
    env = os.environ if env is None else env
    out: list[Path] = []
    if chosen := env.get(IMPORT_ENV):
        out.append(Path(chosen))
    for base in (documents / "GitHub", home / "source" / "repos", home / "GitHub", home):
        out.extend(base / name / "saves" for name in REPO_NAMES)
    return out


def save_slugs(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return sorted(p.name.removesuffix(SAVE_SUFFIX) for p in folder.glob(f"*{SAVE_SUFFIX}"))


def find_offer(target: Path, folders: Sequence[Path]) -> ImportOffer | None:
    """The first folder holding saves the target does not have yet."""
    have = set(save_slugs(target))
    for folder in folders:
        try:
            if folder.resolve() == target.resolve():
                continue
        except OSError:
            continue
        new = [s for s in save_slugs(folder) if s not in have]
        if new:
            return ImportOffer(folder=folder, saves=tuple(new))
    return None


def _copy_save(src: Path, dst: Path) -> None:
    tmp = dst.with_name(dst.name + ".partial")
    source = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(tmp)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    tmp.replace(dst)


def _skip(path: Path) -> bool:
    return path.name in SKIP_NAMES or path.name.endswith(SKIP_SUFFIXES)


def import_saves(source: Path, target: Path) -> list[str]:
    """Copy every save, and the folder's other files (settings, mods; not `backups`), that
    the target lacks. Returns the slugs of the saves copied."""
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        dst = target / rel
        if path.is_dir() or rel.parts[0] in SKIP_DIRS or _skip(path) or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if path.name.endswith(SAVE_SUFFIX) or path.suffix == ".sqlite":
            _copy_save(path, dst)
            if len(rel.parts) == 1 and path.name.endswith(SAVE_SUFFIX):
                copied.append(path.name.removesuffix(SAVE_SUFFIX))
        else:
            shutil.copy2(path, dst)
    return copied
