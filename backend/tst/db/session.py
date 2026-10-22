"""Engine factory for one save file (ADR-0004).

Each save is its own SQLite file. Connections use WAL, foreign keys and synchronous=NORMAL.
pysqlite's implicit transaction handling is disabled and SQLAlchemy emits BEGIN itself, so a
`session.begin()` block is one real SQLite transaction (the SQLAlchemy-documented recipe).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
)


def make_engine(path: Path) -> Engine:
    # NullPool: connections close when a session ends, so no file handle outlives a request.
    engine = create_engine(f"sqlite:///{path.as_posix()}", poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: sqlite3.Connection, _record: Any) -> None:
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        for pragma in PRAGMAS:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
