"""M11: the R&D tree and era milestones (formulas.md 21): research leads by company and
domain (`research_lead`), research projects (`research_project`), arrived eras
(`era_arrival`) and licences (`research_license`). Existing saves start with no leads,
projects or licences; eras whose historical month is before the save's turn are recorded as
arrived on that month, on schedule (21.4), so their boosts and baseline steps are history.

Revision ID: 0028_research
Revises: 0027_exec_authority
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_research"
down_revision: str | None = "0027_exec_authority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_lead",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("domain", sa.String(32), primary_key=True),
        sa.Column("lead", sa.Float(), nullable=False),
    )
    op.create_table(
        "research_project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("end_turn", sa.Integer(), nullable=True),
        sa.Column("recent", sa.JSON(), nullable=False),
        sa.Column("gained", sa.Float(), nullable=False),
        sa.Column("last_event", sa.String(16), nullable=True),
        sa.Column("last_event_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "era_arrival",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("months_early", sa.Integer(), nullable=False),
    )
    op.create_table(
        "research_license",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("licensor_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("licensee_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("royalty_bp", sa.Integer(), nullable=False),
        sa.Column("royalty_end_turn", sa.Integer(), nullable=True),
    )
    _past_eras()
    op.execute("UPDATE save_meta SET schema_version = 28")


def _past_eras() -> None:
    """Eras whose historical month is before the save's turn, arrived on schedule."""
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT current_turn FROM save_meta")).first()
    if meta is None:
        return  # a brand-new save: the engine records eras as they arrive
    from tst.config import Settings
    from tst.loader import load_all
    from tst.sim.calendar import ym_to_turn

    data = load_all(Settings().data_dir).game_data
    for era in data.eras.eras:
        turn = ym_to_turn(*era.arrival)
        if turn < int(meta[0]):
            conn.execute(
                sa.text(
                    "INSERT INTO era_arrival (key, turn, company_id, months_early) "
                    "VALUES (:k, :t, NULL, 0)"
                ),
                {"k": era.key, "t": turn},
            )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 27")
    op.drop_table("research_license")
    op.drop_table("era_arrival")
    op.drop_table("research_project")
    op.drop_table("research_lead")
