"""Run Alembic against one save file (ADR-0004 section 3)."""

from __future__ import annotations

import logging
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


def current_revision(save_path: Path) -> str | None:
    engine = make_engine(save_path)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def _run(save_path: Path, revision: str, *, down: bool = False) -> None:
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
    """Create the schema in a brand-new save file. No backup: there is nothing to lose."""
    _run(save_path, "head")


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
    current = current_revision(save_path)
    if current == head_revision():
        return None
    backup = pre_migration_backup(save_path, _current_turn(save_path), current)
    log.info("Upgrading %s from %s to head (backup %s)", save_path.name, current, backup.name)
    _run(save_path, "head")
    return backup
