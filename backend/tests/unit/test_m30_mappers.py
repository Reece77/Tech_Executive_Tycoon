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
