"""M1b hiring: mission, id counters, searches, candidates, offers, morale log, action seq.

Existing saves get an empty mission, counters from their current maximum ids, and founder
energy of 100 (the M1b default, founder.energy_per_month).

Revision ID: 0003_hiring
Revises: 0002_people
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_hiring"
down_revision: str | None = "0002_people"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOUNDER_ENERGY = 100  # founder.energy_per_month when this migration was written


def upgrade() -> None:
    # Plain ADD/DROP COLUMN (SQLite >= 3.35): batch mode would recreate tables that other
    # tables reference, which foreign_keys=ON forbids.
    op.add_column("company", sa.Column("mission", sa.JSON(), nullable=False, server_default="[]"))
    for column in ("next_person_id", "next_search_id", "next_offer_id", "next_employment_id"):
        op.add_column(
            "save_meta", sa.Column(column, sa.Integer(), nullable=False, server_default="1")
        )
    op.add_column("decision_log", sa.Column("seq", sa.Integer(), nullable=True))

    op.create_table(
        "search",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("opened_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_company_status", "search", ["company_id", "status"])
    op.create_table(
        "candidate",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("expires_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["search.id"]),
        sa.PrimaryKeyConstraint("person_id"),
    )
    op.create_index("ix_candidate_company_status", "candidate", ["company_id", "status"])
    op.create_table(
        "offer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("salary_cents", sa.BigInteger(), nullable=False),
        sa.Column("equity_bp", sa.Integer(), nullable=False),
        sa.Column("made_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_company_status", "offer", ["company_id", "status"])
    op.create_table(
        "person_morale_log",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("morale", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", "turn"),
    )

    op.execute(
        "UPDATE save_meta SET "
        "next_person_id = (SELECT COALESCE(MAX(id), 0) + 1 FROM person), "
        "next_employment_id = (SELECT COALESCE(MAX(id), 0) + 1 FROM employment), "
        "schema_version = 3"
    )
    op.execute(
        "INSERT INTO person_state (person_id, energy, stress, morale) "
        f"SELECT id, {FOUNDER_ENERGY}, NULL, NULL FROM person WHERE is_founder = 1 "
        "AND id NOT IN (SELECT person_id FROM person_state)"
    )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 2")
    op.drop_table("person_morale_log")
    op.drop_index("ix_offer_company_status", table_name="offer")
    op.drop_table("offer")
    op.drop_index("ix_candidate_company_status", table_name="candidate")
    op.drop_table("candidate")
    op.drop_index("ix_search_company_status", table_name="search")
    op.drop_table("search")
    op.drop_column("decision_log", "seq")
    for column in ("next_employment_id", "next_offer_id", "next_search_id", "next_person_id"):
        op.drop_column("save_meta", column)
    op.drop_column("company", "mission")
