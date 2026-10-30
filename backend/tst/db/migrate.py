"""Run Alembic against one save file (ADR-0004 section 3)."""

from __future__ import annotations

import logging
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from tst.config import BACKEND_DIR
from tst.db.backup import pre_migration_backup
from tst.db.session import make_engine

log = logging.getLogger(__name__)

MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


@lru_cache(maxsize=1)
def head_revision() -> str:
    head = ScriptDirectory.from_config(_config()).get_current_head()
    if head is None:
        raise RuntimeError("no migrations found")
    return head


# Saves this process has seen at head, keyed by path and creation time (a file recreated at
# the same path is a new key). Any migration run on a path forgets it (M6 sub-task 0).
_AT_HEAD: set[tuple[str, int, str]] = set()
# One migrated, empty schema per head revision, copied into each new save (M6 sub-task 0).
_SCHEMA: dict[str, Path] = {}


def _key(save_path: Path) -> tuple[str, int, str]:
    return (str(save_path.resolve()), save_path.stat().st_ctime_ns, head_revision())


def is_current(save_path: Path) -> bool:
    """Whether the save is at head (remembered per process once seen)."""
    if _key(save_path) in _AT_HEAD:
        return True
    if current_revision(save_path) == head_revision():
        _AT_HEAD.add(_key(save_path))
        return True
    return False


def _forget(save_path: Path) -> None:
    resolved = str(save_path.resolve())
    for key in [k for k in _AT_HEAD if k[0] == resolved]:
        _AT_HEAD.discard(key)


def current_revision(save_path: Path) -> str | None:
    engine = make_engine(save_path)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def _run(save_path: Path, revision: str, *, down: bool = False) -> None:
    if save_path.exists():
        _forget(save_path)
    cfg = _config()
    engine = make_engine(save_path)
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            if down:
                command.downgrade(cfg, revision)
            else:
                command.upgrade(cfg, revision)
    finally:
        engine.dispose()


def upgrade_new(save_path: Path) -> None:
    """Create the schema in a brand-new save file. No backup: there is nothing to lose.

    The migrations run once per process into an empty schema file, which each new save then
    copies: the same file as running them again, without the time (M6 sub-task 0)."""
    head = head_revision()
    schema = _SCHEMA.get(head)
    if schema is None or not schema.is_file():
        schema = Path(tempfile.mkdtemp(prefix="tst-schema-")) / "schema.sqlite"
        _run(schema, "head")
        engine = make_engine(schema)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            engine.dispose()
        _SCHEMA[head] = schema
    shutil.copyfile(schema, save_path)
    _AT_HEAD.add(_key(save_path))


def downgrade(save_path: Path, revision: str) -> None:
    """Test and maintenance helper."""
    _run(save_path, revision, down=True)


def _current_turn(save_path: Path) -> int:
    engine = make_engine(save_path)
    try:
        with engine.connect() as conn:
            try:
                value = conn.execute(text("SELECT current_turn FROM save_meta")).scalar()
            except Exception:
                return 0
            return int(value or 0)
    finally:
        engine.dispose()


def ensure_current(save_path: Path) -> Path | None:
    """Upgrade an existing save to head, backing it up first. Returns the backup, if any."""
    if _key(save_path) in _AT_HEAD:
        return None
    current = current_revision(save_path)
    if current == head_revision():
        _AT_HEAD.add(_key(save_path))
        return None
    backup = pre_migration_backup(save_path, _current_turn(save_path), current)
    log.info("Upgrading %s from %s to head (backup %s)", save_path.name, current, backup.name)
    _run(save_path, "head")
    _AT_HEAD.add(_key(save_path))
    return backup
