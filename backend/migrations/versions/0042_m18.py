"""M18: prospecting and exploration (formulas.md section 34). `exploration_block` holds every
block's hidden truth (34.1: the true_* fields, ADR-0007), `exploration_supplier_licence`
suppliers' licences (34.4), `exploration_desk_study` desk studies and their heat-map bands,
`exploration_project` licensed blocks and their pipelines, `exploration_hole` drill holes'
assays (34.2), each record's fields in a JSON `data` column (data-dictionary.md); account 6600.

Existing saves: their geology is drawn now, exactly as a new game of the same seed draws it at
turn 0 (stream `geology`), so a save from before M18 can explore too.

Revision ID: 0042_m18
Revises: 0041_m17
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_m18"
down_revision: str | None = "0041_m17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT = ("6600_exploration", "Exploration", "expense")
TABLES = (
    ("exploration_block", (("region", sa.String(32)), ("idx", sa.Integer()))),
    ("exploration_supplier_licence", (("region", sa.String(32)), ("block", sa.Integer()))),
    ("exploration_hole", (("project_id", sa.Integer()), ("n", sa.Integer()))),
)


def upgrade() -> None:
    for name, keys in TABLES:
        op.create_table(
            name,
            *(sa.Column(k, t, primary_key=True) for k, t in keys),
            sa.Column("data", sa.JSON(), nullable=False),
        )
    for name in ("exploration_desk_study", "exploration_project"):
        op.create_table(
            name,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
        )
    conn = op.get_bind()
    has_accounts = conn.execute(sa.text("SELECT COUNT(*) FROM account")).scalar()
    if has_accounts:  # a new save gets it from data
        code, name, kind = ACCOUNT
        conn.execute(
            sa.text(
                "INSERT INTO account (code, name, type) SELECT :c, :n, :t "
                "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = :c)"
            ),
            {"c": code, "n": name, "t": kind},
        )
    _backfill(conn)
    op.execute("UPDATE save_meta SET schema_version = 42")


def _backfill(conn: sa.Connection) -> None:
    seed = conn.execute(sa.text("SELECT master_seed FROM save_meta")).scalar()
    if seed is None:
        return  # a brand-new save: new_game draws its geology
    # Imported here so creating a new save does not read the data files twice.
    from tst.config import Settings
    from tst.db.exploration_io import block_row, licence_row
    from tst.loader import load_all
    from tst.sim.exploration.geology import generate_blocks, supplier_licences
    from tst.sim.rng import RngFactory

    loaded = load_all(Settings().data_dir)
    rng = RngFactory(int(seed))
    blocks = generate_blocks(rng, loaded.balance, loaded.game_data)
    licences = supplier_licences(rng, blocks, loaded.balance, loaded.game_data)
    for table, rows in (
        ("exploration_block", [block_row(b) for b in blocks]),
        ("exploration_supplier_licence", [licence_row(x) for x in licences]),
    ):
        for row in rows:
            row["data"] = json.dumps(row["data"])
        if rows:
            conn.execute(sa.table(table, *(sa.column(c) for c in rows[0])).insert(), rows)


def downgrade() -> None:
    for name in (
        "exploration_hole",
        "exploration_project",
        "exploration_desk_study",
        "exploration_supplier_licence",
        "exploration_block",
    ):
        op.drop_table(name)
    op.execute(
        "DELETE FROM account WHERE code = '6600_exploration' AND NOT EXISTS "
        "(SELECT 1 FROM ledger_line WHERE account_code = '6600_exploration')"
    )
    op.execute("UPDATE save_meta SET schema_version = 41")
