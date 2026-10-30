"""The event service against a save (docs/formulas.md 16.5; ADR-0004, ADR-0005).

`write_pending` runs after a turn commits (and before any later write, in case it did not):
in one transaction it gives every pending event its words and choices and every pending
text its words, logs each adapter call, then adds the spend to the monthly meter. Replay
passes `copy_from` instead: the original save's stored words and choices, no adapter.
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.config import get_settings
from tst.db.mappers import event_from_row
from tst.db.models import EventRow, InboxItemRow, LLMCallLogRow, LLMTextRow
from tst.db.state_io import has_table, sync_state
from tst.events.context import Kpis
from tst.events.service import Writer, write_event, write_text
from tst.llm.base import LLMAdapter
from tst.llm.settings import active_adapter, add_spend, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.finance.statements import projected_runway
from tst.sim.ledger import CASH, account_balance
from tst.sim.state import GameState, with_event

log = logging.getLogger(__name__)


def default_adapter(save_dir: Path) -> LLMAdapter:
    """The adapter the settings choose (TST_LLM_ADAPTER wins; tests set "mock")."""
    settings = get_settings()
    return active_adapter(load_settings(save_dir), settings.anthropic_api_key, settings.llm_adapter)


def _kpis(session: Session, state: GameState, data: LoadedData) -> Kpis:
    from tst.db.repository import current_balances, latest_snapshot

    cid = state.player.id
    cash = account_balance(current_balances(session, state.turn), cid, CASH)
    snap = latest_snapshot(session, cid)
    return Kpis(
        cash_cents=cash,
        runway_months=projected_runway(state, cid, cash, data.balance, data.game_data),
        mrr_cents=snap.mrr_cents if snap else 0,
        headcount=len(state.staff(cid)),
        stage=state.player.stage,
    )


EVENT_KINDS = {"critical": "critical_event"}  # inbox kind (badge) by severity; else "event"
TEASER_WORDS = 30  # tunable-exempt: inbox preview length


def event_inbox_row(event: GameEvent) -> InboxItemRow:
    """An inbox item for a written event: the Event (or Critical) badge, opening the card."""
    words = event.body.split()
    teaser = " ".join(words[:TEASER_WORDS]) + ("…" if len(words) > TEASER_WORDS else "")
    return InboxItemRow(
        turn=event.turn,
        company_id=event.company_id,
        template=EVENT_KINDS.get(event.severity, "event"),
        title=event.title,
        body=teaser,
        link_kind="event",
        link_id=event.id,
        read=False,
        archived=False,
    )


def has_pending(session: Session) -> bool:
    if not has_table(session, EventRow):
        return False
    return (
        session.scalar(select(EventRow.id).where(EventRow.status == "pending").limit(1)) is not None
        or session.scalar(select(LLMTextRow.id).where(LLMTextRow.status == "pending").limit(1))
        is not None
    )


def _copy(session: Session, state: GameState, source: Path) -> GameState:
    """Replay: take each pending event's words and choices from the original save."""
    from tst.db.repository import open_session

    pending = [e for e in state.events if e.status == "pending"]
    texts = session.scalars(select(LLMTextRow).where(LLMTextRow.status == "pending")).all()
    with open_session(source) as src:
        for event in pending:
            row = src.get(EventRow, event.id)
            if row is None:
                continue
            original = event_from_row(row)
            state = with_event(
                state,
                replace(
                    event,
                    status="open",
                    title=original.title,
                    body=original.body,
                    choices=original.choices,
                    source=original.source,  # copied, not written: no adapter is called
                ),
            )
        for text in texts:
            done = src.scalars(
                select(LLMTextRow).where(
                    LLMTextRow.turn == text.turn,
                    LLMTextRow.kind == text.kind,
                    LLMTextRow.ref_id.is_(None)
                    if text.ref_id is None
                    else LLMTextRow.ref_id == text.ref_id,
                )
            ).first()
            text.text = done.text if done else ""
            text.source = done.source if done else "replay"
            text.status = "written"
    return state


def write_pending(
    path: Path,
    data: LoadedData,
    *,
    adapter: LLMAdapter | None = None,
    copy_from: Path | None = None,
    committed: GameState | None = None,
) -> int:
    """Write every pending event and text of the save; returns how many events were written.
    `committed` is the state the turn just wrote, which saves loading it again (run_turn)."""
    from tst.db.repository import (
        CACHED_BALANCES,
        CACHED_STATE,
        load_current,
        remember,
        write_session,
    )

    save_dir = path.parent
    with write_session(path) as session:
        if committed is None and not has_pending(session):
            return 0
        state = committed if committed is not None else load_current(session)
        before = state
        if copy_from is not None:
            state = _copy(session, state, copy_from)
            writer = None
        else:
            settings = load_settings(save_dir)
            spent = month_spend(save_dir).cents
            writer = Writer(
                adapter=adapter or default_adapter(save_dir),
                settings=settings,
                budget_left=lambda: settings.monthly_budget_cents - spent,
                debug=os.environ.get("TST_LLM_DEBUG") == "1",
            )
            kpis = _kpis(session, state, data)
            for event in [e for e in state.events if e.status == "pending"]:
                state = write_event(state, event, kpis, writer, data.balance, data.game_data)
            for text in session.scalars(
                select(LLMTextRow).where(LLMTextRow.status == "pending").order_by(LLMTextRow.id)
            ):
                text.text, text.source = write_text(
                    state, text.kind, text.turn, text.ref_id, writer
                )
                text.status = "written"
            now = datetime.now(UTC).isoformat(timespec="seconds")
            session.add_all(
                LLMCallLogRow(
                    turn=state.turn,
                    purpose=r.purpose,
                    model=r.model,
                    prompt_hash=r.prompt_hash,
                    input_tokens=r.input_tokens,
                    output_tokens=r.output_tokens,
                    cost_cents=r.cost_cents,
                    latency_ms=r.latency_ms,
                    outcome=r.outcome,
                    created_at=now,
                    prompt=r.prompt,
                    response=r.response,
                )
                for r in writer.records
            )
        was_pending = {e.id for e in before.events if e.status == "pending"}
        opened = [e for e in state.events if e.id in was_pending and e.status == "open"]
        session.add_all(event_inbox_row(e) for e in opened)
        sync_state(session, before, state)
        cached = session.info.get(CACHED_STATE)  # writing events posts no ledger lines
        same_turn = cached is not None and cached.turn == state.turn
        balances = session.info.get(CACHED_BALANCES) if same_turn else None
    remember(path, state, balances)
    if writer is not None and (writer.records or writer.spent_cents):
        add_spend(
            save_dir,
            writer.spent_cents,
            calls=sum(1 for r in writer.records if r.outcome != "budget"),
            claude_events=writer.claude_events if writer.adapter.name == "claude" else 0,
            rejected=writer.rejected,
            event_cents=writer.event_cents,
        )
    return len(opened)


def written_text(
    session: Session, kind: str, turn: int | None = None, ref_id: int | None = None
) -> str | None:
    """A written read-only text (16.8): the newest of `kind`, or the one for that turn (and
    person, for an exit line). None before M6 or while still pending."""
    if not has_table(session, LLMTextRow):
        return None
    stmt = select(LLMTextRow).where(LLMTextRow.kind == kind, LLMTextRow.status == "written")
    if turn is not None:
        stmt = stmt.where(LLMTextRow.turn == turn)
    if ref_id is not None:
        stmt = stmt.where(LLMTextRow.ref_id == ref_id)
    row = session.scalars(stmt.order_by(LLMTextRow.turn.desc(), LLMTextRow.id.desc())).first()
    return row.text if row is not None and row.text else None
