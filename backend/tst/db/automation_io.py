"""Loading and syncing M27a's records (formulas.md 40; migration 0049): area owners and the
owners' logged months."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.models import AreaDecisionRow, AreaOwnerRow, HeadcountTargetRow
from tst.sim.automation.models import AreaDecision, AreaOwner, HeadcountTarget
from tst.sim.state import GameState

DECISION_MEMORY = 13  # months of area decisions the state holds (a year's record and digest)


def load_automation(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    if not has_table(session, AreaOwnerRow):
        return state
    owners = tuple(
        AreaOwner(
            r.company_id,
            r.area,
            r.person_id,
            int(r.limit_cents),
            r.priority,
            r.since_turn,
            bool(r.answer_events),
            bool(r.allow_bold),
            int(r.budget_cents or 0),
            tuple(sorted((str(k), float(v)) for k, v in (r.guardrails or {}).items())),
        )
        for r in session.scalars(
            select(AreaOwnerRow).order_by(AreaOwnerRow.company_id, AreaOwnerRow.area)
        )
    )
    decisions = tuple(
        AreaDecision(
            r.company_id,
            r.turn,
            r.seq,
            r.area,
            r.person_id,
            r.kind,  # type: ignore[arg-type]
            r.text,
            int(r.commitment_cents),
            r.ref_id,
        )
        for r in session.scalars(
            select(AreaDecisionRow)
            .where(AreaDecisionRow.turn > state.turn - DECISION_MEMORY)
            .order_by(AreaDecisionRow.company_id, AreaDecisionRow.turn, AreaDecisionRow.seq)
        )
    )
    targets: tuple[HeadcountTarget, ...] = ()
    if has_table(session, HeadcountTargetRow):
        targets = tuple(
            HeadcountTarget(r.company_id, r.unit_id, r.role, r.target, r.set_turn)
            for r in session.scalars(
                select(HeadcountTargetRow).order_by(
                    HeadcountTargetRow.company_id,
                    HeadcountTargetRow.unit_id,
                    HeadcountTargetRow.role,
                )
            )
        )
    return replace(state, area_owners=owners, area_decisions=decisions, headcount_targets=targets)


def sync_automation(
    session: Session,
    old: GameState,
    new: GameState,
    has_table: Callable[[Session, Any], bool],
) -> None:
    if old.headcount_targets != new.headcount_targets and has_table(session, HeadcountTargetRow):
        session.execute(delete(HeadcountTargetRow))
        for t in new.headcount_targets:
            session.add(
                HeadcountTargetRow(
                    company_id=t.company_id,
                    unit_id=t.unit_id,
                    role=t.role,
                    target=t.target,
                    set_turn=t.set_turn,
                )
            )
    if (old.area_owners, old.area_decisions) == (new.area_owners, new.area_decisions):
        return
    if not has_table(session, AreaOwnerRow):
        return
    if old.area_owners != new.area_owners:
        keep = {(o.company_id, o.area) for o in new.area_owners}
        for o in old.area_owners:
            if (o.company_id, o.area) not in keep:
                session.execute(
                    delete(AreaOwnerRow).where(
                        AreaOwnerRow.company_id == o.company_id, AreaOwnerRow.area == o.area
                    )
                )
        before = {(o.company_id, o.area): o for o in old.area_owners}
        for o in new.area_owners:
            if before.get((o.company_id, o.area)) != o:
                session.merge(
                    AreaOwnerRow(
                        company_id=o.company_id,
                        area=o.area,
                        person_id=o.person_id,
                        limit_cents=o.limit_cents,
                        priority=o.priority,
                        since_turn=o.since_turn,
                        answer_events=o.answer_events,
                        allow_bold=o.allow_bold,
                        budget_cents=o.budget_cents,
                        guardrails=dict(o.guardrails),
                    )
                )
    known = {(d.company_id, d.turn, d.seq) for d in old.area_decisions}
    for d in new.area_decisions:  # decisions are written once and never change
        if (d.company_id, d.turn, d.seq) not in known:
            session.merge(
                AreaDecisionRow(
                    company_id=d.company_id,
                    turn=d.turn,
                    seq=d.seq,
                    area=d.area,
                    person_id=d.person_id,
                    kind=d.kind,
                    text=d.text,
                    commitment_cents=d.commitment_cents,
                    ref_id=d.ref_id,
                )
            )
