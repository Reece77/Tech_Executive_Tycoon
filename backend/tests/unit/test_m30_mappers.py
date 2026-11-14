"""M30: sync_state writes new people and reveals from plain parameter rows (`person_values`,
`reveal_values`); they hold exactly the columns of the ORM rows migrations still build
(`person_to_rows`, `reveal_to_rows`)."""

from __future__ import annotations

from typing import Any

from tst.balance import m30
from tst.balance.game import start_game
from tst.balance.report import SCENARIO
from tst.db.mappers import person_to_rows, person_values, reveal_to_rows, reveal_values


def _columns(row: Any) -> dict[str, Any]:
    return {a.key: getattr(row, a.key) for a in type(row).__mapper__.column_attrs}


def _by_table(rows: list[Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(type(row).__tablename__, []).append(_columns(row))
    return out


def test_plain_rows_equal_the_orm_rows() -> None:
    game = start_game(m30.loaded(), 4, SCENARIO)
    script = m30.strategy("research_heavy")
    for _ in range(8):  # candidates and their records arrive
        script(game)
        game.turn()
    state = game.state
    assert len(state.people) > 5 and len(state.reveals) > 2
    for person in state.people:
        plain = {m.__tablename__: v for m, v in person_values(person) if v}
        assert plain == _by_table(person_to_rows(person))
    for reveal in state.reveals:
        records, profile, tags = reveal_values(reveal)
        plain = {"person_reveal": records}
        if profile is not None:
            plain["person_profile_reveal"] = [profile]
        if tags:
            plain["person_tag_reveal"] = tags
        assert {k: v for k, v in plain.items() if v} == _by_table(reveal_to_rows(reveal))


def test_driver_updates_store_what_sqlalchemy_stores() -> None:
    """M30: bulk UPDATEs of plain columns go to the SQLite driver; the rows and their storage
    types equal SQLAlchemy's own UPDATE's (an int bound to a Float column is stored as REAL)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from tst.db import state_io
    from tst.db.models import PersonSkillRow

    table = PersonSkillRow.__table__
    rows = [
        {"person_id": 1, "skill": "coding", "position": 0, "value": 3},  # an int
        {"person_id": 1, "skill": "design", "position": 1, "value": 7.25},
        {"person_id": 2, "skill": "coding", "position": 0, "value": 19.999999999},
    ]
    stored = []
    for raw in (True, False):
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE person (id INTEGER PRIMARY KEY)"))
        table.create(engine)  # type: ignore[attr-defined]
        with Session(engine) as session, session.begin():
            session.execute(
                table.insert(),  # type: ignore[attr-defined]
                [{**r, "value": 1.0} for r in rows],
            )
            if raw:
                state_io._update_rows(session, PersonSkillRow, [dict(r) for r in rows])
            else:
                keys = tuple(rows[0])
                names = tuple(f"b_{k}" for k in keys)
                session.execute(
                    state_io._update_statement(PersonSkillRow, keys),
                    [dict(zip(names, r.values(), strict=True)) for r in rows],
                )
            stored.append(
                session.execute(
                    text(
                        "SELECT person_id, skill, position, value, typeof(value) FROM person_skill"
                        " ORDER BY person_id, skill"
                    )
                ).all()
            )
    assert state_io._raw_sql(PersonSkillRow, tuple(rows[0]), "sqlite") is not None
    assert stored[0] == stored[1]
    assert {r[4] for r in stored[0]} == {"real"}
