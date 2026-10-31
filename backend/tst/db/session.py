"""Engine factory for one save file (ADR-0004).

Each save is its own SQLite file. Connections use WAL, foreign keys and synchronous=NORMAL.
pysqlite's implicit transaction handling is disabled and SQLAlchemy emits BEGIN itself, so a
`session.begin()` block is one real SQLite transaction (the SQLAlchemy-documented recipe).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
)


def _sync_pragma() -> str:
    """NORMAL; TST_SQLITE_SYNC=OFF skips fsync for throwaway saves (the test suite, M6.0)."""
    return f"PRAGMA synchronous={'OFF' if os.environ.get('TST_SQLITE_SYNC') == 'OFF' else 'NORMAL'}"


def make_engine(path: Path) -> Engine:
    # NullPool: connections close when a session ends, so no file handle outlives a request.
    engine = create_engine(f"sqlite:///{path.as_posix()}", poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: sqlite3.Connection, _record: Any) -> None:
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        for pragma in (*PRAGMAS, _sync_pragma()):
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    return engine


_ENGINES: OrderedDict[str, Engine] = OrderedDict()
_ENGINES_GUARD = threading.Lock()
ENGINES_KEPT = 16  # saves whose engines (and compiled SQL) are kept, most recently used


def shared_engine(path: Path) -> Engine:
    """The save's engine, kept between sessions. An engine holds SQLAlchemy's compiled-SQL
    cache, so a new engine per session compiled every statement again on every turn (about a
    third of a turn's write time; M7a sub-task 0). NullPool still closes the file when a
    session ends, so keeping the engine keeps no file open."""
    key = str(path.resolve())
    with _ENGINES_GUARD:
        engine = _ENGINES.get(key)
        if engine is None:
            engine = _ENGINES[key] = make_engine(path)
            while len(_ENGINES) > ENGINES_KEPT:
                _ENGINES.popitem(last=False)[1].dispose()
        else:
            _ENGINES.move_to_end(key)
        return engine


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def forget_engine(path: Path) -> None:
    """Drop a save's kept engine (its file is being deleted; M7b)."""
    with _ENGINES_GUARD:
        engine = _ENGINES.pop(str(path.resolve()), None)
    if engine is not None:
        engine.dispose()
