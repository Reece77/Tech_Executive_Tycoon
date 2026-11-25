"""Save backups with SQLite's online backup API (ADR-0004 section 5).

Layout: <save_dir>/backups/<slug>/<slug>.turn-<NNN>.sqlite for periodic backups, and
<slug>.turn-<NNN>.pre-migration-<rev>.sqlite before a migration. Only periodic backups are
pruned; pre-migration backups are kept forever.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from pathlib import Path

log = logging.getLogger(__name__)

SAVE_SUFFIX = ".tst.sqlite"


def slug_of(save_path: Path) -> str:
    return save_path.name.removesuffix(SAVE_SUFFIX)


def backup_dir(save_path: Path) -> Path:
    return save_path.parent / "backups" / slug_of(save_path)


def _periodic_re(slug: str) -> re.Pattern[str]:
    # M50: a 2008-2009 turn is negative ("turn--12")
    return re.compile(rf"^{re.escape(slug)}\.turn-(-\d{{2,}}|\d{{3,}})\.sqlite$")


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


# M30: a periodic backup copies the whole save (160-350 MB by 2039: 0.4 s here, 1.0 s on CI's
# runner), so it runs on its own thread after the month's commit, reading the committed month
# through its own connection (WAL: a consistent snapshot while the next month writes). Every
# reader of the backups folder, and every file operation on the save, waits for it first; the
# thread is not a daemon, so the interpreter finishes it before it exits.
_RUNNING: dict[Path, threading.Thread] = {}
_RUNNING_LOCK = threading.Lock()


def wait(save_path: Path) -> None:
    """Return once the save's periodic backup in progress, if any, is written."""
    with _RUNNING_LOCK:
        running = _RUNNING.get(save_path.resolve())
    if running is not None and running is not threading.current_thread():
        running.join()


def periodic_backup_in_background(save_path: Path, turn: int, keep: int) -> threading.Thread:
    """`periodic_backup` on its own thread (after the previous one ends); a failure is logged,
    as one after a commit always was (the month is played either way)."""
    wait(save_path)

    def run() -> None:
        try:
            periodic_backup(save_path, turn, keep)
        except Exception:
            log.exception("Turn %d committed; its backup failed", turn)
        finally:
            with _RUNNING_LOCK:
                if _RUNNING.get(key) is thread:
                    del _RUNNING[key]

    key = save_path.resolve()
    thread = threading.Thread(target=run, name=f"backup-{slug_of(save_path)}-{turn}")
    with _RUNNING_LOCK:
        _RUNNING[key] = thread
    thread.start()
    return thread


def periodic_backups(save_path: Path) -> list[Path]:
    """Periodic backups for a save, oldest first."""
    wait(save_path)
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
    wait(save_path)
    slug = slug_of(save_path)
    return _copy(save_path, backup_dir(save_path) / f"{slug}.turn-{turn:03d}.manual-{stamp}.sqlite")


def pre_migration_backup(save_path: Path, turn: int, revision: str | None) -> Path:
    wait(save_path)
    slug = slug_of(save_path)
    rev = revision or "base"
    return _copy(
        save_path, backup_dir(save_path) / f"{slug}.turn-{turn:03d}.pre-migration-{rev}.sqlite"
    )
