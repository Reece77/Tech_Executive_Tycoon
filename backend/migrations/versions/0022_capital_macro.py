"""M10: capital and macro (docs/formulas.md 20).

- `macro_month`: each month's macro indicators (20.1), written by `sync_state` when phase 1
  sets them. A save from before M10 has none; readers fill months up to 2025 from history.
- `loan`: venture debt and bank loans (20.3).
- `finance_history`: the player's operating result and burn at the last month ends, which
  covenants and the bank loan's gate read (20.3). Empty for an old save: it fills as months
  are played.
- `event.loan_id` and `event_queue.loan_id`: a lender event's loan; `event_queue.
  source_event_id` becomes nullable (the engine queues lender events, not an answer).

Revision ID: 0022_capital_macro
Revises: 0021_former_staff
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_capital_macro"
down_revision: str | None = "0021_former_staff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "macro_month",
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("base_rate", sa.Float(), nullable=False),
        sa.Column("climate", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("ai_index", sa.Float(), nullable=False),
        sa.Column("ai_change", sa.Float(), nullable=False),
        sa.Column("downturn_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "loan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("instrument", sa.String(16), nullable=False),
        sa.Column("lender", sa.String(32), nullable=False),
        sa.Column("principal_cents", sa.BigInteger(), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("rate_bp", sa.Integer(), nullable=False),
        sa.Column("signed_turn", sa.Integer(), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("interest_only_months", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=True),
        sa.Column("warrant_shares", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
        sa.Column("interest_paid_cents", sa.BigInteger(), nullable=False),
        sa.Column("principal_paid_cents", sa.BigInteger(), nullable=False),
        sa.Column("breach_turn", sa.Integer(), nullable=True),
        sa.Column("breaches", sa.Integer(), nullable=False),
    )
    op.create_table(
        "finance_history",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("op_history", sa.JSON(), nullable=False),
        sa.Column("burn_history", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("event") as batch:
        batch.add_column(sa.Column("loan_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("event_queue") as batch:
        batch.add_column(sa.Column("loan_id", sa.Integer(), nullable=True))
        batch.alter_column("source_event_id", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE save_meta SET schema_version = 22")


def downgrade() -> None:
    with op.batch_alter_table("event_queue") as batch:
        batch.alter_column("source_event_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("loan_id")
    with op.batch_alter_table("event") as batch:
        batch.drop_column("loan_id")
    op.drop_table("finance_history")
    op.drop_table("loan")
    op.drop_table("macro_month")
    op.execute("UPDATE save_meta SET schema_version = 21")
