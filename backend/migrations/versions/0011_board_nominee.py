"""M4c: the founder chooses the board nominee (docs/formulas.md 14.6).

`board_seat.person_id` may be null (an empty common seat), and table `round_nominee` holds
the nominee named when accepting a term sheet (its own table: migration 0009 builds
funding_round rows from the current models). In an existing save, a common seat held by a
generated director (anyone but the founder) becomes empty, and the player's inbox asks the
founder to name a nominee; if the founder had no seat (0009 seated a generated person in the
funded spinout's founder seat), the founder takes that seat instead. The generated person's
row stays; nothing refers to it.

Revision ID: 0011_board_nominee
Revises: 0010_stage_board_history
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_board_nominee"
down_revision: str | None = "0010_stage_board_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed text (inbox items are rendered when written, ADR-0004); matches the
# board_seat_empty template in inbox_templates.yaml at the time of this migration.
TITLE = "Name your board nominee"
BODY = (
    "Your second common board seat is empty. Name an employee to it on the Board tab; "
    "until then the seat still votes with you."
)


def _rebuild_board_seat(*, nullable: bool) -> None:
    """SQLite rebuilds board_seat to change NOT NULL, and with foreign keys on it cannot drop
    a table another table refers to; board_seat_history is set aside and restored."""
    conn = op.get_bind()
    history = conn.execute(sa.text("SELECT seat_id, history FROM board_seat_history")).all()
    op.drop_table("board_seat_history")
    with op.batch_alter_table("board_seat") as batch:
        batch.alter_column("person_id", existing_type=sa.Integer(), nullable=nullable)
    op.create_table(
        "board_seat_history",
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["seat_id"], ["board_seat.id"]),
        sa.PrimaryKeyConstraint("seat_id"),
    )
    for seat_id, value in history:
        conn.execute(
            sa.text("INSERT INTO board_seat_history (seat_id, history) VALUES (:s, :h)"),
            {"s": seat_id, "h": value},
        )


def upgrade() -> None:
    _rebuild_board_seat(nullable=True)
    op.create_table(
        "round_nominee",
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["round_id"], ["funding_round.id"]),
        sa.PrimaryKeyConstraint("round_id"),
    )
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT current_turn FROM save_meta")).first()
    turn = int(meta[0]) if meta is not None else 0
    generated = conn.execute(
        sa.text(
            "SELECT s.id, s.company_id FROM board_seat s JOIN person p ON p.id = s.person_id "
            "WHERE s.kind = 'common' AND p.is_founder = 0 ORDER BY s.id"
        )
    ).all()
    for seat_id, company_id in generated:
        # A save upgraded by 0009 has a generated person on the founder's own seat; the
        # founder takes it back, and only a second common seat empties.
        founder = conn.execute(
            sa.text(
                "SELECT p.id FROM person p JOIN employment e ON e.person_id = p.id "
                "WHERE p.is_founder = 1 AND e.company_id = :c"
            ),
            {"c": company_id},
        ).scalar()
        seated = conn.execute(
            sa.text("SELECT COUNT(*) FROM board_seat WHERE company_id = :c AND person_id = :f"),
            {"c": company_id, "f": founder},
        ).scalar()
        if founder is not None and not seated:
            conn.execute(
                sa.text("UPDATE board_seat SET person_id = :f WHERE id = :id"),
                {"f": founder, "id": seat_id},
            )
            continue
        conn.execute(
            sa.text("UPDATE board_seat SET person_id = NULL WHERE id = :id"), {"id": seat_id}
        )
        conn.execute(
            sa.text(
                "INSERT INTO inbox_item (turn, company_id, template, title, body, link_kind, "
                "link_id, read) VALUES (:t, :c, 'board_seat_empty', :title, :body, 'finance', "
                "NULL, 0)"
            ),
            {"t": turn, "c": company_id, "title": TITLE, "body": BODY},
        )
    op.execute("UPDATE save_meta SET schema_version = 11")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 10")
    op.drop_table("round_nominee")
    # An empty seat cannot go back to NOT NULL; downgrade drops empty common seats.
    op.execute(
        "DELETE FROM board_seat_history WHERE seat_id IN "
        "(SELECT id FROM board_seat WHERE person_id IS NULL)"
    )
    op.execute("DELETE FROM board_seat WHERE person_id IS NULL")
    _rebuild_board_seat(nullable=False)
