"""M6: events, storylines and LLM text (docs/formulas.md 16; ADR-0005). Tables `event`,
`storyline`, `event_queue` (critical follow-ups), `llm_text` (headlines, minutes, exit lines)
and `llm_call_log`; account `4900_other_income` for event cash gains. Existing saves start
with no events: the director queues the first ones at the end of the next turn.

Revision ID: 0016_events
Revises: 0015_relationships
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_events"
down_revision: str | None = "0015_relationships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storyline",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("started_turn", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("person_ids", sa.JSON(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("rival_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("segment", sa.String(32), nullable=True),
        sa.Column("next_turn", sa.Integer(), nullable=True),
        sa.Column("next_template", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ended_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("person_ids", sa.JSON(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("segment", sa.String(32), nullable=True),
        sa.Column("rival_id", sa.Integer(), nullable=True),
        sa.Column("months", sa.Integer(), nullable=True),
        sa.Column("cash_base_cents", sa.BigInteger(), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("storyline_id", sa.Integer(), sa.ForeignKey("storyline.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=False),
        sa.Column("chosen", sa.String(1), nullable=True),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
    )
    op.create_index("ix_event_turn", "event", ["turn"])
    op.create_index("ix_event_status", "event", ["status"])
    op.create_table(
        "event_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("due_turn", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("event.id"), nullable=False),
        sa.Column("person_ids", sa.JSON(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("rival_id", sa.Integer(), nullable=True),
        sa.Column("segment", sa.String(32), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "llm_text",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(16), nullable=False, server_default=""),
    )
    op.create_index("ix_llm_text_turn_kind", "llm_text", ["turn", "kind"])
    op.create_table(
        "llm_call_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_cents", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
    )
    op.execute(
        "INSERT INTO account (code, name, type) "
        "SELECT '4900_other_income', 'Other income', 'revenue' "
        "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = '4900_other_income') "
        "AND EXISTS (SELECT 1 FROM account)"  # a new save gets its accounts from the data file
    )
    op.execute("UPDATE save_meta SET schema_version = 16")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 15")
    op.execute(
        "DELETE FROM account WHERE code = '4900_other_income' AND NOT EXISTS "
        "(SELECT 1 FROM ledger_line WHERE account_code = '4900_other_income')"
    )
    op.drop_table("llm_call_log")
    op.drop_index("ix_llm_text_turn_kind", "llm_text")
    op.drop_table("llm_text")
    op.drop_table("event_queue")
    op.drop_index("ix_event_status", "event")
    op.drop_index("ix_event_turn", "event")
    op.drop_table("event")
    op.drop_table("storyline")
