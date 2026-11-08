"""The saves manager (M7b): rename, duplicate, delete, list backups and restore one as a new
save. Every action takes the save's write lock, so a busy save (a turn, an action or a
holiday in progress) refuses with SaveBusyError. Ironman saves cannot be duplicated or
restored (ADR-0004: Ironman has no reloads); they can be deleted.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select

from tst.db import migrate, repository
from tst.db.backup import SAVE_SUFFIX, backup_dir, slug_of
from tst.db.models import CompanyRow, SaveMetaRow
from tst.db.session import forget_engine
from tst.db.state_io import META_ID
from tst.sim.calendar import format_turn
from tst.sim.errors import NotFoundError, SaveBusyError, SimError

IRONMAN = "ironman"
NAME_MAX = 80  # characters in a display name (save_meta.display_name)
SLUG_MAX = 48  # characters taken from a display name for a new save's slug
_BACKUP_RE = re.compile(
    r"^(?P<slug>.+)\.turn-(?P<turn>\d{3,})(?:\.pre-migration-(?P<rev>.+))?\.sqlite$"
)


class IronmanSaveError(SimError):
    code = "ironman_save"


class InvalidDisplayNameError(SimError):
    code = "invalid_display_name"


class UnknownBackupError(NotFoundError):
    code = "unknown_backup"


@dataclass(frozen=True, slots=True)
class SaveFile:
    """A save as the Saves screen lists it: the index summary plus what the files say."""

    slug: str
    display_name: str
    company_name: str
    scenario_id: str
    difficulty: str
    current_turn: int
    game_state: str
    last_played: datetime
    size_bytes: int
    busy: bool
    mode: str = "campaign"  # M15b: campaign, sandbox or scenario
    score: int | None = None  # the player's latest company score; never a Sandbox's (30.2)


@dataclass(frozen=True, slots=True)
class BackupFile:
    backup_id: str  # the file name
    kind: Literal["periodic", "pre_upgrade"]
    turn: int
    created: datetime
    size_bytes: int


def _files(path: Path) -> list[Path]:
    return [path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")]


def _stats(path: Path) -> list[os.stat_result]:
    """The save's files that exist now. SQLite removes `-wal` and `-shm` when another
    process's turn closes its connection, so a file can vanish between listing and `stat`
    (a 500 on GET /saves during the M7c playtest)."""
    out = []
    for p in _files(path):
        try:
            out.append(p.stat())
        except FileNotFoundError:
            continue
    return out


def file_size(path: Path) -> int:
    return sum(s.st_size for s in _stats(path))


def last_played(path: Path) -> datetime:
    return datetime.fromtimestamp(max(s.st_mtime for s in _stats(path)), tz=UTC)


def is_busy(path: Path) -> bool:
    return repository.is_reserved(path) or repository._lock(path).locked()


@contextmanager
def exclusive(path: Path) -> Iterator[None]:
    """Hold the save's write lock for a file operation; SaveBusyError if anything else has
    it (a turn, an action, a holiday)."""
    if repository.is_reserved(path):
        raise SaveBusyError(repository.BUSY_MESSAGE)
    lock = repository._lock(path)
    if not lock.acquire(blocking=False):
        raise SaveBusyError(repository.BUSY_MESSAGE)
    try:
        yield
    finally:
        lock.release()


def _clean_name(name: str) -> str:
    text = " ".join(name.split())
    if not text or len(text) > NAME_MAX:
        raise InvalidDisplayNameError(f"a save name has 1 to {NAME_MAX} characters")
    return text


def slug_for(save_dir: Path, name: str) -> str:
    """A free slug from a display name: "Kestrel (restored, Mar 2013)" -> kestrel-restored-
    mar-2013, then -2, -3 if taken."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:SLUG_MAX].strip("-") or "save"
    slug, n = base, 1
    while (save_dir / f"{slug}{SAVE_SUFFIX}").exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


def describe(path: Path) -> SaveFile:
    summary = repository.summarize(path)
    with repository.open_session(path) as session:
        meta = session.get(SaveMetaRow, META_ID)
        assert meta is not None
        display, state = meta.display_name, meta.game_state
        mode, score = _mode_and_score(session)
    return SaveFile(
        mode=mode,
        score=score,
        slug=summary.slug,
        display_name=display or summary.slug,
        company_name=summary.company_name,
        scenario_id=summary.scenario_id,
        difficulty=summary.difficulty,
        current_turn=summary.current_turn,
        game_state=state,
        last_played=last_played(path),
        size_bytes=file_size(path),
        busy=is_busy(path),
    )


def _mode_and_score(session: Any) -> tuple[str, int | None]:
    """The save's mode and the player's latest company score (M15b, 30.1-30.2): a Sandbox
    game is kept out of the scores (spec 3)."""
    from sqlalchemy import inspect, select

    from tst.db.models import CompanyRow, CompanyScoreRow, GameModeRow

    if not inspect(session.get_bind()).has_table(GameModeRow.__tablename__):
        return "campaign", None
    row = session.get(GameModeRow, 1)
    mode = str(row.data.get("kind", "campaign")) if row is not None else "campaign"
    if mode == "sandbox":
        return mode, None
    player = session.scalar(  # the operating company, not a holding company (M16)
        select(CompanyRow.id).where(CompanyRow.is_player.is_(True)).order_by(CompanyRow.id)
    )
    best = session.scalars(
        select(CompanyScoreRow)
        .where(CompanyScoreRow.company_id == player)
        .order_by(CompanyScoreRow.turn.desc())
        .limit(1)
    ).first()
    return mode, int(best.data["score"]) if best is not None else None


def list_files(save_dir: Path) -> list[SaveFile]:
    """Every save in the folder, most recently played first; unreadable ones are skipped
    (the index logs why)."""
    found = []
    for summary in repository.list_saves(save_dir):
        path = save_dir / f"{summary.slug}{SAVE_SUFFIX}"
        if path.is_file():
            try:
                found.append(describe(repository.existing_save_path(save_dir, summary.slug)))
            except SimError:
                continue
    return sorted(found, key=lambda s: (s.last_played, s.slug), reverse=True)


def rename(path: Path, name: str) -> SaveFile:
    """Change the save's display name; the company name and the file stay as they are."""
    text = _clean_name(name)
    with repository.write_session(path) as session:
        meta = session.get(SaveMetaRow, META_ID)
        assert meta is not None
        meta.display_name = text
    return describe(path)


def _difficulty(path: Path) -> str:
    with repository.open_session(path) as session:
        return str(session.scalar(select(SaveMetaRow.difficulty)))


def _refuse_ironman(path: Path, what: str) -> None:
    if _difficulty(path) == IRONMAN:
        raise IronmanSaveError(f"Ironman saves cannot be {what}")


def _copy_into(source: Path, target: Path, display_name: str) -> None:
    """A consistent copy of a save file (SQLite's online backup), renamed inside."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".partial")
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    tmp.replace(target)
    try:
        migrate.ensure_current(target)  # a backup can predate the latest migration
        with repository.open_session(target) as session, session.begin():
            meta = session.get(SaveMetaRow, META_ID)
            assert meta is not None
            meta.name = slug_of(target)
            meta.display_name = display_name
    except BaseException:
        for leftover in _files(target):
            leftover.unlink(missing_ok=True)
        shutil.rmtree(backup_dir(target), ignore_errors=True)
        raise
    repository.update_index(target)


def duplicate(path: Path, name: str) -> SaveFile:
    """Save as: a new save with its own file, slug and backups folder."""
    _refuse_ironman(path, "duplicated")
    text = _clean_name(name)
    target = path.parent / f"{slug_for(path.parent, text)}{SAVE_SUFFIX}"
    with exclusive(path):
        _copy_into(path, target, text)
    return describe(target)


def delete(path: Path) -> None:
    """Delete the save, its backups and its index entry."""
    with exclusive(path):
        forget_engine(path)
        repository.forget(path)
        for f in _files(path):
            f.unlink(missing_ok=True)
        shutil.rmtree(backup_dir(path), ignore_errors=True)
    repository.remove_from_index(path)


def backups(path: Path) -> list[BackupFile]:
    """Periodic and pre-upgrade backups, newest first."""
    folder = backup_dir(path)
    if not folder.is_dir():
        return []
    slug = slug_of(path)
    found = []
    for f in folder.iterdir():
        m = _BACKUP_RE.match(f.name)
        if m is None or m.group("slug") != slug:
            continue
        stat = f.stat()
        found.append(
            BackupFile(
                backup_id=f.name,
                kind="pre_upgrade" if m.group("rev") else "periodic",
                turn=int(m.group("turn")),
                created=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                size_bytes=stat.st_size,
            )
        )
    return sorted(found, key=lambda b: (b.created, b.turn), reverse=True)


def restore(path: Path, backup_id: str) -> SaveFile:
    """Restore a backup as a NEW save, "Company (restored, Mar 2013)"; the original is
    never changed."""
    _refuse_ironman(path, "restored from a backup")
    found = next((b for b in backups(path) if b.backup_id == backup_id), None)
    if found is None:
        raise UnknownBackupError(f"no backup {backup_id!r} for this save")
    with repository.open_session(path) as session:
        company = session.scalar(  # the operating company, not a holding company (M16)
            select(CompanyRow.name).where(CompanyRow.is_player.is_(True)).order_by(CompanyRow.id)
        )
    name = f"{company} (restored, {format_turn(found.turn)})"[:NAME_MAX]
    target = path.parent / f"{slug_for(path.parent, name)}{SAVE_SUFFIX}"
    with exclusive(path):
        _copy_into(backup_dir(path) / found.backup_id, target, name)
    return describe(target)
