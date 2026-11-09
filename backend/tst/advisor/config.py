"""backend/data/advisor.yaml (M25), validated at startup by the loader."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

ADVISOR_FILE = "advisor.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExplainKeys(_Strict):
    history_months: int = Field(ge=2, le=60)
    events_months: int = Field(ge=0, le=60)
    drivers_named: int = Field(ge=1, le=5)


class AskKeys(_Strict):
    max_question_chars: int = Field(ge=20, le=2000)
    max_answer_words: int = Field(ge=20, le=600)


class AdvisorConfig(_Strict):
    explain: ExplainKeys
    ask: AskKeys


DEFAULT_ADVISOR = AdvisorConfig(
    explain=ExplainKeys(history_months=12, events_months=6, drivers_named=2),
    ask=AskKeys(max_question_chars=300, max_answer_words=150),
)
