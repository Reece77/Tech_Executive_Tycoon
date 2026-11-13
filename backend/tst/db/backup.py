"""Save backups with SQLite's online backup API (ADR-0004 section 5).

Layout: <save_dir>/backups/<slug>/<slug>.turn-<NNN>.sqlite for periodic backups, and
<slug>.turn-<NNN>.pre-migration-<rev>.sqlite before a migration. Only periodic backups are
pruned; pre-migration backups are kept forever.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

SAVE_SUFFIX = ".tst.sqlite"


def slug_of(save_path: Path) -> str:
    return save_path.name.removesuffix(SAVE_SUFFIX)


def backup_dir(save_path: Path) -> Path:
    return save_path.parent / "backups" / slug_of(save_path)


def _periodic_re(slug: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(slug)}\.turn-(\d{{3,}})\.sqlite$")


def _copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".partial")
    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(tmp)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    tmp.replace(dst)
    return dst


def periodic_backups(save_path: Path) -> list[Path]:
    """Periodic backups for a save, oldest first."""
    folder = backup_dir(save_path)
    if not folder.is_dir():
        return []
    pattern = _periodic_re(slug_of(save_path))
    found = [(int(m.group(1)), p) for p in folder.iterdir() if (m := pattern.match(p.name))]
    return [p for _, p in sorted(found)]


def periodic_backup(save_path: Path, turn: int, keep: int) -> Path:
    """Back up after a committed turn, then prune to the newest `keep` periodic backups."""
    slug = slug_of(save_path)
    dst = _copy(save_path, backup_dir(save_path) / f"{slug}.turn-{turn:03d}.sqlite")
    existing = periodic_backups(save_path)
    for old in existing[: max(len(existing) - keep, 0)]:
        old.unlink()
    return dst


def manual_backup(save_path: Path, turn: int, stamp: str) -> Path:
    """The player's Back up (M29): kept until the player deletes the save; never pruned."""
    slug = slug_of(save_path)
    return _copy(save_path, backup_dir(save_path) / f"{slug}.turn-{turn:03d}.manual-{stamp}.sqlite")


def pre_migration_backup(save_path: Path, turn: int, revision: str | None) -> Path:
    slug = slug_of(save_path)
    rev = revision or "base"
    return _copy(
        save_path, backup_dir(save_path) / f"{slug}.turn-{turn:03d}.pre-migration-{rev}.sqlite"
    )
