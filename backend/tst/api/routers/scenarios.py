"""The Scenarios screen (M51, formulas.md 63.3): every historical scenario with its brief,
difficulty and the player's best result, read from the app-wide results file (never a save)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.schemas.scenarios import (
    ScenarioCardOut,
    ScenarioResultOut,
    ScenariosOut,
    ScorePartsOut,
)
from tst.profile import results as kept
from tst.profile.store import profile_name
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.modes import challenges

router = APIRouter(tags=["scenarios"])


def result_out(record: dict[str, Any] | None) -> ScenarioResultOut | None:
    if record is None:
        return None
    parts = record.get("parts")
    return ScenarioResultOut(
        save=str(record.get("save", "")),
        company=str(record.get("company", "")),
        result=str(record.get("result", "")),
        date_label=str(record.get("date_label", "")),
        score=int(record.get("score") or 0),
        challenges=[str(c) for c in record.get("challenges") or []],
        score_mult=float(record.get("score_mult") or 1.0),
        adjusted=int(record.get("adjusted") or 0),
        recorded_at=str(record.get("recorded_at", "")),
        parts=ScorePartsOut(**parts) if isinstance(parts, dict) else None,
    )


@router.get("/api/scenarios", response_model=ScenariosOut, operation_id="getScenarios")
def get_scenarios(settings: SettingsDep, data: DataDep) -> ScenariosOut:
    """Every historical scenario: brief, goal, deadline, difficulty and the best result."""
    stored = kept.load(settings.resolved_save_dir())
    cards = []
    for h in data.game_data.historical:
        records = stored.get(h.key, {})
        cards.append(
            ScenarioCardOut(
                key=h.key,
                label=h.label,
                description=h.description,
                year=h.year,
                goal=h.goal.text,
                deadline_label=format_turn(ym_to_turn(*h.deadline)),
                difficulty=challenges.difficulty(h.sensible_wins, data.balance),
                sensible_wins=h.sensible_wins,
                played=len(records),
                best=result_out(kept.best(records)),
            )
        )
    return ScenariosOut(profile=profile_name(), scenarios=cards)
