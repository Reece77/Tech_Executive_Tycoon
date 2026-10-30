"""Ask my COO routes (docs/formulas.md 17.3; M7b): the briefing, a question, the last answers.
Never changes state or costs energy."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.coo import CooAnswerOut, CooIssueOut, CooOut, CooQuestionIn
from tst.db import coo as coo_db
from tst.db.events import default_adapter
from tst.db.models import CooAnswerRow
from tst.llm.settings import load_settings, month_spend
from tst.sim.calendar import format_turn

router = APIRouter(prefix="/api/saves/{save_id}/coo", tags=["coo"])


def _answer(row: CooAnswerRow) -> CooAnswerOut:
    return CooAnswerOut(
        answer_id=row.id,
        turn=row.turn,
        date_label=format_turn(row.turn),
        speaker=row.speaker,
        question=row.question,
        answer=row.answer,
        source=row.source,
        cost_cents=round(row.cost_cents, 4),
    )


@router.get("", response_model=CooOut, responses=ERRORS, operation_id="getCoo")
def get_coo(save_id: str, settings: SettingsDep, data: DataDep) -> CooOut:
    """Who answers, the engine's briefing (always available) and the last answers."""
    path = _path(settings, save_id)
    info = coo_db.coo(path, data)
    save_dir = settings.resolved_save_dir()
    return CooOut(
        person_id=info.person_id,
        name=info.name,
        role_label=info.role_label,
        briefing=[
            CooIssueOut(key=i.key, text=i.text, link_kind=i.link_kind, link_id=i.link_id)
            for i in info.issues
        ],
        answers=[_answer(r) for r in coo_db.answers(path)],
        max_question_chars=data.balance.coo.max_question_chars,
        spend_cents=round(month_spend(save_dir).cents, 4),
        budget_cents=load_settings(save_dir).monthly_budget_cents,
        offline=default_adapter(save_dir).name == "template",
    )


@router.post("/ask", response_model=CooAnswerOut, responses=ERRORS, operation_id="askCoo")
def ask_coo(
    save_id: str, body: CooQuestionIn, settings: SettingsDep, data: DataDep
) -> CooAnswerOut:
    """Ask a question (at most coo.max_question_chars). Offline, over budget or after an
    error the reply is "I can't think that through right now" with the briefing."""
    return _answer(coo_db.ask(_path(settings, save_id), data, body.question))
