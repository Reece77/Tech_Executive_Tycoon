"""Loading and syncing M24's records (formulas.md 32; migration 0037): founders' lives,
the personal book (append-only, in its own table, never in `ledger_entry`), foundations
and influence, each kept as JSON."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import FoundationRow, FounderLifeRow, InfluenceRow, PersonalEntryRow
from tst.sim.founder.models import Foundation, FounderLife, Influence, PersonalEntry
from tst.sim.ledger import LedgerLine
from tst.sim.state import GameState


def load_founder(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every M24 record; a save from before M24 has none (the founder starts fresh)."""
    if not has_table(session, FounderLifeRow):
        return state
    lives = tuple(
        from_data(FounderLife, r.data, person_id=r.person_id)
        for r in session.scalars(select(FounderLifeRow).order_by(FounderLifeRow.person_id))
    )
    book = tuple(
        PersonalEntry(
            turn=r.turn,
            person_id=r.person_id,
            memo=r.memo,
            source=r.source,
            lines=tuple(LedgerLine(str(a), int(c)) for a, c in r.lines),
        )
        for r in session.scalars(select(PersonalEntryRow).order_by(PersonalEntryRow.id))
    )
    foundations = tuple(
        from_data(Foundation, r.data, person_id=r.person_id)
        for r in session.scalars(select(FoundationRow).order_by(FoundationRow.person_id))
    )
    influence = tuple(
        from_data(Influence, r.data, company_id=r.company_id, region=r.region)
        for r in session.scalars(
            select(InfluenceRow).order_by(InfluenceRow.company_id, InfluenceRow.region)
        )
    )
    return replace(
        state,
        founder_lives=lives,
        personal_book=book,
        foundations=foundations,
        influence=influence,
    )


def sync_founder(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if (old.founder_lives, old.personal_book, old.foundations, old.influence) == (
        new.founder_lives,
        new.personal_book,
        new.foundations,
        new.influence,
    ):
        return
    if not has_table(session, FounderLifeRow):
        return
    if new.founder_lives != old.founder_lives:
        before = {life.person_id: life for life in old.founder_lives}
        for life in new.founder_lives:
            if before.get(life.person_id) != life:
                session.merge(
                    FounderLifeRow(person_id=life.person_id, data=to_data(life, ("person_id",)))
                )
    if new.personal_book != old.personal_book:  # append-only
        known = len(old.personal_book)
        if new.personal_book[:known] != old.personal_book:  # tunable-exempt: not a tunable
            session.execute(delete(PersonalEntryRow))
            known = 0
        session.add_all(
            PersonalEntryRow(
                turn=e.turn,
                person_id=e.person_id,
                memo=e.memo[:200],
                source=e.source,
                lines=[[line.account, line.amount] for line in e.lines],
            )
            for e in new.personal_book[known:]
        )
    if new.foundations != old.foundations:
        for f in new.foundations:
            session.merge(FoundationRow(person_id=f.person_id, data=to_data(f, ("person_id",))))
    if new.influence != old.influence:
        before_i = {(i.company_id, i.region): i for i in old.influence}
        for i in new.influence:
            if before_i.get((i.company_id, i.region)) != i:
                session.merge(
                    InfluenceRow(
                        company_id=i.company_id,
                        region=i.region,
                        data=to_data(i, ("company_id", "region")),
                    )
                )
