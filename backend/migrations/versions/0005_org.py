"""M2a organization: units, hiring plans, raises, interview record, decision source.

Existing saves keep everyone in the company root (employment.unit_id NULL), an office
policy, no plans, and unit and plan counters at 1. Candidates the company has already
interviewed get interviewed_turn from decision_log, so the interview-before-offer rule
(ADR-0016) does not lock out offers to them. Logged actions get source 'player' and their
actor from the payload.

Revision ID: 0005_org
Revises: 0004_inbox
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_org"
down_revision: str | None = "0004_inbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_unit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("leader_id", sa.Integer(), nullable=True),
        sa.Column("policy", sa.String(length=16), nullable=True),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dissolved_turn", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["leader_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_unit_company_status", "org_unit", ["company_id", "status"])
    op.create_table(
        "hiring_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("ratio_bp", sa.Integer(), nullable=False),
        sa.Column("equity_bp", sa.Integer(), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("hired", sa.Integer(), nullable=False),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
        sa.Column("last_activity", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hiring_plan_company_status", "hiring_plan", ["company_id", "status"])

    # Plain ADD/DROP COLUMN (SQLite >= 3.35), as in 0003_hiring. Columns added to existing
    # tables carry no REFERENCES clause: SQLite cannot add the constraint by ALTER, and a
    # referencing column could not be dropped again on downgrade. The engine keeps them valid.
    op.add_column(
        "company",
        sa.Column("work_policy", sa.String(length=16), nullable=False, server_default="office"),
    )
    for column in ("next_unit_id", "next_plan_id"):
        op.add_column(
            "save_meta", sa.Column(column, sa.Integer(), nullable=False, server_default="1")
        )
    op.add_column(
        "employment",
        sa.Column("unit_id", sa.Integer(), nullable=True),
    )
    op.add_column("employment", sa.Column("last_raise_turn", sa.Integer(), nullable=True))
    op.add_column("candidate", sa.Column("interviewed_turn", sa.Integer(), nullable=True))
    op.add_column("offer", sa.Column("plan_id", sa.Integer(), nullable=True))
    op.add_column("offer", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.add_column(
        "decision_log",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="player"),
    )
    op.add_column(
        "decision_log",
        sa.Column("actor_id", sa.Integer(), nullable=True),
    )

    op.execute(
        "UPDATE decision_log SET actor_id = json_extract(payload, '$.actor_id') "
        "WHERE seq IS NOT NULL AND json_extract(payload, '$.actor_id') IS NOT NULL"
    )
    op.execute(
        "UPDATE candidate SET interviewed_turn = ("
        " SELECT MIN(d.turn) FROM decision_log d"
        " WHERE d.kind = 'interview' AND d.company_id = candidate.company_id"
        " AND json_extract(d.payload, '$.candidate_id') = candidate.person_id)"
    )
    op.execute("UPDATE save_meta SET schema_version = 5")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 4")
    for table, column in (
        ("decision_log", "actor_id"),
        ("decision_log", "source"),
        ("offer", "unit_id"),
        ("offer", "plan_id"),
        ("candidate", "interviewed_turn"),
        ("employment", "last_raise_turn"),
        ("employment", "unit_id"),
        ("save_meta", "next_plan_id"),
        ("save_meta", "next_unit_id"),
        ("company", "work_policy"),
    ):
        op.drop_column(table, column)
    op.drop_index("ix_hiring_plan_company_status", table_name="hiring_plan")
    op.drop_table("hiring_plan")
    op.drop_index("ix_org_unit_company_status", table_name="org_unit")
    op.drop_table("org_unit")
