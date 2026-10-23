"""M1a people: person and its attribute, tag and reveal tables, employment, relationship.

Revision ID: 0002_people
Revises: 0001_initial
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_people"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _attr_table(name: str, key: str, *, value: bool = True) -> None:
    columns = [
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column(key, sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    ]
    if value:
        columns.append(sa.Column("value", sa.Float(), nullable=False))
    op.create_table(
        name,
        *columns,
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", key),
    )


def upgrade() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=40), nullable=False),
        sa.Column("last_name", sa.String(length=40), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("birth_turn", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("work_style", sa.String(length=16), nullable=False),
        sa.Column("salary_expectation_cents", sa.BigInteger(), nullable=True),
        sa.Column("is_founder", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _attr_table("person_skill", "skill")
    _attr_table("person_personality", "trait")
    _attr_table("person_hidden", "trait")
    _attr_table("person_interest", "interest", value=False)
    _attr_table("person_tag", "tag", value=False)
    op.create_table(
        "person_tag_reveal",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("observer_company_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("revealed_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["observer_company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", "observer_company_id", "tag"),
    )
    op.create_table(
        "person_reveal",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("observer_company_id", sa.Integer(), nullable=False),
        sa.Column("attribute", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("hw", sa.Float(), nullable=False),
        sa.Column("center_offset", sa.Float(), nullable=False),
        sa.Column("last_updated_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["observer_company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", "observer_company_id", "attribute"),
    )
    op.create_table(
        "person_profile_reveal",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("observer_company_id", sa.Integer(), nullable=False),
        sa.Column("revealed_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["observer_company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", "observer_company_id"),
    )
    op.create_table(
        "person_state",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("energy", sa.Float(), nullable=True),
        sa.Column("stress", sa.Float(), nullable=True),
        sa.Column("morale", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id"),
    )
    op.create_table(
        "employment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("salary_cents", sa.BigInteger(), nullable=False),
        sa.Column("equity_bp", sa.Integer(), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("end_reason", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employment_company_status", "employment", ["company_id", "status"])
    op.create_table(
        "relationship",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("other_person_id", sa.Integer(), nullable=False),
        sa.Column("affinity", sa.Float(), nullable=False),
        sa.Column("updated_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["other_person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("person_id", "other_person_id"),
    )
    op.execute("UPDATE save_meta SET schema_version = 2")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 1")
    op.drop_table("relationship")
    op.drop_index("ix_employment_company_status", table_name="employment")
    op.drop_table("employment")
    op.drop_table("person_state")
    op.drop_table("person_profile_reveal")
    op.drop_table("person_reveal")
    op.drop_table("person_tag_reveal")
    for table in ("person_tag", "person_interest", "person_hidden", "person_personality"):
        op.drop_table(table)
    op.drop_table("person_skill")
    op.drop_table("person")
