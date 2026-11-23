"""M47: negotiations by conversation (formulas.md 58; ADR-0023). `conversation` holds each
negotiation (its deal, status, cool-off and the engine's record, hidden values included, never
shown) and `conversation_round` each round (the player's message, the moves it was scored into,
the offer and the reply). Outside the game state: existing saves have none.

Revision ID: 0065_m47
Revises: 0064_m44
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_m47"
down_revision: str | None = "0064_m44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("deal_key", sa.String(120), nullable=False),
        sa.Column("counterpart_key", sa.String(120), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("opened_turn", sa.Integer(), nullable=False),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
        sa.Column("cooldown_until", sa.Integer(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("suggestions_source", sa.String(16), nullable=False),
        sa.Column("relationship_change", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_conversation_deal", "conversation", ["deal_key", "status"])
    op.create_table(
        "conversation_round",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id", sa.Integer(), sa.ForeignKey("conversation.id"), nullable=False
        ),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("message_source", sa.String(16), nullable=False),
        sa.Column("moves", sa.JSON(), nullable=False),
        sa.Column("moves_source", sa.String(16), nullable=False),
        sa.Column("offer", sa.JSON(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("reply_source", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index(
        "ix_conversation_round_conversation_id", "conversation_round", ["conversation_id"]
    )
    op.execute("UPDATE save_meta SET schema_version = 65")


def downgrade() -> None:
    op.drop_index("ix_conversation_round_conversation_id", "conversation_round")
    op.drop_table("conversation_round")
    op.drop_index("ix_conversation_deal", "conversation")
    op.drop_table("conversation")
    op.execute("UPDATE save_meta SET schema_version = 64")
