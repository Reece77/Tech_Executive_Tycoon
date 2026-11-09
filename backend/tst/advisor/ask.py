"""Explain and Ask why (M25 section 1): one number's explanation, and a question about it
answered by the chief of staff through the LLM adapter within the monthly budget, logged in
llm_call_log. Offline, over budget or after an error the answer is the template explanation.

Never changes game state or costs energy: the only write is the call log (and the budget
meter beside the saves), in a short transaction of its own."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from tst.advisor.build import explain
from tst.advisor.model import Explanation
from tst.advisor.prompt import explain_prompt
from tst.advisor.template import explain_text
from tst.db import repository
from tst.db.events import default_adapter
from tst.db.models import LLMCallLogRow
from tst.events.context import Kpis
from tst.events.coo import NOTEBOOK
from tst.events.service import Writer
from tst.llm.base import CallRecord, LLMAdapter, TextPrompt
from tst.llm.settings import add_spend, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.coo import coo_of
from tst.sim.errors import SimError
from tst.sim.finance.statements import projected_runway
from tst.sim.state import GameState, company_cash

PURPOSE: Final = "explain"


class InvalidQuestionError(SimError):
    code = "invalid_question"


@dataclass(frozen=True, slots=True)
class Explained:
    explanation: Explanation
    template: str
    speaker: str


@dataclass(frozen=True, slots=True)
class Answer:
    speaker: str
    question: str
    answer: str
    source: str  # the adapter's name ("claude", "mock"), or "template"
    cost_cents: float


def chief_of_staff(state: GameState, data: LoadedData) -> tuple[int | None, str]:
    """Who answers: the Ask my COO person (17.3), else the founder's notebook. The game has
    no Chief of staff role yet (M25 decision); when it does, it answers first."""
    pid = coo_of(state)
    if pid is None:
        return None, NOTEBOOK
    person = state.person(pid)
    employment = state.employment_of(pid)
    name = f"{person.first_name} {person.last_name}"
    if employment is None:
        return pid, name
    return pid, f"{name}, {data.game_data.role(employment.role).label}"


def explained(path: Path, data: LoadedData, metric: str, entity: str | None) -> Explained:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        e = explain(session, state, data, metric, entity)
    _, speaker = chief_of_staff(state, data)
    return Explained(e, explain_text(e, data.advisor.explain.drivers_named), speaker)


def _kpis(path: Path, data: LoadedData) -> tuple[GameState, Kpis]:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
        snap = repository.latest_snapshot(session, state.player.id)
    runway = projected_runway(state, state.player.id, cash, data.balance, data.game_data)
    return state, Kpis(
        cash_cents=cash,
        runway_months=runway,
        mrr_cents=snap.mrr_cents if snap is not None else 0,
        headcount=len(state.staff(state.player.id)),
        stage=state.player.stage,
    )


def _trim(text: str, words: int) -> str:
    parts = text.split()
    return text.strip() if len(parts) <= words else " ".join(parts[:words]) + "…"


def ask(
    path: Path,
    data: LoadedData,
    metric: str,
    entity: str | None,
    question: str,
    *,
    adapter: LLMAdapter | None = None,
) -> Answer:
    keys = data.advisor.ask
    text = " ".join(question.split())
    if not text or len(text) > keys.max_question_chars:
        raise InvalidQuestionError(f"a question has 1 to {keys.max_question_chars} characters")
    found = explained(path, data, metric, entity)
    state, kpis = _kpis(path, data)
    save_dir = path.parent
    settings = load_settings(save_dir)
    spent = month_spend(save_dir).cents
    writer = Writer(
        adapter=adapter or default_adapter(save_dir),
        settings=settings,
        budget_left=lambda: settings.monthly_budget_cents - spent,
        debug=os.environ.get("TST_LLM_DEBUG") == "1",
    )
    answer, source, cost = found.template, "template", 0.0
    if writer.live and writer.can_spend():
        system, user = explain_prompt(
            state,
            found.explanation,
            kpis,
            found.template,
            found.speaker,
            text,
            keys.max_answer_words,
            data.game_data,
        )
        completion = writer.adapter.generate_text(TextPrompt(PURPOSE, system, user, found.template))
        reply = completion.content if isinstance(completion.content, str) else None
        ok = completion.error is None and bool(reply and reply.strip())
        cost = writer.record(PURPOSE, system + "\n" + user, completion, "ok" if ok else "error")
        if ok and reply:
            answer, source = _trim(reply, keys.max_answer_words), writer.adapter.name
    elif writer.live:
        writer.records.append(
            CallRecord(
                purpose=PURPOSE,
                model="none",
                prompt_hash=hashlib.sha256(f"{metric}\n{entity}\n{text}".encode()).hexdigest()[:16],
                outcome="budget",
            )
        )
    if writer.records:
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
    if writer.spent_cents or any(r.outcome != "budget" for r in writer.records):
        add_spend(
            save_dir,
            writer.spent_cents,
            calls=sum(1 for r in writer.records if r.outcome != "budget"),
        )
    return Answer(found.speaker, text, answer, source, cost)
