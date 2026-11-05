"""M14: mergers and acquisitions (formulas.md section 28): listed rivals' sentiment
(`rival_listing`), what each acquirer knows of a target (`mna_target_file`), deals
(`mna_deal`), closed acquisitions (`mna_acquisition`), acquired key people during culture clash
(`mna_acquired_person`) and kept brands' parent company (`company_parent`). The M&A records
keep their fields in a JSON `data` column (data-dictionary.md). Existing saves start with
none: a company that never buys plays as before.

Revision ID: 0033_mna
Revises: 0032_pitches
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_mna"
down_revision: str | None = "0032_pitches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rival_listing",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("sentiment", sa.Float(), nullable=False),
    )
    op.create_table(
        "company_parent",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
    )
    op.create_table(
        "mna_target_file",
        sa.Column("acquirer_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "mna_deal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "mna_acquisition",
        sa.Column("deal_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "mna_acquired_person",
        sa.Column("person_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "mna_acquired_person",
        "mna_acquisition",
        "mna_deal",
        "mna_target_file",
        "company_parent",
        "rival_listing",
    ):
        op.drop_table(table)
