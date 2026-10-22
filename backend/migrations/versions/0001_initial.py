"""M0 initial schema: save_meta, company, account, ledger, snapshots, logs.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "save_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("master_seed", sa.BigInteger(), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("current_turn", sa.Integer(), nullable=False),
        sa.Column("data_hashes", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_player", sa.Boolean(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("founded_turn", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "account",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("memo", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_entry_company_turn", "ledger_entry", ["company_id", "turn"])
    op.create_table(
        "ledger_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["account_code"], ["account.code"]),
        sa.ForeignKeyConstraint(["entry_id"], ["ledger_entry.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_line_entry", "ledger_line", ["entry_id"])
    op.create_table(
        "turn_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kpis", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_turn_snapshot_turn_company", "turn_snapshot", ["turn", "company_id"], unique=True
    )
    op.create_table(
        "decision_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_log_turn", "decision_log", ["turn"])
    op.create_table(
        "turn_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turn_log_turn", "turn_log", ["turn"])


def downgrade() -> None:
    op.drop_index("ix_turn_log_turn", table_name="turn_log")
    op.drop_table("turn_log")
    op.drop_index("ix_decision_log_turn", table_name="decision_log")
    op.drop_table("decision_log")
    op.drop_index("ux_turn_snapshot_turn_company", table_name="turn_snapshot")
    op.drop_table("turn_snapshot")
    op.drop_index("ix_ledger_line_entry", table_name="ledger_line")
    op.drop_table("ledger_line")
    op.drop_index("ix_ledger_entry_company_turn", table_name="ledger_entry")
    op.drop_table("ledger_entry")
    op.drop_table("account")
    op.drop_table("company")
    op.drop_table("save_meta")
