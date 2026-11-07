"""Loading and syncing M15b's records (formulas.md 30; migration 0035): company scores, the
save's mode and the rankings, each kept as a JSON `data` column."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import CompanyScoreRow, GameModeRow, QuarterMarkRow, RankingRow, VentureRow
from tst.sim.modes.models import CompanyScore, GameMode, QuarterMark, Ranking, Venture
from tst.sim.state import GameState


def load_modes(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Scores, the mode and the rankings (0035); a save from before M15b has none."""
    if not has_table(session, CompanyScoreRow):
        return state
    scores = tuple(
        from_data(CompanyScore, r.data, company_id=r.company_id, turn=r.turn)
        for r in session.scalars(
            select(CompanyScoreRow).order_by(CompanyScoreRow.turn, CompanyScoreRow.company_id)
        )
    )
    row = session.get(GameModeRow, 1)
    mode = from_data(GameMode, row.data) if row is not None else None
    rankings = tuple(
        from_data(Ranking, r.data, turn=r.turn, kind=r.kind, place=r.place)
        for r in session.scalars(
            select(RankingRow).order_by(RankingRow.turn, RankingRow.kind, RankingRow.place)
        )
    )
    marks = tuple(
        from_data(QuarterMark, r.data, product_id=r.product_id)
        for r in session.scalars(select(QuarterMarkRow).order_by(QuarterMarkRow.product_id))
    )
    ventures = tuple(
        from_data(Venture, r.data, company_id=r.company_id)
        for r in session.scalars(select(VentureRow).order_by(VentureRow.company_id))
    )
    return replace(
        state, scores=scores, mode=mode, rankings=rankings, quarter_marks=marks, ventures=ventures
    )


def sync_modes(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    """Append new scores and rankings (they are never changed) and write the mode."""
    if (old.scores, old.mode, old.rankings, old.quarter_marks, old.ventures) == (
        new.scores,
        new.mode,
        new.rankings,
        new.quarter_marks,
        new.ventures,
    ):
        return
    if not has_table(session, CompanyScoreRow):
        return
    known = {(s.company_id, s.turn) for s in old.scores}
    session.add_all(
        CompanyScoreRow(
            company_id=s.company_id, turn=s.turn, data=to_data(s, ("company_id", "turn"))
        )
        for s in new.scores
        if (s.company_id, s.turn) not in known
    )
    if new.mode != old.mode:
        if new.mode is None:
            session.execute(delete(GameModeRow))
        else:
            session.merge(GameModeRow(id=1, data=to_data(new.mode)))
    if new.quarter_marks != old.quarter_marks:  # replaced each quarter
        session.execute(delete(QuarterMarkRow))
        session.add_all(
            QuarterMarkRow(product_id=m.product_id, data=to_data(m, ("product_id",)))
            for m in new.quarter_marks
        )
    if new.ventures != old.ventures:
        for v in new.ventures:
            session.merge(VentureRow(company_id=v.company_id, data=to_data(v, ("company_id",))))
    placed = {(r.turn, r.kind, r.place) for r in old.rankings}
    session.add_all(
        RankingRow(
            turn=r.turn, kind=r.kind, place=r.place, data=to_data(r, ("turn", "kind", "place"))
        )
        for r in new.rankings
        if (r.turn, r.kind, r.place) not in placed
    )
