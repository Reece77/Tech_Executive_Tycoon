"""Alembic environment. Migrations always target a single save file."""

from __future__ import annotations

from pathlib import Path

from alembic import context

from tst.db.models import Base
from tst.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def _run(connection: object) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite cannot ALTER most things in place
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    save = context.get_x_argument(as_dictionary=True).get("save")
    if not save:
        raise SystemExit("pass the save file: alembic -x save=PATH upgrade head")
    engine = make_engine(Path(save))
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported")
run_migrations_online()
