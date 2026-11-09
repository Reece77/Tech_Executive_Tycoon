"""Explain and Ask why routes (M25 section 1). Never change state or cost energy."""

from __future__ import annotations

from fastapi import APIRouter

from tst.advisor import ask as advisor
from tst.advisor.ask import Explained
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.common import BreakdownItemOut
from tst.api.schemas.explain import (
    ExplainAnswerOut,
    ExplainAskIn,
    ExplainDriverOut,
    ExplainOut,
    TrendPointOut,
)
from tst.db.events import default_adapter
from tst.sim.calendar import format_turn

router = APIRouter(prefix="/api/saves/{save_id}/explain", tags=["explain"])


def explain_out(found: Explained, max_chars: int, offline: bool) -> ExplainOut:
    e = found.explanation
    return ExplainOut(
        metric=e.metric.key,
        label=e.metric.label,
        unit=e.metric.unit,
        scope=e.metric.scope,
        entity=e.entity,
        subject=e.subject,
        value=e.value,
        items=[BreakdownItemOut(label=i.label, amount=i.amount, unit=i.unit) for i in e.items],
        note=e.note,
        trend=[
            TrendPointOut(turn=p.turn, date_label=format_turn(p.turn), value=p.value)
            for p in e.trend
        ],
        trend_note=e.trend_note,
        drivers=[
            ExplainDriverOut(
                label=d.label, effect=d.effect, change=d.change, unit=d.unit, kind=d.kind
            )
            for d in e.drivers
        ],
        related=list(e.related),
        explanation=found.template,
        speaker=found.speaker,
        max_question_chars=max_chars,
        offline=offline,
    )


@router.get("/{metric}", response_model=ExplainOut, responses=ERRORS, operation_id="getExplain")
def get_explain(
    save_id: str, metric: str, settings: SettingsDep, data: DataDep, entity: str | None = None
) -> ExplainOut:
    """A number's breakdown, its trend, what moved it and the template explanation."""
    found = advisor.explained(_path(settings, save_id), data, metric, entity)
    offline = default_adapter(settings.resolved_save_dir()).name == "template"
    return explain_out(found, data.advisor.ask.max_question_chars, offline)


@router.post(
    "/{metric}/ask", response_model=ExplainAnswerOut, responses=ERRORS, operation_id="askExplain"
)
def ask_explain(
    save_id: str, metric: str, body: ExplainAskIn, settings: SettingsDep, data: DataDep
) -> ExplainAnswerOut:
    """Ask the chief of staff why. Offline, over budget or after an error the answer is the
    template explanation."""
    a = advisor.ask(_path(settings, save_id), data, metric, body.entity, body.question)
    return ExplainAnswerOut(
        speaker=a.speaker,
        question=a.question,
        answer=a.answer,
        source=a.source,
        cost_cents=round(a.cost_cents, 4),
    )
