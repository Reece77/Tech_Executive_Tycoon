"""M7c: former staff profiles, and `inbox_event_link` (the events a "While you were away"
summary links to).

Former staff profiles. `former_staff` keeps what the player knew of an employee when
they left (displayed ranges, noticed tags, interests and work style once known), frozen at
departure, plus the last role, level, unit, the reason and the rival who poached them.

New departures are written by `sync_state`. An existing save's past departures are backfilled
from what is stored now: for someone who stayed out of work that is what the player saw when
they left; for someone at a rival, their true skills may have moved since, so the backfilled
ranges are a best effort (documented in docs/data-dictionary.md).

Revision ID: 0021_former_staff
Revises: 0020_divisions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_former_staff"
down_revision: str | None = "0020_divisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "former_staff",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("unit_name", sa.String(64), nullable=True),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("rival_id", sa.Integer(), nullable=True),
        sa.Column("knowledge", sa.JSON(), nullable=False),
    )
    op.create_table(
        "inbox_event_link",
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("inbox_item.id"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
    )
    _backfill()
    op.execute("UPDATE save_meta SET schema_version = 21")


def _backfill() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM save_meta")).first() is None:
        return  # a brand-new save
    from sqlalchemy.orm import Session

    from tst.db.former import knowledge_snapshot
    from tst.db.models import FormerStaffRow
    from tst.db.state_io import load_people

    player = conn.execute(sa.text("SELECT id FROM company WHERE is_player = 1")).scalar()
    if player is None:
        return
    rows = conn.execute(
        sa.text(
            "SELECT e.id, e.person_id, e.role, e.level, e.unit_id, e.start_turn, e.end_turn,"
            " e.end_reason FROM employment e JOIN person p ON p.id = e.person_id"
            " WHERE e.company_id = :c AND e.status = 'ended' AND p.is_founder = 0"
            " ORDER BY e.id"
        ),
        {"c": player},
    ).all()
    if not rows:
        return
    session = Session(bind=conn)
    people, reveals = load_people(session, [r[1] for r in rows])
    by_id = {p.id: p for p in people}
    knowledge = {r.person_id: r for r in reveals if r.observer_company_id == player}
    units = dict(conn.execute(sa.text("SELECT id, name FROM org_unit")).all())
    for emp_id, pid, role, level, unit_id, start, end, reason in rows:
        person, reveal = by_id.get(pid), knowledge.get(pid)
        if person is None or reveal is None:
            continue
        rival = conn.execute(
            sa.text(
                "SELECT company_id FROM employment WHERE person_id = :p AND company_id != :c"
                " AND start_turn >= :t ORDER BY start_turn LIMIT 1"
            ),
            {"p": pid, "c": player, "t": end or 0},
        ).scalar()
        session.merge(
            FormerStaffRow(
                person_id=pid,
                company_id=player,
                employment_id=emp_id,
                role=role,
                level=level,
                unit_name=units.get(unit_id),
                start_turn=start,
                end_turn=end if end is not None else start,
                reason=reason or "left",
                rival_id=rival if reason == "poached" else None,
                knowledge=knowledge_snapshot(person, reveal),
            )
        )
    session.flush()


def downgrade() -> None:
    op.drop_table("inbox_event_link")
    op.drop_table("former_staff")
    op.execute("UPDATE save_meta SET schema_version = 20")
