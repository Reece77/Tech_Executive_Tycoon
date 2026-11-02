"""Ask my COO (docs/formulas.md 17.3; M7b): the briefing, a question through the LLM adapter
within the monthly budget, and the stored answers. Never changes game state or costs energy:
the answer is a row of its own, outside the state, written in a short transaction."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select

from tst.db import repository
from tst.db.events import default_adapter
from tst.db.models import CooAnswerRow, InboxItemRow, LLMCallLogRow
from tst.events.coo import NOTEBOOK, KpiMonth, coo_prompt, offline_reply, speaker
from tst.events.service import Writer
from tst.llm.base import CallRecord, LLMAdapter, TextPrompt
from tst.llm.settings import add_spend, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.coo import Issue, briefing, coo_of
from tst.sim.errors import SimError
from tst.sim.org.reports import EXEC_REPORT
from tst.sim.state import GameState, company_cash

KPI_MONTHS = 12  # the last 12 months of turn_snapshot KPIs (17.3)


class InvalidQuestionError(SimError):
    code = "invalid_question"


@dataclass(frozen=True, slots=True)
class Coo:
    person_id: int | None
    name: str  # the person's name, or "Founder's notebook"
    role_label: str | None
    issues: tuple[Issue, ...]


def _who(state: GameState, data: LoadedData) -> tuple[int | None, str, str | None]:
    pid = coo_of(state)
    if pid is None:
        return None, NOTEBOOK, None
    person = state.person(pid)
    employment = state.employment_of(pid)
    role = data.game_data.role(employment.role).label if employment else None
    return pid, f"{person.first_name} {person.last_name}", role


def coo(path: Path, data: LoadedData) -> Coo:
    """Who answers and the engine's briefing; always available, no LLM."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
    pid, name, role = _who(state, data)
    return Coo(pid, name, role, briefing(state, cash, data.balance, data.game_data))


def answers(path: Path) -> list[CooAnswerRow]:
    with repository.open_session(path) as session:
        return list(session.scalars(select(CooAnswerRow).order_by(CooAnswerRow.id.desc())))


def _kpis(path: Path, company: int) -> list[KpiMonth]:
    with repository.open_session(path) as session:
        snaps = repository.recent_snapshots(session, company, KPI_MONTHS)
    return [
        KpiMonth(
            format_turn(turn),
            s.cash_cents,
            s.monthly_burn_cents,
            s.arr_cents,
            s.headcount,
            s.avg_morale,
            s.board_confidence,
        )
        for turn, s in snaps
    ]


def _last_report(path: Path, person_id: int | None) -> str | None:
    """The named COO's latest quarterly report (24.3), as the inbox shows it."""
    if person_id is None:
        return None
    with repository.open_session(path) as session:
        row = session.scalars(
            select(InboxItemRow)
            .where(InboxItemRow.template == EXEC_REPORT, InboxItemRow.link_id == person_id)
            .order_by(InboxItemRow.turn.desc(), InboxItemRow.id.desc())
        ).first()
    return row.body if row is not None else None


def _trim(text: str, words: int) -> str:
    parts = text.split()
    return text.strip() if len(parts) <= words else " ".join(parts[:words]) + "…"


def ask(
    path: Path, data: LoadedData, question: str, *, adapter: LLMAdapter | None = None
) -> CooAnswerRow:
    """Answer one question: by the LLM within the budget, else the offline reply with the
    briefing. Spend counts toward the monthly budget and the call goes to llm_call_log."""
    keys = data.balance.coo
    text = " ".join(question.split())
    if not text or len(text) > keys.max_question_chars:
        raise InvalidQuestionError(f"a question has 1 to {keys.max_question_chars} characters")
    save_dir = path.parent
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
    issues = briefing(state, cash, data.balance, data.game_data)
    pid, name, role = _who(state, data)
    who = name if role is None else f"{name}, {role}"
    settings = load_settings(save_dir)
    spent = month_spend(save_dir).cents
    writer = Writer(
        adapter=adapter or default_adapter(save_dir),
        settings=settings,
        budget_left=lambda: settings.monthly_budget_cents - spent,
        debug=os.environ.get("TST_LLM_DEBUG") == "1",
    )
    report = _last_report(path, pid)
    fallback = offline_reply(issues, report)
    answer, source, cost = fallback, "offline", 0.0
    if writer.live and writer.can_spend():
        system, user = coo_prompt(
            state,
            pid,
            issues,
            _kpis(path, state.player.id),
            text,
            keys.max_answer_words,
            data.game_data,
            report,
        )
        completion = writer.adapter.generate_text(TextPrompt("coo", system, user, fallback))
        reply = completion.content if isinstance(completion.content, str) else None
        ok = completion.error is None and bool(reply and reply.strip())
        cost = writer.record("coo", system + "\n" + user, completion, "ok" if ok else "error")
        if ok and reply:
            answer, source = _trim(reply, keys.max_answer_words), writer.adapter.name
    elif writer.live:
        writer.records.append(_budget_record(question, speaker(state, pid, data.game_data)))
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with repository.write_session(path) as session:
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
        row = CooAnswerRow(
            turn=state.turn,
            person_id=pid,
            speaker=who,
            question=text,
            answer=answer,
            source=source,
            cost_cents=cost,
            created_at=now,
        )
        session.add(row)
        session.flush()
        keep = [
            r.id
            for r in session.scalars(
                select(CooAnswerRow).order_by(CooAnswerRow.id.desc()).limit(keys.keep_answers)
            )
        ]
        session.execute(delete(CooAnswerRow).where(CooAnswerRow.id.not_in(keep)))
        session.expunge(row)
    if writer.spent_cents or any(r.outcome != "budget" for r in writer.records):
        add_spend(
            save_dir,
            writer.spent_cents,
            calls=sum(1 for r in writer.records if r.outcome != "budget"),
        )
    return row


def _budget_record(question: str, who: str) -> CallRecord:
    return CallRecord(
        purpose="coo",
        model="none",
        prompt_hash=hashlib.sha256(f"{who}\n{question}".encode()).hexdigest()[:16],
        outcome="budget",
    )
