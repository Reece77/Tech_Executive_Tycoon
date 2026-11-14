"""M30: world records are written as a diff (front drops, a shared run, a changed tail), and
reading the rows back in `n` order gives exactly the collection written, whatever the
sequence of changes."""

from __future__ import annotations

from typing import Any
from unittest import mock

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tst.db import world_io
from tst.db.mna_io import from_data
from tst.db.models import WorldRecordRow
from tst.db.world_io import STRIDE, _write_changes
from tst.sim.world.models import WorldNews

KIND = "world_news"
BASE = 4 * STRIDE  # world_news's place among the collections


def _news(i: int, turn: int = 0, text: str = "") -> WorldNews:
    return WorldNews(id=i, turn=turn, kind="deal", message=text or f"item {i}")


def _read(session: Session, base: int = BASE, stride: int = STRIDE) -> tuple[Any, ...]:
    rows = session.scalars(select(WorldRecordRow).order_by(WorldRecordRow.n)).all()
    assert all(r.kind == KIND and base <= r.n < base + stride for r in rows)
    return tuple(from_data(WorldNews, r.data) for r in rows)


# one step: drop some from the front, edit one item, append some (or replace everything)
steps = st.lists(
    st.tuples(
        st.integers(0, 6),
        st.one_of(st.none(), st.integers(0, 30)),
        st.integers(0, 5),
        st.booleans(),
    ),
    min_size=1,
    max_size=25,
)


def _play(plan: list[tuple[int, int | None, int, bool]], base: int, stride: int) -> None:
    engine = create_engine("sqlite://")
    WorldRecordRow.__table__.create(engine)  # type: ignore[attr-defined]
    current: tuple[WorldNews, ...] = ()
    next_id = 1
    with Session(engine) as session:
        for drop, edit, add, replace_all in plan:
            after = list(current[drop:])
            if edit is not None and after:
                i = edit % len(after)
                after[i] = _news(after[i].id, 1, "edited")
            for _ in range(add):
                after.append(_news(next_id))
                next_id += 1
            if replace_all:
                after = [_news(next_id + j) for j in range(add)]
                next_id += add
            new = tuple(after)
            if new != current:
                _write_changes(session, KIND, base, current, new)
            assert _read(session, base, stride) == new
            current = new


@settings(max_examples=60, deadline=None)
@given(steps)
def test_rows_read_back_as_the_collection_written(
    plan: list[tuple[int, int | None, int, bool]],
) -> None:
    _play(plan, BASE, STRIDE)


@settings(max_examples=60, deadline=None)
@given(steps)
def test_out_of_numbers_renumbers_from_the_start(
    plan: list[tuple[int, int | None, int, bool]],
) -> None:
    """A stride of 40 runs out within a plan: the collection is renumbered, still whole."""
    with mock.patch.object(world_io, "STRIDE", 40):
        _play(plan, 4 * 40, 40)
